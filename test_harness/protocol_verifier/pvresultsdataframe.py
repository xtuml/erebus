# pylint: disable=R0902
# pylint: disable=R0913
# pylint: disable=W0221
# pylint: disable=W0246
# pylint: disable=W0613
# pylint: disable=C0302
# pylint: disable=C0114
# pylint: disable=C0103
from typing import Any

import numpy as np
import pandas as pd
import scipy.stats as sps

from .pvperformanceresults import (
    PVPerformanceResults,
    AveragesDict,
    FailuresDict,
    ReceptionCountsDict,
)

# TODO change this class name


class PVResultsDataFrameCalculator:
    def __init__(self, events_dict: dict[str, dict[str, Any]], end_times: float | None, data_fields: Any) -> None:
        self.end_times = end_times
        self.data_fields = data_fields
        self._results = pd.DataFrame.from_dict(events_dict, orient="index")
        for new_col in self.data_fields[3:]:
            if new_col not in self.results.columns:
                self.results[new_col] = np.nan

        self._create_response_time_fields()

    @property
    def results(self):
        """The results of this calcualtor in a pandas dataframe."""
        return self._results

    @results.setter
    def results(self, _):
        raise RuntimeError("Redefining self.results is not allowed")

    def __len__(self) -> int:
        """The length of the results

        :return: The length of the results holder
        :rtype: `int`
        """
        return len(self.results)

    # def create_final_results_holder(self) -> None:
    #     self.results = pd.DataFrame.from_dict(self.results, orient="index")
    #     for new_col in self.data_fields[3:]:
    #         if new_col not in self.results.columns:
    #             self.results[new_col] = np.nan

    def _create_response_time_fields(self) -> None:
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
        num_tests = len(self.results)
        num_failures = num_tests - self.results["AEOSVDC_end"].count()
        num_errors = len(self.results[self.results["response"] != ""])
        return {
            "num_tests": num_tests,
            "num_failures": num_failures,
            "num_errors": num_errors,
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
            "aer_end": np.nanmax(self.results["AER_end"]),
        }

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
        if self.end_times is None:
            raise ValueError("self.end_times has not been defined")
        return {
            "average_sent_per_sec": (
                self.results["time_sent"].count() / self.end_times["th_end"]
            ),
            "average_processed_per_sec": (
                self.results["AEOSVDC_end"].count() / self.end_times["pv_end"]
            ),
            "average_queue_time": np.nanmean(self.results["queue_time"]),
            "average_response_time": np.nanmean(
                self.results["full_response_time"]
            ),
        }

    def calc_reception_counts(self) -> ReceptionCountsDict:
        """Returns a dictionary of counts for reception recevied and reception
        written

        :return: Returns a dictionary of reception received and written counts
        :rtype: :class:`ReceptionCountsDict`
        """
        return {
            "num_aer_start": self.results["AER_start"].count(),
            "num_aer_end": self.results["AER_end"].count(),
        }

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
        :type time_window: `int`, optional
        :return: Returns a dataframe of the aggeragted results
        :rtype: :class:`pd`.`DataFrame`
        """
        if self.end_times is None:
            raise ValueError("self.end_times has not been defined")
        test_end_ceil = np.ceil(np.nanmax(list(self.end_times.values())))
        time_range = np.arange(0, test_end_ceil + time_window, time_window)
        # get aggregated events sent per second
        aggregated_sent = sps.binned_statistic(
            self.results["time_sent"],
            [1] * len(self.results),
            bins=time_range,
            statistic="count",
        ).statistic
        # get events per second
        aggregated_events = sps.binned_statistic(
            self.results["AEOSVDC_end"],
            [1] * len(self.results),
            bins=time_range,
            statistic="count",
        ).statistic
        # get aggregated number of events processed by AER
        aggregated_aer_events = sps.binned_statistic(
            self.results["AER_end"],
            [1] * len(self.results),
            bins=time_range,
            statistic="count",
        ).statistic
        # get aggregated full response time
        aggregated_full_response_time = sps.binned_statistic(
            self.results["time_sent"],
            self.results["full_response_time"],
            bins=time_range,
            statistic=np.nanmean,
        ).statistic
        # get aggregated time in queue
        aggregated_queue_time = sps.binned_statistic(
            self.results["time_sent"],
            self.results["queue_time"],
            bins=time_range,
            statistic=np.nanmean,
        ).statistic
        # get cumulative number of events sent per second
        cumulative_events_sent_per_second = np.nancumsum(aggregated_sent)
        # get cumulative number of events processed per second
        cumulative_events_processed_per_second = np.nancumsum(
            aggregated_events
        )
        # get cumulative number of aer events processed per second
        cumulative_aer_events_processed_per_second = np.nancumsum(
            aggregated_aer_events
        )
        # divide sent, processed and aer processed
        aggregated_sent_per_second = aggregated_sent / time_window
        aggregated_events_per_second = aggregated_events / time_window
        aggregated_aer_events_per_second = aggregated_aer_events / time_window

        aggregated_results = pd.DataFrame(
            np.vstack(
                [
                    time_range[:-1] + time_window / 2,
                    aggregated_sent_per_second,
                    aggregated_events_per_second,
                    aggregated_aer_events_per_second,
                    aggregated_queue_time,
                    aggregated_full_response_time,
                    cumulative_events_sent_per_second,
                    cumulative_events_processed_per_second,
                    cumulative_aer_events_processed_per_second,
                ]
            ).T,
            columns=[
                "Time (s)",
                "Events Sent (/s)",
                "Events Processed (/s)",
                "AER Events Processed (/s)",
                "Queue Time (s)",
                "Response Time (s)",
                "Cumulative Events Sent",
                "Cumulative Events Processed",
                "Cumulative AER Events Processed",
            ],
        )
        return aggregated_results


class PVResultsDataFrame(PVPerformanceResults):
    """Sub class of :class:`PVPerformanceResults: to get perfromance results
    using a pandas dataframe as the results holder.
    """

    def __init__(self, binning_window: int = 1) -> None:
        """Constructor method"""
        super().__init__(binning_window)
        self.job_id_event_id_map: dict[str, set[str]] = {}

        self._calculator: PVResultsDataFrameCalculator

    def __len__(self) -> int:
        """The length of the results

        :return: The length of the results holder
        :rtype: `int`
        """
        return len(self.results)


    # This is legit a bit sneaky, 
    @property
    def calculator(self):
        if isinstance(self.results, dict):
            return PVResultsDataFrameCalculator(
                    events_dict=self.results,
                    end_times=self.end_times if hasattr(self, 'end_times') else None,
                    data_fields=self.data_fields if hasattr(self, 'data_fields') else None,
                )
        elif isinstance(self.results, pd.DataFrame):
            return PVResultsDataFrameCalculator(
                    events_dict=self.results.to_dict(orient='index'),
                    end_times=self.end_times if hasattr(self, 'end_times') else None,
                    data_fields=self.data_fields if hasattr(self, 'data_fields') else None,
                )
        else:
            raise ValueError(f"self.results is unsupported type: {type(self.results)}")


        # try:
        #     return self._calculator
        # except AttributeError:
        #     self._calculator = PVResultsDataFrameCalculator(
        #         events_dict=self.results,
        #         end_times=self.end_times if hasattr(self, 'end_times') else None,
        #         data_fields=self.data_fields if hasattr(self, 'data_fields') else None,
        #     )
        #     return self._calculator


    def create_final_results_holder(self) -> None:
        self.results = self.calculator.results

        # self.results = pd.DataFrame.from_dict(self.results, orient="index")
        # for new_col in self.data_fields[3:]:
        #     if new_col not in self.results.columns:
        #         self.results[new_col] = np.nan

    def _create_results_holder(self) -> None:
        """Creates the results holder as pandas DataFrame"""
        # self.results = pd.DataFrame(columns=self.data_fields)
        self.results = {}

    def create_event_result_row(self, event_id: str) -> None:
        """Method to create a row in the results holder based on an
        event id

        :param event_id: Unique event id
        :type event_id: `str`
        """
        self.results[event_id] = {}

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
        if event_id not in self.results:
            return
        self.results[event_id] = {**self.results[event_id], **update_values}
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
        if job_id in self.job_id_event_id_map:
            for event_id in self.job_id_event_id_map[job_id]:
                self.results[event_id] = {
                    **self.results[event_id],
                    **update_values,
                }

    def create_response_time_fields(self) -> None:
        """Method used to create response fields in the results holder
        * full_response_time - the AEOSVDC end time minus the time sent
        * queue_time - The time when event was picked up by AER minus the time
        sent
        """
        pass
        # self.results["full_response_time"] = (
        #     self.results["AEOSVDC_end"] - self.results["time_sent"]
        # )
        # self.results["full_response_time"].clip(lower=0, inplace=True)
        # self.results["queue_time"] = (
        #     self.results["AER_start"] - self.results["time_sent"]
        # )
        # self.results["queue_time"].clip(lower=0, inplace=True)

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
        :type time_window: `int`, optional
        :return: Returns a dataframe of the aggeragted results
        :rtype: :class:`pd`.`DataFrame`
        """
        return self.calculator.calculate_aggregated_results_dataframe(
            time_window=time_window
        )
