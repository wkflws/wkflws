"""Describes workflow lookup classes.

A lookup class is responsible for providing wkflws with a state-language workflow to
execute on incoming trigger events.
"""
from __future__ import annotations

import abc
from functools import lru_cache
from typing import Any

from pydantic import BaseModel

from ..conf import settings
from ..events import Event
from ..utils.execution import module_attribute_from_string
from ..workflow import WorkflowType


class LookupBase:
    """The base workflow lookup class."""

    @abc.abstractmethod
    async def get_workflows(
        self,
        initial_node_id: str,
        event: Event,
    ) -> tuple[WorkflowExecutionData, ...]:
        """Look up all workflows that should be executed with the provided event.

        Args:
            event: The raw incoming event. This should be processed by your lookup
                method to match any user-defined workflows that should be executed.

        Returns:
            The workflows and their context
        """
        raise NotImplementedError("get_workflows must be defined.")


class WorkflowExecutionData(BaseModel):
    """Contains necessary information for ."""

    #: Identifer for the workflow. (This is most likely a primary key.)
    workflow_id: str
    #: The workflow (in states language format) to be executed.
    workflow_definition: WorkflowType
    #: Additional context for each state in the workflow The key should be the state
    #: name and the value should be a JSON serializable value which is passed to the
    #: node during  execution. Check the node's documentation for required and supported
    #: context values.
    state_context: dict[str, Any]


def get_lookup_helper_class():
    return module_attribute_from_string(settings.WORKFLOW_LOOKUP_CLASS)


@lru_cache(maxsize=1)
def get_lookup_helper_object() -> LookupBase:
    return get_lookup_helper_class()()
