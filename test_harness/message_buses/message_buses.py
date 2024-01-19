"""Module for holding the message bus classes.
"""
from typing import Any, Self
from abc import ABC, abstractmethod, abstractproperty
import asyncio

from aiokafka import AIOKafkaProducer
from kafka import KafkaProducer
import aiohttp

from test_harness.utils import wrap_kafka_future


class InputConverter(ABC):
    """Abstract class for message converter.
    """

    @abstractmethod
    def convert_input(
        self,
        message: Any,
        *args,
        **kwargs
    ) -> tuple[Any, tuple, dict, tuple, dict]:
        """Abstract method to convert a message.
        """
        pass


class SimpleInputConverter(InputConverter):
    """Simple message converter.
    """
    def convert_input(
        self,
        message: Any
    ) -> tuple[Any, tuple, dict, tuple, dict]:
        """Convert a message.
        """
        return message, (), {}, (), {}


class ResponseConverter(ABC):
    """Abstract class for response converter.
    """

    @abstractmethod
    def convert_response(self, response: Any, *args, **kwargs) -> Any:
        """Abstract method to convert a response.
        """
        pass


class SimpleResponseConverter(ResponseConverter):
    """Simple response converter.
    """
    def convert_response(self, response: Any) -> Any:
        """Convert a response.
        """
        return response


class MessageProducer(ABC):
    """Abstract class for message sender.
    """
    def __init__(
        self,
        message_bus: "MessageBusSendingController",
    ) -> None:
        """Constructor method
        """
        self.message_bus = message_bus

    async def send_message(self, message: Any, *args, **kwargs) -> None:
        """Abstract method to send a message.
        """
        return await self._send(message, *args, **kwargs)

    @abstractmethod
    async def _send(self, message: Any, *args, **kwargs) -> Any:
        """Abstract method to send a message.
        """
        pass


class MessageBusSendingController(ABC):
    """Abstract class for message bus sending controller.
    """
    def __init__(
        self,
    ) -> None:
        """Constructor method
        """

    @abstractmethod
    async def __aenter__(self) -> Self:
        """Abstract method to enter the context.
        """
        return self

    @abstractmethod
    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Abstract method to exit the context.
        """
        pass

    @abstractmethod
    def get_message_producer(
        self,
        *args,
        **kwargs,
    ) -> "MessageProducer":
        """Abstract method to get a message producer.
        """
        pass

    @abstractmethod
    async def send(self, message: Any, *args, **kwargs) -> None:
        """Abstract method to send a message.
        """
        pass


class KafkaMessageProducer(MessageProducer):
    """AIOKafka message producer.
    """
    def __init__(
        self,
        topic: str,
        message_bus: "KafkaMessageBus",
    ) -> None:
        """Constructor method
        """
        self.topic = topic
        super().__init__(
            message_bus=message_bus,
        )

    async def _send(self, message: bytes) -> bytes:
        """Send a converted message.
        """
        return await self.message_bus.send(
            message=message,
            topic=self.topic,
        )


class KafkaMessageBus(MessageBusSendingController):
    """AIOKafka message bus.
    """
    def __init__(
        self,
        bootstrap_servers: str,
        stop_timeout: int = 10,
    ) -> None:
        """Constructor method
        """
        self.stop_timeout = stop_timeout
        self._bootstrap_servers = bootstrap_servers
        super().__init__()

    @abstractproperty
    def producer(self) -> Any:
        """Abstract property to get a producer.
        """
        pass

    @abstractmethod
    def _set_producer(self) -> Any:
        """Abstract method to get a producer.
        """
        pass

    def get_message_producer(
        self,
        topic: str,
    ) -> "MessageProducer":
        """Get a message producer.
        """
        return KafkaMessageProducer(
            topic=topic,
            message_bus=self,
        )

    async def send(self, message: bytes, topic: str) -> bytes:
        """Send a message to a topic.
        """
        return await self._send_to_topic(data=message, topic=topic)

    @abstractmethod
    async def _send_to_topic(self, data: bytes, topic: str) -> bytes:
        """Abstract method to send a message to a topic.
        """
        pass


class AIOKafkaMessageBus(KafkaMessageBus):
    """AIOKafka message bus.
    """
    def __init__(
        self,
        bootstrap_servers: str,
        stop_timeout: int = 10,
    ) -> None:
        """Constructor method
        """
        self.stop_timeout = stop_timeout
        super().__init__(
            bootstrap_servers=bootstrap_servers,
        )

    @property
    def producer(self) -> AIOKafkaProducer:
        """Property to get a producer.
        """
        if not hasattr(self, "_producer"):
            self._set_producer()
        return self._producer

    def _set_producer(self) -> Any:
        """Get a producer.
        """
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
        )

    async def __aenter__(self) -> Self:
        """Enter the context.
        """
        await self.producer.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Exit the context.
        """
        await asyncio.wait_for(self.producer.stop())

    async def _send_to_topic(self, message: bytes, topic: str) -> bytes:
        """Send a message to a topic.
        """
        return await self.producer.send_and_wait(
            topic=topic, value=message
        )


class Kafka3MessageBus(KafkaMessageBus):
    """Kafka3 message bus.
    """
    def __init__(
        self,
        bootstrap_servers: str,
        stop_timeout: int = 10,
    ) -> None:
        """Constructor method
        """
        self.stop_timeout = stop_timeout
        super().__init__(
            bootstrap_servers=bootstrap_servers,
        )

    @property
    def producer(self) -> KafkaProducer:
        """Property to get a producer.
        """
        if not hasattr(self, "_producer"):
            self._set_producer()
        return self._producer

    def _set_producer(self) -> KafkaProducer:
        """Get a producer.
        """
        self._producer = KafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
        )

    async def __aenter__(self) -> Self:
        """Enter the context.
        """
        self._set_producer()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Exit the context.
        """
        self.producer.close(timeout=self.stop_timeout)

    async def _send_to_topic(self, data: bytes, topic: str) -> bytes:
        """Send a message to a topic.
        """
        return await wrap_kafka_future(
            self.producer.send(topic=topic, value=data)
        )


class HTTPMessageProducer(MessageProducer):
    """HTTP message producer.
    """
    def __init__(
        self,
        url: str,
        message_bus: "HTTPMessageBus",
    ) -> None:
        """Constructor method
        """
        self.url = url
        super().__init__(
            message_bus=message_bus,
        )

    async def _send(self, message: Any, **kwargs) -> Any:
        """Send a converted message.
        """
        return await self.message_bus.send(
            message=message,
            url=self.url,
            **kwargs
        )


class HTTPMessageBus(MessageBusSendingController):
    """HTTP message bus.
    """
    def __init__(
        self,
        max_connections: int = 2000,
    ) -> None:
        """Constructor method
        """
        self.max_connections = max_connections
        super().__init__()

    @property
    def session(self) -> aiohttp.ClientSession:
        """Property to get a session.
        """
        if not hasattr(self, "_session"):
            self._set_session()
        return self._session

    def _set_session(self) -> None:
        """Get a session.
        """
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                limit=self.max_connections,
            ),
        )

    def get_message_producer(
        self,
        url: str,
    ) -> "MessageProducer":
        """Get a message producer.
        """
        return HTTPMessageProducer(
            url=url,
            message_bus=self,
        )

    async def send(self, message: Any, url: str, **kwargs) -> bytes:
        """Send a message to a url.
        """
        return await self._send_post_to_url(message, url, **kwargs)

    async def _send_post_to_url(
        self, message: Any, url: str, **kwargs
    ) -> bytes:
        """Abstract method to send a message to a url.
        """
        async with self.session.post(
            url=url, data=message, **kwargs
        ) as response:
            return await response.read()

    async def __aenter__(self) -> Self:
        """Enter the context.
        """
        await self.session.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Exit the context.
        """
        await self.session.__aexit__(exc_type, exc, tb)


class MessageSender(ABC):
    def __init__(
        self,
        producer: MessageProducer,
        input_converter: InputConverter | None = None,
        response_converter: ResponseConverter | None = None
    ) -> None:
        self._producer = producer
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

    async def send(self, message: Any, *args, **kwargs) -> Any:
        (
            convert_data,
            convert_args,
            convert_kwargs,
            response_args,
            response_kwargs
        ) = self._input_converter.convert_input(message, *args, **kwargs)
        response = await self._sender(
            convert_data, *convert_args, **convert_kwargs
        )
        return self._response_converter.convert_response(
            response=response,
            *response_args,
            **response_kwargs
        )

    @abstractmethod
    async def _sender(self, converted_data: Any, *args, **kwargs) -> Any:
        pass
