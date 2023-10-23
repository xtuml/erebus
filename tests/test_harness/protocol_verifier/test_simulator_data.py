# pylint: disable=W0212
# pylint: disable=W0143
# pylint: disable=R0903
"""Test simulation_data.py
"""
from io import BytesIO
from typing import Generator, Any
from copy import copy, deepcopy
import json

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
    generate_job_batch_events,
    generate_single_events,
    simple_sequencer,
    job_sequencer,
    generate_events_from_template_jobs,
    convert_list_dict_to_json_io_bytes
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
        event_dict = events[0].make_event_dict(
            event_event_id_map=event_event_id_map,
            job_id=job_id
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
        event_dict = events[1].make_event_dict(
            event_event_id_map=event_event_id_map,
            job_id=job_id
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
        event_dict = events[-1].make_event_dict(
            event_event_id_map=event_event_id_map,
            job_id=job_id
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
        event_dict = events[-1].make_event_dict(
            event_event_id_map=event_event_id_map,
            job_id=job_id
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