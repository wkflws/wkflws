""""""  # noqa
import argparse
import asyncio
from io import BytesIO
import json
import os
import subprocess
import sys
import textwrap
from typing import List, Union
import urllib.request
import zipfile

from wkflws.logging import logger
from wkflws.triggers.consumer import AsyncConsumer
from wkflws.utils.execution import module_attribute_from_string

logdict_for_app_server = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "generic": {
            "format": "%(levelname)s | %(asctime)s | %(name)s[%(process)s] | %(message)s",  # noqa
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "generic",
            "stream": "ext://sys.stderr",
        },
        "error_console": {
            "class": "logging.StreamHandler",
            "formatter": "generic",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "gunicorn.error": {
            "level": "INFO",
            "handlers": ["error_console"],
            "propagate": False,
            "qualname": "gunicorn.error",
        },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
            "qualname": "gunicorn.access",
        },
        "uvicorn": {
            "level": "INFO",
            "propagate": False,  # Prevents double logging
            "handlers": ["console"],
        },
    },
}

#: language choice and template trigger node mapping for trigger create command.
_CREATE_TRIGGER_LANG = {
    "py": "https://github.com/wkflws/template-trigger-python/zipball/master",
}
#: languages choice and template node mapping for create_node command.
_CREATE_NODE_LANG = {
    "py": "https://github.com/wkflws/template-node-python/zipball/master",
}


def module_name(value: str):
    """Validate a value as a module name.

    This is used for the create-node command.

    Args:
        value: The proposed module name to verify.

    Raises:
        ValueError: The proposed value is invalid as a module name.

    Returns:
        The value if valid.
    """
    # Based on:
    # https://docs.python.org/3.10/reference/lexical_analysis.html#identifiers

    # Note: the message of the ValueError exceptions seems to be swallowed by argparser,
    # and a generic "Invalid value" message is displayed.
    first_char = ord(value[0])
    if not (
        (first_char >= 0x41 and first_char <= 0x5A)
        or (first_char >= 0x61 and first_char <= 0x7A)  # noqa: W503
        or first_char == ord("_")  # noqa: W503
        or (first_char >= 0x80 and first_char <= 0x10FFFF)  # noqa: W503
    ):
        raise ValueError("Module name must begin a letter or underscore.")
    for char in value[1:]:
        c = ord(char)
        if not (
            (c >= 0x41 and c <= 0x5A)
            or (c >= 0x61 and c <= 0x7A)  # noqa: W503
            or c == ord("_")  # noqa: W503
            or (c >= 0x80 and c <= 0x10FFFF)  # noqa: W503
            or (c >= 0x30 and c <= 0x39)  # noqa: W503
        ):
            raise ValueError("Character '{char}' invalid for module name.")

    return value


def download_and_extract_template(zip_url: str, directory: str, module_name: str):
    """Download and extract a zip into ``directory``.

    Args:
        zip_url: The url for the zip file.
        directory: The directory to extract the zip into
    """
    sys.stderr.write(f"Downloading {zip_url}\n")
    r = urllib.request.urlopen(zip_url)
    zip_bytes = BytesIO(r.read())

    try:
        with zipfile.ZipFile(zip_bytes, "r") as z:
            # Github creates an ugly base directory name that we don't want and we also
            # want to replace some template variables with values so extraction is done
            # manually (otherwise just use .extractall).

            # Figure out the ugly root directory github assigned.
            orig_rootdir = None
            for info in z.infolist():
                # NOTE: all templates repos should be `template-node-<lang>` in the
                # wkflws organization so this will match.
                if info.filename.startswith("wkflws-template-"):
                    orig_rootdir = os.path.split(os.path.dirname(info.filename))[1]
                    sys.stderr.write(f"Found ugly root directory of {orig_rootdir}\n")
                    break

            if orig_rootdir is None:
                sys.stderr.write("Unable to find expected root directory name.\n")
                orig_rootdir = ""

            # Extract, modify, and write the files.
            for info in z.infolist():
                info.filename = info.filename.replace(orig_rootdir, module_name, 1)

                # Rename any directories or files.
                split_path: List[str] = info.filename.split(os.path.sep)

                for i, dirname in enumerate(split_path):
                    if "MODNAME" in split_path[i]:
                        split_path[i] = split_path[i].replace("MODNAME", module_name)

                info.filename = os.path.join(*split_path)

                if os.path.basename(info.filename) == "":
                    # This is a directory
                    if not os.path.exists(info.filename):
                        os.makedirs(info.filename)
                    continue

                with z.open(info) as in_file:
                    content: Union[str, bytes] = in_file.read()
                    file_mode = "wb"
                    try:
                        # `content` is declared as a Union[str, bytes] for the type
                        # checker. When it gets here it complains that str doesn't have
                        # a decode method which is true, but it will always be bytes at
                        # this point. It's only _after_ this point that it might be an
                        # str so we don't need to verify the type hence the type:ignore.
                        content = content.decode("utf-8")  # type:ignore
                        file_mode = "w"  # no error so now `content` is a string
                        if content != "":
                            content = content.replace("MODNAME", module_name)
                    except UnicodeDecodeError:
                        # Probably a binary file. No modifications necessary
                        pass

                    fileloc = os.path.join(directory, info.filename)
                    sys.stderr.write(f"Writing {fileloc}\n")
                    with open(fileloc, file_mode) as outfile:
                        outfile.write(content)

    except zipfile.BadZipFile:
        sys.stderr.write(
            f"Downloaded file is corrupt. Try manually downloading {zip_url} via your "
            "browser.\n"
        )
        sys.exit(1)


def git_init(directory: str, initial_branch="main"):
    """Initialize a new git repository.

    Args:
        directory: The directory to initialize as a repository. (i.e. the root directory
            of the source code.)
        initial_branch: What to call the branch currently/formally known as "master".
    """
    completed_process = subprocess.run(
        ("git", "init", f"--initial-branch={initial_branch}"),
        cwd=directory,
        capture_output=True,
    )

    for line in completed_process.stdout.decode("utf-8").split("\n"):
        if line.strip() == "":
            continue
        sys.stderr.write(f"{line}\n")

    if completed_process.returncode != 0:
        for line in completed_process.stderr.decode("utf-8").split("\n")[:-1]:
            if line.strip() == "":
                continue
            sys.stderr.write(f"{line}\n")


async def _cmd_trigger_start_listener(args: argparse.Namespace):
    from wkflws.conf import settings

    if settings.WORKFLOW_LOOKUP_CLASS == "":
        logger.error("Workflow lookup class is undefined.")
        sys.exit(1)

    nodes = []
    for mod_path in args.modules:
        try:
            nodes.append(module_attribute_from_string(mod_path))
            logger.debug(f"Imported '{mod_path}' as {nodes[-1]}")
        except ModuleNotFoundError as e:
            logger.error(f"The module '{mod_path}' cannot be imported.")
            logger.debug(f"{e}", exc_info=e)

            sys.exit(1)
        except AttributeError as e:
            logger.error(f"The node object '{mod_path}' could not be found.")
            logger.debug(f"{e}", exc_info=e)
            sys.exit(1)

    # asyncio.gather(*(node.start_listener() for node in nodes))

    # There are only webhook listeners, and their routes are added to a global FastAPI
    # app so only one listener needs to be started to listen on all routes.
    await nodes[-1].start_listener()


async def _cmd_trigger_start_processor(args: argparse.Namespace):
    from wkflws.conf import settings

    if settings.WORKFLOW_LOOKUP_CLASS == "":
        logger.error("Workflow lookup class is undefined.")
        sys.exit(1)
    try:
        node = module_attribute_from_string(args.module)
    except ModuleNotFoundError as e:
        logger.error(f"The module '{args.module}' cannot be imported. ({e})")
        logger.debug(f"{e}", exc_info=e)
        sys.exit(1)
    except AttributeError as e:
        logger.error(f"The node object '{args.module}' could not be found. ({e})")
        logger.debug(f"{e}", exc_info=e)
        sys.exit(1)

    if isinstance(node, AsyncConsumer):
        await node.start()
    else:
        await node.start_processor()


def _cmd_trigger_create(args: argparse.Namespace):
    if not args.module_name.startswith("wkflws_"):
        sys.stderr.write(
            "It is recommended to prefix your trigger node with wkflws_ to indicate "
            f"it's intention. (e.g. wkflws_{args.module_name})\n"
        )
    if args.module_name == "MODNAME":
        sys.stderr.write("This is the template variable used, and a bad module name.\n")

    # KeyError shouldn't occur because input was already validated
    download_and_extract_template(
        _CREATE_TRIGGER_LANG[args.lang],
        args.directory,
        args.module_name,
    )
    git_init(os.path.join(args.directory, args.module_name))


def _cmd_node_create(args: argparse.Namespace):
    if not args.module_name.startswith("wkflws_"):
        sys.stderr.write(
            "It is recommended to prefix your node with wkflws_ to indicate it's "
            f"intention. (e.g. wkflws_{args.module_name})\n"
        )
    if args.module_name == "MODNAME":
        sys.stderr.write("This is the template variable used, and a bad module name.\n")

    # KeyError shouldn't occur because input was already validated
    download_and_extract_template(
        _CREATE_NODE_LANG[args.lang],
        args.directory,
        args.module_name,
    )
    git_init(os.path.join(args.directory, args.module_name))


async def _cmd_publish(args: argparse.Namespace):
    from wkflws.events import Event
    from wkflws.triggers.producer import AsyncProducer

    try:
        with open(args.filename) as f:
            payload = json.load(f)
    except ValueError as e:
        sys.stderr.write(f"JSON Parse Error: {e}")
        sys.exit(1)

    if not isinstance(payload, list):
        sys.stderr.write(
            "Format Error: Expecting an array of dictionaries, found: "
            f"{type(payload).__name__}\n"
        )
        sys.exit(1)

    # Verify all the events are valid before actually publishing. This is to prevent
    # heartache in the event the first few events are ok but another one isn't. It
    # will allow the user to confidently republish all the events knowing there won't
    # be unwanted duplicates pushed.
    for i, data in enumerate(payload):
        if "key" not in data:
            sys.stderr.write(f"key missing from event index #{i}\n")
            sys.exit(1)
        if "topic" not in data:
            sys.stderr.write(f"topic missing from event index #{i}\n")
            sys.exit(1)
        if "event" not in data:
            sys.stderr.write(f"event missing from event index #{i}\n")
            sys.exit(1)
        if "identifier" not in data["event"]:
            sys.stderr.write(f"identifier missing from event in index #{i}\n")
            sys.exit(1)
        if "metadata" not in data["event"]:
            sys.stderr.write(f"metadata missing from event in index #{i}\n")
            sys.exit(1)
        if "data" not in data["event"]:
            sys.stderr.write(f"metadata missing from event in index #{i}\n")
            sys.exit(1)

    producer = AsyncProducer(
        # This default topic shouldn't be used when publishing. It is just a
        # placeholder.
        client_id="wkflws.cmdline.producer",
        default_topic="wkflws.cmdline.producer.default_topic",
    )
    try:
        ret = await asyncio.gather(
            *(
                producer.produce(
                    event=Event(
                        identifier=data["event"]["identifier"],
                        metadata=data["event"]["metadata"],
                        data=data["event"]["data"],
                    ),
                    key=data["key"],
                    topic=data["topic"],
                )
                for data in payload
            )
        )

        # Generally optional, but report back on the status of each event published.
        awaitable_count = len(ret)
        complete_awaitables = 0
        while True:
            if complete_awaitables == awaitable_count:
                break

            await asyncio.sleep(0.1)  # give other awaitables time to finish

            for fut in ret:
                if not fut.done():
                    continue

                if fut.exception():
                    sys.stderr.write(fut.exception())
                elif fut.result():
                    sys.stderr.write(
                        f'Published event {fut.result().key.decode("utf-8")}\n'
                    )

                complete_awaitables += 1

        # sys.stderr.write(f'Published event with key {data["key"]}\n')
    finally:
        producer.close()


def main():
    parser = argparse.ArgumentParser(description="wkflws management tool")
    parser.add_argument("-v", action="append_const", const="v", help="verbosity level")

    subparser = parser.add_subparsers(dest="command")

    # version_parser = subparser.add_parser("version", help="Print version information")
    # version_parser.set_defaults(func=_cmd_version)

    # ###
    # trigger nodes
    trigger_parser = subparser.add_parser("trigger", help="manage trigger nodes")
    trigger_subparser = trigger_parser.add_subparsers(dest="trigger_cmd")

    # Note: Disabling async mode allows the node to create it's own loop.

    # ## Start trigger listener
    trigger_start_listener_parser = trigger_subparser.add_parser(
        "start-listener",
        help="start the trigger's listener daemon process",
    )
    trigger_start_listener_parser.add_argument(
        "modules",
        nargs="+",
        help="import paths of the trigger objects you wish to start.",
    )
    # trigger_start_parser.add_argument("--host", type=str, default="127.0.0.1")
    # trigger_start_parser.add_argument("--port", type=int, default=8000)
    trigger_start_listener_parser.set_defaults(func=_cmd_trigger_start_listener)

    # ## Start trigger processor
    trigger_start_processor_parser = trigger_subparser.add_parser(
        "start-processor",
        help="start the trigger's processor (consumer) daemon process",
    )
    trigger_start_processor_parser.add_argument(
        "module",
        help="module path to trigger object you wish to start.",
    )
    # start_parser.add_argument("--dev", action="store_true")
    # for arg in ENV_TO_CLI_ARGS:
    #     start_parser.add_argument(f"--{arg.lower().replace('_', '-')}", type=str)

    trigger_start_processor_parser.set_defaults(func=_cmd_trigger_start_processor)

    # ## Create new trigger node
    trigger_create_parser = trigger_subparser.add_parser(
        "create", help="Create the structure and local git repo for a new trigger node."
    )
    trigger_create_parser.add_argument(
        "--lang",
        choices=_CREATE_TRIGGER_LANG.keys(),
        type=str,
        default="py",
        help="The language you to use.",
    )
    trigger_create_parser.add_argument(
        "--directory",
        type=str,
        default=os.getcwd(),
        help=(
            "The directory to create the trigger node structure in (as a sub "
            "directory). Default is the current directory"
        ),
    )
    trigger_create_parser.add_argument(
        "module_name",
        type=module_name,
        help=(
            "The sacred name you wish to call your node. It's recommended to prefix "
            "your module with `wkflws_` to indicate it is for use with wkflws."
        ),
    )
    trigger_create_parser.set_defaults(func=_cmd_trigger_create, async_mode=False)
    # ###
    # Node commands
    node_parser = subparser.add_parser("node", help="manage nodes")
    node_subparser = node_parser.add_subparsers(dest="node_cmd")

    node_create_parser = node_subparser.add_parser(
        "create", help="Create the structure and local git repo for a new node."
    )
    node_create_parser.add_argument(
        "--lang",
        choices=_CREATE_NODE_LANG.keys(),
        type=str,
        default="py",
        help="The language you to use.",
    )
    node_create_parser.add_argument(
        "--directory",
        type=str,
        default=os.getcwd(),
        help=(
            "The directory to create the node structure in (as a sub directory). "
            "Default is the current directory"
        ),
    )
    node_create_parser.add_argument(
        "module_name",
        type=module_name,
        help=(
            "The sacred name you wish to call your node. It's recommended to prefix "
            "your module with `wkflws_` to indicate it is for use with wkflws."
        ),
    )
    node_create_parser.set_defaults(func=_cmd_node_create, async_mode=False)

    # ###
    # Development and Testing info
    # ###
    # if DEVELOPMENT_MODE:
    #     # Enable development mode options
    publish_parser = subparser.add_parser(
        "publish",
        help="Publish (test) data to Kafka.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """
            Publish test data to Kafka.\n
            The file provided must contain an array of dictionaries with 3 elements:\n\n
              - "key": the key/id of the event
              - "topic": the topic to publish to
              - "event": the payload. The format of this value should follow the
                structure of the Event dataclass."""
        ).strip(),
    )
    publish_parser.add_argument(
        "filename",
        help=(
            "path to file containing JSON array of data to publish. See above for "
            "details"
        ),
    )
    publish_parser.set_defaults(func=_cmd_publish)

    args = parser.parse_args()

    log_level = 20  # Info
    if args.v:
        log_level = log_level - (len(args.v) * 10)
        if log_level < 10:
            log_level = 10  # DEBUG is the lowest
    logger.setLevel(log_level)

    if args.command is None:
        parser.print_help()
        sys.exit(1)
    elif args.command == "trigger" and args.trigger_cmd is None:
        trigger_parser.print_help()
        sys.exit(1)
    elif args.command == "node" and args.node_cmd is None:
        node_parser.print_help()
        sys.exit(1)

    if getattr(args, "async_mode", True):
        try:
            asyncio.run(args.func(args))
        except KeyboardInterrupt:
            sys.exit(0)
    else:
        try:
            args.func(args)
        except KeyboardInterrupt:
            sys.exit(0)
