import abc
import asyncio
from typing import Any, Awaitable, Callable, Optional, Union

from .consumer import AsyncConsumer
from .producer import AsyncProducer
from ..conf import settings
from ..events import Event
from ..exceptions import WkflwConfigurationException
from ..logging import logger
from ..tracing import get_tracer, initialize_tracer, inject_span_context
from ..workflow import initialize_workflows


class BaseTrigger(abc.ABC):
    """Common code useful for any trigger subclass.

    Triggers are designed to be two separate pieces with a event bus (Kafka) in between
    them.
    """

    def __init__(
        self,
        *,
        client_identifier: str,
        client_version: str,
        process_func: Callable[
            [Event],
            Awaitable[
                tuple[Optional[str], Union[list[dict[str, Any]], dict[str, Any]]]
            ],
        ],
        kafka_topic: Optional[str] = None,
        kafka_consumer_group: Optional[str] = None,
    ):
        """Initialize new BaseTrigger object.

        This method is meant to be overridden and called via ``super()``

        Args:
            client_identifier: A unique identifier for this client. Generally your
                module's ``__identifier__`` value should be used.
            client_version: The version of this node. This is generally your module's
                ``__version__`` value.
            process_func: A callable which accepts the data returned by ``accept_func``
                and includes any business logic necessary to begin the workflow. (This
                is the consumer portion of the trigger.)
            kafka_topic: The Kafka topic to publish and receive events on. If this
                value is ``None`` then the data will be passed directly to the data
                processing function (i.e. in memory). If this value is defined then
                ``kafka_consumer_group`` must also be defined.
            kafka_consumer_group: The consumer group this instance belongs to. This
                value is ignored when Kafka is disabled (``kafka_topic`` is ``None``).
        """
        self.client_identifier = client_identifier
        self.client_version = client_version

        self.process_func = process_func

        self.kafka_topic = kafka_topic

        if kafka_topic and "_" in kafka_topic:
            logger.error(
                "Due to limitations in Kafka's metric names, topics with a period "
                "('.') or underscore ('_') could collide. Please use a period instead."
            )

        if self.kafka_topic and kafka_consumer_group is None:
            raise WkflwConfigurationException(
                "kafka_consumer_group must be defined when kafka_topic is defined."
            )

        if self.kafka_topic is None:
            logger.info("No Kafka topic defined. Event processing will be done inline.")

        # casting str to str for type checking. pyright/mypy aren't parsing the compound
        # conditional statement checking for None above.
        self.kafka_consumer_group = str(kafka_consumer_group)

        self.producer: Optional[AsyncProducer] = None
        self.consumer: Optional[AsyncConsumer] = None

    async def send_event(self, event: Event):
        """Send ``event`` to the event bus.

        If Kafka is not configure then the processing function will be executed in this
        process.

        Args:
            event: The data to publish to Kafka.
        """
        with get_tracer().start_as_current_span(
            "triggers.base.BaseTrigger.send_event",
        ) as span:
            inject_span_context(event.metadata)
            if self.producer:
                span.set_attribute("event_process.method", "kafka")
                await self.producer.produce(
                    event=event,
                    # TODO: type error: generate key/identifier if needed
                    key=event.identifier or "123TODO",
                    topic=self.kafka_topic,
                )
            else:
                span.set_attribute("event_process.method", "inline")
                initial_node_id, workflow_input = await self.process_func(event)

                span.set_attribute("initial_node_id", initial_node_id or "None")

                if initial_node_id is None:
                    return
                # Sets node_id so it can be searched easily, even if it's the initial
                span.set_attribute("node_id", initial_node_id)

                workflows = await initialize_workflows(
                    initial_node_id=initial_node_id,
                    event=event,
                    workflow_input=workflow_input,
                )

                asyncio.gather(*(w.start(workflow_input) for w in workflows))

    @abc.abstractmethod
    async def start_listener(self):
        """Start the event loop for processing raw incoming data.

        The listener accepts data from a 3rd party data source, formats it, and
        publishes it to Kafka. You MUST call :meth:`BaseTrigger.initialize_listener`
        to initialize additional configuration.

        .. note::

           The reason why you must manually call ``initialize_listener`` instead of
           being done automatically behind the scenes is because it can't be predicted
           when. For example the WebhookTrigger uses Gunicorn which forks worker
           processes and initialization must be done there rather than the main process.

        """
        raise NotImplementedError(
            "`start_listener` not implemented. If there is no listener then it should "
            "be an explicit no-op. (Be sure to call initialize_listener!)"
        )

    def initialize_listener(self):
        """Initializes additional components of the listener."""

        initialize_tracer()

        if (
            not self.producer
            and self.kafka_topic is not None
            and settings.KAFKA_HOST is not None
        ):
            logger.info(
                f"Initializing producer to topic:{self.kafka_topic} as "
                f"client:{self.client_identifier}"
            )
            self.producer = AsyncProducer(
                client_id=self.client_identifier,
                default_topic=self.kafka_topic,
            )

    async def start_processor(self):
        """Start the event loop for processing data from the event bus.

        The processor accepts data from the event bus (generally formatted by the
        :meth:`start_listener` process) kicking off any necessary pipelines.
        """
        if (
            not self.consumer
            and self.kafka_topic is not None
            and settings.KAFKA_HOST is not None
        ):
            self.consumer = AsyncConsumer(
                client_id=self.client_identifier,
                consumer_group=self.kafka_consumer_group,
                topic=self.kafka_topic,
                process_func=self.process_func,
            )

            initialize_tracer()
            await self.consumer.start()

        elif not self.kafka_topic:
            logger.error(
                f"Kafka topic is undefined for {self.__class__.__module__}"
                f"{self.__class__.__name__}"
            )
        else:
            logger.error(
                "No Kafka host defined. Either define the Kafka host or use inline "
                "processing on the listener."
            )
        # raise NotImplementedError(
        #     "`start_processor` not implemented. If there is no processor then it "
        #     "should be an explicit no-op."
        # )
