"""Tests for job_factory.py
"""
from test_harness.utils import check_dict_equivalency
from test_harness.jobs.job_factory import Event


class TestEvent:
    """Grouping of tests for :class:`Event` methods.
    """
    @staticmethod
    def test_parse_from_input_dict_single_prev_event() -> None:
        """Tests :class:`Event`.`parse_from_input_dict` when there is only a
        single previous event
        """
        input_dict = {
            "jobName": "test",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "1",
            "timestamp": "test o'clock",
            "applicationName": "test application",
            "previousEventIds": "0"
        }
        event = Event()
        event.parse_from_input_dict(input_dict.copy())
        for field, attribute in Event.attribute_mappings.items():
            assert getattr(event, attribute) == input_dict[field]

    @staticmethod
    def test_parse_from_input_dict_multiple_prev_event() -> None:
        """Tests :class:`Event`.`parse_from_input_dict` when there are
        multiple previous events
        """
        input_dict = {
            "jobName": "test",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "1",
            "timestamp": "test o'clock",
            "applicationName": "test application",
            "previousEventIds": ["0", "2"]
        }
        event = Event()
        event.parse_from_input_dict(input_dict.copy())
        for field, attribute in Event.attribute_mappings.items():
            assert getattr(event, attribute) == input_dict[field]

    @staticmethod
    def test_parse_from_input_dict_no_prev_event() -> None:
        """Tests :class:`Event`.`parse_from_input_dict` when there are no
        previous events
        """
        input_dict = {
            "jobName": "test",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "1",
            "timestamp": "test o'clock",
            "applicationName": "test application"
        }
        event = Event()
        event.parse_from_input_dict(input_dict.copy())
        for field, attribute in Event.attribute_mappings.items():
            if field == "previousEventIds":
                previous_event = getattr(event, attribute)
                assert isinstance(previous_event, list)
                assert not previous_event
            else:
                assert getattr(event, attribute) == input_dict[field]

    @staticmethod
    def test_parse_from_input_dict_meta_data() -> None:
        """Tests :class:`Event`.`parse_from_input_dict` when there is meta
        data attached to the input dictionary
        previous events
        """
        input_dict = {
            "jobName": "test",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "1",
            "timestamp": "test o'clock",
            "applicationName": "test application",
            "previousEventIds": ["0", "2"],
            "X": {"dataItemType": "LOOPCOUNT"}
        }
        event = Event()
        event.parse_from_input_dict(input_dict.copy())
        for field, attribute in Event.attribute_mappings.items():
            assert getattr(event, attribute) == input_dict[field]
        assert event.meta_data["X"] == input_dict["X"]

    @staticmethod
    def test_event_to_dict() -> None:
        """Tests :class:`Event`.`event_to_dict`
        """
        input_dict = {
            "jobName": "test",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "1",
            "timestamp": "test o'clock",
            "applicationName": "test application",
            "previousEventIds": ["0", "2"],
            "X": {"dataItemType": "LOOPCOUNT"}
        }
        event = Event()
        event.parse_from_input_dict(input_dict.copy())
        check_dict_equivalency(
            event.event_to_dict(),
            input_dict
        )
