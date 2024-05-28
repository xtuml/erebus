"""Tests for kafka_metrics.py"""
import json

import aiokafka

from test_harness.protocol_verifier.metrics_and_events.kafka_metrics import (
    decode_and_yield_events_from_raw_msgs_no_length,
)


def test_decode_and_yield_events_from_raw_msgs_no_length() -> None:
    """
    Test case for the decode_and_yield_events_from_raw_msgs_no_length function.

    This test verifies that the function correctly decodes and yields events
        from raw messages when the length information is not provided.

    Steps:
    1. Prepare test data with a raw message containing a JSON payload.
    2. Execute the function to decode and yield events from the raw messages.
    3. Assert the results by checking the number of events and their field
        values.

    Expected behavior:
    - The function should decode the JSON payload and yield a single event.
    - The event should have the expected field values.

    """
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
                            "tag": "reception_event_received",
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
    assert results[0]["field"] == "reception_event_received"
    assert results[0]["timestamp"] == '2022-01-01T00:00:00.000Z'
    assert results[0]["event_id"] == "test_event_id"
