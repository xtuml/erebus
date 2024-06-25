# pylint: disable=R0902
# pylint: disable=R0913
# pylint: disable=W0221
# pylint: disable=W0246
# pylint: disable=W0613
# pylint: disable=C0302
# pylint: disable=C0114
# pylint: disable=R0904
import os
from datetime import datetime
import math
from threading import Lock
import tempfile
import random
from typing import Any, TextIO

import pandas as pd
from prometheus_client.parser import text_fd_to_metric_families
from pygrok import Grok

from test_harness.protocol_verifier.reporting.log_analyser import (
    yield_grok_metrics_from_files
)
from test_harness.results.aggregation import (
    AggregationBin,
    AggregationCount,
    AggregationMax,
    AggregationTask,
    BinValueCount,
)
from .pv_results import PVResults
from .pv_results_dataframe_calculator import (
    PVResultsDataFrameCalculatorV2,
    PVResultsDataFrameCalculator,
)
from test_harness.protocol_verifier.utils.types import (
    AveragesDict,
    FailuresDict,
    ProcessErrorDataDict,
    ReceptionCountsDict,
    ResultsDict,
)
from test_harness.results.results import ResultsHolder, DictResultsHolder
from test_harness.protocol_verifier.metrics_and_events.kafka_metrics import (
    consume_events_from_kafka_topic
)


class PVPerformanceResults(PVResults):
    """Base class for perfromance test results extending :class:`PVResults`"""

    pv_grok_map = {
        "aeordering_events_processed_total": "AEOSVDC_start",
        "aeordering_events_processed": "AEOSVDC_start",
        # "reception_event_invalid",
        "reception_event_received_total": "AER_start",
        "reception_event_received": "AER_start",
        # "reception_event_valid",
        "reception_event_written_total": "AER_end",
        "reception_event_written": "AER_end",
        "svdc_event_processed": "AEOSVDC_end",
        "svdc_happy_event_processed": "AEOSVDC_end",
        "svdc_job_failed_total": "AEOSVDC_end",
        "svdc_job_failed": "AEOSVDC_end",
        "svdc_job_success_total": "AEOSVDC_end",
        "svdc_job_success": "AEOSVDC_end",
        "svdc_unhappy_event_processed": "AEOSVDC_end",
    }
    process_error_fields_map = {
        "reception_file_process_error": "AER_file_process_error",
        "aeordering_file_processing_failure": "AEO_file_process_error",
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
    verifier_grok_priority_patterns = [
        Grok(
            "%{TIMESTAMP_ISO8601:timestamp} %{NUMBER} %{WORD:field} :"
            " JobId = %{UUID} : EventId = %{UUID:event_id} : "
            "EventType = %{WORD}"
        ),
        Grok(
            "%{TIMESTAMP_ISO8601:timestamp} %{NUMBER} %{WORD:field} :"
            " JobId = %{UUID:job_id}"
        ),
    ]
    reception_grok_priority_patterns = [
        Grok(
            "%{TIMESTAMP_ISO8601:timestamp} %{WORD:field} :"
            " EventId = %{UUID:event_id}"
        )
    ]

    def __init__(
        self,
        binning_window: int = 1,
        test_output_directory: str | None = None,
        sample_rate: int = 0,
        agg_during_test: bool = False,
        low_memory: bool = False,
    ) -> None:
        """Constructor method"""
        super().__init__()
        self.results = None
        self.binning_window = binning_window
        self.process_errors: dict[int, ProcessErrorDataDict] = {}
        self.test_output_directory = test_output_directory
        self._low_memory = low_memory
        self._create_results_holder()
        self.end_times: dict[str, float] | None = None
        self.failures: FailuresDict | None = None
        self.full_averages: AveragesDict | None = None
        self.reception_event_counts: ReceptionCountsDict | None = None
        self.agg_results: pd.DataFrame | None = None
        self.process_errors_counts: ProcessErrorDataDict | None = None
        self.process_errors_agg_results: pd.DataFrame | None = None

        self.job_id_event_id_map: dict[str, set[str]] = {}
        self._calculator: PVResultsDataFrameCalculatorV2 | None = None
        self._update_lock = Lock()
        self._aggregation_tasks = None
        self._aggregation_map = None
        if sample_rate == 0 or not agg_during_test:
            # if sample rate is 0 or not aggregating during test
            # then do not sample
            self._sampler = None
        else:
            self._sampler = Sampler(sample_rate)
        self._agg_during_test = agg_during_test
        # must aggregate during test if in low memory mode
        if self._low_memory:
            self._agg_during_test = True

    def __len__(self) -> int:
        """The length of the results

        :return: The length of the results holder
        :rtype: `int`
        """
        return len(self.results)

    @property
    def calculator(self):
        """A just-in-time instantiated PVResultsDataFrameCalculator."""
        if self._calculator is None:
            if isinstance(self.results, ResultsHolder):
                self._calculator = PVResultsDataFrameCalculatorV2(
                    results_holder=self.results,
                    end_times=(
                        self.end_times if hasattr(self, "end_times") else None
                    ),
                    aggregation_holders=self.aggregation_tasks,
                )
            elif isinstance(self.results, dict):
                return PVResultsDataFrameCalculator(
                    events_dict=self.results,
                    end_times=(
                        self.end_times if hasattr(self, "end_times") else None
                    ),
                    data_fields=(
                        self.data_fields
                        if hasattr(self, "data_fields")
                        else None
                    ),
                )
            elif isinstance(self.results, pd.DataFrame):
                return PVResultsDataFrameCalculator(
                    events_dict=self.results.to_dict(orient="index"),
                    end_times=(
                        self.end_times if hasattr(self, "end_times") else None
                    ),
                    data_fields=(
                        self.data_fields
                        if hasattr(self, "data_fields")
                        else None
                    ),
                )
            else:
                raise TypeError(
                    f"self.results is unsupported type: {type(self.results)}"
                )
        return self._calculator

    def _create_results_holder(self) -> None:
        """Creates the results holder as pandas DataFrame"""
        # self.results = pd.DataFrame(columns=self.data_fields)
        if self.test_output_directory is None:
            self.test_output_directory = tempfile.mkdtemp()
        self.results = DictResultsHolder(
            fields=self.data_fields if self._low_memory else None
        )
        # TODO: implement DataBaseTableResultsHolder functionality
        # self.results = DataBaseTableResultsHolder(
        #     db_path=f"sqlite:///{self.test_output_directory}/results.db",
        #     columns=[
        #         {
        #             "name": "event_id",
        #             "type_": "string",
        #             "primary_key": True
        #         },
        #         {
        #             "name": "job_id",
        #             "type_": "string",
        #             "primary_key": False
        #         },
        #         {
        #             "name": "time_sent",
        #             "type_": "float",
        #             "primary_key": False
        #         },
        #         {
        #             "name": "response",
        #             "type_": "string",
        #             "primary_key": False
        #         },
        #         {
        #             "name": "AER_start",
        #             "type_": "float",
        #             "primary_key": False
        #         },
        #         {
        #             "name": "AER_end",
        #             "type_": "float",
        #             "primary_key": False
        #         },
        #         {
        #             "name": "AEOSVDC_start",
        #             "type_": "float",
        #             "primary_key": False,
        #         },
        #         {
        #             "name": "AEOSVDC_end",
        #             "type_": "float",
        #             "primary_key": False,
        #         },
        #     ],
        # )
        # os.makedirs(self.test_output_directory, exist_ok=True)
        # self.results = shelve.open(
        #     os.path.join(self.test_output_directory, "results.shelve")
        # )
        # self.results = {}

    def update_event_results_with_event_id(
        self, event_id: str, update_values: dict[str, Any]
    ) -> None:
        """Method that is used to update the results holder with an
        event id as key and update values named in a dictionary

        :param event_id: Unique event id
        :type event_id: `str`
        :param update_values: Arbitrary named update values
        :type update_values: `dict`[`str`, `Any`]
        """
        self._update_results(event_id, update_values)
        if self._low_memory:
            return
        if "job_id" in update_values:
            if update_values["job_id"] not in self.job_id_event_id_map:
                self.job_id_event_id_map[update_values["job_id"]] = set()
            self.job_id_event_id_map[update_values["job_id"]].add(event_id)

    def update_event_results_with_job_id(
        self, job_id: str, update_values: dict[str, Any]
    ) -> None:
        """Method to update all rows in results holder based on the
        column job id match

        :param job_id: Job id
        :type job_id: `str`
        :param update_values: Arbitrary named update values
        :type update_values: `dict`[`str`, `Any`]
        """
        if self._low_memory:
            return
        if job_id in self.job_id_event_id_map:
            for event_id in self.job_id_event_id_map[job_id]:
                self._update_results(event_id, update_values)

    def _update_results(self, event_id: str, update_values: dict[str, Any]):
        self._update_lock.acquire()
        if self._agg_during_test:
            for key, value in update_values.items():
                if key in self.aggregation_map:
                    for agg_key in self.aggregation_map[key]:
                        self.aggregation_tasks[agg_key].update(value)
        if self._low_memory:
            self._update_lock.release()
            return
        if event_id in self.results or self._sampler is None:
            pass
        else:
            if not self._sampler():
                self._update_lock.release()
                return
        self.results[event_id] = update_values
        self._update_lock.release()

    def create_event_result_row(self, event_id: str) -> None:
        """Method to create a row in the results holder based on an
        event id

        :param event_id: Unique event id
        :type event_id: `str`
        """
        self.results[event_id] = {}

    def update_from_sim(
        self,
        event_list: list[dict],
        job_id: str,
        response: str,
        time_completed: datetime,
        file_name: str = "",
        job_info: dict[str, str] | None = None,
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
        if job_info is None:
            job_info = {}
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
        # self.create_event_result_row(event_id)
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

    def add_results_from_log_files(
        self, file_paths: list[str], grok_priority_patterns: list[Grok]
    ) -> None:
        """Method to add results to Results holder for a given list of file
        paths looking for a list of grok patterns in order of priority

        :param file_paths: List of log file paths
        :type file_paths: `list`[`str`]
        :param grok_priority_patterns: List of :class:`Grok` patterns in
        priority order
        :type grok_priority_patterns: `list`[:class:`Grok`]
        """
        for result in yield_grok_metrics_from_files(
            file_paths=file_paths, grok_priorities=grok_priority_patterns
        ):
            self.add_result(result)

    def add_result(self, result: ResultsDict) -> None:
        """Method to add a result to instance. If
        * the result field is an event result the instance will be updated
        using `update_pv_sim_time_field`
        * if the result field is a processing error field the instance will be
        updated using `add_error_process_field`

        :param result: _description_
        :type result: ResultsDict
        """
        if result["field"] in self.pv_grok_map:
            result["field"] = self.pv_grok_map[result["field"]]
            self.update_pv_sim_time_field(**result)
        if result["field"] in self.process_error_fields_map:
            result["field"] = self.process_error_fields_map[result["field"]]
            self.add_error_process_field(result)

    def add_error_process_field(self, result: ResultsDict) -> None:
        """Adds an error processing result to the process_erros attribute dict

        :param result: The dictionary of the input result
        :type result: :class:`ResultsDict`
        """
        converted_time = self.convert_pv_time_string(result["timestamp"])
        bin_number = math.floor(converted_time / self.binning_window)
        if bin_number not in self.process_errors:
            self.process_errors[bin_number] = ProcessErrorDataDict(
                AEO_file_process_error=0, AER_file_process_error=0
            )
        self.process_errors[bin_number][result["field"]] += 1

    def add_verifier_results_from_log_files(
        self, file_paths: list[str]
    ) -> None:
        """Method to add results from verifier log files

        :param file_paths: List of log file paths
        :type file_paths: `list`[`str`]
        """
        self.add_results_from_log_files(
            file_paths, self.verifier_grok_priority_patterns
        )

    def add_reception_results_from_log_files(
        self, file_paths: list[str]
    ) -> None:
        """Method to add results from reception log files

        :param file_paths: List of log file paths
        :type file_paths: `list`[`str`]
        """
        self.add_results_from_log_files(
            file_paths, self.reception_grok_priority_patterns
        )

    def add_kafka_results_from_topic(self, host, topic) -> None:
        """Method to add results from kafka topic

        :param host: Kafka host
        :type host: `str`
        :param topic: Kafka topic
        :type topic: `str`
        """
        events = consume_events_from_kafka_topic(host, topic)
        for result in events:
            self.add_result(result)

    def calc_all_results(self, agg_time_window: float = 1.0) -> None:
        """Method to calculate al aggregated results. Data aggregations happen
        over the given time window inseconds

        :param agg_time_window: The time window in seconds for aggregating
        data,
        defaults to `1.0`
        :type agg_time_window: `float`, optional
        """
        self._filter_out_events_not_from_test()
        if not self._agg_during_test:
            self.results = self.results.to_pandas()
        self.results = self.calculator.results
        self.create_response_time_fields()
        self.end_times = self.calc_end_times()
        self.failures = self.calculate_failures()
        self.full_averages = self.calc_full_averages()
        self.reception_event_counts = self.calc_reception_counts()
        self.process_errors_counts = self.calc_processing_errors_counts()
        self.process_errors_agg_results = (
            self.calc_processing_errors_time_series()
        )
        self.agg_results = self.calculate_aggregated_results_dataframe(
            agg_time_window
        )

    @property
    def aggregation_tasks(self) -> dict[str, AggregationTask]:
        """Dictionary of aggregation tasks

        :return: Returns a dictionary of aggregation tasks
        :rtype: `dict`[`str`, :class:`AggregationTask`]
        """
        if self._aggregation_tasks is None:
            self._aggregation_tasks = {
                **{
                    field: AggregationTask(
                        agg_holder=AggregationBin(
                            binning_window=self.binning_window,
                            bin_type=BinValueCount,
                        ),
                    )
                    for field in [
                        "binned_num_sent",
                        "binned_num_processed",
                        "binned_num_aer_processed"
                    ]
                },
                **{
                    field: AggregationTask(
                        agg_holder=AggregationMax(),
                    )
                    for field in [
                        "th_end",
                        "pv_end",
                        "aer_end",
                    ]
                },
                "num_errors": AggregationTask(
                    agg_holder=AggregationCount(),
                    pre_agg_func=lambda x: 1 if x != "" else None,
                ),
                **{
                    field: AggregationTask(
                        agg_holder=AggregationCount(),
                    )
                    for field in [
                        "num_aer_start",
                        "num_aer_end",
                    ]
                },
            }
        return self._aggregation_tasks

    @property
    def aggregation_map(self) -> dict[str, str]:
        """Dictionary of aggregation map

        :return: Returns a dictionary of aggregation map
        :rtype: `dict`[`str`, `str`]
        """
        if self._aggregation_map is None:
            self._aggregation_map = {
                "time_sent": ["binned_num_sent", "th_end"],
                "response": ["num_errors"],
                "AER_start": ["num_aer_start"],
                "AER_end": [
                    "num_aer_end",
                    "binned_num_aer_processed",
                    "aer_end",
                ],
                "AEOSVDC_end": ["binned_num_processed", "pv_end"],
            }
        return self._aggregation_map

    def update_errors(self, num_errors: int) -> None:
        """Method to add errors to the results holder

        :param num_errors: The number of errors to add
        :type num_errors: `int`
        """
        if self.failures is None:
            raise ValueError("Have not calculated other results yet")
        self.failures["num_errors"] += num_errors

    def _filter_out_events_not_from_test(self):
        """Method to filter out events that are not from the current test"""
        self.results.filter_rows_on_field_value(field="time_sent", value=None)

    def create_response_time_fields(self) -> None:
        """Method used to create response fields in the results holder
        * full_response_time - the AEOSVDC end time minus the time sent
        * queue_time - The time when event was picked up by AER minus the time
        sent
        """
        self.results = self.calculator.results

    def calculate_failures(self) -> FailuresDict:
        """Method to generate the failures and successes from the sim

        :return: Returns a dictionary of integers of the following fields:
        * "num_tests" - The number of events in the simulation
        * "num_failures" - The number of event failures in the PV groked logs
        (i.e. did not register a time in AEOSVDC_end)
        * "num_errors" - The number of event failures given by the test
        harness (i.e. the response received was not empty)
        :rtype: `dict`[`str`, `int`]
        """
        return self.calculator.calculate_failures()

    def calc_end_times(self) -> dict[str, float]:
        """Significant end times in the simulation

        :return: A dictionary of significant ending sim times with the
        following fields:
        * "th_end" - the time when the test harness sent its last event
        * "pv_end" - the time when aeosvdc processed it last event
        * "aer_end" - the time when aer processed its last event
        :rtype: `dict`[`str`, `float`]
        """
        return self.calculator.calc_end_times()

    def calc_full_averages(
        self,
    ) -> AveragesDict:
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
        return self.calculator.calc_full_averages()

    def calc_reception_counts(self) -> ReceptionCountsDict:
        """Returns a dictionary of counts for reception recevied and reception
        written

        :return: Returns a dictionary of reception received and written counts
        :rtype: :class:`ReceptionCountsDict`
        """
        return self.calculator.calc_reception_counts()

    def calc_processing_errors_counts(self) -> ProcessErrorDataDict:
        """Method to calculate the total file processing errors in the
        simulation

        :return: Dictionary with the total count of file processing errors for
        each field
        :rtype: ProcessErrorDataDict
        """
        process_errors = ProcessErrorDataDict(
            AER_file_process_error=0, AEO_file_process_error=0
        )
        for entry in self.process_errors.values():
            for process_error_field, count in entry.items():
                process_errors[process_error_field] += count
        return process_errors

    def calc_processing_errors_time_series(self) -> pd.DataFrame:
        """Method to get a dataframe of processing errors with the following
        columns
        * "Time (s)" - The time bin of the result
        * "AER_file_process_error" - The count of AER file processing errors
        in the bin
        * "AEO_file_process_error" - The count of AEO file processing errors
        in the bin

        :return: Returnd the dataframe of counts of file processing errors
        :rtype: :class:`pd`.`DataFrame`
        """
        processing_errors = pd.DataFrame.from_dict(
            self.process_errors,
            orient="index",
            columns=["AER_file_process_error", "AEO_file_process_error"],
        )
        processing_errors.reset_index(inplace=True, names="Time (s)")
        return processing_errors

    def calculate_aggregated_results_dataframe(
        self, time_window: int | float = 1
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
        :type time_window: `int | float`, optional
        :return: Returns a dataframe of the aggeragted results
        :rtype: :class:`pd`.`DataFrame`
        """
        return self.calculator.calculate_aggregated_results_dataframe(
            time_window=time_window
        )


class Sampler:
    """Class to sample at a given rate

    :param sample_rate: The sample rate in samples per second
    :type sample_rate: `int`
    """
    def __init__(
        self,
        sample_rate: int,
    ) -> None:
        """Constructor method"""
        self.sample_rate = sample_rate
        self._count = 0
        self._t_prev = None
        self._rate = sample_rate
        self._probability = self.sample_rate / self._rate
        self._lock = Lock()

    def __call__(self) -> bool:
        """Method to call the sampler

        :return: Returns a boolean of whether to sample or not
        :rtype: `bool`
        """
        try:
            return self._sample()
        except TypeError:
            self._t_prev = datetime.now()
            return True

    def _sample(self) -> bool:
        """Method to sample

        :return: Returns a boolean of whether to sample or not
        :rtype: `bool`
        """
        t_now = datetime.now()
        t_delta = (t_now - self._t_prev).total_seconds()
        self._count += 1
        if t_delta >= 1:
            self._rate = self._count / t_delta
            self._t_prev = t_now
            self._count = 0
            self._probability = min(self.sample_rate / self._rate, 1)
        return random.choices(
            [True, False],
            weights=[self._probability, 1 - self._probability],
            k=1,
        )[0]
