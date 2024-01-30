"""Module to send events to the protocol verifier
"""
from typing import Any, Callable, Literal
from datetime import datetime
import asyncio
from io import BytesIO
from uuid import uuid4
import logging
from contextlib import asynccontextmanager

import aiohttp
from aiokafka.errors import KafkaTimeoutError as AIOKafkaTimeoutError
from kafka3.errors import KafkaTimeoutError as KafkaTimeoutError3

from test_harness.protocol_verifier.simulator_data import (
    convert_list_dict_to_json_io_bytes,
    convert_list_dict_to_pv_json_io_bytes
)
from test_harness.message_buses.message_buses import (
    MessageProducer, InputConverter, ResponseConverter,
    MessageExceptionHandler, Kafka3MessageBus,
    HTTPMessageBus, AIOKafkaMessageBus
)


@asynccontextmanager
async def get_pv_sender(
    message_bus: Literal["kafka", "http", "kafka3"],
    **kwargs: Any
) -> "PVMessageSender":
    """Function to get a PVMessageSender instance

    :param producer: The message producer
    :type producer: :class:`MessageProducer`
    :param message_bus: The message bus
    :type message_bus: `Literal`["kafka", "http"]
    :return: Returns a :class:`PVMessageSender` instance
    :rtype: :class:`PVMessageSender`
    """
    producer_kwargs = {
        "response_converter": PVMessageResponseConverter(
            message_bus=message_bus
        ),
        "exception_converter": PVMessageExceptionHandler(
            message_bus=message_bus
        )
    }
    match message_bus:
        case "kafka":
            message_bus_kwargs = {
                "bootstrap_servers": kwargs["bootstrap_servers"],
                "stop_timeout": (
                    kwargs["stop_timeout"]
                    if "stop_timeout" in kwargs
                    else 10,
                )
            }
            producer_kwargs["topic"] = kwargs["topic"]
            message_bus_class = AIOKafkaMessageBus
        case "kafka3":
            message_bus_kwargs = {
                "bootstrap_servers": kwargs["bootstrap_servers"],
                "stop_timeout": (
                    kwargs["stop_timeout"]
                    if "stop_timeout" in kwargs
                    else 10,
                )
            }
            producer_kwargs["topic"] = kwargs["topic"]
            message_bus_class = Kafka3MessageBus
        case "http":
            message_bus_kwargs = {
                "max_connections": (
                    kwargs["max_connections"]
                    if "max_connections" in kwargs
                    else 2000
                ),
            }
            producer_kwargs["url"] = kwargs["url"]
            message_bus_class = HTTPMessageBus
        case _:
            raise ValueError(
                f"Message bus {message_bus} not recognised"
            )
    async with message_bus_class(
        **message_bus_kwargs
    ) as message_bus_instance:
        producer = message_bus_instance.get_message_producer(
            **producer_kwargs
        )
        yield PVMessageSender(
            producer=producer,
            message_bus=message_bus,
        )


class PVMessageSender:
    def __init__(
        self,
        producer: MessageProducer,
        message_bus: Literal["kafka", "http"],
    ) -> None:
        self._producer = producer
        self._input_converter = PVInputConverter(
            message_bus=message_bus
        )
        self._response_converter = PVResponseConverter()

    async def send(
        self,
        message: list[dict[str, Any]],
        job_id: str,
        job_info: dict[str, str | None],
    ) -> tuple[
        list[dict[str, Any]], str, str, dict[str, str | None], str, datetime
    ]:
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
        converted_data, _, _, _, _ = self._input_converter(
            message=message
        )
        responses = await self._sender(
            converted_data=converted_data
        )
        return self._response_converter(
            responses=responses,
            list_dict=message,
            job_id=job_id,
            job_info=job_info,
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
        message_bus: Literal["kafka", "http"],
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
            case "kafka":
                self._data_conversion_function = (
                    convert_list_dict_to_pv_json_io_bytes
                )
            case "http":
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
        message_bus: Literal["kafka", "http"],
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
            case "kafka":
                self._data_conversion_function = (
                    self._kafka_conversion_function
                )
            case "http":
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
        message_bus: Literal["kafka", "http"],
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
            case "kafka":
                self._exception_handler = self._kafka_exception_handler
            case "http":
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
            AIOKafkaTimeoutError, KafkaTimeoutError3
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
