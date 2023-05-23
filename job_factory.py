import json
import secrets
import copy
from datetime import datetime, timedelta


class Event:
    def __init__(self):
        self.jobName = ""
        self.jobId = ""
        self.newEventId = ""
        self.eventType = ""
        self.eventId = ""
        self.timestamp = ""
        self.applicationName = ""
        self.previousEventIds = []

    def __str__(self):
        return self.eventId

    def hasPreviousEventId(self):
        if (len(self.previousEventIds) > 0):
            return True
        return False

# TODO: make a type or similar to avoid duplication
    def exportEventToJson(self):
        if self.hasPreviousEventId():
            return json.dumps({
                "jobName": self.jobName,
                "jobId": self.jobId,
                "eventType": self.eventType,
                "eventId": self.eventId,
                "timestamp": self.timestamp,
                "applicationName": self.applicationName,
                "previousEventIds": self.previousEventIds
                }, indent=4)
        return json.dumps({
            "jobName": self.jobName,
            "jobId": self.jobId,
            "eventType": self.eventType,
            "eventId": self.eventId,
            "timestamp": self.timestamp,
            "applicationName": self.applicationName
            }, indent=4)


class Job:
    def __init__(self):
        self.events = []

    def __str__(self):
        return self.events

    def updatePrevIds(self):
        for event in self.events:
            if event.hasPreviousEventId():
                self.processPreviousEvents(event)

    def processPreviousEvents(self, event):
        # need to check if this is a string or list
        match type(event.previousEventIds).__name__:
            case "str":
                prevEvent = self.searchForId(event.previousEventIds)
                event.previousEventIds = prevEvent.newEventId
            case "list":
                # use iterators for the list
                i = 0
                # treat the list of ids as a queue
                while i < len(event.previousEventIds):
                    # find the new id of previous event at list 0
                    prevEvent = self.searchForId(event.previousEventIds[0])
                    newId = prevEvent.newEventId
                    # add it to the back
                    event.previousEventIds.append(newId)
                    # and delete the original at the front
                    event.previousEventIds.pop(0)
                    i = i + 1

    def searchForId(self, targetId):
        for event in self.events:
            if event.eventId == targetId:
                return event
        raise Exception("No event found with ID " + targetId)

    def exportJobToJson(self):
        return json.dumps(self.exportJobToList(), indent=4)

    def exportJobToList(self):
        outputList = []
        for event in self.events:
            if event.hasPreviousEventId():
                outputList.append({
                    "jobName": event.jobName,
                    "jobId": event.jobId,
                    "eventType": event.eventType,
                    "eventId": event.eventId,
                    "timestamp": event.timestamp,
                    "applicationName": event.applicationName,
                    "previousEventIds": event.previousEventIds
                })
            else:
                outputList.append({
                    "jobName": event.jobName,
                    "jobId": event.jobId,
                    "eventType": event.eventType,
                    "eventId": event.eventId,
                    "timestamp": event.timestamp,
                    "applicationName": event.applicationName
                })
        return outputList


# Load template json file from same directory
def loadTemplate():
    inputJobFile = open("test_sequence.json")
    inputJob = json.load(inputJobFile)
    templateJob = Job()
    # iterate over the list of dicts
    for inputEvent in inputJob:
        templateEvent = Event()
        templateEvent.jobName = inputEvent["jobName"]
        templateEvent.jobId = inputEvent["jobId"]
        templateEvent.eventType = inputEvent["eventType"]
        templateEvent.eventId = inputEvent["eventId"]
        templateEvent.timestamp = inputEvent["timestamp"]
        templateEvent.applicationName = inputEvent["applicationName"]
        try:
            templateEvent.previousEventIds = inputEvent["previousEventIds"]
        except KeyError:
            pass
        templateJob.events.append(templateEvent)

    return (templateJob)


def makeJobFromTemplate(template, initDelayMinutes, gapSeconds):
    # copy template job exactly
    copyJob = copy.deepcopy(template)

    # randomise jobId, but make it consistent
    newJobId = makeRandId()

    # set initial timestamp to now - initDelayMinutes
    newStamp = datetime.utcnow() - timedelta(minutes=initDelayMinutes)

    # loop over timestamps, incrementing by gapSeconds
    # include in loop for events (stored in newEventId for now)
    for event in copyJob.events:
        event.newEventId = makeRandId()
        event.jobId = newJobId
        event.timestamp = newStamp.isoformat(timespec='seconds') + 'Z'
        newStamp = newStamp + timedelta(seconds=gapSeconds)

    # once that's done, match prevIds to correct newEventIds
    copyJob.updatePrevIds()

    # set all newEventIds to current now that the links are updated
    for event in copyJob.events:
        event.eventId = event.newEventId

    return copyJob


# Function to make a believable hex token for readability
# e.g. jobId 4b9c4678-85e0-4782-8049-9ee8207c8241
# e.g. eventId cc2db444-f7d5-41e8-b009-f1e5d6adaae5
# in both cases, 8-4-4-4-12 hex strings
def makeRandId():
    outputId = secrets.token_hex(4)+"-"+secrets.token_hex(2)+"-"
    outputId = outputId+secrets.token_hex(2)+"-"+secrets.token_hex(2)+"-"
    outputId = outputId+secrets.token_hex(6)
    return (outputId)


templateJob = loadTemplate()
copyJob = makeJobFromTemplate(templateJob, 40, 1)

# for testing 1 job
with open("output.json", "w") as outfile:
    outfile.write(copyJob.exportJobToJson())

# for testing many jobs
# i = 0
# l = []
# while i<2:
#     l.append(makeJobFromTemplate(t, 30, 1).exportJobToList())
#     i = i + 1
# with open("output.json", "w") as outfile:
#     outfile.write(json.dumps(l, indent=4))
