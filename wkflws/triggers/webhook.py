import multiprocessing
from typing import Any, Awaitable, Callable, Optional

try:
    from fastapi import (
        APIRouter,
        FastAPI,
        Response as FAPIResponse,
        Request as FAPIRequest,
        status,  # This is used as a convenience import
    )
    import gunicorn.app.base  # type:ignore  # no stubs
    import uvicorn  # type:ignore  # no stubs  # noqa - worker imported by string
except ImportError:
    raise ImportError("Webhook modules not installed. (pip install wkflws[webhook]")

from .base import BaseTrigger
from ..events import Event
from ..http import http_method, Request, Response
from ..logging import LOG_FORMAT, logger, LogLevel


class WebhookTrigger(BaseTrigger):
    """Creates a Webhook for processing a workflow.

    This class creates a decoupled trigger node which publishes the raw data it
    receives to the event bus then consumes and processes the data. It is meant to feel
    like a single process, but in reality is is two separate daemons being run.

    .. code-block:: python

       async def process_webhook_request(request: Request) -> Optional[Event]:
           trace_id = request.headers.get("X-Trace-Id", uuid.uuid4())

           metadata = {
               "tenant-id": get_tenant_id(),
           }

           data = json.loads(request.body)

           return Event(
               identifier=trace_id,
               metadata=metadata,
               data=data,
           )

       async def start_workflow(event: Optional[Event]):
           pass

       routes = [
           (
               (http_methods.POST, http_methods.GET),
               "/webhook/",
               process_webhook_request,
           )
       ]

       trigger = WebhookTrigger(
           client_identifier=__identifier__,
           client_version=__version__,
           routes=routes,
           process_func=start_workflow,
           kafka_topic="vendor.webhook",
           kafka_consumer_group=f"wkflws.{__identifier__}",
       )


    """

    #: Declare the global FastAPI listener for all webhooks. It is up to the developers
    #: to ensure paths are unique across the project.
    app = FastAPI(
        redoc_url=None,
        docs_url=None,
        openapi_url=None,
    )

    def __init__(
        self,
        *,
        client_identifier: str,
        client_version: str,
        routes: tuple[
            tuple[
                tuple[http_method, ...],
                str,
                Callable[[Request, Response], Awaitable[Optional[Event]]],
            ],
            ...,
        ],
        process_func: Callable[
            [Event], Awaitable[tuple[Optional[str], dict[str, Any]]]
        ],
        kafka_topic: Optional[str] = None,
        kafka_consumer_group: Optional[str] = None,
    ):
        """Initialize new WebhookTrigger object.

        To define the routes for this webhook each element in the tuple is a tuple which
        must consist of:

        - A list of HTTP routes the endpoint can accept.
        - The http path for this endpoint.
        - A callable which processes the request.

        Args:
            client_identifier: A unique identifier for this client. Generally your
                module's ``__identifier__`` value should be used.
            client_version: The version of this node. This is generally your module's
                ``__version__`` value.
            routes: Define the HTTP routes. See above for more color.
            process_func: A callable which accepts the data returned by ``accept_func``
                and includes any business logic necessary to begin the workflow. (This
                is the consumer portion of the trigger.)
            kafka_topic: The Kafka topic to publish and recieve events on. If this
                value is ``None`` then the data will be passed directly to the data
                processing function (i.e. in memory). If this value is defined then
                ``kafka_consumer_group`` must also be defined.
            kafka_consumer_group: The consumer group this instance belongs to. This
                value is ignored when Kafka is disabled (``kafka_topic`` is ``None``).
        """
        super().__init__(
            client_identifier=client_identifier,
            client_version=client_version,
            process_func=process_func,
            kafka_topic=kafka_topic,
            kafka_consumer_group=kafka_consumer_group,
        )

        self.router = APIRouter()

        self.app.version = self.client_version

        @self.app.on_event("shutdown")
        async def disconnect_producer():
            if self.producer is not None:
                logger.info(
                    "Caught API shutdown event. Trying to gracefully close Kafka "
                    "producer."
                )
                self.producer.close()

        for route in routes:
            self.add_route(*route)

        # This must come after adding routes otherwise they won't be initialized and
        # served.
        self.app.include_router(self.router)

    def add_route(
        self,
        methods: tuple[http_method, ...],
        path: str,
        func: Callable[[Request], Awaitable[Optional[Event]]],
    ):
        """Add a new route and publishes the return value to the event bus.

        This function will add a new new http path to the server. The result of the
        callable ``func`` will be wrapped in an envelop and published to the event bus.

        ``func`` should accept a single :class:`Request` argument and return an
        optional :class:`Event` object. If ``None`` is returned than a 200 status code
        is returned with no other action. It is the developer's responsibility to do
        something or nothing with the data.

        Args:
           methods: A list of HTTP methods this route should respond to.
           path: the path portion of the URI. (e.g. "/callback/")
           func: The function which processes the incoming data into a :class:`Data`
               object
        """
        # This wrapper is used to accept FastAPI's dependency injection stuff and pass
        # it to the actual request handler.
        async def wkflws_webhook_route_wrapper(request: FAPIRequest):
            return await self._handle_request(func, request)

        # By adding the actual source function as a property to the wrapper we can
        # assist the user when they are debugging. With that said this function name is
        # referenced as a string so don't change the name but if you have to be sure to
        # find/replace the entire codebase.
        wkflws_webhook_route_wrapper.func = func  # type:ignore # attribute not found

        logger.debug(f"Adding route '{path}' -> {func}")
        self.router.add_api_route(
            path,
            endpoint=wkflws_webhook_route_wrapper,
            methods=list(m.value for m in methods),
        )

    async def _handle_request(
        self,
        func: Callable[[Request], Awaitable[Optional[Event]]],
        original_request: FAPIRequest,
    ) -> FAPIResponse:
        """Handle the incoming webhook request.

        This function creates the :class:`Request` object before calling the business
        logic which prepares the data for for publishing on the event bus.

        See :meth:`add_route` for more documentation.

        Args:
            func: The original function containing the route logic to execute.
            original_request: FastAPI's normal request object. Data is extracted into
                a :class:`Request` object.

        Returns:
           A 200 status code. Generally this tells the remote server we've accepted
           the data and don't retry.
        """
        incoming_headers = {k: v for k, v in original_request.headers.items()}
        request = Request(
            url=str(original_request.url),
            headers=incoming_headers,
            body=(await original_request.body()).decode("utf-8"),
        )
        response = Response()

        event = await func(request, response)

        if event:
            await self.send_event(event)

        # if response.headers and "Content-Type" in response.headers.keys():
        #     media_type = response.headers.pop("Content-Type")
        # else:
        #     media_type = None
        r = FAPIResponse(
            status_code=response.status_code,
            content=response.body,
            headers=response.headers,  # type:ignore
        )

        return r

    async def start_listener(self):
        """Start a Gunicorn daemon process using uvicorn as the worker.

        By default this will start 1 worker for each CPU core on the host machine.
        """
        logger.debug("Starting listener...")
        # for arg, value in args._get_kwargs():
        #     if arg.upper() in ENV_TO_CLI_ARGS and value is not None:
        #         os.environ[arg.upper()] = value

        # if args.dev:

        # uvicorn.run(
        #     "wkflws_shopify.trigger:webhook_trigger.app",
        #     host="127.0.0.1",  # args.host,
        #     port=8000,  # args.port,
        #     reload=True,
        #     reload_excludes=("bin/*", "**/.mypy_cache/*"),
        #     # log_config=logdict_for_app_server,
        #     server_header=False,
        # )
        # sys.exit(0)

        # this is usually (count*2)+1 but i imagine the async nature of the code base
        # will lend itself to just using all the cores since there shouldn't be anything
        # blocking/waiting.
        num_workers = 1 or multiprocessing.cpu_count()

        options = {
            "bind": "127.0.0.1:8000",  # f"{args.host}:{args.port}",
            "workers": num_workers,
            "worker_class": "uvicorn.workers.UvicornWorker",
            "logconfig_dict": logdict_for_app_server,
            "timeout": 5,
        }

        if logger.getEffectiveLevel() == LogLevel.DEBUG:
            # Go through the trouble of displaying the routes. This can be a useful
            # first step when troubleshooting why a route isn't being executed.
            from fastapi.routing import APIRoute

            # Make the type checker useful:
            # self.app.routes is defined as list[BaseRoute] but actually returns a
            # list of APIRoutes which contain more members.
            #
            # Also self.app is used instead of self.router because the app can add it's
            # own routes and we want to be aware of that.
            logger.debug(f"Found {len(self.app.routes)} routes")
            routes: list[APIRoute] = self.app.routes  # type:ignore
            for route in routes:
                func = route.endpoint
                if func.__name__ == "wkflws_webhook_route_wrapper":
                    # Display the user's function instead of the built-in wrapper.
                    func = route.endpoint.func

                logger.debug(f"Found registered route: {route.path} -> {func} ")

        _GunicornDaemon(self.app, options).run()


class _GunicornDaemon(gunicorn.app.base.BaseApplication):
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config = {
            key: value
            for key, value in self.options.items()
            if key in self.cfg.settings and value is not None  # type:ignore # gunicorn
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)  # type: ignore  # in gunicorn

    def load(self):
        return self.application


logdict_for_app_server = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "generic": {
            "class": "wkflws.logging.ColorizedFormatter",
            "format": LOG_FORMAT,
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
