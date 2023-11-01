"""Module to collect metrics from Kafka topics
"""
import re
import datetime
from typing import Generator, Any, Literal

import kafka3

from test_harness.protocol_verifier.types import ResultsDict


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
    msgbroker: str, topic: str
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
        bootstrap_servers=msgbroker, auto_offset_reset="earliest"
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
                    # # create or find event
                    # if evt_id not in events:
                    #     events[evt_id] = Event(evt_id)
                    # evt = events[evt_id]

                    # match label:
                    #     case "reception_event_received":
                    #         evt.received = d
                    #     case "reception_event_valid":
                    #         evt.validated = d
                    #     case "reception_event_invalid":
                    #         evt.validated = d
                    #         evt.valid = False
                    #     case "reception_event_written":
                    #         evt.written = d
                    #     case "aeordering_events_processed":
                    #         evt.ordering_received = d
                    #     case "svdc_event_received":
                    #         evt.svdc_received = d
                    #     case "svdc_event_processed":
                    #         evt.processed = d
                    #     case "svdc_happy_event_processed":
                    #         evt.processed = d
                    #     case "svdc_unhappy_event_processed":
                    #         evt.processed = d
                    #     # case "svdc_job_success":
                    #     #     evt.processed = d
                    #     # case "svdc_job_failure":
                    #     #     evt.processed = d
                    #     # case "svdc_job_alarm":
                    #     #     evt.processed = d

                    # if label == "reception_event_received"
        raw_msgs = consumer.poll(timeout_ms=30000)
    return events


# if __name__ == "__main__":
#     results_generator = consume_events_from_kafka_topic(
#   "192.168.1.163:9092", "default.BenchmarkingProbe_service0"
#   )
#     for result in results_generator:
#         print(result)
