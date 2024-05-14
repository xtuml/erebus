"""Tests for the test_harness.protocol_verifier.send_events module.
"""
import json
import aiohttp
import re
from datetime import datetime
import asyncio

import pytest
import aioresponses
import aiokafka
import kafka3
from kafka3.future import Future
from aiokafka.errors import KafkaTimeoutError as AIOKafkaTimeoutError
from kafka3.errors import KafkaTimeoutError as KafkaTimeoutError3

from test_harness.utils import check_dict_equivalency
from test_harness.config.config import HarnessConfig
from test_harness.message_buses.message_buses import (
    get_producer_context
)
from test_harness.protocol_verifier.send_events import (
    PVInputConverter,
    PVResponseConverter,
    PVMessageResponseConverter,
    PVMessageExceptionHandler,
    PVMessageSender,
    get_message_bus_kwargs,
    get_producer_kwargs
)

uuid4hex = re.compile(
            '[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}\\Z', re.I
        )


class TestPVInputConverter:
    """Tests for `PVInputConverter`
    """
    @staticmethod
    def test_convert_kafka(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests `convert_list_dict_to_json_io_bytes`

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        test_config = HarnessConfig()
        test_config.send_json_without_length_prefix = False

        data_converter = PVInputConverter(
            message_bus="KAFKA",
            harness_config=test_config
        )
        job_id = "job_id"
        job_info = {"job_info": "job_info"}
        io_bytes_list, _, _, _, response_kwargs = data_converter.convert(
            list_dict=job_list,
            job_id=job_id,
            job_info=job_info
        )
        assert len(io_bytes_list) == len(job_list)
        for io_bytes, event_expected in zip(io_bytes_list, job_list):
            assert isinstance(io_bytes, bytes)
            bytes_array = io_bytes
            msg_length = int.from_bytes(bytes_array[:4], "big")
            json_bytes = bytes_array[4:]
            event_actual = json.loads(json_bytes.decode("utf-8"))
            check_dict_equivalency(event_actual, event_expected)
            assert msg_length == len(json_bytes)
        assert response_kwargs["job_id"] == job_id
        assert response_kwargs["job_info"] == job_info

    @staticmethod
    def test_convert_kafka_no_length(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests `convert_list_dict_to_json_io_bytes`

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """

        test_config = HarnessConfig()
        test_config.send_json_without_length_prefix = True

        data_converter = PVInputConverter(
            message_bus="KAFKA",
            harness_config=test_config
        )
        job_id = "job_id"
        job_info = {"job_info": "job_info"}
        io_bytes_list, _, _, _, response_kwargs = data_converter.convert(
            list_dict=job_list,
            job_id=job_id,
            job_info=job_info
        )
        assert len(io_bytes_list) == len(job_list)
        for io_bytes, event_expected in zip(io_bytes_list, job_list):
            assert isinstance(io_bytes, bytes)
            bytes_array = io_bytes
            try:
                json_bytes = bytes_array[4:]
                event_actual = json.loads(json_bytes.decode("utf-8"))
                AssertionError(
                    "json should not be parseable without first 4 bytes"
                )
            except ValueError:
                pass
            event_actual = json.loads(bytes_array.decode("utf-8"))
            check_dict_equivalency(event_actual, event_expected)

        assert response_kwargs["job_id"] == job_id
        assert response_kwargs["job_info"] == job_info

    @staticmethod
    def test_convert_http(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests `convert_list_dict_to_pv_json_io_bytes` with
        `send_as_pv_bytes` set to `False`

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        data_converter = PVInputConverter(
            message_bus="HTTP",
            harness_config=HarnessConfig()
        )
        job_id = "job_id"
        job_info = {"job_info": "job_info"}
        form_data_list, _, _, _, response_kwargs = data_converter.convert(
            list_dict=job_list,
            job_id=job_id,
            job_info=job_info
        )
        assert len(form_data_list) == 1
        form_data = form_data_list[0]
        assert isinstance(form_data, aiohttp.MultipartWriter)
        # get the payload within the multipart writer
        payload = form_data._parts[0][0]
        payload_dict = json.loads(payload._value.getvalue())
        for expected_event, actual_event in zip(job_list, payload_dict):
            check_dict_equivalency(actual_event, expected_event)
        assert response_kwargs["job_id"] == job_id
        assert response_kwargs["job_info"] == job_info


class TestPVResponseConverter:
    """Tests for `PVResponseConverter`
    """
    @staticmethod
    def test_convert(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests `convert`
        """
        response_converter = PVResponseConverter()
        job_id = "job_id"
        job_info = {"job_info": "job_info"}
        responses = [
            "",
            "Bad"
        ]
        (
            list_dict,
            file_name,
            out_job_id,
            out_job_info,
            result,
            time_completed
        ) = response_converter.convert(
            responses=responses,
            list_dict=job_list,
            job_id=job_id,
            job_info=job_info
        )
        assert list_dict == job_list
        assert bool(uuid4hex.match(
            file_name.replace("-", "").replace(".json", "")
        ))
        assert out_job_id == job_id
        assert out_job_info == job_info
        assert result == "Bad"
        assert isinstance(time_completed, datetime)


class MockClientResponse:
    """Mock aiohttp.ClientResponse
    """
    def __init__(
        self,
        status: int,
        reason: str | None = None,
    ) -> None:
        """Constructor method
        """
        self.status = status
        self.reason = reason

    @property
    def ok(self) -> bool:
        """Returns `True` if status is less than 400, `False` otherwise

        :return: `True` if status is less than 400, `False` otherwise
        :rtype: `bool`
        """
        return 400 > self.status


class TestPVMessageResponseConverter:
    """Tests for `PVMessageResponseConverter`
    """
    @staticmethod
    def test_convert_kafka(
    ) -> None:
        """Tests `convert` for kafka message bus
        """
        response_converter = PVMessageResponseConverter(
            message_bus="KAFKA"
        )
        response = "response"
        result = response_converter.convert(
            response=response
        )
        assert result == ""

    @staticmethod
    def test_convert_http_ok(
    ) -> None:
        """Tests `convert` for http message bus
        """
        response_converter = PVMessageResponseConverter(
            message_bus="HTTP"
        )
        response = MockClientResponse(
            status=200,
            reason="OK"
        )

        result = response_converter.convert(
            response=response
        )
        assert result == ""

    @staticmethod
    def test_convert_http_not_ok(
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Tests `convert` for http message bus

        :param caplog: Pytest fixture
        :type caplog: `pytest.LogCaptureFixture`
        """
        response_converter = PVMessageResponseConverter(
            message_bus="HTTP"
        )
        response = MockClientResponse(
            status=400,
            reason="Bad Request"
        )

        result = response_converter.convert(
            response=response
        )
        assert result == "Bad Request"
        assert (
            "Error sending http payload: Bad Request"
            in caplog.text
        )


class TestPVMessageExceptionHandler:
    """Tests for `PVMessageExceptionHandler`
    """
    @staticmethod
    def test_handle_exception_kafka(
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Tests `handle_exception`

        :param caplog: Pytest fixture
        :type caplog: `pytest.LogCaptureFixture`
        """
        exception_handler = PVMessageExceptionHandler(
            message_bus="KAFKA"
        )
        for exception_class, error_message in [
            (KafkaTimeoutError3, "exception_1"),
            (AIOKafkaTimeoutError, "exception_2")
        ]:
            exception = exception_class(error_message)
            result = exception_handler.handle_exception(
                exception=exception
            )
            assert result == str(exception)
            assert (
                f"Error sending payload to kafka: {exception}"
                in caplog.text
            )

    @staticmethod
    def test_handle_exception_kafka_unhandled(
    ) -> None:
        """Tests `handle_exception` for unhandled kafka exception
        """
        with pytest.raises(ValueError):
            handler = PVMessageExceptionHandler(
                message_bus="KAFKA"
            )
            handler.handle_exception(ValueError("An error"))

    @staticmethod
    def test_handle_exception_http(
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Tests `handle_exception` for http

        :param caplog: Pytest fixture
        :type caplog: `pytest.LogCaptureFixture`
        """
        exception_handler = PVMessageExceptionHandler(
            message_bus="HTTP"
        )
        for exception_class, error_message, expected_result in [
            (asyncio.TimeoutError, "exception_1", "timed out"),
            (aiohttp.ClientConnectionError, "exception_2", "Connection Error")
        ]:
            exception = exception_class(error_message)
            result = exception_handler.handle_exception(
                exception=exception
            )
            assert result == expected_result
            assert (
                f"Error sending http payload: {exception}"
                in caplog.text
            )
        with pytest.raises(ValueError):
            exception_handler.handle_exception(ValueError("An error"))


class TestPVMessageSender:
    """Tests for `PVMessageSender`
    """
    @staticmethod
    @pytest.mark.asyncio
    async def test_send_aio_kafka(
        job_list: list[dict[str, str | list[str]]],
        kafka_producer_mock: list[str]
    ) -> None:
        """Tests `send` for aiokafka

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        :param kafka_producer_mock: Mock kafka producer
        :type kafka_producer_mock: `list`[`str`]
        """
        message_bus_kwargs = dict(
            bootstrap_servers="localhost:9092",
        )
        producer_kwargs = dict(
            topic="test_topic",
            response_converter=PVMessageResponseConverter(
                message_bus="KAFKA"
            ),
            exception_converter=PVMessageExceptionHandler(
                message_bus="KAFKA"
            )
        )
        async with get_producer_context(
            message_bus="KAFKA",
            message_bus_kwargs=message_bus_kwargs,
            producer_kwargs=producer_kwargs
        ) as producer:
            sender = PVMessageSender(
                message_producer=producer,
                message_bus="KAFKA",
                harness_config=HarnessConfig()
            )
            job_id = "job_id"
            job_info = {"job_info": "job_info"}
            results = await sender.send(
                list_dict=job_list,
                job_id=job_id,
                job_info=job_info
            )
        assert results[0] == job_list
        assert bool(uuid4hex.match(
            results[1].replace("-", "").replace(".json", "")
        ))
        assert results[2] == job_id
        assert results[3] == job_info
        assert results[4] == ""
        assert isinstance(results[5], datetime)
        assert kafka_producer_mock[0] == "start"
        assert kafka_producer_mock[-1] == "stop"
        assert all(
            action == "send"
            for action in kafka_producer_mock[1:-1]
        )

    @staticmethod
    @pytest.mark.asyncio
    async def test_send_aio_kafka_timeout_error(
        job_list: list[dict[str, str | list[str]]],
        kafka_producer_mock: list[str],
        monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tests `send` for aiokafka with timeout error

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        :param kafka_producer_mock: Mock kafka producer
        :type kafka_producer_mock: `list`[`str`]
        :param monkeypatch: Pytest fixture
        :type monkeypatch: `pytest.MonkeyPatch`
        """
        timeout_error = AIOKafkaTimeoutError("timeout")

        async def mock_send_wait(*args, **kwargs):
            kafka_producer_mock.append("send")
            raise timeout_error

        monkeypatch.setattr(
            aiokafka.AIOKafkaProducer, "send_and_wait", mock_send_wait
        )
        message_bus_kwargs = dict(
            bootstrap_servers="localhost:9092",
        )
        producer_kwargs = dict(
            topic="test_topic",
            response_converter=PVMessageResponseConverter(
                message_bus="KAFKA"
            ),
            exception_converter=PVMessageExceptionHandler(
                message_bus="KAFKA"
            )
        )
        async with get_producer_context(
            message_bus="KAFKA",
            message_bus_kwargs=message_bus_kwargs,
            producer_kwargs=producer_kwargs
        ) as producer:
            sender = PVMessageSender(
                message_producer=producer,
                message_bus="KAFKA",
                harness_config=HarnessConfig(),
            )
            job_id = "job_id"
            job_info = {"job_info": "job_info"}
            results = await sender.send(
                list_dict=job_list,
                job_id=job_id,
                job_info=job_info
            )
        assert results[0] == job_list
        assert bool(uuid4hex.match(
            results[1].replace("-", "").replace(".json", "")
        ))
        assert results[2] == job_id
        assert results[3] == job_info
        assert results[4] == str(timeout_error) * len(job_list)
        assert isinstance(results[5], datetime)
        assert kafka_producer_mock[0] == "start"
        assert kafka_producer_mock[-1] == "stop"
        assert all(
            action == "send"
            for action in kafka_producer_mock[1:-1]
        )

    @staticmethod
    @pytest.mark.asyncio
    async def test_send_sync_kafka(
        job_list: list[dict[str, str | list[str]]],
        sync_kafka_producer_mock: list[str]
    ) -> None:
        """Tests `send` for kafka3

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        :param sync_kafka_producer_mock: Mock kafka producer
        :type sync_kafka_producer_mock: `list`[`str`]
        """
        message_bus_kwargs = dict(
            bootstrap_servers="localhost:9092",
        )
        producer_kwargs = dict(
            topic="test_topic",
            response_converter=PVMessageResponseConverter(
                message_bus="KAFKA3"
            ),
            exception_converter=PVMessageExceptionHandler(
                message_bus="KAFKA3"
            )
        )
        async with get_producer_context(
            message_bus="KAFKA3",
            message_bus_kwargs=message_bus_kwargs,
            producer_kwargs=producer_kwargs
        ) as producer:
            sender = PVMessageSender(
                message_producer=producer,
                message_bus="KAFKA3",
                harness_config=HarnessConfig(),
            )
            job_id = "job_id"
            job_info = {"job_info": "job_info"}
            results = await sender.send(
                list_dict=job_list,
                job_id=job_id,
                job_info=job_info
            )
        assert results[0] == job_list
        assert bool(uuid4hex.match(
            results[1].replace("-", "").replace(".json", "")
        ))
        assert results[2] == job_id
        assert results[3] == job_info
        assert results[4] == ""
        assert isinstance(results[5], datetime)
        assert sync_kafka_producer_mock[0] == "start"
        assert sync_kafka_producer_mock[-1] == "stop"
        assert all(
            action == "send"
            for action in sync_kafka_producer_mock[1:-1]
        )

    @staticmethod
    @pytest.mark.asyncio
    async def test_send_sync_kafka_error(
        job_list: list[dict[str, str | list[str]]],
        sync_kafka_producer_mock: list[str],
        monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tests `send` for kafka3 with timeout error

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        :param sync_kafka_producer_mock: Mock kafka producer
        :type sync_kafka_producer_mock: `list`[`str`]
        :param monkeypatch: Pytest fixture
        :type monkeypatch: `pytest.MonkeyPatch`
        """
        timeout_error = KafkaTimeoutError3("timeout")
        errors = []

        def _err_callback(err):
            errors.append(str(err))

        def mock_send(*args, **kwargs):
            sync_kafka_producer_mock.append("send")
            future = Future()
            future.failure(timeout_error)
            return future

        monkeypatch.setattr(
            kafka3.KafkaProducer, "send", mock_send
        )
        message_bus_kwargs = dict(
            bootstrap_servers="localhost:9092",
            error_callback=_err_callback
        )
        producer_kwargs = dict(
            topic="test_topic",
            response_converter=PVMessageResponseConverter(
                message_bus="KAFKA3"
            ),
            exception_converter=PVMessageExceptionHandler(
                message_bus="KAFKA3"
            )
        )
        async with get_producer_context(
            message_bus="KAFKA3",
            message_bus_kwargs=message_bus_kwargs,
            producer_kwargs=producer_kwargs
        ) as producer:
            sender = PVMessageSender(
                message_producer=producer,
                message_bus="KAFKA3",
                harness_config=HarnessConfig(),
            )
            job_id = "job_id"
            job_info = {"job_info": "job_info"}
            results = await sender.send(
                list_dict=job_list,
                job_id=job_id,
                job_info=job_info
            )
        assert results[0] == job_list
        assert bool(uuid4hex.match(
            results[1].replace("-", "").replace(".json", "")
        ))
        assert results[2] == job_id
        assert results[3] == job_info
        assert not results[4] == str(timeout_error) * len(job_list)
        assert len(errors) == len(job_list)
        assert all(
            error == str(timeout_error)
            for error in errors
        )
        assert isinstance(results[5], datetime)
        assert sync_kafka_producer_mock[0] == "start"
        assert sync_kafka_producer_mock[-1] == "stop"
        assert all(
            action == "send"
            for action in sync_kafka_producer_mock[1:-1]
        )

    @staticmethod
    @pytest.mark.asyncio
    async def test_send_http(
        job_list: list[dict[str, str | list[str]]],
    ) -> None:
        """Tests `send` for http

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        message_bus_kwargs = dict()
        producer_kwargs = dict(
            url="http://localhost:8080/sendevents",
            response_converter=PVMessageResponseConverter(
                message_bus="HTTP"
            ),
            exception_converter=PVMessageExceptionHandler(
                message_bus="HTTP"
            )
        )
        with aioresponses.aioresponses() as mock:
            mock.post(
                "http://localhost:8080/sendevents",
                status=200,
                body="test response"
            )
            async with get_producer_context(
                message_bus="HTTP",
                message_bus_kwargs=message_bus_kwargs,
                producer_kwargs=producer_kwargs
            ) as producer:
                sender = PVMessageSender(
                    message_producer=producer,
                    message_bus="HTTP",
                    harness_config=HarnessConfig(),
                )
                job_id = "job_id"
                job_info = {"job_info": "job_info"}
                results = await sender.send(
                    list_dict=job_list,
                    job_id=job_id,
                    job_info=job_info
                )
        assert results[0] == job_list
        assert bool(uuid4hex.match(
            results[1].replace("-", "").replace(".json", "")
        ))
        assert results[2] == job_id
        assert results[3] == job_info
        assert results[4] == ""
        assert isinstance(results[5], datetime)

    @staticmethod
    @pytest.mark.asyncio
    async def test_send_http_timeout_error(
        job_list: list[dict[str, str | list[str]]],
    ) -> None:
        """Tests `send` for http

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        message_bus_kwargs = dict()
        producer_kwargs = dict(
            url="http://localhost:8080/sendevents",
            response_converter=PVMessageResponseConverter(
                message_bus="HTTP"
            ),
            exception_converter=PVMessageExceptionHandler(
                message_bus="HTTP"
            )
        )
        with aioresponses.aioresponses() as mock:
            mock.post(
                "http://localhost:8080/sendevents",
                exception=asyncio.TimeoutError()
            )
            async with get_producer_context(
                message_bus="HTTP",
                message_bus_kwargs=message_bus_kwargs,
                producer_kwargs=producer_kwargs
            ) as producer:
                sender = PVMessageSender(
                    message_producer=producer,
                    message_bus="HTTP",
                    harness_config=HarnessConfig(),
                )
                job_id = "job_id"
                job_info = {"job_info": "job_info"}
                results = await sender.send(
                    list_dict=job_list,
                    job_id=job_id,
                    job_info=job_info
                )
        assert results[0] == job_list
        assert bool(uuid4hex.match(
            results[1].replace("-", "").replace(".json", "")
        ))
        assert results[2] == job_id
        assert results[3] == job_info
        assert results[4] == "timed out"
        assert isinstance(results[5], datetime)

    @staticmethod
    @pytest.mark.asyncio
    async def test_send_http_connection_error(
        job_list: list[dict[str, str | list[str]]],
    ) -> None:
        """Tests `send` for http

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        message_bus_kwargs = dict()
        producer_kwargs = dict(
            url="http://localhost:8080/sendevents",
            response_converter=PVMessageResponseConverter(
                message_bus="HTTP"
            ),
            exception_converter=PVMessageExceptionHandler(
                message_bus="HTTP"
            )
        )
        with aioresponses.aioresponses() as mock:
            mock.post(
                "http://localhost:8080/sendevents",
                exception=aiohttp.ClientConnectionError()
            )
            async with get_producer_context(
                message_bus="HTTP",
                message_bus_kwargs=message_bus_kwargs,
                producer_kwargs=producer_kwargs
            ) as producer:
                sender = PVMessageSender(
                    message_producer=producer,
                    message_bus="HTTP",
                    harness_config=HarnessConfig(),
                )
                job_id = "job_id"
                job_info = {"job_info": "job_info"}
                results = await sender.send(
                    list_dict=job_list,
                    job_id=job_id,
                    job_info=job_info
                )
        assert results[0] == job_list
        assert bool(uuid4hex.match(
            results[1].replace("-", "").replace(".json", "")
        ))
        assert results[2] == job_id
        assert results[3] == job_info
        assert results[4] == "Connection Error"
        assert isinstance(results[5], datetime)


def test_get_message_bus_kwargs() -> None:
    """Tests `get_message_bus_kwargs`
    """
    harness_config = HarnessConfig()
    harness_config.message_bus_protocol = "KAFKA"
    harness_config.kafka_message_bus_host = "localhost:9092"
    message_bus_kwargs = get_message_bus_kwargs(harness_config)
    check_dict_equivalency(dict(
        bootstrap_servers="localhost:9092"
    ), message_bus_kwargs)

    harness_config.message_bus_protocol = "KAFKA3"
    message_bus_kwargs = get_message_bus_kwargs(harness_config)
    check_dict_equivalency(dict(
        bootstrap_servers="localhost:9092"
    ), message_bus_kwargs)

    harness_config.message_bus_protocol = "HTTP"
    message_bus_kwargs = get_message_bus_kwargs(harness_config)
    assert len(message_bus_kwargs) == 0


def test_get_producer_kwargs():
    """Tests `get_producer_kwargs`
    """
    harness_config = HarnessConfig()
    harness_config.kafka_message_bus_topic = "test_topic"
    harness_config.pv_send_url = "http://localhost:8080/sendevents"
    for details in [
        dict(
            message_bus="KAFKA",
            location=["topic", "test_topic"],
            response_conv=(
                PVMessageResponseConverter._kafka_conversion_function
            ),
            exception_conv=PVMessageExceptionHandler._kafka_exception_handler
        ),
        dict(
            message_bus="KAFKA3",
            location=["topic", "test_topic"],
            response_conv=(
                PVMessageResponseConverter._kafka_conversion_function
            ),
            exception_conv=PVMessageExceptionHandler._kafka_exception_handler
        ),
        dict(
            message_bus="HTTP",
            location=["url", "http://localhost:8080/sendevents"],
            response_conv=(
                PVMessageResponseConverter._http_conversion_function
            ),
            exception_conv=PVMessageExceptionHandler._http_exception_handler
        ),
    ]:
        harness_config.message_bus_protocol = details["message_bus"]
        producer_kwargs = get_producer_kwargs(harness_config)
        assert all(
            key in producer_kwargs
            for key in [
                details["location"][0],
                "response_converter",
                "exception_converter"
            ]
        )
        assert producer_kwargs[details["location"][0]] == (
            details["location"][1]
        )
        assert isinstance(
            producer_kwargs["response_converter"],
            PVMessageResponseConverter
        )
        assert isinstance(
            producer_kwargs["exception_converter"],
            PVMessageExceptionHandler
        )
        assert (
            producer_kwargs["response_converter"].data_conversion_function
        ) == (
            details["response_conv"]
        )
        assert producer_kwargs["exception_converter"].exception_handler == (
            details["exception_conv"]
        )
