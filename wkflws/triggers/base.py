import abc
import asyncio
from typing import Any, Awaitable, Callable, Optional

from .producer import AsyncProducer
from ..events import Event
from ..exceptions import WkflwConfigurationException
from ..logging import logger
from ..workflow import initialize_workflows


class BaseTrigger(abc.ABC):
    """Common code useful for any trigger subclass.

    Triggers are designed to be two separate pieces with a event bus (Kafka) inbetween
    them.
    """

    def __init__(
        self,
        *,
        client_identifier: str,
        client_version: str,
        process_func: Callable[
            [Event], Awaitable[tuple[Optional[str], dict[str, Any]]]
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
            kafka_topic: The Kafka topic to publish and recieve eventss on. If this
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

        self.kafka_consumer_group = kafka_consumer_group

        self.producer: Optional[AsyncProducer] = None
        if self.kafka_topic is not None:
            self.producer = AsyncProducer(
                client_id=self.client_identifier,
                default_topic=self.kafka_topic,
            )

    async def send_event(self, event: Event):
        """Send ``event`` to the event bus.

        If Kafka is not configure then the processing function will be executed in this
        process.

        Args:
            event: The data to publish to Kafka.
        """
        if self.producer:
            await self.producer.produce(
                event=event,
                # TODO: type error: generate key/identifier if needed
                key=event.identifier or "123TODO",
                topic=self.kafka_topic,
            )
        else:
            initial_node_id, workflow_input = await self.process_func(event)

            if initial_node_id is None:
                return

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
        publishes it to Kafka.
        """
        raise NotImplementedError(
            "`start_listener` not implemented. If there is no listener then it should "
            "be an explicit no-op."
        )

    async def start_processor(self):
        """Start the event loop for processing data from the event bus.

        The processor accepts data from the event bus (generally formatted by the
        :meth:`start_listener` process) kicking off any necessary pipelines.
        """
        # if self.consumer???:
        #     await self.consumer.start()
        # raise NotImplementedError(
        #     "`start_processor` not implemented. If there is no processor then it "
        #     "should be an explicit no-op."
        # )
