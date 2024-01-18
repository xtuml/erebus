"""Module for holding the message bus classes.
"""
from typing import Any, Self
from abc import ABC, abstractmethod, abstractproperty
import asyncio

from aiokafka import AIOKafkaProducer
from kafka import KafkaProducer
import aiohttp

from test_harness.utils import wrap_kafka_future


class MessageConverter(ABC):
    """Abstract class for message converter.
    """

    @abstractmethod
    def convert_message(self, message_data: Any) -> Any:
        """Abstract method to convert a message.
        """
        pass


class SimpleMessageConverter(MessageConverter):
    """Simple message converter.
    """
    def convert_message(self, message_data: Any) -> Any:
        """Convert a message.
        """
        return message_data


class ResponseConverter(ABC):
    """Abstract class for response converter.
    """

    @abstractmethod
    def convert_response(self, response_data: Any) -> Any:
        """Abstract method to convert a response.
        """
        pass


class SimpleResponseConverter(ResponseConverter):
    """Simple response converter.
    """
    def convert_response(self, response_data: Any) -> Any:
        """Convert a response.
        """
        return response_data


class MessageProducer(ABC):
    """Abstract class for message sender.
    """
    def __init__(
        self,
        message_bus: "MessageBusSendingController",
        message_converter: MessageConverter | None = None,
        response_converter: ResponseConverter | None = None
    ) -> None:
        """Constructor method
        """
        self.message_bus = message_bus
        self._message_converter = (
            message_converter
            if message_converter is not None
            else SimpleMessageConverter()
        )
        self._response_converter = (
            response_converter
            if response_converter is not None
            else SimpleResponseConverter()
        )

    async def send_message(self, message: Any) -> None:
        """Abstract method to send a message.
        """
        converted_message = self._message_converter.convert_message(message)
        raw_response = await self._send(converted_message)
        converted_response = self._response_converter.convert_response(
            raw_response
        )
        return converted_response

    @abstractmethod
    async def _send(self, converted_message: Any) -> Any:
        """Abstract method to send a converted message.
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
        message_converter: MessageConverter | None = None,
        response_converter: ResponseConverter | None = None,
        **kwargs,
    ) -> "MessageProducer":
        """Abstract method to get a message producer.
        """
        pass

    @abstractmethod
    async def send(self, data: Any, *args, **kwargs) -> None:
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
        message_converter: MessageConverter | None = None,
        response_converter: ResponseConverter | None = None,
    ) -> None:
        """Constructor method
        """
        self.topic = topic
        super().__init__(
            message_bus=message_bus,
            message_converter=message_converter,
            response_converter=response_converter,
        )

    async def _send(self, converted_message: bytes) -> bytes:
        """Send a converted message.
        """
        return await self.message_bus.send(
            data=converted_message,
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
        *,
        message_converter: MessageConverter | None = None,
        response_converter: ResponseConverter | None = None,
    ) -> "MessageProducer":
        """Get a message producer.
        """
        return KafkaMessageProducer(
            topic=topic,
            message_bus=self,
            message_converter=message_converter,
            response_converter=response_converter,
        )

    async def send(self, data: bytes, topic: str) -> bytes:
        """Send a message to a topic.
        """
        return await self._send_to_topic(data=data, topic=topic)

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

    async def _send_to_topic(self, data: bytes, topic: str) -> bytes:
        """Send a message to a topic.
        """
        await self.producer.send_and_wait(topic=topic, value=data)
        return data


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
        message_converter: MessageConverter | None = None,
        response_converter: ResponseConverter | None = None,
    ) -> None:
        """Constructor method
        """
        self.url = url
        super().__init__(
            message_bus=message_bus,
            message_converter=message_converter,
            response_converter=response_converter,
        )

    async def _send(self, converted_message: bytes) -> bytes:
        """Send a converted message.
        """
        return await self.message_bus.send(
            data=converted_message,
            url=self.url,
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
        *,
        message_converter: MessageConverter | None = None,
        response_converter: ResponseConverter | None = None,
    ) -> "MessageProducer":
        """Get a message producer.
        """
        return HTTPMessageProducer(
            url=url,
            message_bus=self,
            message_converter=message_converter,
            response_converter=response_converter,
        )

    async def send(self, data: bytes, url: str) -> bytes:
        """Send a message to a url.
        """
        return await self._send_post_to_url(data=data, url=url)

    async def _send_post_to_url(self, data: bytes, url: str) -> bytes:
        """Abstract method to send a message to a url.
        """
        async with self.session.post(url=url, data=data) as response:
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
