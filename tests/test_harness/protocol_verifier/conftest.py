"""Config for tests
"""
from typing import Generator, Any

import pytest

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
            "applicationName": "test_application"
        },
        {
            "jobName": "test_job",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "2",
            "timestamp": "2",
            "applicationName": "test_application",
            "previousEventIds": "1"
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
