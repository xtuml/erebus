"""Module to collect metrics from Kafka topics
"""
import json
import re
import datetime
from typing import Generator, Any, Literal, Self
import logging
import asyncio

import kafka3
import aiokafka

from test_harness.simulator.simulator import ResultsHandler
from test_harness.protocol_verifier.types import ResultsDict
from test_harness.metrics.metrics import MetricsRetriever


KEY_EVENTS = (
    "reception_event_received",
    "reception_event_valid",
    "reception_event_invalid",
    "reception_event_written",
    "aeordering_events_processed",
    "svdc_event_received",
    "svdc_event_processed",
    "svdc_happy_event_processed",
    "svdc_unhappy_event_processed",
    # # Added by us
    # "svdc_job_success",
    # "svdc_job_failure",
    # "svdc_job_alarm",
)
PATTERN = (
    r"EventId ="
    r" "
    r"([\da-fA-F]{8}-[\da-fA-F]{4}-[\da-fA-F]{4}-[\da-fA-F]{4}-[\da-fA-F]{12})"
)


# @njit
def decode_data(
    data: bytearray, datatypes: tuple[Literal["string"] | Literal["timestamp"]]
) -> tuple[str]:
    """Decodes data from a byte array into a tuple of values

    :param data: The data to decode
    :type data: :class:`bytearray`
    :param datatypes: The datatypes to decode the data into
    :type datatypes: `tuple`[:class:`Literal`[`"string"`] |
    `Literal`[`"timestamp"`]]
    :raises ValueError: Raises an error if the datatype are not string or
    timestamp
    :return: Returns a tuple of the decoded values
    :rtype: `tuple`[`str`]
    """
    values = []
    for datatype in datatypes:
        if datatype == "string":
            # Let's fly close to the sun, and let python raise errors later
            # # check to make sure there is a length at the beginning of the
            # field if len(data) < 4:
            #     raise ValueError

            # get the length from the 4 byte header
            length = int.from_bytes(data[:4], byteorder="big")

            # remove the header
            data = data[4:]

            # # check to make sure the data contains 'length' more bytes
            # if len(data) < length:
            #     raise ValueError

            # extract the value
            values.append(data[:length].decode("utf-8"))
            # remove the value
            data = data[length:]

        elif datatype == "timestamp":
            # # check to make sure there is enough remaining data
            # if len(data) < 8:
            #     raise ValueError

            nanos = int.from_bytes(data[:8], byteorder="big")
            data = data[8:]

            seconds = nanos / 1e9
            values.append(
                datetime.datetime.fromtimestamp(seconds).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                )
            )

        else:
            raise ValueError

    return tuple(values)


def consume_events_from_kafka_topic(
    msgbroker: str, topic: str, group_id: str = "test_harness"
) -> Generator[ResultsDict, Any, dict]:
    """
    Consume events from a Kafka topic and process them to extract relevant
    information and put into a dictionary of :class:`Event`'s

    :param msgbroker: The Kafka broker to connect to.
    :type msgbroker: `str`
    :param topic: The Kafka topic to consume events from.
    :type topic: `str`
    :return: A dictionary containing the processed events.
    :rtype: `dict`
    """
    consumer = kafka3.KafkaConsumer(
        bootstrap_servers=msgbroker, auto_offset_reset="earliest",
        group_id=group_id
    )
    consumer.subscribe(topic)

    # process messages

    events = {}
    raw_msgs = consumer.poll(timeout_ms=30000)
    while len(raw_msgs) > 0:
        for _, partition in raw_msgs.items():
            for msg in partition:
                data = bytearray(msg.value)
                # DANGER: decode_data mutates data
                label, event_content, d = decode_data(
                    data, ("string", "string", "timestamp")
                )
                # print(label, event_content, d)
                if label in KEY_EVENTS:
                    # extract the UUID from the event content
                    match = re.search(PATTERN, event_content)
                    if match:
                        evt_id = match.group(1)
                    else:
                        continue
                    yield ResultsDict(
                        field=label, timestamp=d, event_id=evt_id
                    )
        raw_msgs = consumer.poll(timeout_ms=30000)
    return events


async def consume_events_from_subscribed_consumer_async(
    consumer: aiokafka.AIOKafkaConsumer,
) -> dict[aiokafka.TopicPartition, list[aiokafka.ConsumerRecord]]:
    """Consume events from a Kafka topic and return the raw message

    :param consumer: The Kafka consumer to consume events from.
    :type consumer: :class:`aiokafka.AIOKafkaConsumer`
    :return: A dictionary containing the raw messages.
    :rtype: `dict`[:class:`aiokafka.TopicPartition`,
    `list`[:class:`aiokafka.ConsumerRecord`]]
    """
    # get raw messages
    raw_msgs = await consumer.getmany(timeout_ms=1000)
    return raw_msgs


def decode_and_yield_events_from_raw_msgs(
    raw_msgs: dict[aiokafka.TopicPartition, list[aiokafka.ConsumerRecord]]
) -> Generator[ResultsDict, Any, ResultsDict | None]:
    """Decode the raw messages and yield the events

    :param raw_msgs: The raw messages to decode and yield events from
    :type raw_msgs: `dict`[:class:`aiokafka.TopicPartition`,
    `list`[:class:`aiokafka.ConsumerRecord`]]
    :yield: The decoded events
    :rtype: :class:`ResultsDict` | `None`
    """
    for partition in raw_msgs.values():
        for msg in partition:
            data = bytearray(msg.value)
            # DANGER: decode_data mutates data
            label, event_content, d = decode_data(
                data, ("string", "string", "timestamp")
            )
            # print(label, event_content, d)
            if label in KEY_EVENTS:
                # extract the UUID from the event content
                match = re.search(PATTERN, event_content)
                if match:
                    evt_id = match.group(1)
                else:
                    continue
                yield ResultsDict(
                    field=label, timestamp=d, event_id=evt_id
                )


def decode_and_yield_events_from_raw_msgs_no_length(
    raw_msgs: dict[aiokafka.TopicPartition, list[aiokafka.ConsumerRecord]],
) -> Generator[ResultsDict, Any, ResultsDict | None]:
    """Decode the raw messages and yield the events

    :param raw_msgs: The raw messages to decode and yield events from
    :type raw_msgs: `dict`[:class:`aiokafka.TopicPartition`,
    `list`[:class:`aiokafka.ConsumerRecord`]]
    :yield: The decoded events
    :rtype: :class:`ResultsDict` | `None`
    """
    json_data = {}
    for partition in raw_msgs.keys():
        for msg in raw_msgs[partition]:
            print(msg.value.decode("utf-8"))
            data = bytearray(msg.value)
            json_data = json.loads(data)
            for key, value in json_data:
                if key in KEY_EVENTS:
                    yield ResultsDict(
                        field=key,
                        timestamp=value["timestamp"],
                        event_id=value["EventId"]
                    )


class PVKafkaMetricsRetriever(MetricsRetriever):
    """Class to retrieve metrics from a Kafka topic

    :param msgbroker: The Kafka broker to connect to.
    :type msgbroker: `str`
    :param topic: The Kafka topic to consume events from.
    :type topic: `str`
    :param group_id: The Kafka consumer group id to use, defaults to
    "test_harness"
    :type group_id: `str`, optional
    """
    def __init__(
        self,
        msgbroker: str,
        topic: str,
        group_id: str = "test_harness",
    ) -> None:
        """Constructor method"""
        self.msgbroker = msgbroker
        self.topic = topic
        self.group_id = group_id
        self.consumer = aiokafka.AIOKafkaConsumer(
            topic,
            bootstrap_servers=msgbroker, auto_offset_reset="earliest",
            group_id=self.group_id
        )

    async def __aenter__(self) -> Self:
        """Method to enter the context manager

        :return: The instance of the class
        :rtype: :class:`PVKafkaMetricsRetriever`
        """
        await self.consumer.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """Method to exit the context manager
        """
        logging.getLogger().info("Test Harness Stopping Kafka consumer")
        try:
            await asyncio.wait_for(self.consumer.stop(), timeout=30)
        except asyncio.TimeoutError:
            logging.getLogger().warning(
                "Timeout error occurred whilst stopping Kafka consumer"
            )
        if exc_type is not None:
            logging.getLogger().error(
                "The folowing type of error occurred %s with value %s",
                exc_type,
                exc_value,
            )
            raise exc_value

    async def async_retrieve_metrics(
        self,
        handler: ResultsHandler
    ) -> None:
        """Method to retrieve metrics from a Kafka topic

        :param handler: The handler to send the results to
        :type handler: :class:`ResultsHandler`
        """
        raw_msgs = await self.consumer.getmany(timeout_ms=1000)
        handler.handle_result(raw_msgs)


# if __name__ == "__main__":
#     results_generator = consume_events_from_kafka_topic(
#   "192.168.1.163:9092", "default.BenchmarkingProbe_service0"
#   )
#     for result in results_generator:
#         print(result)
