"""Module for holding the message bus classes.
"""

from typing import Any, Self, Literal, Generator
from abc import ABC, abstractmethod
import asyncio
from contextlib import asynccontextmanager

from aiokafka import AIOKafkaProducer
from kafka3 import KafkaProducer
import aiohttp

from test_harness.utils import wrap_kafka_future


class InputConverter(ABC):
    """Abstract class for message converter."""

    @abstractmethod
    def convert(
        self, message: Any, *args, **kwargs
    ) -> tuple[Any, tuple, dict, tuple, dict]:
        """Abstract method to convert a message."""
        pass


class SimpleInputConverter(InputConverter):
    """Simple message converter."""

    def convert(
        self, message: Any
    ) -> tuple[Any, tuple, dict, tuple, dict]:
        """Convert a message."""
        return message, (), {}, (), {}


class ResponseConverter(ABC):
    """Abstract class for response converter."""

    @abstractmethod
    def convert(self, response: Any, *args, **kwargs) -> Any:
        """Abstract method to convert a response."""
        pass


class SimpleResponseConverter(ResponseConverter):
    """Simple response converter."""

    def convert(self, response: Any) -> Any:
        """Convert a response."""
        return response


class MessageExceptionHandler(ABC):
    """Abstract class for message exception handler."""

    @abstractmethod
    def handle_exception(self, exception: Exception, *args, **kwargs) -> Any:
        """Abstract method to handle an exception."""
        pass


class SimpleMessageExceptionHandler(MessageExceptionHandler):
    """Simple message exception handler."""

    def handle_exception(self, exception: Exception) -> Any:
        """Handle an exception."""
        raise exception


class MessageProducer(ABC):
    """Abstract class for message sender."""

    def __init__(
        self,
        message_bus: "MessageBusSendingController",
        input_converter: InputConverter | None = None,
        response_converter: ResponseConverter | None = None,
        exception_converter: MessageExceptionHandler | None = None,
    ) -> None:
        """Constructor method"""
        self.message_bus = message_bus
        self._input_converter = (
            input_converter
            if input_converter is not None
            else SimpleInputConverter()
        )
        self._response_converter = (
            response_converter
            if response_converter is not None
            else SimpleResponseConverter()
        )
        self._exception_converter = (
            exception_converter
            if exception_converter is not None
            else SimpleMessageExceptionHandler()
        )

    async def send_message(self, message: Any, *args, **kwargs) -> Any:
        """Abstract method to send a message."""
        (
            converted_message,
            send_args,
            send_kwargs,
            output_args,
            output_kwargs,
        ) = self._input_converter.convert(message, *args, **kwargs)
        try:
            response = await self._send(
                converted_message, *send_args, **send_kwargs
            )
            return self._response_converter.convert(
                response=response, *output_args, **output_kwargs
            )
        except Exception as exception:
            return self._exception_converter.handle_exception(
                exception=exception, *output_args, **output_kwargs
            )

    @abstractmethod
    async def _send(self, message: Any, *args, **kwargs) -> Any:
        """Abstract method to send a message."""
        pass


class MessageBusSendingController(ABC):
    """Abstract class for message bus sending controller."""

    def __init__(
        self,
    ) -> None:
        """Constructor method"""

    @abstractmethod
    async def __aenter__(self) -> Self:
        """Abstract method to enter the context."""
        return self

    @abstractmethod
    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Abstract method to exit the context."""
        pass

    @abstractmethod
    def get_message_producer(
        self,
        *args,
        input_converter: InputConverter | None = None,
        response_converter: ResponseConverter | None = None,
        exception_converter: MessageExceptionHandler | None = None,
        **kwargs,
    ) -> "MessageProducer":
        """Abstract method to get a message producer."""
        pass

    @abstractmethod
    async def send(self, message: Any, *args, **kwargs) -> None:
        """Abstract method to send a message."""
        pass


class KafkaMessageProducer(MessageProducer):
    """AIOKafka message producer."""

    def __init__(
        self,
        topic: str,
        message_bus: "KafkaMessageBus",
        input_converter: InputConverter | None = None,
        response_converter: ResponseConverter | None = None,
        exception_converter: MessageExceptionHandler | None = None,
    ) -> None:
        """Constructor method"""
        self.topic = topic
        super().__init__(
            message_bus=message_bus,
            input_converter=input_converter,
            response_converter=response_converter,
            exception_converter=exception_converter,
        )

    async def _send(self, message: bytes) -> bytes:
        """Send a converted message."""
        return await self.message_bus.send(
            message=message,
            topic=self.topic,
        )


class KafkaMessageBus(MessageBusSendingController):
    """AIOKafka message bus."""

    def __init__(
        self,
        bootstrap_servers: str,
        stop_timeout: int = 10,
    ) -> None:
        """Constructor method"""
        self.stop_timeout = stop_timeout
        self._bootstrap_servers = bootstrap_servers
        super().__init__()

    @property
    def producer(self) -> Any:
        """Property to get a producer."""
        if not hasattr(self, "_producer"):
            self._set_producer()
        return self._producer

    @abstractmethod
    def _set_producer(self) -> Any:
        """Abstract method to get a producer."""
        pass

    def get_message_producer(
        self,
        topic: str,
        input_converter: InputConverter | None = None,
        response_converter: ResponseConverter | None = None,
        exception_converter: MessageExceptionHandler | None = None,
    ) -> "MessageProducer":
        """Get a message producer."""
        return KafkaMessageProducer(
            topic=topic,
            message_bus=self,
            input_converter=input_converter,
            response_converter=response_converter,
            exception_converter=exception_converter
        )

    async def send(self, message: bytes, topic: str) -> bytes:
        """Send a message to a topic."""
        return await self._send_to_topic(message=message, topic=topic)

    @abstractmethod
    async def _send_to_topic(self, message: bytes, topic: str) -> bytes:
        """Abstract method to send a message to a topic."""
        pass


class AIOKafkaMessageBus(KafkaMessageBus):
    """AIOKafka message bus."""

    def __init__(
        self,
        bootstrap_servers: str,
        stop_timeout: int = 10,
    ) -> None:
        """Constructor method"""
        self.stop_timeout = stop_timeout
        super().__init__(
            bootstrap_servers=bootstrap_servers,
        )

    @property
    def producer(self) -> AIOKafkaProducer:
        """Property to get a producer."""
        if not hasattr(self, "_producer"):
            self._set_producer()
        return self._producer

    def _set_producer(self) -> Any:
        """Get a producer."""
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
        )

    async def __aenter__(self) -> Self:
        """Enter the context."""
        await self.producer.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Exit the context."""
        await asyncio.wait_for(self.producer.stop(), timeout=self.stop_timeout)
        if exc is not None:
            raise exc

    async def _send_to_topic(self, message: bytes, topic: str) -> bytes:
        """Send a message to a topic."""
        return await self.producer.send_and_wait(topic=topic, value=message)


class Kafka3MessageBus(KafkaMessageBus):
    """Kafka3 message bus."""

    def __init__(
        self,
        bootstrap_servers: str,
        stop_timeout: int = 10,
    ) -> None:
        """Constructor method"""
        self.stop_timeout = stop_timeout
        super().__init__(
            bootstrap_servers=bootstrap_servers,
        )

    @property
    def producer(self) -> KafkaProducer:
        """Property to get a producer."""
        if not hasattr(self, "_producer"):
            self._set_producer()
        return self._producer

    def _set_producer(self) -> KafkaProducer:
        """Get a producer."""
        self._producer = KafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
        )

    async def __aenter__(self) -> Self:
        """Enter the context."""
        self._set_producer()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Exit the context."""
        self.producer.close(timeout=self.stop_timeout)
        if exc is not None:
            raise exc

    async def _send_to_topic(self, message: bytes, topic: str) -> bytes:
        """Send a message to a topic."""
        return await wrap_kafka_future(
            self.producer.send(topic=topic, value=message)
        )


class HTTPMessageProducer(MessageProducer):
    """HTTP message producer."""

    def __init__(
        self,
        url: str,
        message_bus: "HTTPMessageBus",
        input_converter: InputConverter | None = None,
        response_converter: ResponseConverter | None = None,
        exception_converter: MessageExceptionHandler | None = None,
    ) -> None:
        """Constructor method"""
        self.url = url
        super().__init__(
            message_bus=message_bus,
            input_converter=input_converter,
            response_converter=response_converter,
            exception_converter=exception_converter,
        )

    async def _send(self, message: Any, **kwargs) -> Any:
        """Send a converted message."""
        return await self.message_bus.send(
            message=message, url=self.url, **kwargs
        )


class HTTPMessageBus(MessageBusSendingController):
    """HTTP message bus."""

    def __init__(
        self,
        max_connections: int = 2000,
    ) -> None:
        """Constructor method"""
        self.max_connections = max_connections
        super().__init__()

    @property
    def session(self) -> aiohttp.ClientSession:
        """Property to get a session."""
        if not hasattr(self, "_session"):
            self._set_session()
        return self._session

    def _set_session(self) -> None:
        """Get a session."""
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                limit=self.max_connections,
            ),
        )

    def get_message_producer(
        self,
        url: str,
        input_converter: InputConverter | None = None,
        response_converter: ResponseConverter | None = None,
        exception_converter: MessageExceptionHandler | None = None,
    ) -> "MessageProducer":
        """Get a message producer."""
        return HTTPMessageProducer(
            url=url,
            message_bus=self,
            input_converter=input_converter,
            response_converter=response_converter,
            exception_converter=exception_converter
        )

    async def send(self, message: Any, url: str, **kwargs) -> bytes:
        """Send a message to a url."""
        return await self._send_post_to_url(message, url, **kwargs)

    async def _send_post_to_url(
        self, message: Any, url: str, **kwargs
    ) -> aiohttp.ClientResponse:
        """Abstract method to send a message to a url."""
        async with self.session.post(
            url=url, data=message, **kwargs
        ) as response:
            await response.read()
            return response

    async def __aenter__(self) -> Self:
        """Enter the context."""
        await self.session.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Exit the context."""
        await self.session.__aexit__(exc_type, exc, tb)


class MessageSender(ABC):
    """Abstract class for message sender.

    This class is used to send messages (could be batches or single messages)
    in a variety of ways using a message producer to send the underlying
    messages.
    """

    def __init__(
        self,
        message_producer: MessageProducer,
        input_converter: InputConverter | None = None,
        response_converter: ResponseConverter | None = None,
    ) -> None:
        """Constructor method"""
        self.message_producer = message_producer
        self._input_converter = (
            input_converter
            if input_converter is not None
            else SimpleInputConverter()
        )
        self._response_converter = (
            response_converter
            if response_converter is not None
            else SimpleResponseConverter()
        )

        """Abstract method to send a message."""
    async def send(
        self,
        message: Any,
        *args,
        **kwargs
    ) -> Any:
        """Async method to send a list of dicts as a json payload

        :param message: The list of dictionaries
        :type message: `list`[`dict`[`str`, `Any`]]
        :param job_id: The job id
        :type job_id: `str`
        :param job_info: The job info
        :type job_info: `dict`[`str`, `str` | `None`]
        :return: Returns a tuple of:
        * the list of dicts sent
        * the file name given
        * the result of the request
        :rtype: `tuple`[`list`[`dict`[`str`, `Any`]], `str`, `str`,
        :class:`datetime`]
        """
        (
            converted_data,
            sender_args,
            sender_kwargs,
            response_args,
            response_kwargs
        ) = self._input_converter.convert(
            message=message,
            *args,
            **kwargs
        )
        response = await self._sender(
            converted_data=converted_data,
            *sender_args,
            **sender_kwargs
        )
        return self._response_converter.convert(
            response,
            *response_args,
            **response_kwargs
        )

    @abstractmethod
    async def _sender(
        self,
        *args,
        **kwargs
    ):
        """Abstract method to send a message."""
        pass


@asynccontextmanager
async def get_producer_context(
    message_bus: Literal["KAFKA", "HTTP", "KAFKA3"],
    message_bus_kwargs: dict[str, Any],
    producer_kwargs: dict[str, Any],
) -> Generator[MessageProducer, Any, None]:
    """Function to get a producer instance in a context manager for a message
    bus.

    :param message_bus: The message bus
    :type message_bus: `Literal`["KAFKA", "KAFKA3", "HTTP"]
    :param message_bus_kwargs: The message bus keyword arguments
    :type message_bus_kwargs: `dict`[`str`, `Any`]
    :param producer_kwargs: The producer keyword arguments
    :type producer_kwargs: `dict`[`str`, `Any`]
    :raises ValueError: If the message bus is not recognised
    :raises ValueError: If the bootstrap_servers keyword argument is not
        provided for kafka message bus keyword arguments
    :raises ValueError: If the topic keyword argument is not provided for kafka
        message producer keyword arguments
    :raises ValueError: If the url keyword argument is not provided for http
        message producer keyword arguments
    :return: Returns a message producer instance
    :rtype: `MessageProducer`
    """
    match message_bus:
        case "KAFKA" | "KAFKA3":
            if "bootstrap_servers" not in message_bus_kwargs:
                raise ValueError(
                    "bootstrap_servers must be provided for "
                    "kafka message bus keyword arguments"
                )
            if "topic" not in producer_kwargs:
                raise ValueError(
                    "topic must be provided for "
                    "kafka message producer keyword arguments"
                )
            message_bus_class = (
                AIOKafkaMessageBus
                if message_bus == "KAFKA"
                else Kafka3MessageBus
            )
        case "HTTP":
            if "url" not in producer_kwargs:
                raise ValueError(
                    "url must be provided for "
                    "http message producer keyword arguments"
                )
            message_bus_class = HTTPMessageBus
        case _:
            raise ValueError(
                f"Message bus {message_bus} not recognised"
            )
    async with message_bus_class(
        **message_bus_kwargs
    ) as message_bus_instance:
        yield message_bus_instance.get_message_producer(
            **producer_kwargs
        )
