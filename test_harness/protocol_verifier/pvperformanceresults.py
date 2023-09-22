# pylint: disable=R0902
# pylint: disable=R0913
# pylint: disable=W0221
# pylint: disable=W0246
# pylint: disable=W0613
# pylint: disable=C0302
# pylint: disable=C0114
import os
from abc import abstractmethod
from datetime import datetime
from typing import Any, TextIO, TypedDict

import pandas as pd
from prometheus_client.parser import text_fd_to_metric_families

from .pvresults import PVResults


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


class PVPerformanceResults(PVResults):
    """Base class for perfromance test results extending :class:`PVResults`"""

    pv_grok_map = {
        "reception_event_received_total": "AER_start",
        "reception_event_written_total": "AER_end",
        "aeordering_events_processed_total": "AEOSVDC_start",
        "svdc_job_success_total": "AEOSVDC_end",
        "svdc_job_failed_total": "AEOSVDC_end",
    }
    data_fields = [
        "job_id",
        "time_sent",
        "response",
        "AER_start",
        "AER_end",
        "AEOSVDC_start",
        "AEOSVDC_end",
    ]

    def __init__(
        self,
    ) -> None:
        """Constructor method"""
        super().__init__()
        self.create_results_holder()
        self.end_times: dict[str, float] | None = None
        self.failures: FailuresDict | None = None
        self.full_averages: AveragesDict | None = None
        self.agg_results: pd.DataFrame | None = None

    @abstractmethod
    def create_results_holder(self) -> None:
        """Abstract method that creates the results holder that will be
        updated with results
        """

    @abstractmethod
    def update_event_results_with_event_id(
        self, event_id: str, update_values: dict[str, Any]
    ) -> None:
        """Abstract method that is used to update the results holder with an
        event id as key and update values named in a dictionary

        :param event_id: Unique event id
        :type event_id: `str`
        :param update_values: Arbitrary named update values
        :type update_values: `dict`[`str`, `Any`]
        """

    @abstractmethod
    def update_event_results_with_job_id(
        self, job_id: str, update_values: dict[str, Any]
    ) -> None:
        """Abstract method to update all rows in results holder based on the
        column job id match

        :param job_id: Job id
        :type job_id: `str`
        :param update_values: Arbitrary named update values
        :type update_values: `dict`[`str`, `Any`]
        """

    @abstractmethod
    def create_event_result_row(self, event_id: str) -> None:
        """Abstract method to create a row in the results holder based on an
        event id

        :param event_id: Unique event id
        :type event_id: `str`
        """

    def update_from_sim(
        self,
        event_list: list[dict],
        job_id: str,
        response: str,
        time_completed: datetime,
        file_name: str = "",
        job_info: dict[str, str] = {},
    ) -> None:
        """Method used to do an update when receiving data output
        from the simulation

        :param event_list: The list of event dicts
        :type event_list: `list`[`dict`]
        :param job_id: The job id the lit of events are associated with
        :type job_id: `str`
        :param response: The response received from the http request sending
        the file
        :type response: `str`
        :param time_completed: The time the request was completed at
        :type time_completed: :class:`datetime`
        """
        for event in event_list:
            self.add_first_event_data(
                event_id=event["eventId"],
                job_id=job_id,
                response=response,
                time_completed=time_completed,
            )

    def add_first_event_data(
        self,
        event_id: str,
        job_id: str,
        response: str,
        time_completed: datetime,
    ) -> None:
        """Method to add the first data received fro the simulation to the
        results holder

        :param event_id: The event id
        :type event_id: `str`
        :param job_id: The job id
        :type job_id: `str`
        :param response: The response received from the http request sending
        the file
        :type response: `str`
        :param time_completed: The time the request was completed at
        :type time_completed: :class:`datetime`
        """
        self.create_event_result_row(event_id)
        if self.time_start is None:
            raise ValueError("self.time_start has not been defined")
        time_sent_sim_time = (time_completed - self.time_start).total_seconds()

        update_values = {
            "job_id": job_id,
            "response": response,
            "time_sent": time_sent_sim_time,
        }
        self.update_event_results_with_event_id(
            event_id, update_values=update_values
        )

    def update_pv_sim_time_field(
        self,
        field: str,
        timestamp: str,
        event_id: str | None = None,
        job_id: str | None = None,
        **kwargs,
    ) -> None:
        """Method to update the results holder field with results from PV logs
        that are a timestamp string and coverting the reading to sim time

        :param field: The field of the results holder to update
        :type field: `str`
        :param timestamp: The timestamp string of the field
        :type timestamp: `str`
        :param event_id: The event id, defaults to `None`
        :type event_id: `str` | `None`, optional
        :param job_id: The job id, defaults to `None`
        :type job_id: `str` | `None`, optional
        :raises RuntimeError: Raises a :class:`RuntimeError` if event id and
        job id are not set
        """
        update_value = {field: self.convert_pv_time_string(timestamp)}
        if event_id is None and job_id is None:
            raise RuntimeError(
                "Both event id and job id have not been specified"
            )
        if event_id:
            self.update_event_results_with_event_id(event_id, update_value)
        else:
            if job_id is None:
                raise ValueError(
                    "Job id has not been specified, at least one "
                    "of event_id or job_id must be specified"
                )
            self.update_event_results_with_job_id(job_id, update_value)

    def convert_pv_time_string(self, pv_time_str: str) -> float:
        """Method to convert the PV timstamp string to sim time

        :param pv_time_str: The PV timestamp string
        :type pv_time_str: `str`
        :return: Returns the sim time of the pv time
        :rtype: `float`
        """
        date_time = datetime.strptime(pv_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        if self.time_start is None:
            raise ValueError("self.time_start has not been defined")
        sim_time = (date_time - self.time_start).total_seconds()
        return sim_time

    def get_and_read_grok_metrics(self, file_path: str | os.PathLike) -> None:
        """Opens a file and reads a groked file as a stream into the results
        holder

        :param file_path: The file path of the groked file
        :type file_path: `str`
        """
        with open(file_path, "r", encoding="utf-8") as file:
            self.read_groked_string_io(file)

    def read_groked_string_io(self, grok_string_io: TextIO) -> None:
        """Reads a streamable :class:`TextIO` object into the results holder
        parsing as a grok file

        :param grok_string_io: The streamable grok file :class:`TextIO` object
        :type grok_string_io: :class:`TextIO`
        """
        for family in text_fd_to_metric_families(grok_string_io):
            for sample in family.samples:
                name = sample.name
                if name not in self.pv_grok_map:
                    continue
                self.update_pv_sim_time_field(
                    field=self.pv_grok_map[name], **sample.labels
                )

    def calc_all_results(self, agg_time_window: float = 1.0) -> None:
        """Method to calculate al aggregated results. Data aggregations happen
        over the given time window inseconds

        :param agg_time_window: The time window in seconds for aggregating
        data,
        defaults to `1.0`
        :type agg_time_window: `float`, optional
        """
        self.create_response_time_fields()
        self.end_times = self.calc_end_times()
        self.failures = self.calculate_failures()
        self.full_averages = self.calc_full_averages()
        self.agg_results = self.calculate_aggregated_results_dataframe(
            agg_time_window
        )

    @abstractmethod
    def create_response_time_fields(self) -> None:
        """Abstract method used to create response fields in the rsults holder
        * full_response_time - the AEOSVDC end time minus the time sent
        * queue_time - The time when event was picked up by AER minus the time
        sent
        """

    @abstractmethod
    def calculate_failures(self) -> FailuresDict:
        """Abstract method to generate the failures and successes from the sim

        :return: Returns a dictionary of integers of the following fields:
        * "num_tests" - The number of events in the simulation
        * "num_failures" - The number of event failures in the PV groked logs
        (i.e. did not register a time in all of the pv sim time fields)
        * "num_errors" - The number of event failures given by the test
        harness (i.e. the response received was not empty)
        :rtype: `dict`[`str`, `int`]
        """

    @abstractmethod
    def calc_end_times(self) -> dict[str, float]:
        """Significant end times in the simulation

        :return: A dictionary of significant ending sim times with the
        following fields:
        * "th_end" - the time when the test harness sent its last event
        * "pv_end" - the time when aeosvdc processed it last event
        * "aer_end" - the time when aer processed its last event
        :rtype: `dict`[`str`, `float`]
        """

    @abstractmethod
    def calc_full_averages(self) -> AveragesDict:
        """Averages calculated in the data

        :return: Returns the dictionary of the following full avergaes of the
        simulation:
        * "average_sent_per_sec" - The average events sent per second over the
        entire simulation
        * "average_processed_per_sec" - The average number processed fully by
        the full PV stack over the entire simulation
        * "average_queue_time" - The average time waiting for an event befre
        being picked up by AER
        * "average_response_time" - The average time an event is sent and then
        fully processed by the PV stack
        :rtype: `dict`[`str`, `float`]
        """

    @abstractmethod
    def calculate_aggregated_results_dataframe(
        self, time_window: float | int = 1
    ) -> pd.DataFrame:
        """Abstract method to calculate the following aggregated results
        within bins of the specified time window in seconds. The dataframe has
        the following columns:
        * Time (s) - The midpoint of the time window for the aggregated result
        * Events Sent (/s) - The average number of events sent per second in
        the time window
        * Events Processed (/s) - The average number of events procesed
        per second in the time window
        * Queue Time (s) - The average queuing time before being picked up by
        AER in the time window. Given time window bin of when it is picked up
        not when it is sent.
        * Response Time (s) - The average time before being being fully
        processe by the PV stack in the time window. Given time window bin of
        when it is fully processed not when it is sent.
        :param time_window: The time window to use for aggregations, defaults
        to `1`
        :type time_window: `float | int`, optional
        :return: Returns a dataframe of the aggeragted results
        :rtype: :class:`pd`.`DataFrame`
        """
