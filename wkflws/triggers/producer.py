import asyncio
import atexit
from threading import Thread
from typing import Optional

from ..conf import settings
from ..events import Event, Result
from ..exceptions import WkflwConfigurationException
from ..logging import logger

if settings.KAFKA_HOST:
    try:
        import confluent_kafka  # type:ignore # no types defined.
    except ImportError:
        raise ImportError(
            "Please install wkflws with the optional kafka module (pip install "
            "wkflws[kafka]"
        )


class AsyncProducer:
    """Asynchronous Kafka producer."""

    def __init__(
        self,
        *,
        client_id: str,
        default_topic: str,
        loop: Optional[asyncio.BaseEventLoop] = None,
    ):
        """Initialize AsyncProducer.

        Args:
            client_id: Identifier for this producer. Useful for troubleshooting Kafka.
            default_topic: The default topic used when one isn't provided to the
                :meth:``produce`` method.
            loop: The async loop to use.
                *Default is the current loop or a new loop is created.*
        """
        if settings.KAFKA_HOST is None:
            raise WkflwConfigurationException("Undefined Kafka host.")
        self.client_id = client_id
        bootstrap_urls = (f"{settings.KAFKA_HOST}:{settings.KAFKA_PORT}",)

        kafka_config = {
            "client.id": self.client_id,
            "bootstrap.servers": ",".join(bootstrap_urls),
            # "error_cb": self.on_kafka_error,
            # "enable.auto.commit": True,
            "logger": logger,
        }

        if settings.KAFKA_USERNAME:
            kafka_config.update(
                {
                    "sasl.mechanisms": "PLAIN",
                    "security.protocol": "SASL_SSL",
                    "sasl.username": settings.KAFKA_USERNAME,
                    "sasl.password": settings.KAFKA_PASSWORD or "",
                }
            )
        self._loop = loop or asyncio.get_event_loop()
        self._producer = confluent_kafka.Producer(
            kafka_config,
        )

        self._canceled = False
        self._poll_thread = Thread(target=self._poll_loop)

        self.default_topic = default_topic

        self._poll_thread.start()
        atexit.register(self.close)

    def _poll_loop(self):
        """Loop to poll Kafka.

        This is called from another thread so it doesn't block.
        """
        while not self._canceled:
            self._producer.poll(0.1)

    async def produce(
        self,
        *,
        event: Event,
        key: str,  # TODO: generate this if necessary
        topic: Optional[str] = None,
    ):
        """Send an event to downstream consumers via Kafka.

        Args:
            payload: This is the payload of the event to send. This value is pushed
                as-is to Kafka. Any pre-processing must be done by the caller.
            topic: Sends ``payload`` to this topic. *Default is ``self.default_topic``.
        """
        result = self._loop.create_future()

        def ack(err, msg):
            if err:
                self._loop.call_soon_threadsafe(
                    result.set_exception, confluent_kafka.KafkaException(err)
                )
            else:
                self._loop.call_soon_threadsafe(
                    result.set_result,
                    Result(
                        key=msg.key(),
                        offset=msg.offset,
                        latency=msg.latency,
                        topic=msg.topic,
                        # TODO: i think message is correct here. (not event)
                        message=msg.value,
                    ),
                )

        # Asynchronously pushes the event to Kafka. ``poll`` will call the value of
        # ``on_delivery`` when delivering the event succeeds or fails.
        self._producer.produce(
            topic=topic or self.default_topic,
            value=event.asjson().encode("utf-8"),
            key=key,
            on_delivery=ack,
        )

        return result

    def close(self):
        """Disconnects from Kafka and stops the thread.

        This method should be called when your application exits. See :mod:`atexit`
        if you are using a framework that doesn't have a hook for shutdown.
        """
        self._canceled = True
        self._poll_thread.join()
