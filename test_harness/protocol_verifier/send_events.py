"""Module to send events to the protocol verifier
"""
from typing import Any, Callable, Literal
from datetime import datetime
import asyncio
from io import BytesIO
from uuid import uuid4
import logging

import aiohttp
from aiokafka.errors import KafkaTimeoutError as AIOKafkaTimeoutError
from kafka3.errors import KafkaTimeoutError as Kafka3TimeoutError

from test_harness.config.config import HarnessConfig
from test_harness.protocol_verifier.simulator_data import (
    convert_list_dict_to_json_io_bytes,
    convert_list_dict_to_pv_json_io_bytes
)
from test_harness.message_buses.message_buses import (
    MessageProducer, InputConverter, ResponseConverter,
    MessageExceptionHandler, MessageSender
)


def get_message_bus_kwargs(
    harness_config: HarnessConfig
) -> dict[str, Any]:
    """Function to get the message bus kwargs

    :param harness_config: The harness config
    :type harness_config: :class:`HarnessConfig`
    :raises ValueError: If the message bus protocol is not recognised
    :return: Returns the message bus kwargs
    :rtype: `dict`[`str`, `Any`]
    """
    match harness_config.message_bus_protocol:
        case "KAFKA" | "KAFKA3":
            return {
                "bootstrap_servers": harness_config.kafka_message_bus_host,
            }
        case "HTTP":
            return {}
        case _:
            raise ValueError(
                f"Message bus {harness_config.message_bus_protocol} "
                "not recognised"
            )


def get_producer_kwargs(
    harness_config: HarnessConfig
) -> dict[str, Any]:
    """Function to get the producer kwargs

    :param harness_config: The harness config
    :type harness_config: :class:`HarnessConfig`
    :raises ValueError: If the message bus protocol is not recognised
    :return: Returns the producer kwargs
    :rtype: `dict`[`str`, `Any`]
    """
    producer_kwargs = {
        "response_converter": PVMessageResponseConverter(
            message_bus=harness_config.message_bus_protocol
        ),
        "exception_converter": PVMessageExceptionHandler(
            message_bus=harness_config.message_bus_protocol
        )
    }
    match harness_config.message_bus_protocol:
        case "KAFKA" | "KAFKA3":
            producer_kwargs[
                "topic"
            ] = harness_config.kafka_message_bus_topic
        case "HTTP":
            producer_kwargs[
                "url"
            ] = harness_config.pv_send_url
        case _:
            raise ValueError(
                f"Message bus {harness_config.message_bus_protocol} "
                "not recognised"
            )
    return producer_kwargs


class PVMessageSender(MessageSender):
    def __init__(
        self,
        producer: MessageProducer,
        message_bus: Literal["KAFKA", "KAFKA3", "HTTP"],
    ) -> None:
        self._producer = producer
        input_converter = PVInputConverter(
            message_bus=message_bus
        )
        response_converter = PVResponseConverter()
        super().__init__(
            producer=producer,
            input_converter=input_converter,
            response_converter=response_converter,
        )

    async def _sender(self, converted_data: list[Any]) -> Any:
        return await asyncio.gather(
            *[
                self._producer.send_message(
                    message=message
                )
                for message in converted_data
            ]
        )


class PVInputConverter(InputConverter):
    def __init__(
        self,
        message_bus: Literal["KAFKA", "KAFKA3", "HTTP"],
    ) -> None:
        super().__init__()
        self._message_bus = message_bus
        self._set_data_conversion_function()

    def convert(
        self,
        message: list[dict[str, Any]],
    ) -> tuple[list[Any], tuple[()], dict, tuple[()], dict[str, Any]]:
        output_data = self.data_conversion_function(message)
        return output_data, (), {}, (), {}

    @property
    def data_conversion_function(self) -> Callable[
        [list[dict[str, Any]]], list[Any]
    ]:
        return self._data_conversion_function

    def _set_data_conversion_function(
        self
    ) -> None:
        """Private method to set the data conversion function
        """
        match self._message_bus:
            case "KAFKA" | "KAFKA3":
                self._data_conversion_function = (
                    convert_list_dict_to_pv_json_io_bytes
                )
            case "HTTP":
                self._data_conversion_function = (
                    self._http_conversion_function
                )
            case _:
                raise ValueError(
                    f"Message bus {self._message_bus} not recognised"
                )

    @staticmethod
    def _http_conversion_function(
        list_dict: list[dict[str, Any]]
    ) -> list[aiohttp.Payload]:
        """Method to convert a list of dicts to a list of aiohttp form data
        using the given function

        :param list_dict: The list of dictionaries
        :type list_dict: `list`[`dict`[`str`, `Any`]]
        :return: Returns the :class:`aiohttp`.`FormData` instance
        :rtype: `list`[:class:`aiohttp`.`FormData`]
        """
        form_bytes_list = convert_list_dict_to_json_io_bytes(list_dict)
        form_data_list = []
        for form_bytes in form_bytes_list:
            form_data = aiohttp.FormData()
            form_data.add_field(
                name="upload",
                value=BytesIO(form_bytes),
                filename=str(uuid4) + ".json",
                content_type='application/octet-stream',
            )
            form_data_list.append(form_data())
        return form_data_list


class PVResponseConverter(ResponseConverter):
    def __init__(
        self,
    ) -> None:
        super().__init__()

    def convert(
        self,
        responses: list[str],
        list_dict: list[dict[str, Any]],
        job_id: str,
        job_info: dict[str, str | None]
    ) -> tuple[
        list[dict[str, Any]], str, str, dict[str, str | None], str, datetime
    ]:
        time_completed = datetime.now()
        file_name = str(uuid4()) + ".json"
        result = "".join(responses)
        return (
            list_dict, file_name, job_id, job_info, result,
            time_completed
        )


class PVMessageResponseConverter(ResponseConverter):
    def __init__(
        self,
        message_bus: Literal["KAFKA", "KAFKA3", "HTTP"],
    ) -> None:
        super().__init__()
        self._message_bus = message_bus
        self._set_data_conversion_function()

    @property
    def data_conversion_function(self) -> Callable[
        [Any], str
    ]:
        return self._data_conversion_function

    def convert(
        self,
        response: Any
    ) -> str:
        return self.data_conversion_function(response)

    def _set_data_conversion_function(
        self
    ) -> None:
        """Private method to set the data conversion function
        """
        match self._message_bus:
            case "KAFKA" | "KAFKA3":
                self._data_conversion_function = (
                    self._kafka_conversion_function
                )
            case "HTTP":
                self._data_conversion_function = (
                    self._http_conversion_function
                )
            case _:
                raise ValueError(
                    f"Message bus {self._message_bus} not recognised"
                )

    @staticmethod
    def _http_conversion_function(
        response: aiohttp.ClientResponse
    ) -> str:
        if response.ok:
            return ""
        logging.getLogger().warning(
            "Error sending http payload: %s", response.reason
        )
        return response.reason

    @staticmethod
    def _kafka_conversion_function(
        *_
    ) -> str:
        return ""


class PVMessageExceptionHandler(MessageExceptionHandler):
    def __init__(
        self,
        message_bus: Literal["KAFKA", "KAFKA3", "HTTP"],
    ) -> None:
        super().__init__()
        self._message_bus = message_bus
        self._set_exception_handler()

    @property
    def exception_handler(self) -> Callable[[Exception], str]:
        return self._exception_handler

    def handle_exception(self, exception: Exception) -> str:
        return self._exception_handler(exception)

    def _set_exception_handler(self) -> None:
        """Private method to set the exception handler
        """
        match self._message_bus:
            case "KAFKA" | "KAFKA3":
                self._exception_handler = self._kafka_exception_handler
            case "HTTP":
                self._exception_handler = self._http_exception_handler
            case _:
                raise ValueError(
                    f"Message bus {self._message_bus} not recognised"
                )

    @staticmethod
    def _kafka_exception_handler(
        exception: Exception
    ) -> str:
        if isinstance(exception, (
            AIOKafkaTimeoutError, Kafka3TimeoutError
        )):
            logging.getLogger().warning(
                "Error sending payload to kafka: %s", exception
            )
            return str(exception)
        raise exception

    def _http_exception_handler(
        self,
        exception: Exception
    ) -> str:
        logging.getLogger().warning(
            "Error sending http payload: %s", exception
        )
        if isinstance(exception, asyncio.TimeoutError):
            return "timed out"
        if isinstance(exception, aiohttp.ClientConnectionError):
            return "Connection Error"
        raise exception
