"""Multi-process executor for wkflws.

This module executes each step as a new process on the same host. This can be useful
for development because the memory is separated similarly to a production multi-host
setup.
"""
import asyncio
import json
import os
import shlex
import subprocess
import sys
from typing import Any, Optional

from opentelemetry import trace

from .base import BaseExecutor
from ..exceptions import (
    WkflwExecutionException,
    WkflwStateError,
    WkflwStateNotFoundError,
)
from ..logging import getLogger
from ..trace import tracer
from ..utils.encoder import WkflwsJSONEncoder
from ..workflow import WorkflowExecution

# if this needs to be set then use a context instead
# of global so it doesn't crash setting it a second time.
#
# Fork is unstable on OS X (default is spawn)
# _mp.set_start_method("spawn")


# class _Process(_mp.Process):
#     pass


class MultiProcessExecutor(BaseExecutor):
    """Executes steps as another process on the same host."""

    async def execute(
        self,
        state_name: str,
        *,
        workflow: WorkflowExecution,
        state_input: Optional[dict[str, Any]],
    ) -> str:
        """Run ``state`` as defined in ``workflow``.

        Returns:
            The raw output from stdout. This should be a JSON serialized payload.
        """
        with tracer.start_as_current_span(
            f"{__name__}.MultiProcessExecutor.execute"
        ) as span:
            span.set_attribute("wkflws.state_name", state_name)

            # logger = getLogger("wkflws.executors.mp.MultiProcessExecutor.execute")
            # logger.info(f"Setting up for execution of {state_name}")

            try:
                state = workflow.workflow_definition["States"][state_name]
            except KeyError:
                raise WkflwStateNotFoundError(
                    f"Workflow state '{state_name}` not found."
                )

            resource_path = state.get("Resource", None)

            if resource_path is None:
                raise WkflwExecutionException(
                    f"Workflow State '{state_name}' has no defined resource"
                )

            from opentelemetry.trace.propagation.tracecontext import (
                TraceContextTextMapPropagator,
            )

            span_ctx: dict[str, str] = {}
            TraceContextTextMapPropagator().inject(span_ctx)

            # Execute a helper function detached, which loads the workflow
            # information, state_input, executing `Resource` as a child
            # process to collect it's output.
            args = [
                "python",
                "-m",
                "wkflws.executors.mp",
                resource_path,
                workflow.json(separators=(",", ":")),
            ]

            if state_input is not None:
                args.append(
                    json.dumps(
                        state_input,
                        separators=(",", ":"),
                        cls=WkflwsJSONEncoder,
                    )
                )
            else:
                args.append("{}")

            args.append(json.dumps(span_ctx, separators=(",", ":")))

            # Provide a limited environment to the subprocess.
            env_var_allow_list = [  # TODO: how to make this dynamic?
                "VOYAGE_PLATFORM_API_KEY",
                "LIVERECOVER_API_KEY",
                "VOYAGE_PLATFORM_ENV",
            ]
            env: dict[str, str] = {
                "PATH": os.getenv("PATH", ""),
                # "_WKFLWS_NODE_LOG_LEVEL": str(logger.getEffectiveLevel()),
            }

            # A little hack to get the environment set up properly when
            # executed from within a pex.
            if os.getenv("PEX", False):
                # logger.debug("pex detected, Applying PYTHONPATH env")
                env["PYTHONPATH"] = ":".join(sys.path)
                env_var_allow_list.append("PEX")
                env_var_allow_list.append("PYTHONPATH")

            for env_var in env_var_allow_list:
                if env_var in os.environ:
                    env[env_var] = os.environ[env_var]

            # print(f"Executing {state_name} -> {args}")
            # Executing the process asynchronously let's the gunicorn worker function.
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=subprocess.PIPE,
                # stderr=None,
                env=os.environ,
                # check=True, # Raise exception if failure
            )
            raw_output = ""
            while True:
                _output, _ = await process.communicate()
                raw_output += _output.decode("utf-8")

                if process.returncode is not None:
                    break

            if process.returncode != 0:
                e = WkflwStateError("Execution failed due to non-zero return code.")
                span.record_exception(
                    e,
                    attributes={"return_code": process.returncode},
                )
                raise e

            _output, _ = await process.communicate()
            raw_output += _output.decode("utf-8")

            return raw_output


async def execution_entry_point(
    resource_path: str,
    workflow_execution: WorkflowExecution,
    state_input: Optional[str] = None,
    span_ctx: Optional[dict[str, str]] = None,
) -> str:
    """Entry point to the node subprocess.

    This function serves as an entry point to the sub-process which executes a
    node. This function is responsible for preparing the input, context, and output for
    the actual node.

    Args:
        resource_path: `Resource` defined in the Step. For multi-process this will be a
            command-line command to execute on a shell.
        workflow_execution: The entire workflow execution definition so that it can be
            used during data preparation.
        state_input: The processed input to this node's execution.
        span_ctx: the context for the current span if tracing.
    Returns:
        The raw output from stdout. This should be a serialized JSON payload.
    """
    logger = getLogger("wkflws.executors.mp.execution_entry_point")
    if workflow_execution.current_state_name is None:
        logger.error(
            f"Undefined current state for resource {resource_path}. Unable to continue"
        )
        sys.exit(1)

    logger.debug(
        f"Executing {resource_path} for State {workflow_execution.current_state_name}."
    )

    # Execute resource_path receiving output
    args = shlex.split(resource_path)
    if state_input is not None:
        args.append(state_input)  # already serialized by the execute() method
    else:
        args.append("{}")

    if not span_ctx:
        span_ctx = {}

    args.append(
        json.dumps(
            workflow_execution.get_task_context(
                workflow_execution.current_state_name,
                span_ctx,
            )
        )
    )

    completed_process = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=None,
        env=os.environ,
    )

    if completed_process.returncode != 0:
        # Error is logged in the calling execute() statement.

        if completed_process.stderr is not None:
            logger.error(completed_process.stderr)

        sys.exit(completed_process.returncode)

    raw_output = completed_process.stdout.decode("utf-8")
    return raw_output


if __name__ == "__main__":
    logger = getLogger("wkflws.executors.mp.__main__")

    try:
        resource_path: Optional[str] = sys.argv[1]
    except IndexError:
        resource_path = None

    if not resource_path:
        logger.error("Expected resource path")
        sys.exit(1)

    try:
        workflow_execution_data: Optional[str] = sys.argv[2]
    except IndexError:
        workflow_execution_data = None

    if not workflow_execution_data:
        logger.error("Expected the workflow execution payload.")
        sys.exit(1)

    try:
        workflow_execution = WorkflowExecution.parse_raw(workflow_execution_data)
    except WkflwExecutionException as e:
        logger.error(f"Unable to load workflow information. ({e})")
        sys.exit(1)

    try:
        state_input: Optional[str] = sys.argv[3]
    except IndexError:
        state_input = None

    if not workflow_execution_data:
        logger.error("Expected the state input payload (even if it is {}).")
        sys.exit(1)

    try:
        span_ctx: dict[str, str] = json.loads(sys.argv[4])
    except IndexError:
        span_ctx = {}

    # Reset the log level for this new process's logger. Default is INFO
    logger.setLevel(int(os.getenv("_WKFLWS_NODE_LOG_LEVEL", 20)))

    output = asyncio.run(
        execution_entry_point(resource_path, workflow_execution, state_input, span_ctx)
    )

    # Display the output for the `execute()` method to grab
    print(output)

    # Non-async if needed:
    # asyncio.get_event_loop().run_until_complete(func(context, raw_input))

#     async def execute_old(self, resource_path, context, raw_input):
#         """Run the provided ``resource_path``.

#         Args:
#             resource_path: the module path of the function to execute.
#             context: The :class:`wkflws.context.Context` of the workflow.
#             raw_input: The output of the previous step.
#         """
#         process = _Process(
#             target=entry,
#             args=(resource_path, context, raw_input),
#         )
#         process.start()
#         process.join()
