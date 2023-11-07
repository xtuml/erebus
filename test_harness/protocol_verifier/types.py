"""
This is a module for assorted types with no have behaviour attached.

"""
from datetime import datetime
from typing import TypedDict, NotRequired, NamedTuple, Any, Iterator

from matplotlib import pyplot as plt


class AveragesDict(TypedDict):
    """Dictionary of averages"""

    average_sent_per_sec: float
    average_processed_per_sec: float
    average_queue_time: float
    average_response_time: float


class FailuresDict(TypedDict):
    """Dictionary of failures and successes"""

    num_tests: int
    num_failures: int
    """
    This represents when the test harness successfully send a file but the PV
    fails in processing.
    """

    num_errors: int
    """
    This represents when the test harness fails to send a file to PV.
    """


class ReceptionCountsDict(TypedDict):
    """Dictionary of reception counts"""

    num_aer_start: int
    """Number of events received by AEReception
    """
    num_aer_end: int
    """Number of events written by AEReception
    """


class ProcessErrorDataDict(TypedDict):
    """Dictionary of processing errors"""

    AER_file_process_error: int
    """Dictionary of counts of AER file processing errors in bins
    """
    AEO_file_process_error: int
    """Dictionary of counts of AEO file processing errors in bins
    """


class ResultsDict(TypedDict):
    """Dictionary of the result of a processing error"""

    field: str
    """The field of the processing error
    """
    timestamp: str
    """The timestamp of the occurence of the error
    """
    event_id: NotRequired[str]
    """Unique id for an event
    """
    job_id: NotRequired[str]
    """Unique id for a job
    """


class PVResultsHandlerItem(NamedTuple):
    """
    An item representing a list of events from Protocol Verifier
    """

    # TODO have a better descriptions here, if not better types
    event_list: list[dict[str, Any]]

    file_name: str
    """A string representing the filename used to send the data.
    """

    job_id: str
    """A string representing the job id.
    """

    job_info: dict[str, str | None]
    """A dict representing the job info.
    """

    response: str
    """A string representing the response from the request.
    """

    time_completed: datetime


class TemplateOptions(NamedTuple):
    """Named tuple to holde template options
    """
    invariant_matched: bool = True
    """Whether the invariants match
    """
    invariant_length: int = 1
    """The length (multiple of uuid4 36 length string) of the invariants
    """


class TemplateOptionsDict(TypedDict):
    """Typed dict that type hints for an expected template options dict
    """
    invariant_matched: NotRequired[bool]
    """Whether the invariants match
    """
    invariant_length: NotRequired[int]
    """The length (multiple of uuid4 36 length string) of the invariants
    """


class TestJobFile(TypedDict):
    """Typed dict that type hints for an expected test event list job json file
    """
    job_file: list[dict[str, str | list | dict]]
    """The list of events in the job file
    """
    job_name: str
    """The name of the job
    """
    sequence_type: str
    """The sequence type of the job
    """
    validity: bool
    """The validity of the job
    """
    options: NotRequired[TemplateOptionsDict]
    """The options for the job to be used in the test harness
    """


class GeneratedJobData(NamedTuple):
    """Named tuple that holds the events list and optionally:
    * the event ids
    * the DAG figure of the generated job
    * the job id
    """
    event_list: list[dict]
    """The list of events in the job
    """
    event_ids: list[str] | None = None
    """The list of event ids in the job, optional
    """
    graph_figure: plt.Figure | None = None
    """The DAG figure of the generated job, optional
    """
    job_id: str | None = None
    """The job id of the generated job, optional
    """


class TemplateJobsDataAndValidityTuple(NamedTuple):
    """Named tuple that holds the events, validity and options of
    the template
    """
    jobs_data: Iterator[
        GeneratedJobData
    ]
    """The iterator of jobs data
    """
    validity: bool
    """The validity of the template
    """
