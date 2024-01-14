# pylint: disable=R0902
# pylint: disable=R0903
# pylint: disable=R0913
# pylint: disable=R1708
"""Methods to create simulator data
"""
from __future__ import annotations
from typing import (
    Generator, Any, Callable, Awaitable, TypedDict, Literal, Iterable
)
import json
from uuid import uuid4
from datetime import datetime
import logging
import itertools
from abc import ABC, abstractmethod
import asyncio

import aiohttp
from aiokafka import AIOKafkaProducer
from kafka3 import KafkaProducer

from test_harness.jobs.job_delivery import send_payload_async
from test_harness.simulator.simulator import SimDatum, Batch, async_do_nothing
from test_harness.protocol_verifier.types import TemplateOptions
from test_harness.utils import wrap_kafka_future


class PVSimDatumTransformer(ABC):
    """Base abstract class to provide a base for transforming PV list of event
    dicts to a generator of :class:`SimDatum`
    """

    @abstractmethod
    def get_sim_datum(
        self, event: list[dict], job_info: dict[str, str | bool]
    ) -> Generator[SimDatum, Any, None]:
        """Abstract method to generate sim datums

        :param event: Takes a list of a single event dict as input
        :type event: `list`[`dict`]
        :param job_info: Dictionary of job info
        :type job_info: `dict`[`str`, `str` | `bool`]
        :yield: Generates a single :class:`SimDatum`
        """


class EventSimDatumTransformer(PVSimDatumTransformer):
    """Subclass to provide a transformation from PV list of event
    dicts to a generator of :class:`SimDatum`
    """

    def get_sim_datum(
        self, event: list[dict], job_info: dict[str, str | bool]
    ) -> Generator[SimDatum, Any, None]:
        """Method to generate sim datums for a single event

        :param event: Takes a list of a single event dict as input
        :type event: `list`[`dict`]
        :param job_info: Dictionary of job info
        :type job_info: `dict`[`str`, `str` | `bool`]
        :yield: Generates a single :class:`SimDatum`
        """
        job_id = event[0]["jobId"]
        yield SimDatum(
            kwargs={"list_dict": event, "job_id": job_id, "job_info": job_info}
        )


class BatchJobSimDatumTransformer(PVSimDatumTransformer):
    """Subclass of SimDatumTransformer to get the correct :class:`SimDatum`'s
    when jobs are batched together
    """

    def __init__(self) -> None:
        """Constructor method"""
        self.batch_jobs: dict[str, Batch] = {}

    def get_sim_datum(
        self, event: list[dict], job_info: dict[str, str | bool]
    ) -> Generator[SimDatum, Any, None]:
        """Method to generate the sim datums. Will continue to batch events
        until the correct batch number for the job (i.e. the number of events
        in the job) is given

        :param event: Takes a list of a single event dict as input
        :type event: `list`[`dict`]
        :param job_info: Dictionary of job info
        :type job_info: `dict`[`str`, `str` | `bool`]
        :yield: Generates a single :class:`SimDatum` that has either of the
        following structures:
        * `SimDatum(args=[], kwargs={}, action_func=async_do_nothing)` if the
        event is not the end event of the job
        * `SimDatum(args=[], kwargs={"list_dict": [<list of all job events>]},
        action_func=async_do_nothing)` if the event is the end event of the job
        :rtype: :class:`Generator`[:class:`SimDatum`, `Any`, `None`]
        """
        job_id = event[0]["jobId"]
        if self.batch_jobs[job_id].update_batcher(event):
            yield SimDatum(
                kwargs={
                    "list_dict": self.batch_jobs[job_id].batch_output,
                    "job_id": job_id,
                    "job_info": job_info,
                }
            )
        else:
            yield SimDatum(action_func=async_do_nothing)

    def initialise_batch(self, job_id: str, length: int) -> None:
        """Method to initialise a batch for a given job id and batch length

        :param job_id: Unique job identifier
        :type job_id: `str`
        :param length: The length of the batch i.e. the number of events in
        the job
        :type length: `int`
        """
        self.batch_jobs[job_id] = Batch(
            length=length,
            batch_concat=lambda x: list(itertools.chain.from_iterable(x)),
        )


def generate_events_from_template_jobs(
    template_jobs: list["Job"],
    sequence_generator: Callable[
        [Iterable[Generator[SimDatum, Any, None]]],
        Generator[SimDatum, Any, None]
    ],
    generator_function: Callable[
        [list["Job"]], Iterable[Generator[SimDatum, Any, None]]
    ],
    sequencer_kwargs: dict[str, Any] | None = None,
) -> Generator[SimDatum, Any, None]:
    """Method to generate the :class:`SimDatum` data from template jobs

    :param template_jobs: Template jobs used to create the test data
    :type template_jobs: `list`[:class:`Job`]
    :param sequence_generator: A function that will sequence the generated
    simulation data into a :class:`Generator` of :class:`SimDatum`
    :type sequence_generator: :class:`Callable`[
    [`list`[:class:`Generator`[:class:`SimDatum`, `Any`, `None`]]],
    :class:`Generator`[:class:`SimDatum`, `Any`, `None`] ]
    :param generator_function: A function that generates the required list of
    job :class:`SimDatum`'s
    :type generator_function: :class:`Callable`[ [`list`[:class:`Job`]],
    `list`[:class:`Generator`[:class:`SimDatum`, `Any`, `None`]] ]
    :param sequencer_kwargs: Keyword arguments for the sequencer, defaults to
    `None`
    :type sequencer_kwargs: `dict`[`str`, `Any`] | `None`, optional
    :yield: Generates :class:`SimDatum`'s for the simulator
    :rtype: :class:`Generator`[:class:`SimDatum`, `Any`, `None`]
    """
    if not sequencer_kwargs:
        sequencer_kwargs = {}
    generated_events = generator_function(template_jobs)
    yield from sequence_generator(generated_events, **sequencer_kwargs)


def generate_job_batch_events(
    template_jobs: list["Job"],
) -> Generator[Generator[SimDatum, Any, None], Any, None]:
    """Method to generate job batch :class:`SimDatum`'s using
    :class:`BatchJobSimDatumTransformer`

    :param template_jobs: A list of the template jobs with which to generate
    the sim data
    :type template_jobs: `list`[:class:`Job`]
    :return: Returns a list of :class:`Generator`'s of :class:`SimDatum` for
    each job
    :rtype: `list`[:class:`Generator`[:class:`SimDatum`, `Any`, `None`]]
    """
    sim_datum_transformer = BatchJobSimDatumTransformer()
    generators = []
    for job in template_jobs:
        job_id_data_map = job.create_job_id_data_map()
        for job_id, named_job_id in job.job_ids.named_uuids.items():
            sim_datum_transformer.initialise_batch(
                job_id=job_id_data_map[job_id].get_data(),
                length=named_job_id.count,
            )
        yield job.generate_simulation_job_events(
            job_id_data_map=job_id_data_map,
            sim_datum_transformer=sim_datum_transformer,
        )
    return generators


def generate_single_events(
    template_jobs: list["Job"],
) -> Generator[Generator[SimDatum, Any, None], Any, None]:
    """Method to generate non-batched single events

    :param template_jobs: A list of the template jobs with which to generate
    the sim data
    :type template_jobs: `list`[:class:`Job`]
    :return: Returns an iterable of :class:`Generator`'s of :class:`SimDatum`
    for each job
    :rtype: `list`[:class:`Generator`[:class:`SimDatum`, `Any`, `None`]]
    """
    sim_datum_transformer = EventSimDatumTransformer()
    generators = []
    for job in template_jobs:
        job_id_data_map = job.create_job_id_data_map()
        yield job.generate_simulation_job_events(
            job_id_data_map=job_id_data_map,
            sim_datum_transformer=sim_datum_transformer,
        )
    return generators


def simple_sequencer(
    generated_events: Iterable[Generator[SimDatum, Any, None]]
) -> Generator[SimDatum, Any, None]:
    """A simple sequencer that flattens an iterable of generators of
    :class:`SimDatum`

    :param generated_events: An iterable of generated :class:`SimDatum`
    :type generated_events:
    :class:`Iterable`[:class:`Generator`[:class:`SimDatum`, `Any`, `None`]]
    :yield: Generates :class:`SimDatum`
    :rtype: :class:`Generator`[:class:`SimDatum`, `Any`, `None`]
    """
    for generator_of_events in generated_events:
        yield from generator_of_events


def job_sequencer(
    generated_events: Iterable[Generator[SimDatum, Any, None]],
    min_interval_between_job_events: float,
    desired_job_event_gap: float = 1.0,
) -> Generator[SimDatum, Any, None]:
    """Method to sequence jobs so that the events in each job have a desired
    gap (in seconds
    between them). This won't guarentee that the final sequenced events will
    have the gap but for numbers of events much larger than the maximum rate
    this will be good enough.

    This method assumes a job has at least 1 event.

    :param generated_events: Iterable of generated :class:`SimDatum` for jobs
    :type generated_events:
    :class:`Iterable`[:class:`Generator`[:class:`SimDatum`, `Any`, `None`]]
    :param min_interval_between_job_events: The minimum interval between jobs
    in the input profile
    :type min_interval_between_job_events: `float`
    :param desired_job_event_gap: The desired gap in seconds between events in
    the same job, defaults to `1.0`
    :type desired_job_event_gap: `float`, optional
    :yield: Generates :class:`SimDatums`'s
    :rtype: :class:`Generator`[:class:`SimDatum`, `Any`, `None`]
    """
    ratio = desired_job_event_gap / min_interval_between_job_events
    if ratio < 1.5:
        logging.getLogger().warning(
            "Ratio of desired job event gap and the minium interval between "
            "events is less than 1.5 (rounded down to 1) so jobs will be "
            "placed in order"
        )
    rate = round(ratio)
    chunk_generated_events = []
    iterator_generated_events = iter(generated_events)
    # fill up the chunk of generated events
    while True:
        if len(chunk_generated_events) < rate:
            try:
                chunk_generated_events.append(next(iterator_generated_events))
                continue
            except StopIteration:
                break
        else:
            break
    continue_bool = True
    indexes = {
        index: True
        for index in range(len(chunk_generated_events))
    }
    while continue_bool:
        for index in indexes.keys():
            try:
                yield next(chunk_generated_events[index])
            except StopIteration:
                try:
                    chunk_generated_events[index] = next(
                        iterator_generated_events
                    )
                    yield next(chunk_generated_events[index])
                except StopIteration:
                    indexes[index] = False
                    if all(
                        not truth_value for truth_value in indexes.values()
                    ):
                        continue_bool = False


def convert_list_dict_to_json_io_bytes(
    list_dict: list[dict[str, Any]]
) -> list[bytes]:
    """Method to convert a list of dicts into list with containing a single
    :class:`bytes`

    :param list_dict: The list of dictionaries
    :type list_dict: `list`[`dict`[`str`, `Any`]]
    :return: Returns the :class:`bytes` instance
    :rtype: `list`[:class:`bytes`]
    """
    io_bytes = json.dumps(list_dict, indent=4).encode("utf8")
    return [io_bytes]


def convert_list_dict_to_pv_json_io_bytes(
    list_dict: list[dict[str, Any]]
) -> list[bytes]:
    """Method to convert a list of dicts into a list of :class:`bytes` for
    each event suitable for ingestion directly by the PV

    :param list_dict: The list of dictionaries
    :type list_dict: `list`[`dict`[`str`, `Any`]]
    :return: Returns the :class:`bytes` instance
    :rtype: `list`[:class:`bytes`]
    """
    io_bytes_list = []
    for event in list_dict:
        pay_load = json.dumps(event).encode("utf8")
        msg_len = len(pay_load).to_bytes(4, byteorder="big")
        io_bytes = msg_len + pay_load
        io_bytes_list.append(io_bytes)
    return io_bytes_list


def send_list_dict_as_json_wrap_url(
    url: str,
    session: aiohttp.ClientSession | None = None,
    list_dict_converter: Callable[[list[dict[str, Any]]], list[bytes]] = (
        convert_list_dict_to_json_io_bytes
    ),
) -> Callable[
    [str],
    Callable[
        [list[dict[str, Any]]], Awaitable[tuple[list[dict[str, Any]], str]]
    ],
]:
    """Closure to provide an asynchronous function given an input url

    :param url: The url to use for requests
    :type url: `str`
    :param session: The session for HTTP requests, defaults to `None`
    :type session: `aiohttp`.`ClientSession` | `None`, optional
    :param list_dict_converter: The function to convert a list of dicts to
    a list of :class:`bytes`, defaults to
    :func:`convert_list_dict_to_json_io_bytes`
    :type list_dict_converter: :class:`Callable`[ [`list`[`dict`[`str`,
    `Any`]]], `list`[:class:`bytes`] ], optional
    :return: Returns an asynchrcnous function for sending list dictionaries
    as json packets
    :rtype: :class:`Callable`[ [`list`[`dict`[`str`, `Any`]]],
    :class:`Awaitable`[`tuple`[`list`[`dict`[`str`, `Any`]], `str`]] ]
    """

    async def send_list_dict_as_json(
        list_dict: list[dict[str, Any]],
        job_id: str,
        job_info: dict[str, str | None],
    ) -> tuple[
        list[dict[str, Any]], str, str, dict[str, str | None], str, datetime
    ]:
        """Async method to send a list of dicts as a json payload

        :param list_dict: The list of dictionaries
        :type list_dict: `list`[`dict`[`str`, `Any`]]
        :param url: The url to send the payload to
        :type url: `str`
        :return: Returns a tuple of:
        * the list of dicts sent
        * the file name given
        * the result of the request
        :rtype: `tuple`[`list`[`dict`[`str`, `Any`]], `str`, `str`,
        :class:`datetime`]
        """
        files = list_dict_converter(list_dict)
        file_names = [str(uuid4()) + ".json" for _ in range(len(files))]
        results = await asyncio.gather(
            *[
                send_payload_async(
                    file=file,
                    file_name=file_name_sent,
                    url=url,
                    session=session,
                )
                for file, file_name_sent in zip(files, file_names)
            ]
        )
        time_completed = datetime.now()
        file_name = str(uuid4()) + ".json"
        result = "".join(results)
        return list_dict, file_name, job_id, job_info, result, time_completed

    return send_list_dict_as_json


def send_list_dict_as_json_wrap_send_function(
    send_function: Callable[[Any, Any], Awaitable[str]],
    list_dict_converter: Callable[[list[dict[str, Any]]], list[bytes]] = (
        convert_list_dict_to_json_io_bytes
    ),
    **send_kwargs: Any,
) -> Callable[
    [str],
    Callable[
        [list[dict[str, Any]]], Awaitable[tuple[list[dict[str, Any]], str]]
    ],
]:
    """Closure to provide an asynchronous function given an input url

    :param send_function: The function to send the payload
    :type send_function: :class:`Callable`[ [`Any`, `Any`], `Awaitable`[`str`]
    :param list_dict_converter: The function to convert a list of dicts to
    a list of :class:`bytes`, defaults to
    :func:`convert_list_dict_to_json_io_bytes`
    :type list_dict_converter: :class:`Callable`[ [`list`[`dict`[`str`,
    `Any`]]], `list`[:class:`bytes`] ], optional
    :param send_kwargs: Keyword arguments for the send function
    :type send_kwargs: `Any`
    :return: Returns an asynchrcnous function for sending list dictionaries
    as json packets
    :rtype: :class:`Callable`[ [`list`[`dict`[`str`, `Any`]]],
    :class:`Awaitable`[`tuple`[`list`[`dict`[`str`, `Any`]], `str`]] ]
    """

    async def send_list_dict_as_json(
        list_dict: list[dict[str, Any]],
        job_id: str,
        job_info: dict[str, str | None],
    ) -> tuple[
        list[dict[str, Any]], str, str, dict[str, str | None], str, datetime
    ]:
        """Async method to send a list of dicts as a json payload

        :param list_dict: The list of dictionaries
        :type list_dict: `list`[`dict`[`str`, `Any`]]
        :param url: The url to send the payload to
        :type url: `str`
        :return: Returns a tuple of:
        * the list of dicts sent
        * the file name given
        * the result of the request
        :rtype: `tuple`[`list`[`dict`[`str`, `Any`]], `str`, `str`,
        :class:`datetime`]
        """
        files = list_dict_converter(list_dict)
        file_names = [str(uuid4()) + ".json" for _ in range(len(files))]
        results = await asyncio.gather(
            *[
                send_function(file, file_name_sent, **send_kwargs)
                for file, file_name_sent in zip(files, file_names)
            ]
        )
        time_completed = datetime.now()
        file_name = str(uuid4()) + ".json"
        result = "".join(results)
        return list_dict, file_name, job_id, job_info, result, time_completed

    return send_list_dict_as_json


async def send_payload_kafka(
    file: bytes,
    file_name: str,
    kafka_producer: KafkaProducer,  # AIOKafkaProducer,
    kafka_topic: str,
) -> Literal["", "KafkaTimeoutError"]:
    """Async method to send a payload to a kafka producer

    :param file: The file to send
    :type file: :class:`bytes`
    :param producer: The kafka producer
    :type producer: :class:`KafkaProducer`
    """
    try:
        await wrap_kafka_future(
            kafka_producer.send(topic=kafka_topic, value=file)
        )
        # future = kafka_producer.send(topic=kafka_topic, value=file)
        # while not future.is_done:
        #     await asyncio.sleep(0.001)
        # # await kafka_producer.send_and_wait(topic=kafka_topic, value=file)
        # future.get()
        result = ""
        logging.getLogger().debug(
            f"Sent file {file_name} payload to kafka topic {kafka_topic}"
        )
    except Exception as error:
        logging.getLogger().warning(
            "Error sending payload to kafka: %s", error
        )
        result = str(error)
    return result


class MetaDataCategory(TypedDict):
    """Dictionary for categories of event meta data"""

    invariants: dict[str, str]
    """Set of meta data names
    """
    fixed: dict[str, Any]
    """Dictionary of meta data name mapped to any value but string
    """


class Event:
    """Class to hold data and links pertaining to Protocol Verifier Events.

    :param job: The job this event belongs to, defaults to `None`
    :type job: :class:`Job`, optional
    :param job_name: Name of the job this event belongs to, defaults to ""
    :type job_name: `str`, optional
    :param job_id: The job's unique hex ID, defaults to ""
    :type job_id: `str`, optional
    :param event_type: Type of event, defaults to ""
    :type event_type: `str`, optional
    :param event_id: This event's unique hex ID, defaults to ""
    :type event_id: `str`, optional
    :param timestamp: Time e.g. 2023-04-27T08:13:56Z, defaults to ""
    :type timestamp: `str`, optional
    :param application_name: Name of job's application, defaults to ""
    :type application_name: `str`, optional
    :param previous_event_ids: IDs of previous events, defaults to ""
    :type previous_event_ids: `list[str]`, optional
    :param meta_data: Any meta data attached to event, defaults to `None`
    :type meta_data: `dict`[`str`, `Any`], optional

    """

    attribute_mappings = {
        "jobName": "job_name",
        "jobId": "job_id",
        "eventType": "event_type",
        "eventId": "event_id",
        "timestamp": "time_stamp",
        "applicationName": "application_name",
        "previousEventIds": "previous_event_ids",
    }

    def __init__(
        self,
        job: Job | None = None,
        job_name: str | None = None,
        job_id: str | None = None,
        event_type: str | None = None,
        event_id: str | None = None,
        time_stamp: str | None = None,
        application_name: str | None = None,
        previous_event_ids: str | list[str] | None = None,
        meta_data: dict[str, Any] | None = None,
    ) -> None:
        """Constructor method"""
        if job is None:
            job = Job()
        self.job = job
        self.job_name = job_name
        self.job_id = job_id
        self.event_type = event_type
        self.event_id = event_id
        self.time_stamp = time_stamp
        self.application_name = application_name
        self.previous_event_ids = (
            previous_event_ids if previous_event_ids is not None else []
        )
        self.categorised_meta_data = meta_data if meta_data else {}
        self.prev_events = []

    def parse_from_input_dict(
        self, input_dict: dict[str, str | list[str], dict]
    ) -> None:
        """Updates the instances attributes given an input dictionary

        :param input_dict: The incoming dict with key-value pairs
        :type input_dict: `dict`[`str`, `str` | `list`[`str`], `dict`]
        """
        for field, attribute in self.attribute_mappings.items():
            if field == "previousEventIds" and field not in input_dict:
                attribute_value = []
            elif field not in input_dict:
                continue
            else:
                attribute_value = input_dict.pop(field)
            if field == "jobId":
                self.job.job_ids.update(attribute_value)
            setattr(self, attribute, attribute_value)
        self.categorised_meta_data = input_dict

    @property
    def meta_data(self) -> dict[str, Any]:
        """Property defining meta data

        :return: Returns a dictionary of the meta data
        :rtype: `dict`[`str`, `Any`]
        """
        return {
            **self.categorised_meta_data["fixed"],
            **self.categorised_meta_data["invariants"],
        }

    @property
    def categorised_meta_data(self) -> MetaDataCategory:
        """Property getter for meta data on the instance

        :return: Returns a dictionary of the categorised meta data using
        :rtype: :class:`MetaDataCategory`
        """
        return self._categorised_meta_data

    @categorised_meta_data.setter
    def categorised_meta_data(self, input_dict: dict[str, Any]) -> None:
        """Property setter for meta data from an input meta data dictionary
        from a template. Uses :class:`categorise_meta_data` to categorise the
        input

        :param input_dict: The input meta data dictionary
        :type input_dict: `dict`[`str`, `Any`]
        """
        self._categorised_meta_data = self.categorise_meta_data(
            input_dict, self.job.invariants
        )

    @staticmethod
    def categorise_meta_data(
        input_dict: dict[str, Any], invariant_store: NamedUUIDStore
    ) -> MetaDataCategory:
        """Method to categorise data within a given input dictionary into:
        * fixed - entries whose value is not a string
        * random_string - entries whose value is a string

        :param input_dict: The input dictionary with values to categorise
        :type input_dict: `dict`[`str`, `Any`]
        :param invariant_store: The invariant store in which to store
        invariants
        :type invariant_store: :class:`NamedUUIDStore`
        :return: Returns a dictionary with the categorised values and keys
        :rtype: :class:`MetaDataCategory`
        """
        categories = MetaDataCategory(invariants={}, fixed={})
        for meta_data_name, meta_data_value in input_dict.items():
            if isinstance(meta_data_value, str):
                invariant_store.update(meta_data_name)
                categories["invariants"][meta_data_name] = meta_data_value
            else:
                if isinstance(meta_data_value, dict):
                    # here as a fix for the fact that the
                    # loop counts and branch counts are now parsed differently
                    # should maybe introduce backwards compatibility flag
                    if "value" in meta_data_value:
                        meta_data_value = meta_data_value["value"]
                categories["fixed"][meta_data_name] = meta_data_value
        return categories

    @staticmethod
    def generate_meta_data(
        categorised_meta_data: MetaDataCategory,
        invariant_name_data_map: dict[str, str],
    ) -> dict[str, Any]:
        """Method to generate a meta data dictionary from a categorised meta
        data dictionary. If an entry is classed as "invariant" then the
        output meta data will have a random uuid4 produced for that entry
        using the invariant_name_data_map.
        Otherwise the value of the entry will be used.

        :param categorised_meta_data: Categorised meta data
        :type categorised_meta_data: :class:`MetaDataCategory`
        :param invariant_name_data_map: The map from invariant name to
        randomised invariant data
        :type invariant_name_data_map: `dict`[`str`, `str`]
        :return: Returns a dictionary with values for the meta data
        :rtype: `dict`[`str`, `Any`]
        """
        meta_data = {**categorised_meta_data["fixed"]}
        for name in categorised_meta_data["invariants"]:
            meta_data[name] = invariant_name_data_map[name].get_data()
        return meta_data

    def has_previous_event_id(self) -> bool:
        """Checks whether an event's previous_event_ids is populated

        :return: true if there are previous event ids, false otherwise
        :rtype: boolean
        """
        if self.previous_event_ids:
            return True
        return False

    def link_prev_events(
        self, event_id_map: dict[str, "Event"]
    ) -> list["Event"]:
        """Method to link to previous events. Finds missing events that are in
        previous event ids but not in event id map and creates and updates the
        event id map

        :param event_id_map: An event id map that provides a map from the
        event id to the :class:`Event` object
        :type event_id_map: `dict`[`str`, :class:`Event`]
        :return: Produces a list of missing events that were not found in
        event id map
        :rtype: `list`[:class:`Event`]
        """
        missing_events: list[Event] = []
        if isinstance(self.previous_event_ids, str):
            self.add_prev_event(
                prev_event_id=self.previous_event_ids,
                event_id_map=event_id_map,
                missing_events=missing_events,
            )
        else:
            for prev_event_id in self.previous_event_ids:
                self.add_prev_event(
                    prev_event_id=prev_event_id,
                    event_id_map=event_id_map,
                    missing_events=missing_events,
                )
        return missing_events

    def add_prev_event(
        self,
        prev_event_id: str,
        event_id_map: dict[str, "Event"],
        missing_events: list["Event"],
    ) -> None:
        """Method to add a an event to the attribute `prev_events`. Updates a
        `missing_events` list with newly created events that were not found in
        the `event_id_map`. Also updates `event_id_map` with the event

        :param prev_event_id: The id of the previous event to add
        :type prev_event_id: `str`
        :param event_id_map: The event id map to look up the event id
        :type event_id_map: `dict`[`str`, :class:`Event`]
        :param missing_events: A list of missing events to update
        :type missing_events: `list`[:class:`Event`]
        """
        if prev_event_id not in event_id_map:
            missing_event = Event()
            missing_events.append(missing_event)
            event_id_map[prev_event_id] = missing_event
        self.prev_events.append(event_id_map[prev_event_id])

    def make_event_dict(
        self,
        event_event_id_map: dict[int, str],
        job_id_data_map: dict[str, UUIDString],
        invariant_name_data_map: dict[str, UUIDString],
    ) -> dict[str, str | list | dict]:
        """Method to generate an event dict with an event to event id map and
        given job id

        :param event_event_id_map: The map from the `id` call of an event
        (producing a unique integer) to the event id
        :type event_event_id_map: `dict`[`int`, `str`]
        :param job_id_data_map: The map from job id to randomised job id as a
        `UUIDString` class
        :type job_id_data_map: `dict`[`str`, :class:`UUIDString`]
        :param invariant_name_data_map: The map from invariant name to
        randomised invariant data as a `UUIDString` class
        :type invariant_name_data_map: `dict`[`str`, `UUIDString`]
        :return: Returns a dictionary of the event dict
        :rtype: `dict`[`str`, `str` | `list` | `dict`]
        """
        job_id = job_id_data_map[self.job_id].get_data()
        event_dict = {
            field: attr
            for field, attr in zip(
                ["jobName", "eventType", "applicationName"],
                [self.job_name, self.event_type, self.application_name],
            )
            if attr is not None
        }
        if self.time_stamp is not None:
            event_dict["timestamp"] = (
                datetime.utcnow().isoformat(timespec="seconds") + "Z"
            )
        event_dict = {
            **event_dict,
            "jobId": job_id,
            "eventId": event_event_id_map[id(self)],
        }
        if self.has_previous_event_id():
            event_dict["previousEventIds"] = [
                event_event_id_map[id(prev_event)]
                for prev_event in self.prev_events
            ]
        # add meta data if it exists
        event_dict = {
            **event_dict,
            **self.generate_meta_data(
                self.categorised_meta_data, invariant_name_data_map
            ),
        }
        return event_dict

    def generate_simulation_event_dict(
        self,
        event_event_id_map: dict[int, str],
        job_id_data_map: dict[str, UUIDString],
        sim_datum_transformer: PVSimDatumTransformer,
        invariant_name_data_map: dict[str, UUIDString],
    ) -> Generator[SimDatum, Any, None]:
        """Method to generate a :class:`SimDatum` from an event dict

        :param event_event_id_map: The map from the `id` call of an event
        (producing a unique integer) to the event id
        :type event_event_id_map: `dict`[`int`, `str`]
        :param job_id_data_map: The map from job id to randomised job id as a
        `UUIDString` class
        :type job_id_data_map: `dict`[`str`, :class:`UUIDString`]
        :param sim_datum_transformer: The arbitrary transformer class to
        transform the data into the required :class:`SimDatum` to generate
        :type sim_datum_transformer: :class:`SimDatumTransformer`
        :param invariant_name_data_map: The map from invariant name to
        randomised invariant data
        :type invariant_name_data_map: `dict`[`str`, `str`]
        :yield: Generates the :class:`SimDatum` for the event
        :rtype: :class:`Generator`[:class:`SimDatum`, `Any`, `None`]
        """
        event_dict = self.make_event_dict(
            event_event_id_map=event_event_id_map,
            job_id_data_map=job_id_data_map,
            invariant_name_data_map=invariant_name_data_map,
        )
        try:
            yield from sim_datum_transformer.get_sim_datum(
                event=[event_dict], job_info=self.job.job_info
            )
        except AttributeError as error:
            logging.getLogger().error(
                "The event job has not been set and is required for job info"
            )
            raise error


class UUIDString(ABC):
    """Abstract class to hold a UUID string"""

    def __init__(
        self,
        length: int = 1,
    ) -> None:
        """Constructor method"""
        self.length = length

    @abstractmethod
    def get_data(self) -> str:
        """Method to get a randomised string

        :return: Returns a randomised string
        :rtype: `str`
        """
        pass


class MatchedUUIDString(UUIDString):
    """Class to hold a UUID string that is the same
    each time `get_data` is called

    :param length: the number of lengths of the standard uuid to set the
    string, defaults to 1
    :type length: `int`, optional
    """
    def __init__(
        self,
        length: int = 1,
    ) -> None:
        """Constructor method
        """
        super().__init__(length=length)
        self._uuid = str(uuid4()) * self.length

    def get_data(self) -> str:
        """Method to get a randomised string

        :return: Returns a randomised string
        :rtype: `str`
        """
        return self._uuid


class UnmatchedUUIDString(UUIDString):
    """Class to hold a UUID string that is different each time `get_data` is
    called

    :param length: the number of lengths of the standard uuid to set the
    string, defaults to 1
    :type length: `int`, optional
    """
    def __init__(
        self,
        length: int = 1,
    ) -> None:
        """Constructor method"""
        super().__init__(length=length)

    def get_data(self) -> str:
        """Method to get a randomised string

        :return: Returns a randomised string
        :rtype: `str`
        """
        return str(uuid4()) * self.length


class NamedUUID:
    """Class to hold named uuid and create a randomised data when requested"""

    def __init__(
        self, name: str, length: int = 1, matched_uuids: bool = True
    ) -> None:
        """_summary_

        :param name: The name of the uuid
        :type name: `str`
        :param length: the number of lengths of the standard uuid to set the
        string, defaults to 1
        :type length: `int`, optional
        :param matched_uuids: Boolean indicating whether the uuids will be
        matched or unmatched, defaults to True
        :type matched_uuids: `bool`, optional
        """
        self.name = name
        self.length = length
        self.matched_uuids = matched_uuids
        self._counter = 0

    def create_random_data(self) -> UUIDString:
        """Method to create a uuid string class

        :return: Returns a uuid string class
        :rtype: :class:`UUIDString`
        """
        if self.matched_uuids:
            return MatchedUUIDString(length=self.length)
        else:
            return UnmatchedUUIDString(length=self.length)

    def update_counter(self) -> None:
        """Method to update the counter"""
        self._counter += 1

    @property
    def count(self) -> int:
        """Property to get the count of the instance

        :return: Returns the count
        :rtype: `int`
        """
        return self._counter


class NamedUUIDStore:
    """Class to store named UUID and create random data"""

    def __init__(
        self, matched_uuids: bool = True, uuid_lengths: int = 1
    ) -> None:
        """Constructor method"""
        self.named_uuids: dict[str, NamedUUID] = {}
        self.matched_uuids = matched_uuids
        self.uuid_lengths = uuid_lengths

    def update(self, name: str) -> NamedUUID:
        """Method to update named uuids given a name

        :param name: The name of the named uuid
        :type name: `str`
        :return: Returns the named uuid mapped to the name
        :rtype: :class:`NamedUUID`
        """
        if name not in self.named_uuids:
            self.named_uuids[name] = NamedUUID(
                name, self.uuid_lengths, self.matched_uuids
            )
        self.named_uuids[name].update_counter()
        return self.named_uuids[name]

    def create_name_data_map(self) -> dict[str, UUIDString]:
        """Creates a map from named UUID to a randomised uuid4

        :return: Returns the map of named UUID to uuid4
        :rtype: `dict`[`str`, :class:`UUIDString`]
        """
        return {
            name: named_uuid.create_random_data()
            for name, named_uuid in self.named_uuids.items()
        }


class Job:
    """Describes a group of related events, contains proccessing them"""

    def __init__(
        self,
        job_info: dict[str, str | bool] | None = None,
        job_options: TemplateOptions | None = None,
    ) -> None:
        """Constructor method"""
        self.events: list[Event] = []
        self.missing_events: list[Event] = []
        self.job_info = job_info
        self.template_options = (
            TemplateOptions() if job_options is None else job_options
        )
        self.invariants = NamedUUIDStore(
            matched_uuids=self.template_options.invariant_matched,
            uuid_lengths=self.template_options.invariant_length,
        )
        self.job_ids = NamedUUIDStore()

    def create_job_id_data_map(self) -> dict[str, UUIDString]:
        """Creates a map from job id to a randomised uuid4

        :return: Returns the map of job id to uuid4
        :rtype: `dict`[`str`, `str`]
        """
        return self.job_ids.create_name_data_map()

    @property
    def job_info(self) -> dict[str, str | bool]:
        """Property to get the job info of the instance

        :return: Returns the job info
        :rtype: `dict`[`str`, `str` | `bool`]
        """
        return self._job_info

    @job_info.setter
    def job_info(self, input_job_info: dict[str, str | bool] | None) -> None:
        """Setter function for the job info. Provides a default if not set

        :param input_job_info: Input job info dictionary
        :type input_job_info: `dict`[`str`, `str`  |  `bool`] | `None`
        """
        # default
        if not input_job_info:
            input_job_info = {
                "SequenceName": "Default",
                "Category": "ValidSols",
                "Validity": True,
            }
        self._job_info = input_job_info

    def update_missing_events(self, missing_events: list[Event]) -> None:
        """Method to update the missing events list with a new list

        :param missing_events: A list of extra missing events
        :type missing_events: `list`[:class:`Event`]
        """
        self.missing_events.extend(missing_events)

    def generate_simulation_job_events(
        self,
        job_id_data_map: dict[str, UUIDString],
        sim_datum_transformer: PVSimDatumTransformer,
    ) -> Generator[SimDatum, Any, None]:
        """Method to generate :class:`SimDatum`'s for each event in the job
        given the input :class:`SimDatumTransformer` instance

        :param job_id_data_map: The map from job id to randomised job id
        :type job_id_data_map: `dict`[`str`, `str`]
        :param sim_datum_transformer: The arbitrary transformer class to
        transform the data into the required :class:`SimDatum` to generate
        :type sim_datum_transformer: :class:`SimDatumTransformer`
        :yield: Generates the :class:`SimDatum`'s for the job
        :rtype: :class:`Generator`[:class:`SimDatum`, `Any`, `None`]
        """
        event_event_id_map = self.create_new_event_event_id_map()
        invariant_name_data_map = self.invariants.create_name_data_map()
        for event in self.events:
            yield from event.generate_simulation_event_dict(
                event_event_id_map=event_event_id_map,
                job_id_data_map=job_id_data_map,
                sim_datum_transformer=sim_datum_transformer,
                invariant_name_data_map=invariant_name_data_map,
            )

    def create_new_event_event_id_map(self) -> dict[int, str]:
        """Method to create a new id(event) to event id map

        :return: Returns the map of id to event id
        :rtype: `dict`[`int`, `str`]
        """
        return {
            **{id(event): str(uuid4()) for event in self.events},
            **{id(event): str(uuid4()) for event in self.missing_events},
        }

    def parse_input_jobfile(self, input_jobfile: list[dict]) -> None:
        """Creates a Job object from a loaded JSON job file

        :param input_jobfile: A loaded JSON job file
        :type input_jobfile: `list[dict]`
        :return: The same data delivered as a Job object, carrying Event
        objects
        :rtype: :class:`Job`
        """
        event_id_map: dict[str, Event] = {}
        # iterate over the list of dicts
        for input_dict in input_jobfile:
            template_event = Event(job=self)
            template_event.parse_from_input_dict(input_dict)
            event_id_map[template_event.event_id] = template_event
            self.events.append(template_event)
        # link events
        for event in self.events:
            missing_events = event.link_prev_events(event_id_map)
            self.update_missing_events(missing_events)
