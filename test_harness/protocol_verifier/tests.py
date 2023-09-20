# pylint: disable=R0902
# pylint: disable=R0913
# pylint: disable=W0221
# pylint: disable=W0246
# pylint: disable=W0613
# pylint: disable=C0302
"""Methods and classes relating to tests
"""
from typing import Generator, Any, Type, TextIO
from abc import ABC, abstractmethod
from random import choice, choices
import os
import asyncio
import logging
import math
from queue import Queue, Empty
import json
from threading import Thread
from datetime import datetime


import matplotlib.pyplot as plt
import flatdict
import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure
from requests import ReadTimeout
import numpy as np
import scipy.stats as sps
from prometheus_client.parser import text_fd_to_metric_families

from test_harness.config.config import HarnessConfig, TestConfig
from test_harness.utils import clean_directories
from test_harness.protocol_verifier.calc_pv_finish import PVFileInspector
from test_harness.protocol_verifier.simulator_data import (
    Job,
    generate_events_from_template_jobs,
    generate_job_batch_events,
    generate_single_events,
    job_sequencer,
    send_list_dict_as_json_wrap_url
)
from test_harness.simulator.simulator import (
    SimDatum, Simulator, ResultsHandler
)
from test_harness.simulator.simulator_profile import Profile
from test_harness.reporting.report_delivery import deliver_test_report_files
from test_harness.reporting import create_report_files
from test_harness.requests import send_get_request, download_file_to_path


class PVResults(ABC):
    """Base abstract class to hold an calculate results from a PV simulation
    """
    def __init__(self) -> None:
        """Constructor method
        """
        self.time_start = None

    @property
    def time_start(self) -> datetime | None:
        """Property getter for the start time of the simulation

        :return: Returns the start time if set
        :rtype: :class:`datetime` | `None`
        """
        return self._time_start

    @time_start.setter
    def time_start(self, input_time_start: datetime | None) -> None:
        """Property setter for the start time of the simulation

        :param input_time_start: The start time
        :type input_time_start: :class:`datetime` | `None`
        """
        self._time_start = input_time_start

    @abstractmethod
    def update_from_sim(
        self,
        event_list: list[dict],
        job_id: str,
        file_name: str,
        job_info: dict[str, str],
        response: str,
        time_completed: datetime
    ) -> None:
        """Abstract method used to do an update when receiving data output
        from the simulation

        :param event_list: The list of event dicts
        :type event_list: `list`[`dict`]
        :param job_id: The job id the lit of events are associated with
        :type job_id: `str`
        :param file_name: The name of the file that was sent and/or saved
        :type file_name: `str`
        :param job_info: The validity information pertaining to the job
        :type job_info: `dict`[`str`, `str`]
        :param response: The response received from the http request sending
        the file
        :type response: `str``
        :param time_completed: The time the request was completed at
        :type time_completed: :class:`datetime`
        """


class PVPerformanceResults(PVResults):
    """Base class for perfromance test results extending :class:`PVResults`
    """
    pv_grok_map = {
        "reception_event_received_total": "AER_start",
        "reception_event_written_total": "AER_end",
        "aeordering_events_processed_total": "AEOSVDC_start",
        "svdc_job_success_total": "AEOSVDC_end",
        "svdc_job_failed_total": "AEOSVDC_end"
    }
    data_fields = [
        "job_id",
        "time_sent",
        "response",
        "AER_start",
        "AER_end",
        "AEOSVDC_start",
        "AEOSVDC_end"
    ]

    def __init__(
        self,
    ) -> None:
        """Constructor method
        """
        super().__init__()
        self.create_results_holder()
        self.end_times: dict[str, float] | None = None
        self.failures: dict[str, int] | None = None
        self.full_averages: dict[str, float] | None = None
        self.agg_results: pd.DataFrame | None = None

    @abstractmethod
    def create_results_holder(self) -> None:
        """Abstract method that creates the results holder that will be
        updated with results
        """

    @abstractmethod
    def update_event_results_with_event_id(
        self,
        event_id: str,
        update_values: dict[str, Any]
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
        self,
        job_id: str,
        update_values: dict[str, Any]
    ) -> None:
        """Abstract method to update all rows in results holder based on the
        column job id match

        :param job_id: Job id
        :type job_id: `str`
        :param update_values: Arbitrary named update values
        :type update_values: `dict`[`str`, `Any`]
        """

    @abstractmethod
    def create_event_result_row(
        self,
        event_id: str
    ) -> None:
        """Abstract method to create a row in the results holder based on an
        event id

        :param event_id: Unique event id
        :type event_id: `str`
        """

    def update_from_sim(
        self,
        event_list: list[dict],
        job_id: str,
        response: bool,
        time_completed: datetime,
        **kwargs
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
                time_completed=time_completed
            )

    def add_first_event_data(
        self,
        event_id: str,
        job_id: str,
        response: str,
        time_completed: datetime
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
        self.create_event_result_row(
            event_id
        )
        time_sent_sim_time = (
            time_completed - self.time_start
        ).total_seconds()

        update_values = {
            "job_id": job_id,
            "response": response,
            "time_sent": time_sent_sim_time,
        }
        self.update_event_results_with_event_id(
            event_id,
            update_values=update_values
        )

    def update_pv_sim_time_field(
        self,
        field: str,
        timestamp: str,
        event_id: str | None = None,
        job_id: str | None = None,
        **kwargs
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
        update_value = {
            field: self.convert_pv_time_string(timestamp)
        }
        if event_id is None and job_id is None:
            raise RuntimeError(
                "Both event id and job id have not been specified"
            )
        if event_id:
            self.update_event_results_with_event_id(
                event_id,
                update_value
            )
        else:
            self.update_event_results_with_job_id(
                job_id,
                update_value
            )

    def convert_pv_time_string(
        self,
        pv_time_str: str
    ) -> float:
        """Method to convert the PV timstamp string to sim time

        :param pv_time_str: The PV timestamp string
        :type pv_time_str: `str`
        :return: Returns the sim time of the pv time
        :rtype: `float`
        """
        date_time = datetime.strptime(
            pv_time_str,
            '%Y-%m-%dT%H:%M:%S.%fZ'
        )
        sim_time = (
            date_time - self.time_start
        ).total_seconds()
        return sim_time

    def get_and_read_grok_metrics(
        self,
        file_path: str
    ) -> None:
        """Opens a file and reads a groked file as a stream into the results
        holder

        :param file_path: The file path of the groked file
        :type file_path: `str`
        """
        with open(file_path, "r", encoding="utf-8") as file:
            self.read_groked_string_io(file)

    def read_groked_string_io(
        self,
        grok_string_io: TextIO
    ) -> None:
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
                    field=self.pv_grok_map[name],
                    **sample.labels
                )

    def calc_all_results(
        self,
        agg_time_window: float = 1.0
    ) -> None:
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
    def calculate_failures(self) -> dict[str, int]:
        """Abstract method to generate the failures and successes from the sim

        :return: Returns a dictionary of integers of the following fields:
        * "th_failures" - The number of event failures given by the test
        harness (i.e. the response received was not empty)
        * "pv_failures" - The number of event failures in the PV groked logs
        (i.e. did not register a time in all of the pv sim time fields)
        * "pv_sccesses" - The number of event successes in the PV groked logs
        (i.e. registered a time in all of the pv sim time fields)
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
    def calc_full_averages(self) -> dict[str, float]:
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
        self,
        time_window: int = 1
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
        :type time_window: `int`, optional
        :return: Returns a dataframe of the aggeragted results
        :rtype: :class:`pd`.`DataFrame`
        """


class PVResultsDataFrame(PVPerformanceResults):
    """Sub class of :class:`PVPerformanceResults: to get perfromance results
    using a pandas dataframe as the results holder.
    """
    def __init__(
        self,
    ) -> None:
        """Constructor method
        """
        super().__init__()

    def __len__(self) -> int:
        """The length of the results

        :return: The length of the results holder
        :rtype: `int`
        """
        return len(self.results)

    def create_results_holder(self) -> None:
        """Creates the results holder as pandas DataFrame
        """
        self.results = pd.DataFrame(columns=self.data_fields)

    def create_event_result_row(self, event_id: str) -> None:
        """Method to create a row in the results holder based on an
        event id

        :param event_id: Unique event id
        :type event_id: `str`
        """
        self.results.loc[event_id] = None

    def update_event_results_with_event_id(
        self,
        event_id: str,
        update_values: dict[str, Any]
    ) -> None:
        """Method that is used to update the results holder with an
        event id as key and update values named in a dictionary

        :param event_id: Unique event id
        :type event_id: `str`
        :param update_values: Arbitrary named update values
        :type update_values: `dict`[`str`, `Any`]
        """
        self.results.loc[
            event_id, list(update_values.keys())
        ] = list(update_values.values())

    def update_event_results_with_job_id(
        self,
        job_id: str,
        update_values: dict[str, Any]
    ) -> None:
        """Method to update all rows in results holder based on the
        column job id match

        :param job_id: Job id
        :type job_id: `str`
        :param update_values: Arbitrary named update values
        :type update_values: `dict`[`str`, `Any`]
        """
        self.results.loc[
            self.results["job_id"] == job_id,
            list(update_values.keys())
        ] = list(update_values.values())

    def create_response_time_fields(self) -> None:
        """Method used to create response fields in the results holder
        * full_response_time - the AEOSVDC end time minus the time sent
        * queue_time - The time when event was picked up by AER minus the time
        sent
        """
        self.results["full_response_time"] = (
            self.results["AEOSVDC_end"] - self.results["time_sent"]
        )
        self.results["full_response_time"].clip(lower=0, inplace=True)
        self.results["queue_time"] = (
            self.results["AER_start"] - self.results["time_sent"]
        )
        self.results["queue_time"].clip(lower=0, inplace=True)

    def calculate_failures(self) -> dict[str, int]:
        """Method to generate the failures and successes from the sim

        :return: Returns a dictionary of integers of the following fields:
        * "th_failures" - The number of event failures given by the test
        harness (i.e. the response received was not empty)
        * "pv_failures" - The number of event failures in the PV groked logs
        (i.e. did not register a time in all of the pv sim time fields)
        * "pv_sccesses" - The number of event successes in the PV groked logs
        (i.e. registered a time in all of the pv sim time fields)
        :rtype: `dict`[`str`, `int`]
        """
        th_failures = len(self.results[self.results["response"] != ""])
        pv_failures = pd.isnull(
            self.results.loc[:, [
                "AER_start",
                "AER_end",
                "AEOSVDC_start",
                "AEOSVDC_end"
            ]]
        ).all(axis=1).sum()
        pv_successes = len(self.results) - pv_failures
        return {
            "th_failures": th_failures,
            "pv_failures": pv_failures,
            "pv_successes": pv_successes,
        }

    def calc_end_times(self) -> dict[str, float]:
        """Significant end times in the simulation

        :return: A dictionary of significant ending sim times with the
        following fields:
        * "th_end" - the time when the test harness sent its last event
        * "pv_end" - the time when aeosvdc processed it last event
        * "aer_end" - the time when aer processed its last event
        :rtype: `dict`[`str`, `float`]
        """
        return {
            "th_end": np.nanmax(self.results["time_sent"]),
            "pv_end": np.nanmax(self.results["AEOSVDC_end"]),
            "aer_end": np.nanmax(self.results["AER_end"])
        }

    def calc_full_averages(
        self,
    ) -> dict[str, float]:
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
        averages = {
            "average_sent_per_sec": (
                self.results["time_sent"].count() / self.end_times["th_end"]
            ),
            "average_processed_per_sec": (
                self.results["AEOSVDC_end"].count() / self.end_times["pv_end"]
            ),
            "average_queue_time": np.nanmean(self.results["queue_time"]),
            "average_response_time": np.nanmean(
                self.results["full_response_time"]
            )
        }
        return averages

    def calculate_aggregated_results_dataframe(
        self,
        time_window: int = 1
    ) -> pd.DataFrame:
        """Method to calculate the following aggregated results
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
        :type time_window: `int`, optional
        :return: Returns a dataframe of the aggeragted results
        :rtype: :class:`pd`.`DataFrame`
        """
        test_end_ceil = np.ceil(np.nanmax(
            list(self.end_times.values())
        ))
        time_range = np.arange(
            0,
            test_end_ceil + time_window,
            time_window
        )
        # get aggregated events sent per second
        aggregated_sent_per_second = sps.binned_statistic(
            self.results["time_sent"],
            [1] * len(self.results),
            bins=time_range,
            statistic='count'
        ).statistic / time_window
        # get events per second
        aggregated_events_per_second = sps.binned_statistic(
            self.results["AEOSVDC_end"],
            [1] * len(self.results),
            bins=time_range,
            statistic='count'
        ).statistic / time_window
        # get aggregated full response time
        aggregated_full_response_time = sps.binned_statistic(
            self.results["AEOSVDC_end"],
            self.results["full_response_time"],
            bins=time_range,
            statistic=np.nanmean
        ).statistic
        # get aggregated time in queue
        aggregated_queue_time = sps.binned_statistic(
            self.results["AER_start"],
            self.results["queue_time"],
            bins=time_range,
            statistic=np.nanmean
        ).statistic
        aggregated_results = pd.DataFrame(
            np.vstack(
                [
                    time_range[:-1] + time_window / 2,
                    aggregated_sent_per_second,
                    aggregated_events_per_second,
                    aggregated_queue_time,
                    aggregated_full_response_time
                ]
            ).T,
            columns=[
                "Time (s)",
                "Events Sent (/s)",
                "Events Processed (/s)",
                "Queue Time (s)",
                "Response Time (s)"
            ]
        )
        return aggregated_results


class PVFunctionalResults(PVResults):
    """Sub-class of :class:`PVResults` to update and store functional results
    within a Functional test run
    """
    def __init__(
        self,
    ) -> None:
        """Constructor method
        """
        super().__init__()
        self.job_ids = []
        self.jobs_info = []
        self.file_names = []
        self.responses = []

    def update_from_sim(
        self,
        job_id: str,
        file_name: str,
        job_info: dict[str, str],
        response: str,
        **kwargs
    ) -> None:
        """Implementation of abstract method when given a data point from the
        Functional simulaiona

        :param job_id: The unique id of the job
        :type job_id: `str`
        :param file_name: The name of the output file the test file has been
        saved as.
        :type file_name: `str`
        :param job_info: The validity information related to the job
        :type job_info: `dict`[`str`, `str`]
        :param response: Th response received from the http intermediary
        :type response: `str`
        """
        self.update_test_files_info(
            job_ids=[job_id],
            jobs_info=[job_info],
            file_names=[file_name]
        )
        self.update_responses([response])

    def update_test_files_info(
        self,
        job_ids: list[str],
        jobs_info: list[dict[str, str]],
        file_names: list[str]
    ) -> None:
        """Method to update the test files info for the results.
        The lists should be of the same legnth and every index of each list
        should refer to the same file

        :param job_ids: List of job ids
        :type job_ids: `list`[`str`]
        :param jobs_info: List of dictionary mapping name of info to info
        :type jobs_info: `list`[`dict`[`str`, `str`]]
        :param file_names: List of file names of the tests
        :type file_names: `list`[`str`]
        :raises RuntimeError: Raises a :class:`RuntimeError` if the lists are
        not all of the same length
        """
        if len(set(
            len(obj_list)
            for obj_list in [job_ids, jobs_info, file_names]
        )) != 1:
            raise RuntimeError("all lists should be the same length")
        self.job_ids.extend(job_ids)
        self.jobs_info.extend(jobs_info)
        self.file_names.extend(file_names)

    def update_responses(self, responses: list[str]) -> None:
        """Method to update the responses

        :param response: List of responses
        :type response: `str`
        """
        self.responses.extend(responses)

    def create_validity_dataframe(self) -> pd.DataFrame:
        """Create a validity dataframe for the instance

        :return: Returns the validity dataframe
        :rtype: :class:`pd`.`DataFrame`
        """
        validity_df_lines = [
            {
                **{
                    "JobId": job_id,
                    "FileName": file_name
                },
                **job_info
            }
            for job_id, job_info, file_name in zip(
                self.job_ids,
                self.jobs_info,
                self.file_names
            )
        ]
        validity_df = pd.DataFrame.from_records(
            validity_df_lines
        )
        validity_df.set_index("JobId", inplace=True)
        return validity_df


class PVResultsHandler(ResultsHandler):
    """Subclass of :class:`ResultsHandler` to handle saving of files and data
    from a PV test run. Uses a context manager and daemon thread to save
    results in the background whilst a test is running.


    :param results_holder: Instance used to hold the data relating to the sent
    jobs/events
    :type results_holder: :class:`Results`
    :param test_output_directory: The path of the output directory of the test
    :type test_output_directory: `str`
    :param save_files: Boolean indicating whether the files should be saved or
    not, defaults to `False`
    :type save_files: `bool`, optional
    """
    def __init__(
        self,
        results_holder: PVResults,
        test_output_directory: str,
        save_files: bool = False
    ) -> None:
        """Constructor method
        """
        self.queue = Queue()
        self.results_holder = results_holder
        self.test_output_directory = test_output_directory
        self.daemon_thread = Thread(target=self.queue_handler, daemon=True)
        self.daemon_not_done = True
        self.save_files = save_files

    def __enter__(self) -> None:
        """Entry to the context manager
        """
        self.daemon_thread.start()
        return self

    def __exit__(
        self,
        exc_type: Type[Exception] | None,
        exc_value: Exception | None,
        *args
    ) -> None:
        """Exit from context manager

        :param exc_type: The type of the exception
        :type exc_type: :class:`Type` | `None`
        :param exc_value: The value of the excpetion
        :type exc_value: `str` | `None`
        :param traceback: The traceback fo the error
        :type traceback: `str` | `None`
        :raises RuntimeError: Raises a :class:`RuntimeError`
        if an error occurred in the main thread
        """
        if exc_type is not None:
            logging.getLogger().error(
                "The folowing type of error occurred %s with value %s",
                exc_type,
                exc_value
            )
            raise exc_value
        while self.queue.qsize() != 0:
            continue
        self.daemon_not_done = False
        self.daemon_thread.join()

    def handle_result(
        self,
        result: tuple[
            list[dict[str, Any]], str, str, dict[str, str | None], str,
            datetime
        ] | None
    ) -> None:
        """Method to handle the result from a simulation iteration

        :param result: The result from the PV simulation iteration - could be
        `None` or a tuple of:
        * the event dicts in a list
        * a string representing the filename used to send the data
        * a string representing the job id
        * a dict representing the job info
        * a string representing the response from the request
        :type result: `tuple`[ `list`[`dict`[`str`, `Any`]], `str`, `str`,
        :class:`datetime`
        `dict`[`str`, `str`  |  `None`], `str` ] | `None`
        """
        self.queue.put(result)

    def queue_handler(self) -> None:
        """Method to handle the queue as it is added to
        """
        while self.daemon_not_done:
            try:
                item = self.queue.get(timeout=1)
                self.handle_item_from_queue(item)
            except Empty:
                continue

    def handle_item_from_queue(
        self,
        item: tuple[
            list[dict[str, Any]], str, str, dict[str, str | None], str,
            datetime
        ] | None
    ) -> None:
        """Method to handle saving the data when an item is take from the queue

        :param item: PV iteration data taken from the queue
        :type item: `tuple`[ `list`[`dict`[`str`, `Any`]], `str`, `str`,
        :class:`datetime`
        `dict`[`str`, `str`  |  `None`], `str` ] | `None`
        """
        if item is None:
            return
        self.results_holder.update_from_sim(
            event_list=item[0],
            job_id=item[2],
            file_name=item[1],
            job_info=item[3],
            response=item[4],
            time_completed=item[5]
        )
        if self.save_files:
            output_file_path = os.path.join(
                self.test_output_directory,
                item[1]
            )
            with open(output_file_path, 'w', encoding="utf-8") as file:
                json.dump(item[0], file)


class Test(ABC):
    """Base class to hold and run a test.

    :param test_file_generators: Dictionary containing generated tests for
    each job definition
    :type test_file_generators: `dict`[ `str`, `dict`[ `str`, `tuple`[
    :class:`Generator`[ `tuple`[`list`[`dict`], `list`[`str`],
    :class:`plt`.`Figure`  |  `None`, `str`], `Any`, `None`, ], `bool`, ], ], ]
    :param harness_config: Main config for the test harness, defaults to `None`
    :type harness_config: :class:`HarnessConfig` | `None`, optional
    :param test_config: Config for the specific test, defaults to `None`
    :type test_config: :class:`TestConfig` | `None`, optional
    :param test_output_directory: The path of the test output directory where
    files relating to the test results are stored, defaults to `None`
    :type test_output_directory: `str` | `None`, optional
    :param save_files: Boolean indicating whether to save test results - will
    only save if a test output directory has been given, defaults to `True`
    :type save_files: `bool`, optional
    """

    def __init__(
        self,
        test_file_generators: dict[
            str,
            dict[
                str,
                tuple[
                    Generator[
                        tuple[list[dict], list[str], plt.Figure | None, str],
                        Any,
                        None,
                    ],
                    bool,
                ],
            ],
        ],
        harness_config: HarnessConfig | None = None,
        test_config: TestConfig | None = None,
        test_output_directory: str | None = None,
        test_profile: Profile | None = None,
        save_files: bool = True,
    ) -> None:
        """Constructor method"""
        self.test_files = test_file_generators
        self.test_output_directory = test_output_directory
        self.harness_config = (
            harness_config if harness_config else HarnessConfig()
        )
        self.test_config = test_config if test_config else TestConfig()
        self.test_profile = test_profile
        self.simulator: Simulator | None = None
        self.sim_data_generator: Generator[SimDatum, Any, None] | None = None
        if save_files and not test_output_directory:
            logging.getLogger().warning(
                (
                    "Save files has been set but there is not output directory"
                    " for tests"
                )
            )
        self.save_files = (
            save_files if save_files and test_output_directory else False
        )
        # set up requires attributes
        self.job_templates: list[Job] = []
        self.results = self.set_results_holder()
        self.pv_file_inspector = PVFileInspector(harness_config)
        self.total_number_of_events: int
        self.delay_times: list[float]
        self.jobs_to_send: list[Job]
        self.set_test_rate()
        # prepare the test given inputs
        self.prepare_test()

    @abstractmethod
    def set_results_holder(self) -> PVResults | PVPerformanceResults:
        """Abstract metho to return the results holder

        :return: Returns a :class:`PVResults` object
        :rtype: :class:`PVResults` | :class:`PVPerformanceResults`
        """
        return PVFunctionalResults()

    def _make_job_templates(self) -> None:
        """Method to make the template jobs from the generated tests files
        """
        flattened_test_files = flatdict.FlatDict(self.test_files)
        flattened_keys: list[str] = flattened_test_files.keys()
        counter = 0
        # loop until the max number of different sequences have been templated
        # or until all test sequences have been used up
        while (
            counter < (self.test_config.max_different_sequences)
            and flattened_keys
        ):
            try:
                flattened_key: str = choice(flattened_keys)
                try:
                    job_sequence = next(
                        flattened_test_files[flattened_key][0]
                    )[0]
                    job_name_sol_type = flattened_key.split(":")
                    job_info = {
                        "SequenceName": job_name_sol_type[0],
                        "Category": job_name_sol_type[1],
                        "Validity": flattened_test_files[
                            flattened_key
                        ][1],
                    }
                    job = Job(job_info=job_info)
                    job.parse_input_jobfile(job_sequence)
                    self.job_templates.append(job)
                except StopIteration:
                    flattened_keys.remove(flattened_key)
            except IndexError:
                break

    def prepare_test(self) -> None:
        """Method to prepare the test data
        """
        self._make_job_templates()
        if self.test_profile is not None:
            self.test_profile.transform_raw_profile()
        self._set_jobs_to_send()
        self._set_total_number_of_events()
        self._set_delay_profile()
        self.sim_data_generator = self._get_sim_data(
            self.jobs_to_send
        )

    def _set_total_number_of_events(self) -> None:
        """Method to calculate and set the total number of events of the
        simulation
        """
        self.total_number_of_events = sum(
            len(job.events)
            for job in self.jobs_to_send
        )

    def _set_delay_profile(self) -> None:
        """Method to set the delay profile for the test. If no test profile
        has been input a uniform profile is created using a rate of one
        divided by the `interval` attribute
        """
        if self.test_profile is None:
            num_per_sec = min(
                self.total_number_of_events, round(1 / self.interval)
            )
            self.test_profile = Profile(
                pd.DataFrame([
                    [sim_time, num_per_sec] for sim_time in range(
                        math.ceil(
                            (self.total_number_of_events + 1) / num_per_sec
                        ) + 1
                    )
                ])
            )
            self.test_profile.transform_raw_profile()
        self.delay_times = self.test_profile.delay_times[
            : self.total_number_of_events
        ]

    def _get_min_interval(self) -> float | int:
        return np.min(np.diff(self.delay_times))

    @abstractmethod
    def _get_sim_data(
        self,
        jobs_to_send: list[Job]
    ) -> Generator[SimDatum, Any, None]:
        """Abstract method to get the sim data for the test

        :param jobs_to_send: A list of the template jobs to send
        :type jobs_to_send: `list`[:class:`Job`]
        :yield: Yields :class:`SimDatum` containing the relevant simulation
        information for each event, respectively
        :rtype: :class:`Generator`[:class:`SimDatum`, `Any`, `None`]
        """
        yield from generate_events_from_template_jobs(
            template_jobs=jobs_to_send,
            sequence_generator=job_sequencer,
            generator_function=generate_job_batch_events,
            sequencer_kwargs={
                "min_interval_between_job_events": self._get_min_interval()
            }
        )

    def _set_jobs_to_send(self):
        self.jobs_to_send = self._get_jobs_to_send()

    @abstractmethod
    def _get_jobs_to_send(self) -> list[Job]:
        """Method to get all the jobs to send

        :return: Returns a list of jobs sequences and their info
        :rtype: `list`[:class:`Job`]
        """

    @abstractmethod
    def set_test_rate(self) -> None:
        """Method to set the test interval and shard attribute
        """
        self.interval = 0.1
        self.shard = False

    async def send_test_files(
        self,
        results_handler: PVResultsHandler
    ) -> None:
        """Asynchronous method to send test files to the PV

        :param results_handler: A list of the template jobs to send
        :type results_handler: `list`[:class:`Job`]
        """
        self.simulator = Simulator(
            delays=self.delay_times,
            simulation_data=self.sim_data_generator,
            action_func=send_list_dict_as_json_wrap_url(
                url=self.harness_config.pv_send_url
            ),
            results_handler=results_handler
        )
        # set the sim start time
        results_handler.results_holder.time_start = datetime.now()
        await self.simulator.simulate()

    async def run_test(self) -> None:
        """Asynchronous method to run the test
        """
        with PVResultsHandler(
            results_holder=self.results,
            test_output_directory=self.test_output_directory,
            save_files=self.save_files
        ) as pv_results_handler:
            try:
                await asyncio.gather(
                    self.send_test_files(results_handler=pv_results_handler),
                    self.pv_file_inspector.run_pv_file_inspector(),
                )
            except RuntimeError as error:
                logging.getLogger().info(msg=str(error))

    @abstractmethod
    def calc_results(self) -> None:
        """Method to cal the results and save reports for the test
        """

    def clean_directories(self) -> None:
        """Method to clean up log and uml file store directories
        """
        clean_directories(
            [
                self.harness_config.uml_file_store,
                self.harness_config.log_file_store,
                self.harness_config.profile_store
            ]
        )
        try:
            response_tuple = send_get_request(
                url=self.harness_config.pv_clean_folders_url,
                max_retries=self.harness_config.requests_max_retries,
                timeout=(
                    self.harness_config.requests_timeout,
                    self.harness_config.pv_clean_folders_read_timeout
                )
            )
            if not response_tuple[0]:
                logging.getLogger().warning(
                    "There was an error with the request to clean up PV"
                    "folders"
                    " for next test with request response: %s",
                    response_tuple[2].text
                )
        except ReadTimeout:
            logging.getLogger().warning(
                "The read time out limit of %s was reached. Not all PV folders"
                "will be empty. It is suggested the harness config "
                "'pv_clean_folder_read_timeout' is increased."
            )


class FunctionalTest(Test):
    """Child class of :class:`Test` for functional tests.

    :param test_file_generators: Dictionary containing generated tests for
    each job definition
    :type test_file_generators: `dict`[ `str`, `dict`[ `str`, `tuple`[
    :class:`Generator`[ `tuple`[`list`[`dict`], `list`[`str`],
    :class:`plt`.`Figure`  |  `None`, `str`], `Any`, `None`, ], `bool`, ], ], ]
    :param harness_config: Main config for the test harness, defaults to `None`
    :type harness_config: :class:`HarnessConfig` | `None`, optional
    :param test_config: Config for the specific test, defaults to `None`
    :type test_config: :class:`TestConfig` | `None`, optional
    :param test_output_directory: The path of the test output directory where
    files relating to the test results are stored, defaults to `None`
    :type test_output_directory: `str` | `None`, optional
    """

    def __init__(
        self,
        test_file_generators: dict[
            str,
            dict[
                str,
                tuple[
                    Generator[
                        tuple[list[dict], list[str], plt.Figure | None, str],
                        Any,
                        None,
                    ],
                    bool,
                ],
            ],
        ],
        harness_config: HarnessConfig | None = None,
        test_config: TestConfig | None = None,
        test_output_directory: str | None = None,
        test_profile: None = None
    ) -> None:
        super().__init__(
            test_file_generators,
            harness_config,
            test_config,
            test_output_directory=test_output_directory,
            save_files=True,
            test_profile=test_profile
        )

    def set_results_holder(self) -> PVResults:
        return super().set_results_holder()

    def _get_sim_data(
        self,
        jobs_to_send: list[Job]
    ) -> Generator[SimDatum, Any, None]:
        """Method to get the sim data for the test

        :param jobs_to_send: A list of the template jobs to send
        :type jobs_to_send: `list`[:class:`Job`]
        :yield: Yields :class:`SimDatum` containing the relevant simulation
        information for each event, respectively
        :rtype: :class:`Generator`[:class:`SimDatum`, `Any`, `None`]
        """
        yield from super()._get_sim_data(jobs_to_send)

    def _get_jobs_to_send(self) -> list[Job]:
        """Method to get all the jobs to send

        :return: Returns a list of jobs sequences and their info
        :rtype: `list`[:class:`Job`]
        """
        return self.job_templates

    def set_test_rate(self) -> None:
        """Method to set the test interval at the default value of 0.1 seconds
        """
        self.interval = 0.1
        self.shard = False

    def calc_results(self) -> None:
        """Method to calc the results after the test and save reports
        """
        # load verifier logs and concatenate string
        log_string = self.pv_file_inspector.load_log_files_and_concat_strings()
        # get the validity dataframe
        validity_df = self.results.create_validity_dataframe()
        # analyse the logs and get report files
        report_files_mapping = create_report_files(
            log_string=log_string,
            validity_df=validity_df,
            test_name="Results"
        )
        report_files_mapping["Results_Aggregated.html"] = self.make_figs(
            report_files_mapping["Results.csv"]
        )
        deliver_test_report_files(
            report_files_mapping=report_files_mapping,
            output_directory=self.test_output_directory,
        )

    @staticmethod
    def make_figs(results_df: pd.DataFrame) -> Figure:
        """Method to generate a grouped bar chart from the test output
        dataframe

        :param results_df: Dataframe with columns:
        * "Category" - The category of sequence
        * "TestResult" - The result of the test
        * "JobId" - the identifier of the job
        :type results_df: :class:`pd`.`DataFrame`
        :return: Returns the plotly :class:`Figure` object
        :rtype: :class:`Figure`
        """
        results_df = results_df.reset_index()
        aggregated_df = results_df[
            ["Category", "TestResult", "JobId"]
        ].groupby(
            [
                "Category", "TestResult"
            ]
        ).agg("count").reset_index()
        aggregated_df.columns = ["Category", "TestResult", "Count"]
        fig = px.bar(
            aggregated_df,
            x="TestResult",
            y="Count",
            color="Category"
        )
        fig.add_hline(len(results_df))
        return fig


class PerformanceTest(Test):
    """Class to hold and run a performance test. Sub class of :class:`Test`

    :param test_file_generators: Dictionary containing generated tests for
    each job definition
    :type test_file_generators: `dict`[ `str`, `dict`[ `str`, `tuple`[
    :class:`Generator`[ `tuple`[`list`[`dict`], `list`[`str`],
    :class:`plt`.`Figure`  |  `None`, `str`], `Any`, `None`, ], `bool`, ], ], ]
    :param harness_config: Main config for the test harness, defaults to `None`
    :type harness_config: :class:`HarnessConfig` | `None`, optional
    :param test_config: Config for the specific test, defaults to `None`
    :type test_config: :class:`TestConfig` | `None`, optional
    :param test_output_directory: The path of the test output directory where
    files relating to the test results are stored, defaults to `None`
    :type test_output_directory: `str` | `None`, optional
    """
    def __init__(
        self,
        test_file_generators: dict[
            str,
            dict[
                str,
                tuple[
                    Generator[
                        tuple[list[dict], list[str], Any | None, str],
                        Any,
                        None,
                    ],
                    bool,
                ],
            ],
        ],
        harness_config: HarnessConfig | None = None,
        test_config: TestConfig | None = None,
        test_output_directory: str | None = None,
        test_profile: Profile | None = None
    ) -> None:
        """Constructor method
        """
        super().__init__(
            test_file_generators,
            harness_config,
            test_config,
            test_output_directory=test_output_directory,
            save_files=False,
            test_profile=test_profile
        )

    def set_results_holder(self) -> PVPerformanceResults:
        return PVResultsDataFrame()

    def _get_sim_data(
        self,
        jobs_to_send: list[Job]
    ) -> Generator[SimDatum, Any, None]:
        """Method to get the sim data for the test

        :param jobs_to_send: A list of the template jobs to send
        :type jobs_to_send: `list`[:class:`Job`]
        :yield: Yields :class:`SimDatum` containing the relevant simulation
        information for each event, respectively
        :rtype: :class:`Generator`[:class:`SimDatum`, `Any`, `None`]
        """
        if self.shard:
            event_generator = generate_single_events
        else:
            event_generator = generate_job_batch_events
        yield from generate_events_from_template_jobs(
            template_jobs=jobs_to_send,
            sequence_generator=job_sequencer,
            generator_function=event_generator,
            sequencer_kwargs={
                "min_interval_between_job_events": self._get_min_interval()
            }
        )

    def _get_jobs_to_send(self) -> list[Job]:
        """Method to create the jobs to send

        :return: Returns the jobs to send
        :rtype: `list`[`tuple`[:class:`Job`, `dict`[`str`, `str` | `bool`]]]
        """
        if self.test_profile:
            jobs_to_send = []
            num_events = 0
            max_number_of_events = len(self.test_profile.delay_times)
            while True:
                job = choice(self.job_templates)
                num_events += len(job.events)
                if num_events > max_number_of_events:
                    break
                jobs_to_send.append(job)
        else:
            jobs_to_send = choices(
                self.job_templates,
                k=self.test_config.performance_options["total_jobs"],
            )
        return jobs_to_send

    def set_test_rate(self) -> None:
        """Method to set the test interval at the default value of 0.1 seconds
        and shard attribute
        """
        self.interval = (
            1 / self.test_config.performance_options["num_files_per_sec"]
        )
        self.shard = self.test_config.performance_options["shard"]

    def get_all_simulation_data(self) -> None:
        """Method to read and calculate al simulation data
        """
        self.get_pv_sim_data()
        self.results.calc_all_results()

    def get_pv_sim_data(self) -> None:
        """Method to get the PV sim data from the grok endpoint and read into
        results
        """
        # download grok file
        grok_file_path = os.path.join(
            self.harness_config.log_file_store,
            "grok.txt"
        )
        download_file_to_path(
            self.harness_config.pv_grok_exporter_url,
            self.harness_config.log_file_store
        )
        self.results.get_and_read_grok_metrics(
            grok_file_path
        )

    def calc_results(self) -> None:
        """Method to calc the results after the test and save reports
        """
        if any(
            len(domain_coords) < 2
            for domain_coords in self.pv_file_inspector.coords.values()
        ):
            logging.getLogger().warning(
                "Cannot calculate results as not enough data points were "
                "taken. The read timeout of io folder calculations may need "
                "to be increased"
            )
            return
        self.pv_file_inspector.calc_test_boundaries()
        self.pv_file_inspector.normalise_coords()
        num_jobs = len(self.jobs_to_send)
        num_events = self.total_number_of_events
        average_num_jobs_per_sec = (
            num_jobs / self.pv_file_inspector.test_boundaries[2]
        )
        average_num_events_per_sec = (
            num_events / self.pv_file_inspector.test_boundaries[2]
        )
        df_basic_results = pd.DataFrame.from_dict(
            {
                "num_jobs": num_jobs,
                "num_events": num_events,
                "average_jobs_per_sec": average_num_jobs_per_sec,
                "average_events_per_sec": average_num_events_per_sec,
                "reception_end_time": (
                    self.pv_file_inspector.test_boundaries[3]
                ),
                "verifier_end_time": self.pv_file_inspector.test_boundaries[4],
            },
            orient="index",
        )
        df_basic_results.index.name = "Data Field"
        df_pv_file_results = pd.DataFrame(
            [
                (
                    time,
                    self.test_config.performance_options["num_files_per_sec"],
                    "Files Sent/s",
                )
                for time in range(
                    len(self.results)
                    // self.test_config.performance_options[
                        "num_files_per_sec"
                    ]
                )
            ]
            + [
                coord + ("AER Incoming\nFiles",)
                for coord in self.pv_file_inspector.coords["aer"]
            ]
            + [
                (time, 0, "Files Sent/s")
                for time in range(
                    len(self.results)
                    // self.test_config.performance_options[
                        "num_files_per_sec"
                    ],
                    self.pv_file_inspector.test_boundaries[2],
                )
            ]
            + [
                coord + ("Verifier Files",)
                for coord in self.pv_file_inspector.coords["ver"]
            ],
            columns=["Time (s)", "Number", "Metric"],
        )
        df_pv_file_results = df_pv_file_results.groupby(
            ["Time (s)", "Metric"]
        ).mean().reset_index()
        # add verifier files pers second
        verifier_files_per_second = (
            df_pv_file_results.loc[
                df_pv_file_results["Metric"] == "Verifier Files"
            ].sort_values("Time (s)").reset_index(
                drop=True
            )
        )
        verifier_files_per_second["Number"] = verifier_files_per_second[
            "Number"
        ].diff()
        verifier_files_per_second.loc[0, "Number"] = 0
        verifier_files_per_second["Metric"] = "Verifier Files/s"
        df_pv_file_results = pd.concat(
            [df_pv_file_results, verifier_files_per_second],
            ignore_index=True
        )
        # filter out results that are greater than the calculated test end time
        df_pv_file_results = df_pv_file_results[
            (
                df_pv_file_results["Time (s)"]
            ) <= self.pv_file_inspector.test_boundaries[2]
        ]
        df_pv_file_results.index.name = "Index"
        # make figures
        figure = self.make_figs(df_pv_file_results)
        deliver_test_report_files(
            {
                "Basic_Stats.csv": df_basic_results,
                "PV_File_IO.csv": df_pv_file_results,
                "PV_File_IO.html": figure,
            },
            output_directory=self.test_output_directory,
        )

    @staticmethod
    def make_figs(df_pv_file_results: pd.DataFrame) -> Figure:
        """Method to generate a grouped bar chart from the test output
        dataframe

        :param df_pv_file_results: Dataframe with columns:
        * "Time (s)" - the simulation time of the entry - integer
        * "Number" - the value of the given metric - float
        * "Metric" - the identifier of the metric
        :type df_pv_file_results: :class:`pd`.`DataFrame`
        :return: Returns the plotly :class:`Figure` object
        :rtype: :class:`Figure`
        """
        # first figure
        fig = px.bar(
            df_pv_file_results,
            x="Time (s)",
            y="Number",
            color="Metric",
            barmode="group",
        )
        fig.update_xaxes(dtick=1)
        return fig
