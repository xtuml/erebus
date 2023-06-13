"""Reads a job JSON from a file, then writes n copies to file

:raises KeyError: When failing to find an event ID within a job
:return: n file copies of the input event
"""
# pylint: disable=R0913
# pylint: disable=R0902
# pylint: disable=R0903
import json
import copy
from datetime import datetime, timedelta
from functools import partial
from uuid import uuid4
open_utf8 = partial(open, encoding='UTF-8')


class Event:
    """Describes one UML entity, as well as links to other entities

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
    :param new_event_id: Remembers previous IDs, defaults to ""
    :type new_event_id: `str`, optional
    """
    def __init__(
            self,
            job_name: str = "",
            job_id: str = "",
            event_type: str = "",
            event_id: str = "",
            timestamp: str = "",
            application_name: str = "",
            previous_event_ids: list[str] = "",
            new_event_id: str = ""
            ):
        """Constructor method
        """
        self.job_name = job_name
        self.job_id = job_id
        self.new_event_id = new_event_id
        self.event_type = event_type
        self.event_id = event_id
        self.timestamp = timestamp
        self.application_name = application_name
        self.previous_event_ids = previous_event_ids

    def has_previous_event_id(self) -> bool:
        """Checks whether an event's previous_event_ids is populated

        :return: true if there are previous event ids, false otherwise
        :rtype: boolean
        """
        if len(self.previous_event_ids) > 0:
            return True
        return False


class Job:
    """Describes a group of related events, contains proccessing them
    """
    def __init__(self):
        """Constructor method
        """
        self.events: list[Event] = []

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
        for event in self.events:
            if event.event_id == target_id:
                return event
        raise KeyError("No event found with ID " + target_id)

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
            if event.has_previous_event_id():
                output_list.append({
                    "jobName": event.job_name,
                    "jobId": event.job_id,
                    "eventType": event.event_type,
                    "eventId": event.event_id,
                    "timestamp": event.timestamp,
                    "applicationName": event.application_name,
                    "previousEventIds": event.previous_event_ids
                })
            else:
                output_list.append({
                    "jobName": event.job_name,
                    "jobId": event.job_id,
                    "eventType": event.event_type,
                    "eventId": event.event_id,
                    "timestamp": event.timestamp,
                    "applicationName": event.application_name
                })
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
        template_event = parse_input_dict(input_dict)
        template_job.events.append(template_event)

    return template_job


def parse_input_dict(input_dict: dict) -> Event:
    """Creates an Event object with the parameters of a JSON dict

    :param input_dict: The incoming dict with key-value pairs
    :type input_dict: `dict`
    :return: The event object with properties
    :rtype: :class:`Event`
    """
    if "previousEventIds" in input_dict:
        input_previous_ids = input_dict["previousEventIds"]
    else:
        input_previous_ids = []
    return Event(
        input_dict["jobName"],
        input_dict["jobId"],
        input_dict["eventType"],
        input_dict["eventId"],
        input_dict["timestamp"],
        input_dict["applicationName"],
        input_previous_ids
    )


def make_job_from_template(
        template: Job,
        init_delay_minutes: int,
        gap_seconds: int
        ) -> Job:
    """Deep copies a template and randomises unique values

    :param template: Existing job to be duplicated
    :type template: :class:`Job`
    :param init_delay_minutes: Time gap, in minutes, before now for first event
    :type init_delay_minutes: `int`
    :param gap_seconds: Time gap in seconds between events in job
    :type gap_seconds: `int`
    :return: Unique replicated job
    :rtype: :class:`Job`
    """
    # copy template job exactly
    copy_job = copy.deepcopy(template)

    # randomise jobId, but make it consistent
    new_job_id = str(uuid4())

    # set initial timestamp to now - initDelayMinutes
    new_stamp = datetime.utcnow() - timedelta(minutes=init_delay_minutes)

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
        outfile.write(copy_obj.export_job_to_json())


input_job_file = open_utf8("test_sequence.json")
input_job = json.load(input_job_file)

template_obj = parse_input_jobfile(input_job)


# move this into test_harness

# for testing 1 job
# copy_obj = make_job_from_template(template_obj, 40, 1)
# write_job_to_file(copy_obj, "output/")

# for testing many jobs
j = 0
while j < 5:
    copy_obj = make_job_from_template(template_obj, 40, 1)
    write_job_to_file(copy_obj, "output/")
    j = j + 1
