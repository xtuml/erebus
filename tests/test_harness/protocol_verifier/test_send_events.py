"""Tests for the test_harness.protocol_verifier.send_events module.
"""
import json
import aiohttp
import re
from datetime import datetime
import asyncio

import pytest
from aiokafka.errors import KafkaTimeoutError as AIOKafkaTimeoutError
from kafka3.errors import KafkaTimeoutError as KafkaTimeoutError3

from test_harness.utils import check_dict_equivalency
from test_harness.protocol_verifier.send_events import (
    PVInputConverter,
    PVResponseConverter,
    PVMessageResponseConverter,
    PVMessageExceptionHandler
)

uuid4hex = re.compile(
            '[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}\\Z', re.I
        )


class TestPVInputConverter:
    @staticmethod
    def test_convert_kafka(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests `convert_list_dict_to_json_io_bytes`

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        data_converter = PVInputConverter(
            message_bus="kafka"
        )
        io_bytes_list, _, _, _, _ = data_converter.convert(
            message=job_list
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
            message_bus="http"
        )
        form_data_list, _, _, _, _ = data_converter.convert(
            message=job_list
        )
        assert len(form_data_list) == 1
        form_data = form_data_list[0]
        assert isinstance(form_data, aiohttp.MultipartWriter)
        # get the payload within the multipart writer
        payload = form_data._parts[0][0]
        payload_dict = json.loads(payload._value.getvalue())
        for expected_event, actual_event in zip(job_list, payload_dict):
            check_dict_equivalency(actual_event, expected_event)


class TestPVResponseConverter:
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
    def __init__(
        self,
        status: int,
        reason: str | None = None,
    ) -> None:
        self.status = status
        self.reason = reason

    @property
    def ok(self) -> bool:
        return 400 > self.status


class TestPVMessageResponseConverter:
    @staticmethod
    def test_convert_kafka(
    ) -> None:
        """Tests `convert` for kafka message bus
        """
        response_converter = PVMessageResponseConverter(
            message_bus="kafka"
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
            message_bus="http"
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
        """
        response_converter = PVMessageResponseConverter(
            message_bus="http"
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
    @staticmethod
    def test_handle_exception_kafka(
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Tests `handle_exception`
        """
        exception_handler = PVMessageExceptionHandler(
            message_bus="kafka"
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
                message_bus="kafka"
            )
            handler.handle_exception(ValueError("An error"))

    @staticmethod
    def test_handle_exception_http(
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Tests `handle_exception` for http
        """
        exception_handler = PVMessageExceptionHandler(
            message_bus="http"
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
