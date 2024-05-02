import datetime
import json
from typing import Any, Generator
from unittest.mock import MagicMock

import aiokafka
import pytest

from test_harness.protocol_verifier.kafka_metrics import (
    decode_and_yield_events_from_raw_msgs_no_length,
    ResultsDict,
)


def test_decode_and_yield_events_from_raw_msgs_no_length() -> None:
    # Prepare test data
    raw_msgs = {
        aiokafka.TopicPartition("topic", 0): [
            aiokafka.ConsumerRecord(
                topic="topic",
                partition=0,
                offset=0,
                key=None,
                value=bytearray(
                    json.dumps(
                        {
                            "tag": "test_tag",
                            "timestamp": "2022-01-01T00:00:00.000Z",
                            "EventId": "test_event_id",
                        }
                    ).encode("utf-8")
                ),
                timestamp=0,
                timestamp_type=0,
                headers=None,
                checksum=None,
                serialized_key_size=-1,
                serialized_value_size=-1,
            )
        ]
    }

    # Execute the function
    results = list(decode_and_yield_events_from_raw_msgs_no_length(raw_msgs))

    # Assert the results
    assert len(results) == 1
    assert results[0]["field"] == "test_tag"
    assert results[0]["timestamp"] == datetime.datetime(2022, 1, 1, 0, 0, 0)
    assert results[0]["event_id"] == "test_event_id"
