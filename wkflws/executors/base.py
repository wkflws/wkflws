import abc
from typing import Optional

from ..workflow import WorkflowExecution


class BaseExecutor(abc.ABC):
    """Class all executors should inherit from.

    This class provides a template of functionality all executor classes should
    implement.
    """

    @abc.abstractmethod
    async def execute(
        self,
        state_name: str,
        *,
        workflow: WorkflowExecution,
        state_input: Optional[str],
    ):
        """Entry point for executing a workflow node.

        Args:
            state_name: The ``State`` to execute.
            workflow: The workflow execution. Used to prepare input, output, and
                context.
            state_input: The input for the state (e.g. the output of the previous
                state.)
        """
        raise NotImplementedError()
