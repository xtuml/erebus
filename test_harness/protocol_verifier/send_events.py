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
    convert_list_dict_to_pv_json_io_bytes,
    convert_list_dict_to_pv_json_io_bytes_without_prefix
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
    """Class to handle sending messages to the protocol verifier given a
    message producer relating to a message bus
    """
    def __init__(
        self,
        message_producer: MessageProducer,
        message_bus: Literal["KAFKA", "KAFKA3", "HTTP"],
        harness_config: HarnessConfig
    ) -> None:
        """Constructor method
        """
        input_converter = PVInputConverter(
            message_bus=message_bus,
            harness_config=harness_config
        )
        response_converter = PVResponseConverter()
        super().__init__(
            message_producer=message_producer,
            input_converter=input_converter,
            response_converter=response_converter,
        )

    async def _sender(self, converted_data: list[Any]) -> Any:
        """Private method to send the converted data used by the base class
        `send` method

        :param converted_data: The converted data
        :type converted_data: `list`[`Any`]
        :return: Returns the response
        :rtype: `Any`
        """
        return await asyncio.gather(
            *[
                self.message_producer.send_message(
                    message
                )
                for message in converted_data
            ]
        )


class PVInputConverter(InputConverter):
    """Class to handle converting input data to the PVMessageSender

    :param message_bus: The message bus
    :type message_bus: :class:`Literal`["KAFKA", "KAFKA3", "HTTP"]
    """
    def __init__(
        self,
        message_bus: Literal["KAFKA", "KAFKA3", "HTTP"],
        harness_config: HarnessConfig
    ) -> None:
        """Constructor method
        """
        super().__init__()
        self._message_bus = message_bus
        self._set_data_conversion_function(harness_config=harness_config)

    def convert(
        self,
        list_dict: list[dict[str, Any]],
        job_id: str,
        job_info: dict[str, str | None]
    ) -> tuple[
        list[Any], tuple[Any, ...], dict, tuple[Any, ...], dict[str, Any]
    ]:
        """Method to convert the input data to the PVMessageSender `send`
        method

        :param list_dict: The list of dictionaries
        :type list_dict: `list`[`dict`[`str`, `Any`]]
        :param job_id: The job id
        :type job_id: `str`
        :param job_info: The job info
        :type job_info: `dict`[`str`, `str` | `None`]

        :return: Returns the converted data
        :rtype: `tuple`[
            `list`[`Any`], `tuple`[`Any`, ...], `dict`, `tuple`[`Any`, ...],
            `dict`[`str`, `Any`]
        ]
        """
        output_data = self.data_conversion_function(list_dict)
        return output_data, (), {}, (), {
            "list_dict": list_dict,
            "job_id": job_id,
            "job_info": job_info
        }

    @property
    def data_conversion_function(self) -> Callable[
        [list[dict[str, Any]]], list[Any]
    ]:
        """Property to get the data conversion function

        :return: Returns the data conversion function
        :rtype: `Callable`[[`list`[`dict`[`str`, `Any`]]], `list`[`Any`]]
        """
        return self._data_conversion_function

    def _set_data_conversion_function(
        self,
        harness_config: HarnessConfig
    ) -> None:
        """Private method to set the data conversion function
        """
        match self._message_bus:
            case "KAFKA" | "KAFKA3":
                if (harness_config.send_json_without_length_prefix):
                    self._data_conversion_function = (
                        convert_list_dict_to_pv_json_io_bytes_without_prefix
                    )
                else:
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
    """Class to handle converting the response from the PVMessageSender
    """
    def __init__(
        self,
    ) -> None:
        """Constructor method
        """
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
        """Method to convert the response from the PVMessageSender `send`
        method

        :param responses: The responses
        :type responses: `list`[`str`]
        :param list_dict: The list of dictionaries
        :type list_dict: `list`[`dict`[`str`, `Any`]]
        :param job_id: The job id
        :type job_id: `str`
        :param job_info: The job info
        :type job_info: `dict`[`str`, `str` | `None`]
        :return: Returns the converted data
        :rtype: `tuple`[
            `list`[`dict`[`str`, `Any`]], `str`, `str`, `dict`[`str`, `str` |
            `None`], `str`, :class:`datetime`.`datetime`
        ]
        """
        time_completed = datetime.now()
        file_name = str(uuid4()) + ".json"
        result = "".join(responses)
        return (
            list_dict, file_name, job_id, job_info, result,
            time_completed
        )


class PVMessageResponseConverter(ResponseConverter):
    """Class to handle converting the response in the :class:`MessageProducer`
    used

    :param message_bus: The message bus
    :type message_bus: :class:`Literal`["KAFKA", "KAFKA3", "HTTP"]
    """
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
        """Property to get the data conversion function

        :return: Returns the data conversion function
        :rtype: `Callable`[[`Any`], `str`]
        """
        return self._data_conversion_function

    def convert(
        self,
        response: Any
    ) -> str:
        """Method to convert the response from the :class:`MessageProducer`
        `send` method

        :param response: The response
        :type response: `Any`
        :return: Returns the converted data
        :rtype: `str`
        """
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
        """Method to convert the response from the :class:`MessageProducer`
        `send` method for the HTTP message bus

        :param response: The response
        :type response: :class:`aiohttp`.`ClientResponse`
        :return: Returns the converted data
        :rtype: `str`
        """
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
        """Method to convert the response from the :class:`MessageProducer`
        `send` method for the kafka message bus

        :return: Returns the converted data
        :rtype: `str`
        """
        return ""


class PVMessageExceptionHandler(MessageExceptionHandler):
    """Class to handle exceptions in the :class:`MessageProducer` used

    :param message_bus: The message bus
    :type message_bus: :class:`Literal`["KAFKA", "KAFKA3", "HTTP"]
    """
    def __init__(
        self,
        message_bus: Literal["KAFKA", "KAFKA3", "HTTP"],
    ) -> None:
        """Constructor method
        """
        super().__init__()
        self._message_bus = message_bus
        self._set_exception_handler()

    @property
    def exception_handler(self) -> Callable[[Exception], str]:
        """Property to get the exception handler

        :return: Returns the exception handler
        :rtype: `Callable`[[`Exception`], `str`]
        """
        return self._exception_handler

    def handle_exception(self, exception: Exception) -> str:
        """Method to handle an exception

        :param exception: The exception
        :type exception: :class:`Exception`
        :return: Returns the exception message
        :rtype: `str`
        """
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
        """Method to handle an exception for the kafka message bus

        :param exception: The exception
        :type exception: :class:`Exception`
        :return: Returns the exception message
        :rtype: `str`
        """
        if isinstance(exception, (
            AIOKafkaTimeoutError, Kafka3TimeoutError
        )):
            logging.getLogger().warning(
                "Error sending payload to kafka: %s", exception
            )
            return str(exception)
        raise exception

    @staticmethod
    def _http_exception_handler(
        exception: Exception
    ) -> str:
        """Method to handle an exception for the HTTP message bus

        :param exception: The exception
        :type exception: :class:`Exception`
        :return: Returns the exception message
        :rtype: `str`
        """
        logging.getLogger().warning(
            "Error sending http payload: %s", exception
        )
        if isinstance(exception, asyncio.TimeoutError):
            return "timed out"
        if isinstance(exception, aiohttp.ClientConnectionError):
            return "Connection Error"
        raise exception
