"""Utilities for the receiving end of a trigger ndoe."""
import asyncio
import functools
import json
from typing import Any, Awaitable, Callable, Optional

from ..conf import settings
from ..events import Event
from ..exceptions import (
    WkflwConfigurationException,
    WkflwException,
    WkflwKafkaException,
)
from ..logging import logger
from ..workflow import initialize_workflows

if settings.KAFKA_HOST:
    try:
        import confluent_kafka  # type:ignore # no types defined.
        from confluent_kafka import KafkaError  # type:ignore # if it isn't installed
    except ImportError:
        raise ImportError(
            "Please install wkflws with the optional kafka module (pip install "
            "wkflws[kafka]"
        )


class AsyncConsumer:
    """Asynchronous Kafka consumer."""

    def __init__(
        self,
        *,
        client_identifier: str,
        consumer_group: str,
        topic: str,
        process_func: Callable[
            [Event], Awaitable[tuple[Optional[str], dict[str, Any]]]
        ],
        loop: Optional[asyncio.BaseEventLoop] = None,
    ):
        """Initialize new asynchronous Kafka consumer.

        Args:
            client_identifer: The client identifier for this consumer. Generally your
                module's ``__identifier__`` value should be used. (This value is
                provided to the ``WORKFLOW_MODEL``.)
            consuer_group: The consumer group name to assign to this consumer.
            topic: The topic to subscribe to.
            loop: The async event loop to use.
                *Default is the current loop or a new loop is created.*
        """
        if settings.KAFKA_HOST is None:
            raise WkflwConfigurationException("Undefined Kafka host.")
        self._loop = loop or asyncio.get_running_loop()

        self.process_func = process_func

        # You can technically subscribe to multiple topics but there isn't a known
        # use-case for that at this point.
        self.topic = topic
        self.consumer_group = consumer_group
        self.client_identifier = client_identifier

        self._canceled = False
        self._consumer: Optional[confluent_kafka.Consumer] = None

    async def start(self):
        """Start the event loop for the consumer."""
        # Instantiating the consumer immediately connects it to Kafka, thus it needs
        # to be closed so it is done in the `start` method.
        consumer_settings = {
            "client.id": self.client_identifier,
            "bootstrap.servers": f"{settings.KAFKA_HOST}:{settings.KAFKA_PORT}",
            "group.id": self.consumer_group,
            # Begin reading from the smallest offset in the event there are no
            # committed offsets, or the committed offset is invalid.
            "auto.offset.reset": "smallest",
            "enable.auto.commit": True,
        }
        if settings.KAFKA_USERNAME:
            consumer_settings.update(
                {
                    "sasl.mechanisms": "PLAIN",
                    "security.protocol": "SASL_SSL",
                    "sasl.username": settings.KAFKA_USERNAME,
                    "sasl.password": settings.KAFKA_PASSWORD or "",
                }
            )
        self._consumer = confluent_kafka.Consumer(
            consumer_settings,
            logger=logger,
        )

        logger.debug(f"Subscribing to topic {self.topic}")
        self._consumer.subscribe(
            [
                self.topic,
            ]
        )

        try:
            # self._loop.run_forever()
            if self._loop.is_running():
                # self._loop.call_soon(self._poll_loop)
                await self._poll_loop()
            else:
                self._loop.run_until_complete(self._poll_loop())
        except Exception:
            logger.exception("Caught exception during process loop.")
        finally:
            logger.debug("Starting shut down sequence...")

            # Complete any in-flight requests
            if self._loop.is_running():
                logger.debug("Completing inflight tasks...")
                await self._loop.shutdown_asyncgens()
                # self._loop.call_soon(self._loop.shutdown_asyncgens)
            else:
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())

            # This will close open sockets and immediately trigger a group rebalance.
            logger.debug("Closing connection to Kafka...")
            self._consumer.close()

            # logger.debug("Stopping the loop...")
            # self._loop.close()

            logger.info("Farewell.")

    async def _poll_loop(self):
        """Loop to poll Kafka.

        This is called from another thread so it doesn't block.
        """
        if not self._consumer:
            raise WkflwException(
                "Cannot start poll loop before consumer has been configured."
            )

        while True:
            kfk_msg: confluent_kafka.Message = await self._loop.run_in_executor(
                None,
                functools.partial(self._consumer.poll, timeout=1.0),
            )

            if kfk_msg is None:
                # timeout reached, nothing to do
                continue
            if kfk_msg.error():  # this is None if it's not an error.
                if kfk_msg.error().code() == KafkaError._PARTITION_EOF:
                    logger.debug(
                        "Reached the end of partition #{msg.partition()} "
                        f"for topic {kfk_msg.topic()} - offset:{kfk_msg.offset()}"
                    )
                    continue

                # TODO: Maybe convert this to a log message.
                # cimpl.KafkaException: KafkaError{
                #  code=UNKNOWN_TOPIC_OR_PART,
                #  val=3,
                #  str=(
                #      "Subscribed topic not available: webhook.shopify: Broker: "
                #      "Unknown topic or partition"
                #  ),
                # }
                raise WkflwKafkaException(kfk_msg.error())

            # The incoming event seems valid so process it...
            payload = json.loads(kfk_msg.value())

            kfk_key = kfk_msg.key()
            # The Voyage monolith doesn't always set the Kafka key
            identifier = kfk_key.decode("utf-8") if kfk_key else payload["identifier"]

            event = Event(
                identifier=identifier,
                metadata=payload.get("metadata", {}),
                data=payload.get("data", None),
            )

            initial_node_id, workflow_input = await self.process_func(event)

            if initial_node_id is None:
                continue

            workflows = await initialize_workflows(
                initial_node_id=initial_node_id,
                event=event,
                workflow_input=workflow_input,
            )

            if len(workflows) < 1:
                continue

            asyncio.gather(*(w.start(workflow_input) for w in workflows))

            # TODO: If successful possibly asynchronously commit the offset (it's
            # autocommit now)
