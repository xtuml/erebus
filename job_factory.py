"""Reads a job JSON from a file, then writes n copies to file"""
import json
import secrets
import copy
from datetime import datetime, timedelta
from functools import partial
open_utf8 = partial(open, encoding='UTF-8')


class Event:
    """Describes one UML entity, as well as links to other entities"""
    def __init__(self):
        self.job_name = ""
        self.job_id = ""
        self.new_event_id = ""
        self.event_type = ""
        self.event_id = ""
        self.timestamp = ""
        self.application_name = ""
        self.previous_event_ids = []

    def has_previous_event_id(self):
        """Checks whether an event's previous_event_ids is populated"""
        if len(self.previous_event_ids) > 0:
            return True
        return False

# TODO: make a type or similar to avoid duplication
    def export_event_to_json(self):
        """Converts an event into a JSON object"""
        if self.has_previous_event_id():
            return json.dumps({
                "jobName": self.job_name,
                "jobId": self.job_id,
                "eventType": self.event_type,
                "eventId": self.event_id,
                "timestamp": self.timestamp,
                "applicationName": self.application_name,
                "previousEventIds": self.previous_event_ids
                }, indent=4)
        return json.dumps({
            "jobName": self.job_name,
            "jobId": self.job_id,
            "eventType": self.event_type,
            "eventId": self.event_id,
            "timestamp": self.timestamp,
            "applicationName": self.application_name
            }, indent=4)


class Job:
    """Describes a group of related events, contains proccessing them"""
    def __init__(self):
        self.events = []

    def update_prev_ids(self):
        """Checks all events for previous ids and updates them"""
        for event in self.events:
            if event.has_previous_event_id():
                self.process_previous_events(event)

    def process_previous_events(self, event):
        """Replaces previous ids with associated new_event_ids"""
        # need to check if this is a string or list
        match type(event.previous_event_ids).__name__:
            case "str":
                prev_event = self.search_for_id(event.previous_event_ids)
                event.previous_event_ids = prev_event.new_event_id
            case "list":
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

    def search_for_id(self, target_id):
        """Scans for an event with the target_id, throws if absent"""
        for event in self.events:
            if event.event_id == target_id:
                return event
        raise KeyError("No event found with ID " + target_id)

    def export_job_to_json(self):
        """Converts a job to a JSON object"""
        return json.dumps(self.export_job_to_list(), indent=4)

    def export_job_to_list(self):
        """Converts a job into a list of readable events"""
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


def load_template():
    """Load template json file from same directory and return Job object"""
    input_job_file = open_utf8("test_sequence.json")
    input_job = json.load(input_job_file)
    template_job = Job()
    # iterate over the list of dicts
    for input_event in input_job:
        template_event = Event()
        template_event.job_name = input_event["jobName"]
        template_event.job_id = input_event["jobId"]
        template_event.event_type = input_event["eventType"]
        template_event.event_id = input_event["eventId"]
        template_event.timestamp = input_event["timestamp"]
        template_event.application_name = input_event["applicationName"]
        try:
            input_previous_ids = input_event["previousEventIds"]
            template_event.previous_event_ids = input_previous_ids
        except KeyError:
            pass
        template_job.events.append(template_event)

    return template_job


def make_job_from_template(template, init_delay_minutes, gap_seconds):
    """Deep copies a template and randomises unique values"""
    # copy template job exactly
    copy_job = copy.deepcopy(template)

    # randomise jobId, but make it consistent
    new_job_id = make_rand_id()

    # set initial timestamp to now - initDelayMinutes
    new_stamp = datetime.utcnow() - timedelta(minutes=init_delay_minutes)

    # loop over timestamps, incrementing by gapSeconds
    # include in loop for events (stored in newEventId for now)
    for event in copy_job.events:
        event.new_event_id = make_rand_id()
        event.job_id = new_job_id
        event.timestamp = new_stamp.isoformat(timespec='seconds') + 'Z'
        new_stamp = new_stamp + timedelta(seconds=gap_seconds)

    # once that's done, match prevIds to correct newEventIds
    copy_job.update_prev_ids()

    # set all newEventIds to current now that the links are updated
    for event in copy_job.events:
        event.event_id = event.new_event_id

    return copy_job


def make_rand_id():
    """Creates a random hex string in the event/job id format"""
    output_id = secrets.token_hex(4)+"-"+secrets.token_hex(2)+"-"
    output_id = output_id+secrets.token_hex(2)+"-"+secrets.token_hex(2)+"-"
    output_id = output_id+secrets.token_hex(6)
    return output_id


template_obj = load_template()
copy_obj = make_job_from_template(template_obj, 40, 1)

# for testing 1 job
with open_utf8("output.json", "w") as outfile:
    outfile.write(copy_obj.export_job_to_json())

# for testing many jobs
# i = 0
# test_list = []
# while i<2:
#     test_list.append(make_job_from_template(t, 30, 1).export_job_to_list())
#     i = i + 1
# with open("output.json", "w") as outfile:
#     outfile.write(json.dumps(test_list, indent=4))
