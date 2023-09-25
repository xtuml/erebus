# flake8: noqa
# noqa: E501
# pylint: disable=R0902
# pylint: disable=R0913
# pylint: disable=W0221
# pylint: disable=W0246
# pylint: disable=W0613
# pylint: disable=C0302
# pylint: disable=C0114
from typing import Any, Optional

import dask.dataframe as dd
import dataset
import numpy as np
import pandas as pd
import scipy.stats as sps

from .pvperformanceresults import (
    AveragesDict,
    FailuresDict,
    PVPerformanceResults,
)


class PVResultsDaskDataFrame(PVPerformanceResults):
    """Sub class of :class:`PVPerformanceResults: to get perfromance results
    using a dask dataframe as the results holder.
    """

    def __init__(
        self,
        # TODO figure out why the mode=memory&cache=shared query params are being ignored
        sqlite_address="sqlite:///tmp.db?mode=memory&cache=shared",
    ) -> None:
        """Constructor method"""
        self.sqlite_address = sqlite_address
        self.create_results_holder()
        self._results: Optional[dd.DataFrame] = None
        super().__init__()

    @property
    def results(self) -> dd.DataFrame:
        """This property returns the results holder as a dask dataframe.
        If the results holder is not created, it will create it on the fly

        :return: The results holder
        :rtype: `dask.dataframe.DataFrame`
        """
        if self._results is not None:
            return self._results
        return dd.read_sql_table(
            "results", self.sqlite_address, index_col="id"
        )

    @results.setter
    def results(self, results: dd.DataFrame) -> None:
        self._results = results

    def __len__(self) -> int:
        """The length of the results

        :return: The length of the results holder
        :rtype: `int`
        """
        return len(self.results)

    def create_results_holder(self) -> None:
        """Required by the abstract class but not needed here"""
        # """Creates the results holder as pandas DataFrame"""
        # self.results = pd.DataFrame(columns=self.data_fields)
        # with dataset.connect(self.sqlite_address) as db:
        #     # db.create_table("results", self.data_fields)
        #     table: dataset.Table = db.create_table("results", 'id')

        #     # TODO instead do this at some point when we receive the first piece of data
        #     table.create_column('id', db.types.bigint, primary_key=True)
        #     for field in self.data_fields:
        #         table.create_column(field, db.types.string)

        # with dataset.connect(self.sqlite_address) as db:
        #     t: dataset.Table = db.get_table('results')
        #     assert t.columns, t.columns
        #     # db.create_table("results", self.data_fields)

    def create_event_result_row(self, event_id: str) -> None:
        """Method to create a row in the results holder based on an
        event id

        :param event_id: Unique event id
        :type event_id: `str`
        """
        # return NotImplemented
        # self.results.loc[event_id] = None

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

        with dataset.connect(self.sqlite_address) as database:
            t: dataset.Table = database["results"]
            t.upsert({"event_id": event_id, **update_values}, ["event_id"])

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
        with dataset.connect(self.sqlite_address) as database:
            t: dataset.Table = database["results"]
            t.create_column("event_id", database.types.string)
            t.upsert({"job_id": job_id, **update_values}, ["job_id"])

    def create_response_time_fields(self) -> None:
        """Method used to create response fields in the results holder
        * full_response_time - the AEOSVDC end time minus the time sent
        * queue_time - The time when event was picked up by AER minus the time
        sent
        """
        self.results["full_response_time"] = (
            self.results["AEOSVDC_end"] - self.results["time_sent"]
        )
        self.results["full_response_time"] = self.results[
            "full_response_time"
        ].clip(lower=0)
        self.results["queue_time"] = (
            self.results["AER_start"] - self.results["time_sent"]
        )
        self.results["queue_time"] = self.results["queue_time"].clip(lower=0)

    def calculate_failures(self) -> FailuresDict:
        """Method to generate the failures and successes from the sim

        :return: Returns a dictionary of integers of the following fields:
        * "th_failures" - The number of event failures given by the test
        harness (i.e. the response received was not empty)
        * "pv_failures" - The number of event failures in the PV groked logs
        (i.e. did not register a time in all of the pv sim time fields)
        * "pv_sccesses" - The number of event successes in the PV groked logs
        (i.e. registered a time in all of the pv sim time fields)
        :rtype: `FailuresDict`
        """
        th_failures = len(self.results[self.results["response"] != ""])
        pv_failures = (
            pd.isnull(
                self.results.loc[
                    :, ["AER_start", "AER_end", "AEOSVDC_start", "AEOSVDC_end"]
                ]
            )
            .all(axis=1)
            .sum()
        )
        return {
            "num_tests": len(self.results),
            "num_failures": pv_failures,
            "num_errors": th_failures,
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
        :rtype: `AveragesDict`
        """
        if self.end_times is None:
            raise ValueError("self.end_times has not been defined")
        return {
            "average_sent_per_sec": (
                self.results["time_sent"].count().compute()
                / self.end_times["th_end"]
            ),
            "average_processed_per_sec": (
                self.results["AEOSVDC_end"].count().compute()
                / self.end_times["pv_end"]
            ),
            "average_queue_time": np.nanmean(
                self.results["queue_time"].compute()
            ),
            "average_response_time": np.nanmean(
                self.results["full_response_time"].compute()
            ),
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
        aggregated_sent_per_second = (
            sps.binned_statistic(
                self.results["time_sent"],
                [1] * len(self.results),
                bins=time_range,
                statistic="count",
            ).statistic
            / time_window
        )
        # get events per second
        aggregated_events_per_second = (
            sps.binned_statistic(
                self.results["AEOSVDC_end"],
                [1] * len(self.results),
                bins=time_range,
                statistic="count",
            ).statistic
            / time_window
        )
        # get aggregated full response time
        aggregated_full_response_time = sps.binned_statistic(
            self.results["AEOSVDC_end"],
            self.results["full_response_time"],
            bins=time_range,
            statistic=np.nanmean,
        ).statistic
        # get aggregated time in queue
        aggregated_queue_time = sps.binned_statistic(
            self.results["AER_start"],
            self.results["queue_time"],
            bins=time_range,
            statistic=np.nanmean,
        ).statistic
        aggregated_results = pd.DataFrame(
            np.vstack(
                [
                    time_range[:-1] + time_window / 2,
                    aggregated_sent_per_second,
                    aggregated_events_per_second,
                    aggregated_queue_time,
                    aggregated_full_response_time,
                ]
            ).T,
            columns=[
                "Time (s)",
                "Events Sent (/s)",
                "Events Processed (/s)",
                "Queue Time (s)",
                "Response Time (s)",
            ],
        )
        return aggregated_results
