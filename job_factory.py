import json
import secrets
import copy

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
        if(len(self.previousEventIds) > 0): 
            return True 
        return False

    def exportEventToJson(self):
        if self.hasPreviousEventId():
            return json.dumps({ 
                "jobName":self.jobName, 
                "jobId":self.jobId, 
                "eventType":self.eventType, 
                "eventId":self.eventId, 
                "timestamp":self.timestamp, 
                "applicationName":self.applicationName,
                "previousEventIds":self.previousEventIds
                }, indent=4)
        return json.dumps({ 
            "jobName":self.jobName, 
            "jobId":self.jobId, 
            "eventType":self.eventType, 
            "eventId":self.eventId, 
            "timestamp":self.timestamp, 
            "applicationName":self.applicationName 
            }, indent=4)

class Job:
    def __init__(self):
        self.events = []

    def __str__(self):
        return self.events

    def updatePrevIds(self):
        for e in self.events:
            if e.hasPreviousEventId():
                #need to check if this is a string or list
                match type(e.previousEventIds).__name__:
                    case "str":
                        e.previousEventIds = self.searchForId(e.previousEventIds).newEventId
                    case "list":
                        # use iterators for the list
                        i = 0
                        # treat the list of ids as a queue
                        while i<len(e.previousEventIds):
                            # find the new id of the previous id at the front of the list
                            newId = self.searchForId(e.previousEventIds[0]).newEventId
                            # add it to the back
                            e.previousEventIds.append(newId)
                            # and delete the original at the front
                            e.previousEventIds.pop(0)
                            i = i + 1
                
    def searchForId(self, targetId):
        for e in self.events:
            if e.eventId == targetId:
                return e
        raise Exception("No event found with ID " + targetId)

    def exportJobToJson(self):
        o = []
        for e in self.events:
            if e.hasPreviousEventId():
                o.append({ 
                "jobName":e.jobName, 
                "jobId":e.jobId, 
                "eventType":e.eventType, 
                "eventId":e.eventId, 
                "timestamp":e.timestamp, 
                "applicationName":e.applicationName,
                "previousEventIds":e.previousEventIds
                })
            else:
                o.append({ 
                "jobName":e.jobName, 
                "jobId":e.jobId, 
                "eventType":e.eventType, 
                "eventId":e.eventId, 
                "timestamp":e.timestamp, 
                "applicationName":e.applicationName
                })
        return json.dumps(o, indent=4)


# Load template json file from same directory
def loadTemplate():
    f = open("output.json")
    data = json.load(f)
    template = Job()
    # iterate over the list of dicts
    for d in data:
        e = Event()
        e.jobName = d["jobName"]
        e.jobId = d["jobId"]
        e.eventType = d["eventType"]
        e.eventId = d["eventId"]
        e.timestamp = d["timestamp"]
        e.applicationName = d["applicationName"]
        try:
            e.previousEventIds = d["previousEventIds"]
        except KeyError:
            pass
        template.events.append(e)
    #template.createLinks()

    return(template)

def makeJobFromTemplate(template):
    # copy template job exactly
    copyJob = copy.deepcopy(template)

    # randomise jobId, but make it consistent
    newJobId = makeRandId()

    # each event in the job needs a new eventid
    for e in copyJob.events:
        e.newEventId = makeRandId()
        e.jobId = newJobId
    
    # once that's done, call updater to follow previous id links and set them to new ids
    copyJob.updatePrevIds()
    
    # set all new event ids to current now that the links are updated
    for e in copyJob.events:
        e.eventId = e.newEventId
        
    return copyJob
        


# Function to make a believable hex token for readability
# e.g. jobId 4b9c4678-85e0-4782-8049-9ee8207c8241
# e.g. eventId cc2db444-f7d5-41e8-b009-f1e5d6adaae5
# in both cases, 8-4-4-4-12 hex strings
def makeRandId():
    return(secrets.token_hex(4)+"-"+secrets.token_hex(2)+"-"+secrets.token_hex(2)+"-"+secrets.token_hex(2)+"-"+secrets.token_hex(6))
    
# makeJobFromTemplate(loadTemplate())
t = loadTemplate()
c = makeJobFromTemplate(t)
# print(t.events[5].exportEventToJson())
# print(t.exportJobToJson())

with open("output.json", "w") as outfile:
    outfile.write(c.exportJobToJson())