"""Config for tests
"""
from typing import Generator, Any
import json
import datetime

import pytest
import aiokafka

from test_harness.simulator.simulator import SimDatum


@pytest.fixture
def job_list() -> list[dict[str, str | list[str]]]:
    """Fixture providing a job list of event dicts

    :return: event dict list
    :rtype: `list`[`dict`[`str`, `str` | `list`[`str`]]]
    """
    return [
        {
            "jobName": "test_job",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "1",
            "timestamp": "1",
            "applicationName": "test_application",
        },
        {
            "jobName": "test_job",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "2",
            "timestamp": "2",
            "applicationName": "test_application",
            "previousEventIds": "1",
        },
        {
            "jobName": "test_job",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "3",
            "timestamp": "3",
            "applicationName": "test_application",
            "previousEventIds": "1"
        },
        {
            "jobName": "test_job",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "4",
            "timestamp": "4",
            "applicationName": "test_application",
            "previousEventIds": ["2", "3"]
        },
    ]


@pytest.fixture
def job_list_with_meta_data() -> list[dict[str, str | list[str]]]:
    """Fixture providing a job list of event dicts

    :return: event dict list
    :rtype: `list`[`dict`[`str`, `str` | `list`[`str`]]]
    """
    return [
        {
            "jobName": "test_job",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "1",
            "timestamp": "1",
            "applicationName": "test_application",
            "X": "some invariant",
            "Y": 12
        },
        {
            "jobName": "test_job",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "2",
            "timestamp": "2",
            "applicationName": "test_application",
            "previousEventIds": "1",
            "X": "some invariant"
        },
        {
            "jobName": "test_job",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "3",
            "timestamp": "3",
            "applicationName": "test_application",
            "previousEventIds": "1"
        },
        {
            "jobName": "test_job",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "4",
            "timestamp": "4",
            "applicationName": "test_application",
            "previousEventIds": ["2", "3"]
        },
    ]


@pytest.fixture
def job_list_with_multiple_job_ids() -> list[dict[str, str | list[str]]]:
    """Fixture providing a job list of event dicts

    :return: event dict list
    :rtype: `list`[`dict`[`str`, `str` | `list`[`str`]]]
    """
    return [
        {
            "jobName": "test_job",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "1",
            "timestamp": "1",
            "applicationName": "test_application",
        },
        {
            "jobName": "test_job",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "2",
            "timestamp": "2",
            "applicationName": "test_application",
            "previousEventIds": "1",
        },
        {
            "jobName": "test_job_2",
            "jobId": "2",
            "eventType": "test_event",
            "eventId": "3",
            "timestamp": "3",
            "applicationName": "test_application",
        },
        {
            "jobName": "test_job_2",
            "jobId": "2",
            "eventType": "test_event",
            "eventId": "4",
            "timestamp": "4",
            "applicationName": "test_application",
            "previousEventIds": "3"
        },
    ]


@pytest.fixture
def list_generated_sim_datum() -> list[Generator[SimDatum, Any, None]]:
    """Fixture providing list of generators of :class:`SimDatum`'s

    :return: List of generators of :class:`SimDatum`
    :rtype: `list`[:class:`Generator`[:class:`SimDatum`, `Any`, `None`]]
    """
    def generate_sim_datums(args: list) -> Generator[SimDatum, Any, None]:
        for arg in args:
            yield SimDatum(
                args=[arg]
            )
    return [
        generate_sim_datums(
            args=["a" * multiplier, "b" * multiplier]
        )
        for multiplier in range(1, 4)
    ]


@pytest.fixture
def events_sent_list() -> list[dict[str, str | list[str]]]:
    """Fixture providing a list of event dicts

    :return: event dict list
    :rtype: `list`[`dict`[`str`, `str` | `list`[`str`]]]
    """
    return []


@pytest.fixture
def kafka_producer_mock(
    monkeypatch: pytest.MonkeyPatch,
    events_sent_list: list[dict[str, str | list[str]]]
) -> None:
    """Fixture providing a mock kafka producer

    :param monkeypatch: Pytest monkeypatch
    :type monkeypatch: :class:`pytest`.`MonkeyPatch`
    :param events_sent_list: List of events sent
    :type events_sent_list: `list`[`dict`[`str`, `str` | `list`[`str`]]]
    """
    async def mock_send_wait(*args, **kwargs):
        events_sent_list.append(json.loads(kwargs['value'][4:]))
        return ""

    async def mock_start(*agrs, **kwargs):
        return None
    monkeypatch.setattr(
        aiokafka.AIOKafkaProducer, "send_and_wait", mock_send_wait
    )
    monkeypatch.setattr(
        aiokafka.AIOKafkaProducer, "start", mock_start
    )


@pytest.fixture
def kafka_consumer_mock(
    monkeypatch: pytest.MonkeyPatch,
    events_sent_list: list[dict[str, str | list[str]]]
) -> None:
    """Fixture providing a mock kafka consumer

    :param monkeypatch: Pytest monkeypatch
    :type monkeypatch: :class:`pytest`.`MonkeyPatch`
    :param events_sent_list: List of events sent
    :type events_sent_list: `list`[`dict`[`str`, `str` | `list`[`str`]]]
    """
    async def mock_get_many(*args, **kwargs):
        consumer_records = []
        time_stamp = datetime.datetime.utcnow().timestamp()
        for _ in range(len(events_sent_list)):
            event = events_sent_list.pop(0)
            log_field = [
                "reception_event_received",
                "reception_event_valid",
                "reception_event_written",
                "aeordering_events_processed",
                "svdc_event_received",
                "svdc_event_processed",
            ]
            for i, field in enumerate(log_field):
                bytes_field = len(
                    field
                ).to_bytes(4, byteorder="big") + field.encode("utf-8")
                event_id_string = f"EventId = {event['eventId']}"
                event_id_bytes = len(
                    event_id_string
                ).to_bytes(
                    4, byteorder="big"
                ) + event_id_string.encode("utf-8")
                timestamp_bytes = int(
                    time_stamp * 10**9
                ).to_bytes(8, byteorder="big")
                consumer_record = aiokafka.ConsumerRecord(
                    topic="test_topic",
                    partition=0,
                    offset=0,
                    timestamp=0,
                    timestamp_type=0,
                    key=None,
                    value=bytes_field + event_id_bytes + timestamp_bytes,
                    headers=None,
                    checksum=0,
                    serialized_key_size=0,
                    serialized_value_size=0,
                )
                consumer_records.append(consumer_record)
                time_stamp += 1
        return {aiokafka.TopicPartition(
            topic='default.BenchmarkingProbe_service0', partition=0
        ): consumer_records}

    async def mock_start(*agrs, **kwargs):
        return None
    monkeypatch.setattr(
        aiokafka.AIOKafkaConsumer, "getmany", mock_get_many
    )
    monkeypatch.setattr(
        aiokafka.AIOKafkaConsumer, "start", mock_start
    )
