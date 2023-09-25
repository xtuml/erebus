# pylint: disable=W0613
# pylint: disable=R0801
# pylint: disable=C2801
# pylint: disable=C0302
# pylint: disable=C0103
"""Tests for tests.py
"""
from pathlib import Path
import os

from tempfile import NamedTemporaryFile
from datetime import datetime

from io import StringIO
from typing import Iterable

import pandas as pd
import numpy as np
import dask.dataframe as dd

from test_harness.protocol_verifier.pvresultsdaskdataframe import (
    PVResultsDaskDataFrame,
)

# get test config
test_config_path = os.path.join(
    Path(__file__).parent.parent, "config/test_config.config"
)

# get path of tests uml file
test_file_path = os.path.join(
    Path(__file__).parent.parent / "test_files", "test_uml_job_def.puml"
)


# grok file path
grok_file = Path(__file__).parent.parent / "test_files" / "grok_file.txt"


def check_numpy_expected_vs_actual(
    expected_iterable: Iterable[float], actual_iterable: Iterable[float]
) -> None:
    """Method to check iterable of floats for equivalency

    :param expected_iterable: Expected iterable
    :type expected_iterable: :class:`Iterable`[`float`]
    :param actual_iterable: Actual iterable
    :type actual_iterable: :class:`Iterable`[`float`]
    """
    for expected, actual in zip(expected_iterable, actual_iterable):
        if np.isnan(expected):
            assert np.isnan(actual)
        else:
            assert expected == actual


class TestPVResultsDaskDataFrame:
    """Group of tests for :class:`PVResultsDaskDataFrame`"""

    # @staticmethod
    # def test_create_results_holder() -> None:
    #     """Tests :class:`PVResultsDaskDataFrame`.`create_results_holder`
    #     """
    #     results = PVResultsDaskDataFrame()
    #     assert isinstance(results.results, pd.DaskDataFrame)

    @staticmethod
    def test_create_event_result_row() -> None:
        """Tests :class:`PVResultsDaskDataFrame`.`create_event_result_row`"""
        results = PVResultsDaskDataFrame()
        results.create_event_result_row("event_id")
        # TODO consider what I need to test here, there's no great need to
        # implement this function, and it causes more complication than
        # benefits

        # assert len(results.results) == 1
        # assert "event_id" in results.results.index
        # assert set(results.data_fields) == set(results.results.columns)
        # for col in results.results.columns:
        #     assert pd.isnull(results.results.loc["event_id", col])

    @staticmethod
    def test_update_event_results_with_event_id() -> None:
        """Tests
        :class:`PVResultsDaskDataFrame`.`update_event_results_with_event_id`
        """
        with NamedTemporaryFile(suffix=".db") as f:
            results = PVResultsDaskDataFrame(f"sqlite:///{f.name}")
            results.create_event_result_row("event_id")
            results.update_event_results_with_event_id(
                "event_id", {"job_id": "job_id"}
            )
            assert (
                results.results.loc[results.results["event_id"] == "event_id"]
                .compute()["job_id"]
                .iloc[0]
                == "job_id"
            )

    @staticmethod
    def test_update_event_results_with_job_id() -> None:
        """Tests
        :class:`PVResultsDaskDataFrame`.`update_event_results_with_job_id`
        """
        with NamedTemporaryFile(suffix=".db") as f:
            results = PVResultsDaskDataFrame(f"sqlite:///{f.name}")
            results.create_event_result_row("event_id")
            results.update_event_results_with_event_id(
                "event_id", {"job_id": "job_id"}
            )
            results.update_event_results_with_job_id(
                "job_id", {"response": "a response"}
            )
            assert (
                results.results.loc[results.results["event_id"] == "event_id"]
                .compute()["job_id"]
                .iloc[0]
                == "job_id"
            )
            assert (
                results.results.loc[results.results["job_id"] == "job_id"]
                .compute()["response"]
                .iloc[0]
                == "a response"
            )

    @staticmethod
    def test_add_first_event_data(
        start_time: datetime,
        event_job_response_time_dicts,
    ) -> None:
        """Tests :class:`PVResultsDaskDataFrame`.`add_first_event_data`

        :param start_time: Fixture providing a starttime
        :type start_time: :class:`datetime`
        :param event_job_response_time_dicts: Fixture providing event ids, job
        ids, responses and times
        :type event_job_response_time_dicts: `list`[`dict`[`str`, `str`  |
        :class:`datetime`]]
        """
        # TODO revisit this test with Freddie to check it's really doing what
        # it should be doing
        with NamedTemporaryFile(suffix=".db") as f:
            results = PVResultsDaskDataFrame(f"sqlite:///{f.name}")
            results.time_start = start_time
            for event_job_response_time_dict in event_job_response_time_dicts:
                results.add_first_event_data(**event_job_response_time_dict)
                event_id = event_job_response_time_dict["event_id"]
                job_id = event_job_response_time_dict["job_id"]
                time_sent = (
                    event_job_response_time_dict["time_completed"] - start_time
                ).total_seconds()
                response = event_job_response_time_dict["response"]

                assert event_id in results.results["event_id"]
                relevant_row = results.results.loc[
                    results.results["event_id"] == event_id
                ].compute()
                assert (relevant_row["job_id"] == job_id).all()
                assert (relevant_row["time_sent"] == time_sent).all()
                assert (relevant_row["response"] == response).all()

    @staticmethod
    def test_update_from_sim(
        start_time: datetime,
        event_job_response_time_dicts,
    ) -> None:
        """Tests :class:`PVResultsDaskDataFrame`.`update_from_sim`

        :param start_time: Fixture providing a starttime
        :type start_time: :class:`datetime`
        :param event_job_response_time_dicts: Fixture providing event ids, job
        ids, responses and times
        :type event_job_response_time_dicts: `list`[`dict`[`str`, `str`  |
        :class:`datetime`]]
        """
        events = [
            {"eventId": event["event_id"]}
            for event in event_job_response_time_dicts[:3]
        ]
        time_completed = event_job_response_time_dicts[2]["time_completed"]
        job_id = "job_id"
        response = "a response"
        with NamedTemporaryFile(suffix=".db") as f:
            results = PVResultsDaskDataFrame(f"sqlite:///{f.name}")
            results.time_start = start_time
            results.update_from_sim(events, job_id, response, time_completed)
            assert len(results.results.compute()) == 3
            assert set(results.results["job_id"].compute()) == set(["job_id"])
            assert set(results.results["response"].compute()) == set(
                ["a response"]
            )
            assert set(results.results["time_sent"].compute()) == set(
                [(time_completed - start_time).total_seconds()]
            )
            assert set(results.results["event_id"].compute()) == set(
                event["eventId"] for event in events
            )

    @staticmethod
    def test_update_pv_sim_time_field(
        start_time: datetime,
        event_job_response_time_dicts,
    ) -> None:
        """Tests :class:`PVResultsDaskDataFrame`.`update_pv_sim_time_field`

        :param start_time: Fixture providing a starttime
        :type start_time: :class:`datetime`
        :param event_job_response_time_dicts: Fixture providing event ids, job
        ids, responses and times
        :type event_job_response_time_dicts: `list`[`dict`[`str`, `str`  |
        :class:`datetime`]]
        """
        with NamedTemporaryFile(suffix=".db") as f:
            results = PVResultsDaskDataFrame(f"sqlite:///{f.name}")
            results.time_start = start_time
            for event_job_response_time_dict in event_job_response_time_dicts:
                results.add_first_event_data(**event_job_response_time_dict)
                results.update_pv_sim_time_field(
                    "AER_start",
                    event_job_response_time_dict["time_completed"].strftime(
                        "%Y-%m-%dT%H:%M:%S.%fZ"
                    ),
                    event_job_response_time_dict["event_id"],
                )
            for _, row in results.results.compute().iterrows():
                assert row["time_sent"] == row["AER_start"]

    @staticmethod
    def test_read_groked_string(
        start_time: datetime,
        event_job_response_time_dicts,
    ) -> None:
        """Tests :class:`PVResultsDaskDataFrame`.`update_read_groked_string`

        :param start_time: Fixture providing a starttime
        :type start_time: :class:`datetime`
        :param event_job_response_time_dicts: Fixture providing event ids, job
        ids, responses and times
        :type event_job_response_time_dicts: `list`[`dict`[`str`, `str`  |
        :class:`datetime`]]
        """
        groked_string_io = StringIO(
            "# TYPE grok_exporter_lines_matching_total counter\n"
            'grok_exporter_lines_matching_total{metric="svdc_event_received"}'
            " 15\n"
            "# TYPE reception_event_received counter\n"
            'reception_event_received{event_id="205d5d7e-4eb7-4b8a-a638-'
            '1bd0a2ae6497",timestamp="2023-09-04T10:40:37.456217Z"} 1\n'
        )
        with NamedTemporaryFile(suffix=".db") as f:
            results = PVResultsDaskDataFrame(f"sqlite:///{f.name}")
            results.time_start = start_time
            for event_job_response_time_dict in event_job_response_time_dicts:
                results.add_first_event_data(**event_job_response_time_dict)
            results.read_groked_string_io(groked_string_io)
            assert not pd.isnull(
                results.results[
                    results.results["event_id"]
                    == "205d5d7e-4eb7-4b8a-a638-1bd0a2ae6497"
                ]["AER_start"].compute()
            ).any()
            assert pd.isnull(
                results.results[
                    results.results["event_id"]
                    != "205d5d7e-4eb7-4b8a-a638-1bd0a2ae6497"
                ]["AER_start"].compute()
            ).all()

            # TODO ask Freddie if this forms part of the interface; this
            # implementation of PVPerformanceResults only makes columns after
            # they have been used once
            # for col in results.data_fields[-3:]:
            #     breakpoint()
            #     assert pd.isnull(results.results[col].compute()).all()

    @staticmethod
    def test_get_and_read_grok_metrics(
        start_time: datetime,
        event_job_response_time_dicts,
    ) -> None:
        """Tests :class:`PVResultsDaskDataFrame`.`get_an_read_grok_metrics`

        :param start_time: Fixture providing a starttime
        :type start_time: :class:`datetime`
        :param event_job_response_time_dicts: Fixture providing event ids, job
        ids, responses and times
        :type event_job_response_time_dicts: `list`[`dict`[`str`, `str`  |
        :class:`datetime`]]
        """
        with NamedTemporaryFile(suffix=".db") as f:
            results = PVResultsDaskDataFrame(f"sqlite:///{f.name}")
            results.time_start = start_time
            for event_job_response_time_dict in event_job_response_time_dicts:
                results.add_first_event_data(**event_job_response_time_dict)
            results.get_and_read_grok_metrics(grok_file)
            for col in results.data_fields[-4:]:
                assert all(~pd.isnull(results.results[col]))

    @staticmethod
    def test_create_response_time_fields(
        results_dataframe: pd.DataFrame,
    ) -> None:
        """Tests :class:`PVResultsDaskDataFrame`.`create_respone_time_fields`

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`dd`.`DaskDataFrame`
        """
        with NamedTemporaryFile(suffix=".db") as f:
            results = PVResultsDaskDataFrame(f"sqlite:///{f.name}")
            results.results = dd.from_pandas(results_dataframe, npartitions=1)
            results.create_response_time_fields()
            assert (
                len(
                    set(["full_response_time", "queue_time"]).difference(
                        set(results.results.columns)
                    )
                )
                == 0
            )
            assert (
                results.results["full_response_time"].compute() == 4.0
            ).all()
            assert (results.results["queue_time"].compute() == 1.0).all()

    @staticmethod
    def test_calculate_failures_no_failures(
        results_dataframe: pd.DataFrame,
    ) -> None:
        """Tests :class:`PVResultsDaskDataFrame`.`calculate_failures` with no
        failures

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DaskDataFrame`
        """
        results = PVResultsDaskDataFrame()
        results.results = dd.from_pandas(results_dataframe, npartitions=1)
        results.create_response_time_fields()
        failures = results.calculate_failures()
        assert failures["num_errors"] == 0
        assert failures["num_failures"] == 0
        assert failures["num_tests"] == 10

    @staticmethod
    def test_calculate_failures_th_failures(
        results_dataframe: pd.DataFrame,
    ) -> None:
        """Tests :class:`PVResultsDaskDataFrame`.`calculate_failures` with a th
        failure

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DaskDataFrame`
        """
        results = PVResultsDaskDataFrame()
        results_dataframe.loc["event_0", "response"] = "error response"
        results.results = dd.from_pandas(results_dataframe, npartitions=1)
        results.create_response_time_fields()
        failures = results.calculate_failures()
        assert failures["num_errors"] == 1
        assert failures["num_failures"] == 0
        assert failures["num_tests"] == 10

    @staticmethod
    def test_calculate_failures_pv_failures(
        results_dataframe: pd.DataFrame,
    ) -> None:
        """Tests :class:`PVResultsDaskDataFrame`.`calculate_failures` with a pv
        failure

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DaskDataFrame`
        """
        results = PVResultsDaskDataFrame()
        results_dataframe.loc[
            "event_0", ["AER_start", "AER_end", "AEOSVDC_start", "AEOSVDC_end"]
        ] = None
        results.results = dd.from_pandas(results_dataframe, npartitions=1)
        results.create_response_time_fields()
        failures = results.calculate_failures()
        assert failures["num_errors"] == 0
        assert failures["num_failures"] == 1
        assert failures["num_tests"] == 10

    @staticmethod
    def test_calc_end_times_no_nans(results_dataframe: pd.DataFrame) -> None:
        """Tests :class:`PVResultsDaskDataFrame`.`calc_end_times` with no nan
        entries

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DaskDataFrame`
        """
        results = PVResultsDaskDataFrame()
        results.results = dd.from_pandas(results_dataframe, npartitions=1)
        results.create_response_time_fields()
        end_times = results.calc_end_times()
        assert end_times["th_end"] == 9.0
        assert end_times["pv_end"] == 13.0
        assert end_times["aer_end"] == 11.0

    @staticmethod
    def test_calc_end_times_nans(results_dataframe: pd.DataFrame) -> None:
        """Tests :class:`PVResultsDaskDataFrame`.`calc_end_times` with nan
        entries

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DaskDataFrame`
        """
        results = PVResultsDaskDataFrame()
        results_dataframe.loc["event_9", "AEOSVDC_end"] = None
        results.results = dd.from_pandas(results_dataframe, npartitions=1)
        results.create_response_time_fields()
        end_times = results.calc_end_times()
        assert end_times["th_end"] == 9.0
        assert end_times["pv_end"] == 12.0
        assert end_times["aer_end"] == 11.0

    @staticmethod
    def test_calc_full_averages(results_dataframe: pd.DataFrame) -> None:
        """Tests :class:`PVResultsDaskDataFrame`.`calc_full_averages`

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DaskDataFrame`
        """
        results = PVResultsDaskDataFrame()
        results.results = dd.from_pandas(results_dataframe, npartitions=1)
        results.create_response_time_fields()
        results.end_times = results.calc_end_times()
        averages = results.calc_full_averages()
        assert averages["average_sent_per_sec"] == 10 / 9
        assert averages["average_processed_per_sec"] == 10 / 13.0
        assert averages["average_queue_time"] == 1.0
        assert averages["average_response_time"] == 4.0

    @staticmethod
    def test_calculate_aggregated_results_dataframe(
        results_dataframe: pd.DataFrame,
    ) -> None:
        """Tests
        :class:`PVResultsDaskDataFrame`.`calculate_aggregated_results_dataframe`

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DaskDataFrame`
        """
        results = PVResultsDaskDataFrame()
        results.results = dd.from_pandas(results_dataframe, npartitions=1)
        results.create_response_time_fields()
        results.end_times = results.calc_end_times()
        aggregated_results = results.calculate_aggregated_results_dataframe(
            time_window=1
        )
        assert len(aggregated_results) == 13
        for time_floor_val, time_val in enumerate(
            aggregated_results["Time (s)"]
        ):
            assert time_val == time_floor_val + 0.5
        expected_agg_sent_per_second = [1.0] * 10 + [0.0] * 3
        check_numpy_expected_vs_actual(
            expected_agg_sent_per_second,
            aggregated_results["Events Sent (/s)"],
        )
        expected_agg_events_per_second = [0.0] * 4 + [1.0] * 8 + [2.0]
        check_numpy_expected_vs_actual(
            expected_agg_events_per_second,
            aggregated_results["Events Processed (/s)"],
        )
        expected_agg_full_response_time = [np.nan] * 4 + [4.0] * 9
        check_numpy_expected_vs_actual(
            expected_agg_full_response_time,
            aggregated_results["Response Time (s)"],
        )
        expected_agg_queue_time = [np.nan] + [1.0] * 10 + [np.nan] * 2
        check_numpy_expected_vs_actual(
            expected_agg_queue_time, aggregated_results["Queue Time (s)"]
        )

    @staticmethod
    def test_calc_all_results(results_dataframe: pd.DataFrame) -> None:
        """Tests :class:`PVResultsDaskDataFrame`.`calc_all_results`

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DaskDataFrame`
        """
        results = PVResultsDaskDataFrame()
        results.results = dd.from_pandas(results_dataframe, npartitions=1)
        results.calc_all_results()
        assert results.end_times is not None
        assert results.failures is not None
        assert results.full_averages is not None
        assert results.agg_results is not None
