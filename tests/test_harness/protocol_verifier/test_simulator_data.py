# pylint: disable=W0212
# pylint: disable=W0143
# pylint: disable=R0903
# pylint: disable=C0302
"""Test simulation_data.py
"""
from io import BytesIO
from typing import Generator, Any
from copy import copy, deepcopy
import json
import re

from hypothesis import given, strategies as st
import pytest

from test_harness.utils import check_dict_equivalency
from test_harness.simulator.simulator import (
    Batch,
    SimDatum,
    async_do_nothing
)
from test_harness.protocol_verifier.simulator_data import (
    BatchJobSimDatumTransformer,
    EventSimDatumTransformer,
    Job,
    Event,
    NamedUUID,
    NamedUUIDStore,
    generate_job_batch_events,
    generate_single_events,
    simple_sequencer,
    job_sequencer,
    generate_events_from_template_jobs,
    convert_list_dict_to_json_io_bytes,
)

uuid4hex = re.compile(
            '[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}\\Z', re.I
        )


class TestBatchJobSimDatumTransformer:
    """Group of tests for :class:`BatchJobSimDatumTransformer`
    """
    @staticmethod
    def test_initialise_batch() -> None:
        """Tests the method
        :class:`BatchJobSimDatumTransformer`.`initialise_batch`
        """
        transformer = BatchJobSimDatumTransformer()
        transformer.initialise_batch(
            job_id="1",
            length=3
        )
        assert "1" in transformer.batch_jobs
        batch = transformer.batch_jobs["1"]
        assert isinstance(batch, Batch)
        assert batch._length == 3
        for actual, expected in zip(
            batch.batch_concat([[1, 2, 3], [4, 5, 6]]),
            [1, 2, 3, 4, 5, 6]
        ):
            assert actual == expected

    @staticmethod
    def test_get_sim_datum(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests the method
        :class:`BatchJobSimDatumTransformer`.`get_sim_datum`

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        transformer = BatchJobSimDatumTransformer()
        job_id = job_list[0]["jobId"]
        transformer.initialise_batch(
            job_id=job_id,
            length=len(job_list)
        )
        sim_datums: list[SimDatum] = []
        job_info = {}
        # check sim datums are correct
        for index, event in enumerate(job_list):
            sim_datum = next(
                transformer.get_sim_datum(
                    [event],
                    job_info=job_info
                )
            )
            assert event in (
                transformer.batch_jobs[job_id].batch_list[index]
            )
            assert isinstance(sim_datum, SimDatum)
            assert not sim_datum.args
            sim_datums.append(sim_datum)
        # check all sim datums apart from last
        for sim_datum in sim_datums[:-1]:
            assert not sim_datum.kwargs
            assert sim_datum.action_func == async_do_nothing
        # check last sim datum
        assert "list_dict" in sim_datums[-1].kwargs
        assert sim_datums[-1].kwargs["list_dict"] == (
            transformer.batch_jobs[job_id].batch_output
        )
        assert "job_info" in sim_datums[-1].kwargs
        assert sim_datums[-1].kwargs["job_info"] == job_info


class TestEventSimDatumTransformer:
    """Group of tests for :class:`EventSimDatumTransformer`
    """
    @staticmethod
    def test_get_sim_datum(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests the method
        :class:`EventSimDatumTransformer`.`get_sim_datum`

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        transformer = EventSimDatumTransformer()
        job_id = job_list[0]["jobId"]
        job_info = {}
        event_list = [job_list[0]]
        sim_datum = next(
            transformer.get_sim_datum(
                event_list,
                job_info=job_info
            )
        )
        assert isinstance(sim_datum, SimDatum)
        assert not sim_datum.args
        assert "list_dict" in sim_datum.kwargs
        assert sim_datum.kwargs["list_dict"] == event_list
        assert "job_info" in sim_datum.kwargs
        assert sim_datum.kwargs["job_info"] == job_info
        assert "job_id" in sim_datum.kwargs
        assert sim_datum.kwargs["job_id"] == job_id
        assert sim_datum.action_func is None


class TestInvariants:
    """Tests for the classes:
    * :class:`NamedUUID`
    * :class:`NamedUUIDStore`
    """
    @staticmethod
    def test_create_random_data() -> None:
        """Tests the method :class:`NamedUUID`.`create_random_data`
        """
        random_data = NamedUUID.create_random_data()
        is_uuid = bool(uuid4hex.match(
                random_data.replace("-", "")
            ))
        assert is_uuid

    @staticmethod
    @given(
        st.lists(
            st.text()
        )
    )
    def test_update_invariants(names: list[str]) -> None:
        """Tests the method :class:`NamedUUIDStore`.`update`

        :param names: list of names of named_uuids
        :type names: `list`[`str`]
        """
        named_uuid_store = NamedUUIDStore()
        named_uuids = [
            named_uuid_store.update(name)
            for name in names
        ]
        assert len(set(names)) == len(named_uuid_store.named_uuids)
        for named_uuid in named_uuids:
            assert named_uuid.name in named_uuid_store.named_uuids
            assert named_uuid_store.named_uuids[named_uuid.name] == named_uuid

    @staticmethod
    @given(
        st.lists(
            st.text()
        )
    )
    def test_create_name_data_map(names: list[str]) -> None:
        """Tests the method
        :class:`NamedUUIDStore`.`create_name_data_map`

        :param names: List of names of named uuids
        :type names: `list`[`str`]
        """
        named_uuid_store = NamedUUIDStore()
        named_uuids = [
            named_uuid_store.update(name)
            for name in names
        ]
        named_uuid_name_data_map = (
            named_uuid_store.create_name_data_map()
        )
        assert len(set(names)) == len(named_uuid_name_data_map)
        for named_uuid in named_uuids:
            assert named_uuid.name in named_uuid_name_data_map
            random_data = named_uuid_name_data_map[named_uuid.name]
            is_uuid = bool(uuid4hex.match(
                    random_data.replace("-", "")
                ))
            assert is_uuid


class TestEvent:
    """Group of tests for :class:`Event`
    """
    @staticmethod
    def test_parse_from_input_dict_no_prev_event(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests :class:`Event`.`parse_from_input_dict` with no previous event

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        event = Event()
        event.parse_from_input_dict(
            input_dict=copy(job_list[0])
        )
        for dict_key, attribute_name in Event.attribute_mappings.items():
            attr_value = getattr(event, attribute_name)
            if attribute_name == "previous_event_ids":
                assert isinstance(attr_value, list)
                assert not attr_value
            else:
                assert attr_value == job_list[0][dict_key]
        assert not event.has_previous_event_id()

    @staticmethod
    def test_parse_from_input_dict_single_prev_event(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests :class:`Event`.`parse_from_input_dict` with single previous
        event

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        event = Event()
        event.parse_from_input_dict(
            input_dict=copy(job_list[1])
        )
        for dict_key, attribute_name in Event.attribute_mappings.items():
            attr_value = getattr(event, attribute_name)
            assert attr_value == job_list[1][dict_key]
        assert event.has_previous_event_id()

    @staticmethod
    def test_parse_from_input_dict_multiple_prev_event(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests :class:`Event`.`parse_from_input_dict` with multiple previous
        events

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        event = Event()
        event.parse_from_input_dict(
            input_dict=copy(job_list[-1])
        )
        for dict_key, attribute_name in Event.attribute_mappings.items():
            attr_value = getattr(event, attribute_name)
            assert attr_value == job_list[-1][dict_key]
        assert event.has_previous_event_id()

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
        assert event.meta_data["X"] == input_dict["X"]

    @staticmethod
    def test_add_prev_event_event_exists(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests :class:`Event`.`add_prev_event` when the event exists in the
        `event_id_map`

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        events: list[Event] = []
        event_id_map = {}
        missing_events: list[Event] = []
        for event_dict in job_list[:2]:
            event = Event()
            event.parse_from_input_dict(event_dict)
            event_id_map[event.event_id] = event
            events.append(event)
        events[-1].add_prev_event(
            prev_event_id=events[-1].previous_event_ids,
            event_id_map=event_id_map,
            missing_events=missing_events
        )
        assert events[0] in events[-1].prev_events
        assert not missing_events

    @staticmethod
    def test_add_prev_event_event_missing(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests :class:`Event`.`add_prev_event` when the event does not exist
        in the `event_id_map`

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        events: list[Event] = []
        event_id_map = {}
        missing_events: list[Event] = []
        for event_dict in job_list[1: 2]:
            event = Event()
            event.parse_from_input_dict(event_dict)
            event_id_map[event.event_id] = event
            events.append(event)
        events[-1].add_prev_event(
            prev_event_id=events[-1].previous_event_ids,
            event_id_map=event_id_map,
            missing_events=missing_events
        )
        assert len(missing_events) == 1
        assert missing_events[0] in events[-1].prev_events
        assert event_id_map[events[-1].previous_event_ids] == missing_events[0]

    @staticmethod
    def make_events_from_job_list(
        job_list: list[dict[str, str | list[str]]],
        events: list[Event],
        event_id_map: dict,
        missing_events: list[Event]
    ) -> None:
        """Helper method to make :class:`Event` instances from a job list

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        :param events: A list to conatin events
        :type events: `list`[:class:`Event`]
        :param event_id_map: The event id map
        :type event_id_map: `dict`
        :param missing_events: A list of missing events to update
        :type missing_events: `list`[:class:`Event`]
        """
        for event_dict in job_list:
            event = Event()
            event.parse_from_input_dict(event_dict)
            event_id_map[event.event_id] = event
            events.append(event)
        for event in events:
            missing_events.extend(event.link_prev_events(event_id_map))

    @staticmethod
    def test_link_prev_events(
        job_list: list[dict[str, str | list[str]]]
    ) -> list[Event]:
        """Tests :class:`Event`.`link_prev_events`

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        events: list[Event] = []
        event_id_map = {}
        missing_events: list[Event] = []
        TestEvent.make_events_from_job_list(
            job_list,
            events,
            event_id_map,
            missing_events
        )
        assert not missing_events
        assert not events[0].prev_events
        for i in [1, 2]:
            assert len(events[i].prev_events) == 1
            assert events[0] in events[i].prev_events
            assert events[i] in events[3].prev_events
        assert len(events[3].prev_events) == 2
        return events

    @staticmethod
    def test_make_event_dict_no_previous_event(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests :class:`Event`.`make_event_dict` when the event has no
        previous event

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        job_list_copy = deepcopy(job_list)
        events: list[Event] = []
        event_id_map = {}
        missing_events: list[Event] = []
        TestEvent.make_events_from_job_list(
            job_list,
            events,
            event_id_map,
            missing_events
        )
        event_event_id_map = {
            id(event): str(index)
            for index, event in enumerate(events)
        }
        job_id = "1"
        job_id_data_map = {job_id: job_id}
        invariant_name_data_map = {}
        event_dict = events[0].make_event_dict(
            event_event_id_map=event_event_id_map,
            job_id_data_map=job_id_data_map,
            invariant_name_data_map=invariant_name_data_map
        )
        for field in ["jobName", "eventType", "applicationName"]:
            assert event_dict[field] == job_list_copy[0][field]
        assert event_dict["eventId"] == event_event_id_map[id(events[0])]
        assert event_dict["jobId"] == job_id
        assert event_dict["timestamp"] != events[0].time_stamp
        assert "previousEventIds" not in event_dict

    @staticmethod
    def test_make_event_dict_single_previous_event(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests :class:`Event`.`make_event_dict` when the event has a single
        previous event

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        job_list_copy = deepcopy(job_list)
        events: list[Event] = []
        event_id_map = {}
        missing_events: list[Event] = []
        TestEvent.make_events_from_job_list(
            job_list,
            events,
            event_id_map,
            missing_events
        )
        event_event_id_map = {
            id(event): str(index)
            for index, event in enumerate(events)
        }
        job_id = "1"
        job_id_data_map = {job_id: job_id}
        invariant_name_data_map = {}
        event_dict = events[1].make_event_dict(
            event_event_id_map=event_event_id_map,
            job_id_data_map=job_id_data_map,
            invariant_name_data_map=invariant_name_data_map
        )
        for field in ["jobName", "eventType", "applicationName"]:
            assert event_dict[field] == job_list_copy[1][field]
        assert event_dict["eventId"] == event_event_id_map[id(events[1])]
        assert event_dict["jobId"] == job_id
        assert event_dict["timestamp"] != events[1].time_stamp
        assert event_dict["previousEventIds"] == event_event_id_map[
            id(events[0])
        ]

    @staticmethod
    def test_make_event_dict_mulitple_previous_events(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests :class:`Event`.`make_event_dict` when the event has multiple
        previous events

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        job_list_copy = deepcopy(job_list)
        events: list[Event] = []
        event_id_map = {}
        missing_events: list[Event] = []
        TestEvent.make_events_from_job_list(
            job_list,
            events,
            event_id_map,
            missing_events
        )
        event_event_id_map = {
            id(event): str(index)
            for index, event in enumerate(events)
        }
        job_id = "1"
        job_id_data_map = {job_id: job_id}
        invariant_name_data_map = {}
        event_dict = events[-1].make_event_dict(
            event_event_id_map=event_event_id_map,
            job_id_data_map=job_id_data_map,
            invariant_name_data_map=invariant_name_data_map
        )
        for field in ["jobName", "eventType", "applicationName"]:
            assert event_dict[field] == job_list_copy[-1][field]
        assert event_dict["eventId"] == event_event_id_map[id(events[-1])]
        assert event_dict["jobId"] == job_id
        assert event_dict["timestamp"] != events[-1].time_stamp
        assert len(event_dict["previousEventIds"]) == 2
        for index in [1, 2]:
            assert event_event_id_map[
                id(events[index])
            ] in event_dict["previousEventIds"]

    @staticmethod
    def test_make_event_dict_meta_data() -> None:
        """Tests :class:`Event`.`make_event_dict` with meta data
        """
        input_dict = {
            "jobName": "test",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "1",
            "timestamp": "test o'clock",
            "applicationName": "test application",
            "previousEventIds": ["1", "2"],
            "X": {"dataItemType": "LOOPCOUNT"}
        }
        events: list[Event] = []
        event_id_map = {}
        missing_events: list[Event] = []
        TestEvent.make_events_from_job_list(
            [input_dict.copy()],
            events,
            event_id_map,
            missing_events
        )
        event_event_id_map = {
            id(event): str(index)
            for index, event in enumerate(events + missing_events)
        }
        job_id = "1"
        job_id_data_map = {job_id: job_id}
        invariant_name_data_map = {}
        event_dict = events[-1].make_event_dict(
            event_event_id_map=event_event_id_map,
            job_id_data_map=job_id_data_map,
            invariant_name_data_map=invariant_name_data_map
        )
        fields_to_check = [
            "jobId", "jobName", "eventType", "applicationName", "X"
        ]
        check_dict_equivalency(
            {
                key: value
                for key, value in event_dict.items()
                if key in fields_to_check
            },
            {
                key: value
                for key, value in input_dict.items()
                if key in fields_to_check
            }
        )

    @staticmethod
    @given(
        st.lists(
            st.one_of(
                st.none(),
                st.integers(),
                st.floats(),
                st.dictionaries(
                    st.characters(exclude_characters=":"),
                    st.text()
                ),
            )
        ),
        st.lists(
            st.text()
        )
    )
    def test_categorise_meta_data(
        non_string_type: list,
        string_type: list
    ) -> None:
        """Tests :class:`Event`.`categorise_meta_data`

        :param non_string_type: A list of any type but string
        :type non_string_type: `list`[`Any`]
        :param string_type: A list of strings
        :type string_type: `list`[`str`]
        """
        string_type_dict = {
            str(i): val
            for i, val in enumerate(string_type)
        }
        num_string_type = len(string_type)
        non_string_type_dict = {
            str(i + num_string_type): val
            for i, val in enumerate(non_string_type)
        }
        num_non_string_type = len(non_string_type)
        input_dict = {
            **string_type_dict,
            **non_string_type_dict
        }
        categorised_meta_data = Event.categorise_meta_data(
            input_dict,
            NamedUUIDStore()
        )
        assert len(categorised_meta_data["fixed"]) == num_non_string_type
        assert len(categorised_meta_data["invariants"]) == num_string_type
        check_dict_equivalency(
            string_type_dict, categorised_meta_data["invariants"]
        )
        check_dict_equivalency(
            non_string_type_dict, categorised_meta_data["fixed"]
        )

    @staticmethod
    @given(
        st.lists(
            st.one_of(
                st.none(),
                st.integers(),
                st.floats(),
                st.dictionaries(
                    st.text(
                        st.characters(exclude_characters=":")
                    ),
                    st.text()
                ),
            )
        ),
        st.lists(
            st.text()
        )
    )
    def test_generate_meta_data(
        non_string_type: list[Any],
        string_type: list[str]
    ) -> None:
        """Tests :class:`Event`.`generate_meta_data`

        :param non_string_type: A list of any type but string
        :type non_string_type: `list`[`Any`]
        :param string_type: A list of strings
        :type string_type: `list`[`str`]
        """
        string_type_dict = {
            str(i): val
            for i, val in enumerate(string_type)
        }
        num_string_type = len(string_type)
        non_string_type_dict = {
            str(i + num_string_type): val
            for i, val in enumerate(non_string_type)
        }
        input_dict = {
            **string_type_dict,
            **non_string_type_dict
        }
        invariant_store = NamedUUIDStore()
        categorised_meta_data = Event.categorise_meta_data(
            input_dict,
            invariant_store
        )
        generated_meta_data = Event.generate_meta_data(
            categorised_meta_data,
            invariant_store.create_name_data_map()
        )
        fixed_dict = {
            key: generated_meta_data.pop(key)
            for key in non_string_type_dict.keys()
        }
        check_dict_equivalency(non_string_type_dict, fixed_dict)
        for key in string_type_dict.keys():
            value = generated_meta_data.pop(key)
            is_uuid = bool(uuid4hex.match(
                    value.replace("-", "")
                ))
            assert is_uuid
        assert not generated_meta_data

    @staticmethod
    @given(
        st.lists(
            st.one_of(
                st.none(),
                st.integers(),
                st.floats(),
                st.dictionaries(
                    st.characters(exclude_characters=":"),
                    st.text()
                ),
            )
        ),
        st.lists(
            st.text(),
            min_size=1
        )
    )
    def test_generate_meta_data_not_in_invariant_map(
        non_string_type: list[Any],
        string_type: list[str]
    ) -> None:
        """Tests :class:`Event`.`generate_meta_data` when data is not in the
        invariant map

        :param non_string_type: A list of any type but string
        :type non_string_type: `list`[`Any`]
        :param string_type: A list of strings
        :type string_type: `list`[`str`]
        """
        string_type_dict = {
            str(i): val
            for i, val in enumerate(string_type)
        }
        num_string_type = len(string_type)
        non_string_type_dict = {
            str(i + num_string_type): val
            for i, val in enumerate(non_string_type)
        }
        input_dict = {
            **string_type_dict,
            **non_string_type_dict
        }
        categorised_meta_data = Event.categorise_meta_data(
            input_dict,
            NamedUUIDStore()
        )
        with pytest.raises(KeyError):
            Event.generate_meta_data(
                categorised_meta_data,
                {}
            )

    @staticmethod
    def test_make_event_dict_meta_data_string_type() -> None:
        """Tests :class:`Event`.`make_event_dict` with meta data including
        as string type and an integer type.
        """
        input_dict = {
            "jobName": "test",
            "jobId": "1",
            "eventType": "test_event",
            "eventId": "1",
            "timestamp": "test o'clock",
            "applicationName": "test application",
            "previousEventIds": ["1", "2"],
            "X": "some invariant",
            "Y": 12
        }
        events: list[Event] = []
        event_id_map = {}
        missing_events: list[Event] = []
        TestEvent.make_events_from_job_list(
            [input_dict.copy()],
            events,
            event_id_map,
            missing_events
        )
        event_event_id_map = {
            id(event): str(index)
            for index, event in enumerate(events + missing_events)
        }
        job_id = "1"
        job_id_data_map = {job_id: job_id}
        invariant_store = NamedUUIDStore()
        invariant_store.update("X")
        invaraint_name_data_map = (
            invariant_store.create_name_data_map()
        )
        event_dict = events[-1].make_event_dict(
            event_event_id_map=event_event_id_map,
            job_id_data_map=job_id_data_map,
            invariant_name_data_map=invaraint_name_data_map
        )
        fields_to_check = [
            "jobId", "jobName", "eventType", "applicationName", "Y"
        ]
        check_dict_equivalency(
            {
                key: value
                for key, value in event_dict.items()
                if key in fields_to_check
            },
            {
                key: value
                for key, value in input_dict.items()
                if key in fields_to_check
            }
        )
        is_uuid = bool(uuid4hex.match(
                    event_dict["X"].replace("-", "")
                ))
        assert is_uuid


class TestJob:
    """Group of tests for :class:`Job`
    """
    @staticmethod
    def test_update_missing_events() -> None:
        """Tests :class:`Job`.`update_missing_events`
        """
        job = Job()
        event = Event()
        job.update_missing_events([event])
        assert event in job.missing_events

    @staticmethod
    def test_parse_input_job_file_all_events(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests :class:`Job`.`parse_input_job_file` with all events present

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        job = Job()
        job.parse_input_jobfile(job_list)
        events = job.events
        assert len(events) == 4
        assert not job.missing_events
        assert not events[0].prev_events
        for i in [1, 2]:
            assert len(events[i].prev_events) == 1
            assert events[0] in events[i].prev_events
            assert events[i] in events[3].prev_events
        assert len(events[3].prev_events) == 2

    @staticmethod
    def test_parse_input_job_file_all_events_meta_data(
        job_list_with_meta_data: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests :class:`Job`.`parse_input_job_file` with all events present
        for meta data and invariants

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        job = Job()
        job.parse_input_jobfile(job_list_with_meta_data)
        events = job.events
        assert len(job.invariants.named_uuids) == 1
        assert "X" in job.invariants.named_uuids
        assert len(events[0].meta_data) == 2
        assert all(
            name in events[0].meta_data
            for name in ["X", "Y"]
        )
        assert len(events[0].categorised_meta_data["fixed"]) == 1
        assert len(events[0].categorised_meta_data["invariants"]) == 1
        assert "Y" in events[0].categorised_meta_data["fixed"]
        assert "X" in events[0].categorised_meta_data["invariants"]
        assert len(events[1].meta_data) == 1
        assert "X" in events[1].meta_data
        assert len(events[1].categorised_meta_data["fixed"]) == 0
        assert len(events[1].categorised_meta_data["invariants"]) == 1
        assert "X" in events[1].categorised_meta_data["invariants"]

    @staticmethod
    def test_parse_input_job_file_all_events_two_jobs(
        job_list_with_multiple_job_ids: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests :class:`Job`.`parse_input_job_file` with all events present
        for two job ids present

        :param job_list_with_multiple_job_ids: A list of event dicts in a job
        :type job_list_with_multiple_job_ids: `list`[`dict`[`str`, `str`  |
        `list`[`str`]]]
        """
        job = Job()
        job.parse_input_jobfile(job_list_with_multiple_job_ids)
        events = job.events
        assert len(events) == 4
        assert len(job.job_ids.named_uuids) == 2
        assert "1" in job.job_ids.named_uuids
        assert "2" in job.job_ids.named_uuids
        assert job.job_ids.named_uuids["1"].count == 2
        assert job.job_ids.named_uuids["2"].count == 2

    @staticmethod
    def test_parse_input_job_file_missing_event(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests :class:`Job`.`parse_input_job_file` with a missing event

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        job = Job()
        job.parse_input_jobfile(job_list[1:])
        events = job.events
        assert len(events) == 3
        assert len(job.missing_events) == 1
        assert not job.missing_events[0].prev_events
        for i in [0, 1]:
            assert len(events[i].prev_events) == 1
            assert job.missing_events[0] in events[i].prev_events
            assert events[i] in events[2].prev_events
        assert len(events[2].prev_events) == 2

    @staticmethod
    def test_create_new_event_event_id_map(
        job_list: list[dict[str, str | list[str]]]
    ) -> None:
        """Tests :class:`Job`.`create_new_event_event_id_map`

        :param job_list: A list of event dicts in a job
        :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
        """
        job = Job()
        job.parse_input_jobfile(job_list)
        event_event_id_map = job.create_new_event_event_id_map()
        assert len(event_event_id_map) == 4
        for event in job.events:
            assert id(event) in event_event_id_map
            assert isinstance(event_event_id_map[id(event)], str)


def test_generate_job_batch_events(
    job_list: list[dict[str, str | list[str]]]
) -> None:
    """Tests `generate_job_batch_events`

    :param job_list: A list of event dicts in a job
    :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
    """
    job = Job()
    job.parse_input_jobfile(job_list)
    generators = generate_job_batch_events([job])
    assert len(generators) == 1
    sim_datums = list(generators[0])
    assert len(sim_datums) == 4
    for sim_datum in sim_datums[: -1]:
        assert sim_datum.action_func == async_do_nothing
        assert not sim_datum.args
        assert not sim_datum.kwargs
    assert not sim_datums[-1].args
    assert not sim_datums[-1].action_func
    assert "list_dict" in sim_datums[-1].kwargs
    assert len(sim_datums[-1].kwargs["list_dict"]) == 4
    assert "job_info" in sim_datums[-1].kwargs
    assert "job_id" in sim_datums[-1].kwargs


def test_generate_job_batch_events_multiple_job_ids(
    job_list_with_multiple_job_ids: list[dict[str, str | list[str]]]
) -> None:
    """Tests `generate_job_batch_events` with multiple job ids in the event
    sequence

    :param job_list: A list of event dicts in a job
    :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
    """
    job = Job()
    job.parse_input_jobfile(job_list_with_multiple_job_ids)
    generators = generate_job_batch_events([job])
    assert len(generators) == 1
    sim_datums = list(generators[0])
    assert len(sim_datums) == 4
    for sim_datum in sim_datums[::2]:
        assert sim_datum.action_func == async_do_nothing
        assert not sim_datum.args
        assert not sim_datum.kwargs
    for sim_datum in sim_datums[1::2]:
        assert not sim_datum.args
        assert not sim_datum.action_func
        assert "list_dict" in sim_datum.kwargs
        assert len(sim_datum.kwargs["list_dict"]) == 2
        assert "job_info" in sim_datum.kwargs
        assert "job_id" in sim_datum.kwargs
    assert sim_datums[1].kwargs["job_id"] != sim_datums[3].kwargs["job_id"]
    assert len(set(
        event["jobId"]
        for event in sim_datums[1].kwargs["list_dict"]
    )) == 1
    assert len(set(
        event["jobId"]
        for event in sim_datums[3].kwargs["list_dict"]
    )) == 1


def test_generate_single_events(
    job_list: list[dict[str, str | list[str]]]
) -> None:
    """Tests `generate_single_events`

    :param job_list: A list of event dicts in a job
    :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
    """
    job = Job()
    job.parse_input_jobfile(job_list)
    generators = generate_single_events([job])
    assert len(generators) == 1
    sim_datums = list(generators[0])
    assert len(sim_datums) == 4
    for sim_datum in sim_datums:
        assert not sim_datum.args
        assert not sim_datum.action_func
        assert "list_dict" in sim_datum.kwargs
        assert len(sim_datum.kwargs["list_dict"]) == 1
        assert "job_info" in sim_datum.kwargs
        assert "job_id" in sim_datum.kwargs


def test_generate_single_events_multiple_job_ids(
    job_list_with_multiple_job_ids: list[dict[str, str | list[str]]]
) -> None:
    """Tests `generate_single_events` with multiple job ids in the event
    sequence

    :param job_list_with_multiple_job_ids: A list of event dicts in a job
    :type job_list_with_multiple_job_ids: `list`[`dict`[`str`, `str`  |
    `list`[`str`]]]
    """
    job = Job()
    job.parse_input_jobfile(job_list_with_multiple_job_ids)
    generators = generate_single_events([job])
    assert len(generators) == 1
    sim_datums = list(generators[0])
    assert len(sim_datums) == 4
    for sim_datum in sim_datums:
        assert not sim_datum.args
        assert not sim_datum.action_func
        assert "list_dict" in sim_datum.kwargs
        assert len(sim_datum.kwargs["list_dict"]) == 1
        assert "job_info" in sim_datum.kwargs
        assert "job_id" in sim_datum.kwargs
    job_1_ids = set(
        sim_datum.kwargs["job_id"]
        for sim_datum in sim_datums[:2]
    )
    job_2_ids = set(
        sim_datum.kwargs["job_id"]
        for sim_datum in sim_datums[2:]
    )
    assert job_1_ids != job_2_ids
    assert len(job_1_ids) == 1
    assert len(job_2_ids) == 1
    assert len(set(
        sim_datum.kwargs["list_dict"][0]["jobId"]
        for sim_datum in sim_datums[:2]
    )) == 1
    assert len(set(
        sim_datum.kwargs["list_dict"][0]["jobId"]
        for sim_datum in sim_datums[2:]
    )) == 1


def test_simple_sequencer(
    list_generated_sim_datum: list[Generator[SimDatum, Any, None]]
) -> None:
    """Tests `simple_sequencer`

    :param list_generated_sim_datum: Fixture providing a list of generators of
    :class:`SimDatum``s
    :type list_generated_sim_datum:
    `list`[:class:`Generator`[:class:`SimDatum`, `Any`, `None`]]
    """
    result = list(simple_sequencer(
            list_generated_sim_datum
        ))
    for sim_datum, expected_args in zip(
        result,
        ["a", "b", "aa", "bb", "aaa", "bbb"]
    ):
        assert isinstance(sim_datum, SimDatum)
        assert len(sim_datum.args) == 1
        assert sim_datum.args[0] == expected_args


def test_job_sequencer(
    list_generated_sim_datum: list[Generator[SimDatum, Any, None]]
) -> None:
    """Tests `job_sequencer`

    :param list_generated_sim_datum: Fixture providing a list of generators of
    :class:`SimDatum``s
    :type list_generated_sim_datum:
    `list`[:class:`Generator`[:class:`SimDatum`, `Any`, `None`]]
    """
    generated_sequence = job_sequencer(
        generated_events=list_generated_sim_datum,
        min_interval_between_job_events=1,
        desired_job_event_gap=2
    )

    result = list(generated_sequence)
    for sim_datum, expected_args in zip(
        result,
        ["a", "aa", "b", "bb", "aaa", "bbb"]
    ):
        assert isinstance(sim_datum, SimDatum)
        assert len(sim_datum.args) == 1
        assert sim_datum.args[0] == expected_args


def test_generate_events_from_template_jobs_job_batch(
    job_list: list[dict[str, str | list[str]]]
) -> None:
    """Tests `generate_events_from_template_jobs` for a job batch

    :param job_list: A list of event dicts in a job
    :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
    """
    job = Job()
    job.parse_input_jobfile(job_list)
    jobs = [
        deepcopy(job)
        for _ in range(4)
    ]
    generated_sim_data = generate_events_from_template_jobs(
        jobs,
        job_sequencer,
        generate_job_batch_events,
        sequencer_kwargs={
            "min_interval_between_job_events": 0.5,
            "desired_job_event_gap": 1.0
        }
    )
    sim_data = list(generated_sim_data)
    assert all(
        (
            isinstance(sim_datum, SimDatum)
            and not sim_datum.args and not sim_datum.kwargs
            and sim_datum.action_func == async_do_nothing
        )
        for index, sim_datum in enumerate(sim_data)
        if index not in [6, 7, 14, 15]
    )
    assert all(
        (
            isinstance(sim_datum, SimDatum)
            and not sim_datum.args
            and not sim_datum.action_func
            and "list_dict" in sim_datum.kwargs
            and len(sim_datum.kwargs["list_dict"]) == 4
            and isinstance(sim_datum.kwargs["list_dict"], list)
            and all(
                isinstance(event, dict)
                for event in sim_datum.kwargs["list_dict"]
            )
        )
        for index, sim_datum in enumerate(sim_data)
        if index in [6, 7, 14, 15]
    )


def test_convert_list_dict_to_json_io_bytes(
    job_list: list[dict[str, str | list[str]]]
) -> None:
    """Tests `convert_list_dict_to_json_io_bytes`

    :param job_list: A list of event dicts in a job
    :type job_list: `list`[`dict`[`str`, `str`  |  `list`[`str`]]]
    """
    io_bytes = convert_list_dict_to_json_io_bytes(
        job_list
    )
    assert isinstance(io_bytes, BytesIO)
    json_string = io_bytes.read().decode("utf-8")
    json_dicts = json.loads(json_string)
    for event_actual, event_expected in zip(
        json_dicts, job_list
    ):
        check_dict_equivalency(
            event_actual,
            event_expected
        )
