"""Tests for message buses module
"""
import pytest
import aioresponses

from test_harness.message_buses.message_buses import (
    Kafka3MessageBus, AIOKafkaMessageBus, HTTPMessageBus,
    get_producer_context
)


class TestAIOKafkaMessageBus:
    """Tests for `AIOKafkaMessageBus`
    """
    @staticmethod
    @pytest.mark.asyncio
    async def test_context_manager(
        aio_kafka_producer_mock: list[str]
    ) -> None:
        """Tests `send` for kafka message bus

        :param aio_kafka_producer_mock: Mock kafka producer
        :type aio_kafka_producer_mock: `list`[`str`]
        """
        async with AIOKafkaMessageBus(
            bootstrap_servers="localhost:9092",
        ) as message_bus:
            message = b"message"
            result = await message_bus.send(
                message=message,
                topic="test_topic"
            )
        assert len(aio_kafka_producer_mock) == 3
        assert result == ""
        assert aio_kafka_producer_mock[0] == "start"
        assert aio_kafka_producer_mock[1] == "send"
        assert aio_kafka_producer_mock[2] == "stop"

    @staticmethod
    @pytest.mark.asyncio
    async def test_context_manager_error(
        aio_kafka_producer_mock: list[str]
    ) -> None:
        """Tests `send` for kafka message bus

        :param aio_kafka_producer_mock: Mock kafka producer
        :type aio_kafka_producer_mock: `list`[`str`]
        """
        with pytest.raises(ValueError) as error:
            async with AIOKafkaMessageBus(
                bootstrap_servers="localhost:9092",
            ) as _:
                raise ValueError("An error")
        assert str(error.value) == "An error"
        assert len(aio_kafka_producer_mock) == 2
        assert aio_kafka_producer_mock[0] == "start"
        assert aio_kafka_producer_mock[1] == "stop"


class TestKafka3MessageBus:
    """Tests for `Kafka3MessageBus`
    """
    @staticmethod
    @pytest.mark.asyncio
    async def test_context_manager(
        sync_kafka_producer_mock: list[str]
    ) -> None:
        """Tests `send` for kafka message bus

        :param kafka_producer_mock: Mock kafka producer
        :type kafka_producer_mock: `list`[`str`]
        """
        async with Kafka3MessageBus(
            bootstrap_servers="localhost:9092",
        ) as message_bus:
            message = b"message"
            result = await message_bus.send(
                message=message,
                topic="test_topic"
            )
        assert len(sync_kafka_producer_mock) == 3
        assert result == ""
        assert sync_kafka_producer_mock[0] == "start"
        assert sync_kafka_producer_mock[1] == "send"
        assert sync_kafka_producer_mock[2] == "stop"


class TestHTTPMessageBus:
    """Tests for `HTTPMessageBus`
    """
    @staticmethod
    @pytest.mark.asyncio
    async def test_context_manager_send() -> None:
        """Tests `send` for kafka message bus

        :param http_client_mock: Mock http client
        :type http_client_mock: `list`[`str`]
        """
        with aioresponses.aioresponses() as mock:
            mock.post(
                "http://localhost:8080/topics/test_topic",
                status=200,
                body="test response"
            )
            async with HTTPMessageBus(
            ) as message_bus:
                message = b"message"
                result = await message_bus.send(
                    message=message,
                    url="http://localhost:8080/topics/test_topic"
                )
        text = await result.text()
        assert text == "test response"


class TestMessageProducer:
    """Tests for `MessageProducer`
    """
    @staticmethod
    @pytest.mark.asyncio
    async def test_send_message_aio(
        aio_kafka_producer_mock: list[str]
    ) -> None:
        """Tests `send` for kafka message bus

        :param kafka_producer_mock: Mock kafka producer
        :type kafka_producer_mock: `list`[`str`]
        """
        async with AIOKafkaMessageBus(
            bootstrap_servers="localhost:9092",
        ) as message_bus:
            kafka_message_producer = message_bus.get_message_producer(
                topic="test_topic"
            )
            result = await kafka_message_producer.send_message(
                b"message"
            )
        assert result == ""
        assert aio_kafka_producer_mock[0] == "start"
        assert aio_kafka_producer_mock[1] == "send"
        assert aio_kafka_producer_mock[2] == "stop"

    @staticmethod
    @pytest.mark.asyncio
    async def test_send_message_sync(
        sync_kafka_producer_mock: list[str]
    ) -> None:
        """Tests `send` for kafka message bus

        :param kafka_producer_mock: Mock kafka producer
        :type kafka_producer_mock: `list`[`str`]
        """
        async with Kafka3MessageBus(
            bootstrap_servers="localhost:9092",
        ) as message_bus:
            kafka_message_producer = message_bus.get_message_producer(
                topic="test_topic"
            )
            result = await kafka_message_producer.send_message(
                b"message"
            )
        assert result == ""
        assert sync_kafka_producer_mock[0] == "start"
        assert sync_kafka_producer_mock[1] == "send"
        assert sync_kafka_producer_mock[2] == "stop"

    @staticmethod
    @pytest.mark.asyncio
    async def test_send_message_http() -> None:
        """Tests `send` for http message producer

        :param http_client_mock: Mock http client
        :type http_client_mock: `list`[`str`]
        """
        with aioresponses.aioresponses() as mock:
            mock.post(
                "http://localhost:8080/topics/test_topic",
                status=200,
                body="test response"
            )
            async with HTTPMessageBus(
            ) as message_bus:
                http_message_producer = message_bus.get_message_producer(
                    url="http://localhost:8080/topics/test_topic"
                )
                result = await http_message_producer.send_message(
                    b"message"
                )
        text = await result.text()
        assert text == "test response"


class TestGetProducerContext:
    """Tests for `get_producer_context`
    """
    @staticmethod
    @pytest.mark.asyncio
    async def test_get_producer_context_aio_kafka(
        aio_kafka_producer_mock: list[str]
    ) -> None:
        """Tests `get_producer_context` for kafka message bus

        :param aio_kafka_producer_mock: Mock kafka producer
        :type aio_kafka_producer_mock: `list`[`str`]
        """
        async with get_producer_context(
            message_bus="KAFKA",
            message_bus_kwargs=dict(
                bootstrap_servers="localhost:9092"
            ),
            producer_kwargs=dict(
                topic="test_topic"
            )
        ) as producer:
            result = await producer.send_message(
                b"message"
            )
        assert result == ""
        assert aio_kafka_producer_mock[0] == "start"
        assert aio_kafka_producer_mock[1] == "send"
        assert aio_kafka_producer_mock[2] == "stop"

    @staticmethod
    @pytest.mark.asyncio
    async def test_get_producer_context_kafka3(
        sync_kafka_producer_mock: list[str]
    ) -> None:
        """Tests `get_producer_context` for kafka message bus

        :param sync_kafka_producer_mock: Mock kafka producer
        :type sync_kafka_producer_mock: `list`[`str`]
        """
        async with get_producer_context(
            message_bus="KAFKA3",
            message_bus_kwargs=dict(
                bootstrap_servers="localhost:9092"
            ),
            producer_kwargs=dict(
                topic="test_topic"
            )
        ) as producer:
            result = await producer.send_message(
                b"message"
            )
        assert result == ""
        assert sync_kafka_producer_mock[0] == "start"
        assert sync_kafka_producer_mock[1] == "send"
        assert sync_kafka_producer_mock[2] == "stop"

    @staticmethod
    @pytest.mark.asyncio
    async def test_get_producer_context_http() -> None:
        """Tests `get_producer_context` for http message bus

        :param http_client_mock: Mock http client
        :type http_client_mock: `list`[`str`]
        """
        with aioresponses.aioresponses() as mock:
            mock.post(
                "http://localhost:8080/topics/test_topic",
                status=200,
                body="test response"
            )
            async with get_producer_context(
                message_bus="HTTP",
                message_bus_kwargs=dict(),
                producer_kwargs=dict(
                    url="http://localhost:8080/topics/test_topic"
                )
            ) as producer:
                result = await producer.send_message(
                    b"message"
                )
        text = await result.text()
        assert text == "test response"
