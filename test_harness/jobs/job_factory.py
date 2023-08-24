"""Module to create multiple jobs and events from templates
"""
# pylint: disable=R0913
# pylint: disable=R0902
# pylint: disable=R0903
import json
import copy
from datetime import datetime, timedelta
from functools import partial
from uuid import uuid4
import logging
open_utf8 = partial(open, encoding='UTF-8')


class Event:
    """Class to hold data and links pertaining to Protocol Verifier Events.

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
    :param meta_data: Any meta data attached to event, defaults to ""
    :type meta_data: `dict`, optional
    :param new_event_id: Remembers previous IDs, defaults to ""
    :type new_event_id: `str`, optional

    """
    attribute_mappings = {
        "jobName": "job_name",
        "jobId": "job_id",
        "eventType": "event_type",
        "eventId": "event_id",
        "timestamp": "timestamp",
        "applicationName": "application_name",
        "previousEventIds": "previous_event_ids"
    }

    def __init__(
            self,
            job_name: str = "",
            job_id: str = "",
            event_type: str = "",
            event_id: str = "",
            timestamp: str = "",
            application_name: str = "",
            previous_event_ids: str | list[str] = "",
            meta_data: dict = {},
            new_event_id: str = ""
            ) -> None:
        """Constructor method
        """
        self.job_name = job_name
        self.job_id = job_id
        self.event_type = event_type
        self.event_id = event_id
        self.timestamp = timestamp
        self.application_name = application_name
        self.previous_event_ids = previous_event_ids
        self.meta_data = meta_data
        self.new_event_id = new_event_id

    def parse_from_input_dict(
        self,
        input_dict: dict[str, str | list[str], dict]
    ) -> None:
        """Updates the instances attributes given an input dictionary

        :param input_dict: The incoming dict with key-value pairs
        :type input_dict: `dict`[`str`, `str` | `list`[`str`], `dict`]
        """
        for field, attribute in self.attribute_mappings.items():
            if field == "previousEventIds" and field not in input_dict:
                attribute_value = []
            else:
                attribute_value = input_dict.pop(field)
            setattr(self, attribute, attribute_value)
        self.meta_data = {
            **input_dict
        }

    def has_previous_event_id(self) -> bool:
        """Checks whether an event's previous_event_ids is populated

        :return: true if there are previous event ids, false otherwise
        :rtype: boolean
        """
        if self.previous_event_ids:
            return True
        return False

    def event_to_dict(self) -> dict[str, str | list[str] | dict]:
        """Method to generate and event dict for the instance

        :return: Returns the event dict
        :rtype: `dict`[`str`, `str`]
        """
        event_dict = {
            "jobName": self.job_name,
            "jobId": self.job_id,
            "eventType": self.event_type,
            "eventId": self.event_id,
            "timestamp": self.timestamp,
            "applicationName": self.application_name
        }
        if self.has_previous_event_id():
            event_dict["previousEventIds"] = self.previous_event_ids
        # add meta data if it exists
        event_dict = {
            **event_dict,
            **self.meta_data
        }
        return event_dict

    def export_event_to_json_list(self) -> str:
        """Method to export the event to a json list

        :return: Returns a json string of the event
        :rtype: `str`
        """
        return json.dumps([self.event_to_dict()], indent=4)


class Job:
    """Describes a group of related events, contains proccessing them
    """
    def __init__(self):
        """Constructor method
        """
        self.events: list[Event] = []
        self.job_id: str = ""
        self.lost_events: dict[str, Event] = {}

    def update_prev_ids(self):
        """Checks all events for previous ids and updates them
        """
        for event in self.events:
            if event.has_previous_event_id():
                self.process_previous_events(event)

    def process_previous_events(self, event: Event):
        """Replaces previous ids with associated new_event_ids

        :param event: The event that is to have its previous IDs updated
        :type event: :class:`Event`
        """
        # need to check if this is a string or list
        if isinstance(event.previous_event_ids, str):
            prev_event = self.search_for_id(event.previous_event_ids)
            event.previous_event_ids = prev_event.new_event_id
        elif isinstance(event.previous_event_ids, list):
            # use iterators for the list
            i = 0
            # treat the list of ids as a queue
            while i < len(event.previous_event_ids):
                # find the new id of previous event at list 0
                old_id = event.previous_event_ids[0]
                prev_event = self.search_for_id(old_id)
                new_id = prev_event.new_event_id
                # add it to the back
                event.previous_event_ids.append(new_id)
                # and delete the original at the front
                event.previous_event_ids.pop(0)
                i = i + 1

    def search_for_id(self, target_id: str) -> Event:
        """Scans for an event with the target_id, throws if absent

        :param target_id: The ID that is checked for matches
        :type target_id: `str`
        :raises KeyError: No event has been found with the target ID
        :return: The event that has the same event ID as the target ID
        :rtype: :class:`Event`
        """
        if not self.events:
            raise RuntimeError("The job has no events")
        for event in self.events:
            if event.event_id == target_id:
                return event
        logging.getLogger().warning(
            "No event found with ID %s. Likely an event for an invalid test"
            " job is being processed",
            target_id
            )
        if target_id in self.lost_events:
            return self.lost_events[target_id]
        else:
            event = Event(
                job_name=event.job_name,
                new_event_id=str(uuid4())
            )
            self.lost_events[target_id] = event
            return event

    def export_job_to_json(self) -> str:
        """Converts a job to a JSON object

        :return: JSON representation of the job
        :rtype: `str`
        """
        return json.dumps(self.export_job_to_list(), indent=4)

    def export_job_to_list(self) -> list[dict]:
        """Converts a job into a list of readable events

        :return: List of dicts that represent the data of a job of events
        :rtype: `list[dict]`
        """
        output_list = []
        for event in self.events:
            output_list.append(event.event_to_dict())
        return output_list


def parse_input_jobfile(input_jobfile: list[dict]) -> Job:
    """Creates a Job object from a loaded JSON job file

    :param input_jobfile: A loaded JSON job file
    :type input_jobfile: `list[dict]`
    :return: The same data delivered as a Job object, carrying Event objects
    :rtype: :class:`Job`
    """
    template_job = Job()
    # iterate over the list of dicts
    for input_dict in input_jobfile:
        template_event = Event()
        template_event.parse_from_input_dict(input_dict)
        template_job.events.append(template_event)

    return template_job


def make_job_from_template(
    template: Job,
    gap_seconds: float,
    start_time: datetime | None = None,
    init_delay_minutes: float = 0,
) -> Job:
    """Deep copies a template and randomises unique values

    :param template: Existing job to be duplicated
    :type template: :class:`Job`
    :param gap_seconds: Time gap in seconds between events in job
    :type gap_seconds: `float`
    :param start_time: Optional start time for the first job, defaults to
    `None`
    :type start_time: `datetime` | `None`, optional
    :param init_delay_minutes: Time gap, in minutes, before now for first
    event, defaults to `0`
    :type init_delay_minutes: `float`, optional
    :return: Unique replicated job
    :rtype: :class:`Job`
    """
    # copy template job exactly
    copy_job = copy.deepcopy(template)

    # randomise jobId, but make it consistent
    new_job_id = str(uuid4())
    if not start_time:
        # set initial timestamp to now - initDelayMinutes
        new_stamp = datetime.utcnow() - timedelta(minutes=init_delay_minutes)
    else:
        new_stamp = start_time
    # set job id to job
    copy_job.job_id = new_job_id

    # loop over timestamps, incrementing by gapSeconds
    # include in loop for events (stored in newEventId for now)
    for event in copy_job.events:
        event.new_event_id = str(uuid4())
        event.job_id = new_job_id
        event.timestamp = new_stamp.isoformat(timespec='seconds') + 'Z'
        new_stamp = new_stamp + timedelta(seconds=gap_seconds)

    # once that's done, match prevIds to correct newEventIds
    copy_job.update_prev_ids()

    # set all newEventIds to current now that the links are updated
    for event in copy_job.events:
        event.event_id = event.new_event_id

    return copy_job


def write_job_to_file(write_job: Job, filepath: str):
    """Saves the input job to a JSON file at the specified filepath

    :param write_job: The job that needs to be saved
    :type write_job: :class:`Job`
    :param filepath: The path that the JSON files are to be sent to
    :type filepath: `str`
    """
    filename = filepath + write_job.events[0].job_id + ".json"
    with open_utf8(filename, "w") as outfile:
        outfile.write(write_job.export_job_to_json())


def concat_jobs_to_file(jobs: list[Job], out_file_path: str) -> None:
    """Method to concatenate a list of jobs into a single list and then dump
    to one file

    :param jobs: List of :class:`Job`'s
    :type jobs: `list`[:class:`Job`]
    :param out_file_path: The output file path of the concatenated jobs
    :type out_file_path: `str`
    """
    events_json_list = concat_jobs_to_list(
        jobs
    )
    with open_utf8(out_file_path, "w") as outfile:
        outfile.write(json.dumps(events_json_list, indent=4))


def concat_jobs_to_list(
    jobs: list[Job]
) -> list[dict]:
    """Method to concatenate a list of jobs into a single list of events

    :param jobs: List of :class:`Job`'s
    :type jobs: `list`[:class:`Job`]
    :return: Returns a list of event dictionaries
    :rtype: `list`[`dict`]
    """
    return [
        event
        for job in jobs
        for event in job.export_job_to_list()
    ]
