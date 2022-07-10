from copy import deepcopy
from dataclasses import dataclass
from hashlib import md5
import json
import os
from typing import Any

from . import LookupBase, WorkflowExecutionData
from ..events import Event
from ..logging import getLogger
from ..workflow import WorkflowType

logger = getLogger("wkflws.lookups.filesystem")


@dataclass
class _FileSystemWorkflow:
    """Defines the properties of a workflow file."""

    #: hash of the full file path
    identifier: str
    #: ASL workflow definition
    definition: WorkflowType


class FileSystemLookup(LookupBase):
    """An example Lookup class which reads data from a file system.

    This lookup will pre-load all ``.asl`` workflows and cache the credentials from the
    current working directory.

    .. warning::
       This lookup class provides a quick way to test the app out and is not meant for
       production use. This does not support a secure method of storing credentials and
       should be modified before any real world use.

    Usage:

    Create a directory with a ``credentials.json`` file and at least 1 ``.asl`` file
    defining your workflow. ASL files can be organized in subdirectories if you
    wish. The credentials file should contain a map with the node name and a map of
    credentials to pass. For example:

    .. code::

       {
         "wkflws_slack": { "slack_bot_token": "xoxb-2930" }
       }


    """

    def __init__(self):
        super().__init__()

        # {"trigger_node_identifier": [workflows,]}
        self.workflows: dict[str, list[_FileSystemWorkflow]] = {}
        self.credentials: dict[str, Any] = {}

        for root, _, files in os.walk(os.getcwd()):
            for f in files:
                if os.path.splitext(f)[-1] == ".asl":
                    file_path = os.path.join(root, f)
                    identifier = md5(file_path.encode("utf-8")).hexdigest()
                    logger.debug(f"Loading '{file_path}' as {identifier}")

                    with open(file_path, "r") as fh:
                        j = json.load(fh)
                        try:
                            # Use the trigger node as the key for a quick lookup
                            key = j["States"][j["StartAt"]]["Resource"]
                        except KeyError as e:
                            logger.error(
                                f"Unable to find first State in {file_path} - Not "
                                f"Found: {e}."
                            )
                            continue

                        if key not in self.workflows:
                            self.workflows[key] = []

                        self.workflows[key].append(
                            _FileSystemWorkflow(
                                identifier=identifier,
                                definition=j,
                            )
                        )
        with open(os.path.join(os.getcwd(), "credentials.json")) as fh:
            self.credentials = json.load(fh)

    async def get_workflows(
        self,
        initial_node_id: str,
        event: Event,
    ) -> tuple[WorkflowExecutionData, ...]:
        workflows = self.workflows.get(initial_node_id, None)

        if not workflows:
            return ()

        # A copy is made so any modifications to the definition stay local to the
        # executions.
        workflows = deepcopy(workflows)

        workflow_executions: tuple[WorkflowExecutionData, ...] = ()
        for workflow in workflows:
            workflow_executions += (await self.get_workflow_execution(workflow),)

        return workflow_executions

    async def get_workflow_execution(
        self,
        workflow_definition: _FileSystemWorkflow,
    ) -> WorkflowExecutionData:

        # Get the state context before rewriting the Resource
        state_context = await self.get_state_context(workflow_definition.definition)
        # type ignore because this is defined as a dict behind the scenese
        wf: WorkflowType = workflow_definition.definition.copy()  # type: ignore
        for state_name in workflow_definition.definition.get("States", {}):
            try:
                # Replace the resource with the correct one for the execution model.
                old_resource = wf["States"][state_name]["Resource"]
                wf["States"][state_name]["Resource"] = f"python -m {old_resource}"

            except KeyError:
                # No resource defined
                pass

        return WorkflowExecutionData(
            workflow_id=workflow_definition.identifier,
            workflow_definition=wf,
            state_context=state_context,
        )

    async def get_state_context(
        self,
        workflow_definition: WorkflowType,
    ) -> dict[str, Any]:
        """Retrieve any credentials for the provided states."""
        retval: dict[str, str] = {}
        states = workflow_definition.get("States", {}).items()

        for state_name, state_definition in states:
            if "Resource" in state_definition:
                node_id = state_definition["Resource"].split(".")[0]
                retval[state_name] = self.credentials.get(node_id, {})

        return retval
