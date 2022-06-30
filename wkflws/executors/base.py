import abc
from typing import Any, Optional

from ..workflow import WorkflowExecution


class BaseExecutor(abc.ABC):
    @abc.abstractmethod
    async def execute(
        self,
        state_name: str,
        *,
        workflow: dict[str, Any],
        state_input: Optional[str],
    ):
        raise NotImplementedError()
