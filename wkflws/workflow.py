from datetime import datetime, timezone
from decimal import Decimal
import json
from types import MappingProxyType
from typing import Any, Optional, Type, TYPE_CHECKING, Union

from pydantic import BaseModel

from .conf import settings
from .events import Event
from .exceptions import (
    WkflwExecutionAlreadyStartedError,
    WkflwExecutionException,
    WkflwStateError,
    WkflwStateNotFoundError,
)
from .intrinsic_funcs.interpreter import Interpreter
from .intrinsic_funcs.parser import Parser
from .intrinsic_funcs.scanner import Scanner
from .logging import logger, LogLevel
from .utils.execution import module_attribute_from_string
from .utils.jsonpath import get_jsonpath_value, set_jsonpath_value


if TYPE_CHECKING:
    from .executors.base import BaseExecutor

WorkflowType = MappingProxyType[str, Any]


class WorkflowExecution(BaseModel):
    """Describes the execution of a workflow and it's state."""

    #: A unique string identifying this execution of the workflow.
    execution_id: str
    #: the identifier for the workflow being executed (i.e. database primary key).
    workflow_id: str
    #: holds a deserialized version of the state language workflow definition.
    workflow_definition: WorkflowType
    #: The input provided to the trigger node.
    original_input: dict[str, Any]
    #: Context by state that should be provided to each state as it is executed.
    state_context: dict[str, Any]

    #: describes the start time of this execution.
    execution_start_time: datetime

    #: The name of the current state. If this is None then the workflow has not started.
    current_state_name: Optional[str] = None

    async def start(self, state_input: dict[str, Any]):
        """Begin the execution of ``workflow_definition``."""
        logger.debug(f"Starting workflow id {self.workflow_id}")
        if self.current_state_name is not None:
            raise WkflwExecutionAlreadyStartedError(
                f"Workflow execution id {self.execution_id} has already started."
            )

        try:
            self.set_current_state_name(self.workflow_definition["StartAt"])
        except KeyError:
            raise WkflwExecutionException(
                f"Unable to start workflow {self.workflow_id}. No StartAt defined"
            )

        if self.current_state_name is None:
            # This is mostly to evaluate all branches for the type checker.
            raise WkflwExecutionException(
                f"Unable to start workflow {self.workflow_id}. StartAt defined as null"
            )

        await self.execute_state(self.current_state_name, state_input)

    def set_current_state_name(self, state_name: str):
        """Set the current state to the provided name.

        Args:
            state_name: The name of the current state.
        """
        if state_name not in self.workflow_definition["States"]:
            raise WkflwStateNotFoundError(
                f"Cannot set current state to {state_name} because it was not found "
                "in the definition."
            )

        self.current_state_name = state_name

    async def execute_next_state(self, state_input: dict[str, Any]):
        """Execute the state defined by ``Next`` for the current state.

        Args:
            state_input: The input to the next state (i.e. the output of the current
                state)
        """
        if self.current_state.get("End", False):  # TODO: coerce boolean
            return  # nothing to do

        next_state = self.current_state.get("Next", None)

        if self.current_state_name is None:
            raise WkflwExecutionException(
                f"Unknown next step for {self.current_state_name}"
            )
        self.set_current_state_name(str(next_state))

        await self.execute_state(self.current_state_name, state_input)

    async def execute_state(self, state_name: str, state_input: dict[str, Any]):
        """Execute the state defined by ``state_name``.

        Args:
            state_name: The name of the state to execute.
            state_input: The input for the state (i.e. output of another state.)
        """
        logger.debug(f"Processing state {state_name}")
        state = self.get_state(state_name)

        processed_input = await self.get_processed_state_input(
            self.current_state,
            state_input,
        )

        output = {}
        match state["Type"]:
            case "Task":
                raw_output = await self.state_process_task(
                    state_name,
                    processed_input,
                )
                output = await self.get_processed_output(
                    input_=state_input,
                    output=raw_output,
                )
            case "Choice":
                # TODO: Choice only supports InputPath or OutputPath
                await self.state_process_choice(state, state_input)
                output = state_input
            case "Pass":
                # > The Pass State (identified by "Type":"Pass") by default passes its
                # > input to its output, performing no work.
                # >
                # > A Pass State MAY have a field named "Result". If present, its value
                # > is treated as the output of a virtual task, and placed as prescribed
                # > by the "ResultPath" field, if any, to be passed on to the next
                # > state. If "Result" is not provided, the output is the input. Thus if
                # > neither "Result" nor "ResultPath" are provided, the Pass State
                # > copies its input through to its output.
                if "Result" in self.current_state:
                    # I'm taking some liberty here by assuming ``Result`` is a Payload
                    # Template. It is not specified one way or the other in the spec.
                    #
                    # > "Result" means the JSON text that a state generates, for example
                    # > from external code invoked by a Task State, the combined result
                    # > of the branches in a Parallel or Map State, or the Value of the
                    # > "Result" field in a Pass State.
                    result = await self.evaluate_payload_template(
                        self.current_state["Result"],
                        processed_input,
                    )

                    output = await self.process_result_path(
                        input_=processed_input,
                        output=result,
                    )
                    logger.debug(
                        f" > Effective Output ({type(output)}): '{json.dumps(output)}'"
                    )
                else:
                    output = state_input

            case _:
                raise WkflwExecutionException(f'Unknown state type: {state["Type"]}')

        await self.execute_next_state(output)

    def get_state(self, state_name: str) -> dict[str, Any]:
        """Return the requested state."""
        try:
            return self.workflow_definition["States"][state_name]
        except KeyError:
            raise WkflwStateNotFoundError(
                f"Workflow state '{self.current_state_name}` not found."
            )

    @property
    def current_state(self):
        """Return the current state's definition."""
        if self.current_state_name is None:
            raise WkflwStateError(
                "There is no current state because the workflow is not executing."
            )
        return self.get_state(self.current_state_name)

    @property
    def executor_class(self) -> Type["BaseExecutor"]:
        """Return the executor class by parsing ``self.executor_class_path``."""
        clz: Type["BaseExecutor"] = module_attribute_from_string(
            settings.EXECUTOR_CLASS
        )

        return clz

    def get_task_context(
        self,
        state_name: str,
        entered_time: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Build the context object that should be provided to the task.

        .. code:: javascript

           {
             "Execution": {
               "Id": "<identifier for this execution instance>",
               "Input" "<original input provided to the trigger node>",
               "StartTime": "<ISO 8601>"
             },
             "State": {
               "EnteredTime": "<ISO 8601>",
               "Name": "<name of the current step>",
               "RetryCount": 123
             },
             "Workflow": {
               "Id": "<identifier for the workflow being executed>",
               "Name": "<name of the workflow>"
             },
             "Task": {
               "Secrets": {
                 "<key>": "<value>",
               }
             }
           }

        Args:
            state_name: The name of the state being executed as defined by the "Name"
                field in the States section of the workflow definition.
            entered_time: The time the state execution started. By default ``now`` will
                be used.

        """
        if entered_time is None:
            entered_time = datetime.now()

        task_context: dict[str, Any] = {}
        task_context.update(self.state_context.get(state_name, {}))

        return {
            "Execution": {
                "Id": self.execution_id,
                "Input": self.original_input,
                "StartTime": self.execution_start_time.isoformat(),
            },
            "Workflow": {
                "Id": self.workflow_id,
                "Name": self.workflow_definition.get("Comment", ""),
            },
            "State": {
                "Name": state_name,
                "EnteredTime": entered_time.isoformat(),
                "RetryCount": 0,  # unimplemented
            },
            "Task": task_context,
        }

    async def state_process_task(
        self,
        state_name: str,
        state_input: dict[str, Any],
    ) -> dict[str, Any]:
        """Process a ``Task`` state type.

        Args:
            state_name: The name of the Task state to execute.
            state_input: The input to the Task state. (i.e. output of the previous
                state.)

        Return:
           The deserialized output from the task
        """
        logger.debug(f"Executing 'Task' state type: '{self.current_state_name}'")

        logger.debug(f" > Task input ({type(state_input)}): {state_input}")

        executor = self.executor_class()
        logger.debug(f"Using executor '{executor.__class__.__name__}'")
        try:
            output = await executor.execute(
                state_name,
                workflow=self,
                state_input=state_input,
            )
            deserialized_output = json.loads(output)
        except Exception:
            logger.exception(f"Exception found during execution of {state_name}...")
            return {}
        return deserialized_output

    async def state_process_choice(
        self,
        state: dict[str, Any],
        state_input: dict[str, Any],
    ):
        """Process a ``Choice`` state type.

        Args:
            state_name: The defintion of the Choice state to execute.
            state_input: The input to the Task state. (i.e. output of the previous
                state.)
        """
        next_state_name = state.get("Default", None)

        for i, choice in enumerate(state["Choices"]):
            # > A Choice State MUST NOT be an End state.
            if "End" in choice:
                raise WkflwExecutionException("Choice rule cannot be an End")

            result = self.evaluate_choice_branch(branch=choice, state_input=state_input)

            if result:
                logger.debug(f"Choice index {i} successful")
                next_state_name = choice["Next"]
                break

        if not next_state_name:
            raise WkflwExecutionException("States.NoChoiceMatched")

        self.set_current_state_name(next_state_name)
        await self.execute_state(next_state_name, state_input)

    def evaluate_choice_branch(
        self,
        *,
        branch: dict[str, Any],
        state_input: dict[str, Any],
    ) -> bool:
        """Evaluate a branch of a ``Choice`` state.

        Args:
            branch: The branch to evaluate
            state_input: The input to the Choice state. Used during evaluation.
        """
        if "And" in branch:
            for and_branch in branch["And"]:
                and_result = self.evaluate_choice_branch(
                    branch=and_branch,
                    state_input=state_input,
                )

                if not and_result:
                    return False
            return True
        elif "Not" in branch:
            return not self.evaluate_choice_branch(
                branch=branch["Not"],
                state_input=state_input,
            )

        _is_value_present = True

        try:
            jsonpath_expr = branch["Variable"]
            if jsonpath_expr.startswith("$$"):
                jsonpath_expr = jsonpath_expr[1:]

            value: Union[str, list[Any]] = get_jsonpath_value(
                state_input, jsonpath_expr
            )
        except ValueError:
            _is_value_present = False
            # This is done for the type checker. It's unused for IsPresent and an
            # exception raised otherwise.
            value = "WkflwsInsertedNoneValue"
            if "IsPresent" not in branch:
                raise WkflwExecutionException(
                    "Cannot find match in input for JSON Path "
                    f'\'{branch["Variable"]}\''
                )

        if "IsPresent" in branch:
            logger.debug(
                f'Evaluating IsPresent: {branch["Variable"]} = {_is_value_present}'
            )
            return _is_value_present
        elif "NumericGreaterThan" in branch:
            return Decimal(str(value)) >= Decimal(branch["NumericGreaterThan"])
        elif "NumericGreaterThanEquals" in branch:
            return Decimal(str(value)) >= Decimal(branch["NumericGreaterThanEquals"])
        elif "NumericLessThan" in branch:
            return Decimal(str(value)) < Decimal(branch["NumericLessThan"])
        elif "NumericLessThanEquals" in branch:
            return Decimal(str(value)) < Decimal(branch["NumericLessThan"])
        elif "NumericEquals" in branch:
            return Decimal(str(value)) == Decimal(branch["NumericEquals"])
        elif "StringEquals" in branch:
            logger.debug(
                f"Evaluating StringEquals "
                f'{str(value)} == {branch["StringEquals"]} = '
                f'{str(value) == branch["StringEquals"]}'
            )
            return str(value) == branch["StringEquals"]
        elif "IsNull" in branch:
            return value is None
        elif "IsNumeric" in branch:
            return isinstance(value, (int, float, Decimal))
        elif "IsString" in branch:
            return isinstance(value, str)
        elif "IsBoolean" in branch:
            return isinstance(value, bool)
        # elif "IsTimestamp" in branch:
        #     pass
        # elif "TimestampGreaterThanEquals" in branch:
        #     pass
        # elif "TimestampLessThanEquals" in branch:
        #     pass
        # elif "TimestampGreaterThan" in branch:
        #     pass
        # elif "TimestampLessThan" in branch:
        #     pass
        # elif "TimestampEquals" in branch:
        #     pass
        # elif "BooleanEquals" in branch:
        #     pass

        raise Exception("TODO: Unknown choice rule comparison operator.")

    async def get_processed_state_input(
        self,
        state: dict[str, Any],
        original_state_input: dict[str, Any],
    ) -> dict[str, Any]:
        """Process the effective input for the state.

        Args:
            state: The ``State`` definition.
            original_state_input: The unprocessed input to this tate (i.e output of the
                previous state).

        Return:
            The effective input for the node.
        """
        # The value of "InputPath" MUST be a Path, which is applied to a State’s raw
        # input to select some or all of it; that selection is used by the state, for
        # example in passing to Resources in Task States and Choices selectors in Choice
        # States.
        # TODO: self.process_input_path()
        new_input: dict[str, Any] = original_state_input

        # The value of "Parameters" MUST be a Payload Template which is a JSON object,
        # whose input is the result of applying the InputPath to the raw input. If the
        # "Parameters" field is provided, its payload, after the extraction and
        # embedding, becomes the effective input.
        if "Parameters" not in state:
            return new_input

        payload_template = state["Parameters"]

        new_input = await self.evaluate_payload_template(payload_template, new_input)

        return new_input

    async def get_processed_output(
        self,
        *,
        input_: Optional[dict[str, Any]],
        output: dict[str, Any],
    ) -> dict[str, Any]:
        """Process the output of a node for the input to the next node.

        Args:
            input_: The original input of the 'current' node. This is used for
                the ``ResultPath`` case.
            output: The raw output of the 'current' node. This value is parsed as
                JSON and processed with ``ResultSelector`` and ``OutputPath``

        Returns:
            The effective output of this node's execution.
        """
        if input_ is None:
            input_ = {}

        if "ResultSelector" in self.current_state:
            # > The value of "ResultSelector" MUST be a Payload Template, whose input is
            # > the result, and whose payload replaces and becomes the effective result.

            if isinstance(output, dict):
                output = await self.evaluate_payload_template(
                    self.current_state["ResultSelector"],
                    input_,
                )
            else:
                # This is a work around for older workflows and should be removed when
                # they no longer define a direct JSONPath
                #
                # See Also: https://github.com/awslabs/states-language/issues/23
                output = get_jsonpath_value(
                    output, self.current_state["ResultSelector"]
                )  # type:ignore

        output = await self.process_result_path(input_=input_, output=output)

        if "OutputPath" in self.current_state:
            # > The value of "OutputPath" MUST be a Path, which is applied to the
            # > state’s output after the application of ResultPath, producing the
            # > effective output which serves as the raw input for the next state.

            output = get_jsonpath_value(
                output, self.current_state["OutputPath"]
            )  # type:ignore

        return output

    async def process_result_path(
        self,
        *,
        input_: Optional[dict[str, Any]],
        output: dict[str, Any],
    ):
        if "ResultPath" in self.current_state:
            # > The value of "ResultPath" MUST be a Reference Path, which specifies the
            # > raw input’s combination with or replacement by the state’s result.
            result_path = str(self.current_state["ResultPath"])

            if result_path.startswith("$$"):
                # > The value of "ResultPath" MUST NOT begin with "$$"; i.e. it may not
                # > be used to insert content into the Context Object.
                raise WkflwExecutionException(
                    f"ResultPath for {self.current_state_name} must not access the "
                    "context object"
                )
            elif not result_path.startswith("$"):
                raise WkflwExecutionException(
                    f"ResultPath for {self.current_state_name} must be a JSONPath "
                    "value."
                )

            # Disable use of copy because the original is no longer needed.
            output = set_jsonpath_value(
                input_ or {},
                output,
                result_path,
                create_if_missing=True,
                use_copy=False,
            )

        return output

    async def evaluate_payload_template(
        self,
        payload_template: dict[str, Any],
        state_input: dict[str, Any],
    ) -> dict[str, Any]:
        """Process a Payload template.

        Args:
            payload_template: The payload template to evaluate.
            state_input: The input to the state. Used for the ``$`` values.

        Return:
            The effective result of the payload
        """
        output: dict[str, Any] = {}

        for param, value in payload_template.items():
            if param.endswith(".$"):
                # > If any field within the Payload Template (however deeply nested) has
                # > a name ending with the characters ".$", its value is transformed
                # > according to rules below and the field is renamed to strip the ".$"
                # > suffix.

                if value.startswith("$"):
                    if value.startswith("$$"):
                        # > If the field value begins with "$$", the first dollar sign
                        # > is stripped and the remainder MUST be a Path. In this case,
                        # > the Path is applied to the Context Object and is the new
                        # > field value.
                        # TODO: What should the context object consist of?
                        # output[param.rstrip(".$")]=jp_parser.find(raw_input)[0].value
                        found_value = get_jsonpath_value(self.current_state, value[1:])
                        output[param.rstrip(".$")] = found_value
                        logger.debug(f"Parameter {value} resolved to " f"{found_value}")
                    else:
                        # > If the field value begins with only one "$", the value MUST
                        # > be a Path. In this case, the Path is applied to the Payload
                        # > Template’s input and is the new field value.
                        found_value = get_jsonpath_value(state_input, value)
                        output[param.rstrip(".$")] = found_value
                        logger.debug(f"Parameter {value} resolved to " f"{found_value}")
                else:
                    # > If the field value does not begin with "$", it MUST be an
                    # > Intrinsic Function. The interpreter invokes the Intrinsic
                    # > Function and the result is the new field value.
                    output[param.rstrip(".$")] = await self.value_from_intrinsic_func(
                        value, state_input
                    )
            else:
                if isinstance(value, dict):
                    output[param] = await self.evaluate_payload_template(
                        value,
                        state_input,
                    )
                else:
                    output[param] = value

        return output

    async def value_from_intrinsic_func(
        self,
        value: str,
        state_input: dict[str, Any],
    ) -> Any:
        """Interpret and return the value of an intrinsic function call.

        Args:
            value: the intrinsic function call as a string / raw source code.
            raw_input: The input for the function

        Return:
            The result of the intrinsic function call
        """
        interpreter = Interpreter(func_input_json=state_input)
        tokens = Scanner(value).scan()

        # We know there is only 1 function call statement because that's all we allow
        # the user to input when defining a workflow.
        func_call = Parser(tokens).parse()[0]
        result = interpreter.visit_call_expr(func_call.expression)  # type: ignore

        ifunc_name = func_call.expression.callee.name.lexeme  # type:ignore
        logger.debug(f"{ifunc_name} evaluates to '{result}'")

        return result


async def initialize_workflows(
    *,
    initial_node_id: str,
    event: Event,
    workflow_input: dict[str, Any],
) -> tuple[WorkflowExecution, ...]:
    """Initialize workflows that need to be executed by calling the lookup helper."""
    from .lookup import get_lookup_helper_object  # prevent circular import

    lookup_helper = get_lookup_helper_object()
    workflow_exec_datas = await lookup_helper.get_workflows(initial_node_id, event)

    if logger.getEffectiveLevel() == LogLevel.DEBUG:
        logger.debug(f"Executing {len(workflow_exec_datas)} workflows")

    workflows: tuple[WorkflowExecution, ...] = ()
    for wkflw_exec_data in workflow_exec_datas:
        workflows += (
            WorkflowExecution(
                execution_id=event.identifier,
                workflow_id=wkflw_exec_data.workflow_id,
                workflow_definition=wkflw_exec_data.workflow_definition,
                original_input=workflow_input,
                state_context=wkflw_exec_data.state_context,
                execution_start_time=datetime.now(tz=timezone.utc),
            ),
        )
        # await workflow_execution.start(event.asdict())
    return workflows
