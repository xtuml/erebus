# pylint: disable=W0613
# pylint: disable=R0801
# pylint: disable=C2801
# pylint: disable=C0302
# pylint: disable=R0904
"""Tests for tests.py"""
import asyncio
import glob
import logging
import math
import os
import xml.etree.ElementTree as ET
from copy import copy, deepcopy
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterable
import time
import json

import numpy as np
import pandas as pd
import pytest
import responses
from aioresponses import CallbackResult
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pygrok import Grok
import kafka3
from kafka3.future import Future
from kafka3.errors import KafkaTimeoutError as KafkaTimeoutError3
from configparser import ConfigParser

from test_harness.config.config import TestConfig
from test_harness.protocol_verifier.config.config import ProtocolVerifierConfig
from test_harness.protocol_verifier.testing_suite.generate_test_files import (
    generate_test_events_from_puml_files,
)
from test_harness.protocol_verifier.results.pv_performance_results import (
    ProcessErrorDataDict,
    ResultsDict,
)
from test_harness.protocol_verifier.results.pv_performance_results import (
    PVPerformanceResults,
)
from test_harness.protocol_verifier.testing_suite.base_test_classes import (
    FunctionalTest,
    PerformanceTest,
    PVFunctionalResults,
    PVResultsHandler,
)
from test_harness import TestHarnessPbar
from test_harness.protocol_verifier.utils.types import PVResultsHandlerItem
from test_harness.simulator.simulator_profile import Profile
from test_harness.utils import (
    check_dict_equivalency,
    clean_directories,
    ProcessGeneratorManager,
)
from test_harness.protocol_verifier.mocks.mock_pv_http_interface import (
    mock_pv_http_interface,
)
from test_harness.results.results import DictResultsHolder, ResultsHolder
from test_harness import AsyncTestStopper
from test_harness.protocol_verifier.utils.types import ERROR_LOG_FILE_PREFIX

# get test config
test_config_path = os.path.join(
    Path(__file__).parent.parent.parent.parent.parent
    / "tests/test_harness/config/test_config.config",
)

# set config_parser object
config_parser = ConfigParser()
config_parser.read(test_config_path)

# test files directory path
test_files_path = Path(__file__).parent.parent / "test_files"

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


class TestPVPerformanceResults:
    """Group of tests for :class:`PVPerformanceResults`"""

    @staticmethod
    def test_create_results_holder() -> None:
        """Tests :class:`PVPerformanceResults`.`create_results_holder`"""
        results = PVPerformanceResults()
        assert isinstance(results.results, ResultsHolder)

    @staticmethod
    def test_create_event_result_row() -> None:
        """Tests :class:`PVPerformanceResults`.`create_event_result_row`"""
        results = PVPerformanceResults()
        results.create_event_result_row("event_id")
        assert len(results.results) == 1
        assert "event_id" in results.results
        assert len(results.results["event_id"]) == 0

    @staticmethod
    def test_update_event_results_with_event_id() -> None:
        """Tests
        :class:`PVPerformanceResults`.`update_event_results_with_event_id`
        """
        results = PVPerformanceResults()
        results.create_event_result_row("event_id")
        results.update_event_results_with_event_id(
            "event_id", {"job_id": "job_id"}
        )
        assert "job_id" in results.results["event_id"]
        assert results.results["event_id"]["job_id"] == "job_id"

    @staticmethod
    def test_update_event_results_with_job_id() -> None:
        """Tests
        :class:`PVPerformanceResults`.`update_event_results_with_job_id`
        """
        results = PVPerformanceResults()
        results.create_event_result_row("event_id")
        results.update_event_results_with_event_id(
            "event_id", {"job_id": "job_id"}
        )
        results.update_event_results_with_job_id(
            "job_id", {"response": "a response"}
        )
        assert "response" in results.results["event_id"]
        assert results.results["event_id"]["response"] == "a response"

    @staticmethod
    def test_add_first_event_data(
        start_time: datetime,
        event_job_response_time_dicts: list[dict[str, str | datetime]],
    ) -> None:
        """Tests :class:`PVPerformanceResults`.`add_first_event_data`

        :param start_time: Fixture providing a starttime
        :type start_time: :class:`datetime`
        :param event_job_response_time_dicts: Fixture providing event ids, job
        ids, responses and times
        :type event_job_response_time_dicts: `list`[`dict`[`str`, `str`  |
        :class:`datetime`]]
        """
        results = PVPerformanceResults()
        results.time_start = start_time
        for event_job_response_time_dict in event_job_response_time_dicts:
            results.add_first_event_data(**event_job_response_time_dict)
            event_id = event_job_response_time_dict["event_id"]
            job_id = event_job_response_time_dict["job_id"]
            time_sent = (
                event_job_response_time_dict["time_completed"] - start_time
            ).total_seconds()
            response = event_job_response_time_dict["response"]
            assert event_id in results.results
            assert results.results[event_id]["job_id"] == job_id
            assert results.results[event_id]["time_sent"] == time_sent
            assert results.results[event_id]["response"] == response

    @staticmethod
    def test_update_from_sim(
        start_time: datetime,
        event_job_response_time_dicts: list[dict[str, str | datetime]],
    ) -> None:
        """Tests :class:`PVPerformanceResults`.`update_from_sim`

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
        results = PVPerformanceResults()
        results.time_start = start_time
        results.update_from_sim(events, job_id, response, time_completed)
        assert len(results.results) == 3
        for values in results.results.values():
            assert values["job_id"] == "job_id"
            assert values["response"] == "a response"
            assert (
                values["time_sent"]
                == (time_completed - start_time).total_seconds()
            )
        assert set(results.results.keys()) == set(
            event["eventId"] for event in events
        )

    @staticmethod
    def test_update_pv_sim_time_field(
        start_time: datetime,
        event_job_response_time_dicts: list[dict[str, str | datetime]],
    ) -> None:
        """Tests :class:`PVPerformanceResults`.`update_pv_sim_time_field`

        :param start_time: Fixture providing a starttime
        :type start_time: :class:`datetime`
        :param event_job_response_time_dicts: Fixture providing event ids, job
        ids, responses and times
        :type event_job_response_time_dicts: `list`[`dict`[`str`, `str`  |
        :class:`datetime`]]
        """
        results = PVPerformanceResults()
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
        for row in results.results.values():
            assert row["time_sent"] == row["AER_start"]

    @staticmethod
    @given(
        st.datetimes(datetime(1000, 1, 1)),
        st.lists(
            st.timedeltas(timedelta(seconds=0), max_value=timedelta(days=100))
        ),
        st.lists(
            st.timedeltas(timedelta(seconds=0), max_value=timedelta(days=100))
        ),
    )
    def test_add_error_process_field(
        starting_time: datetime,
        aer_processing_errors: list[timedelta],
        aeo_processing_errors: list[timedelta],
    ) -> None:
        """Tests the method `add_error_process_field`

        :param starting_time: The starting time of the simulation
        :type starting_time: :class:`datetime`
        :param aer_processing_errors: A list of time deltas to add to the
        simulation starting time for AER processing errors
        :type aer_processing_errors: `list`[:class:`timedelta`]
        :param aeo_processing_errors: A list of time deltas to add to the
        simulation starting time for AEO processing errors
        :type aeo_processing_errors: `list`[:class:`timedelta`]
        """
        results = PVPerformanceResults()
        results.time_start = starting_time
        results_dicts = [
            ResultsDict(
                field=error_name,
                timestamp=(starting_time + time_delta).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                ),
            )
            for error_name, error_list in zip(
                ["AER_file_process_error", "AEO_file_process_error"],
                [aer_processing_errors, aeo_processing_errors],
            )
            for time_delta in error_list
        ]
        expected_bins = {}
        for error_name, error_list in zip(
            ["AER_file_process_error", "AEO_file_process_error"],
            [aer_processing_errors, aeo_processing_errors],
        ):
            for time_delta in error_list:
                bin_number = math.floor(
                    time_delta.total_seconds() / results.binning_window
                )
                if bin_number not in expected_bins:
                    expected_bins[bin_number] = ProcessErrorDataDict(
                        AER_file_process_error=0, AEO_file_process_error=0
                    )
                expected_bins[bin_number][error_name] += 1
        for result in results_dicts:
            results.add_error_process_field(result)
        assert set(expected_bins.keys()) == set(results.process_errors.keys())
        for binned_window, expected_result in expected_bins.items():
            actual_result = results.process_errors[binned_window]
            check_dict_equivalency(expected_result, actual_result)

    @staticmethod
    @given(
        st.datetimes(datetime(1000, 1, 1)),
        st.lists(
            st.timedeltas(timedelta(seconds=0), max_value=timedelta(days=100))
        ),
        st.lists(
            st.timedeltas(timedelta(seconds=0), max_value=timedelta(days=100))
        ),
    )
    @settings(deadline=None)
    def test_calc_processing_errors_counts(
        starting_time: datetime,
        aer_processing_errors: list[timedelta],
        aeo_processing_errors: list[timedelta],
    ) -> None:
        """Tests the method `calc_processing_errors_counts`

        :param starting_time: The starting time of the simulation
        :type starting_time: :class:`datetime`
        :param aer_processing_errors: A list of time deltas to add to the
        simulation starting time for AER processing errors
        :type aer_processing_errors: `list`[:class:`timedelta`]
        :param aeo_processing_errors: A list of time deltas to add to the
        simulation starting time for AEO processing errors
        :type aeo_processing_errors: `list`[:class:`timedelta`]
        """
        results = PVPerformanceResults()
        results.time_start = starting_time
        results_dicts = [
            ResultsDict(
                field=error_name,
                timestamp=(starting_time + time_delta).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                ),
            )
            for error_name, error_list in zip(
                ["AER_file_process_error", "AEO_file_process_error"],
                [aer_processing_errors, aeo_processing_errors],
            )
            for time_delta in error_list
        ]
        for result in results_dicts:
            results.add_error_process_field(result)
        expected_counts = ProcessErrorDataDict(
            AER_file_process_error=len(aer_processing_errors),
            AEO_file_process_error=len(aeo_processing_errors),
        )
        actual_counts = results.calc_processing_errors_counts()
        check_dict_equivalency(expected_counts, actual_counts)

    @staticmethod
    @given(
        st.datetimes(datetime(1000, 1, 1)),
        st.lists(
            st.timedeltas(timedelta(seconds=0), max_value=timedelta(days=100))
        ),
        st.lists(
            st.timedeltas(timedelta(seconds=0), max_value=timedelta(days=100))
        ),
    )
    @settings(deadline=None)
    def test_calc_processing_errors_time_series(
        starting_time: datetime,
        aer_processing_errors: list[timedelta],
        aeo_processing_errors: list[timedelta],
    ) -> None:
        """Tests the method `calc_processing_errors_time_series`

        :param starting_time: The starting time of the simulation
        :type starting_time: :class:`datetime`
        :param aer_processing_errors: A list of time deltas to add to the
        simulation starting time for AER processing errors
        :type aer_processing_errors: `list`[:class:`timedelta`]
        :param aeo_processing_errors: A list of time deltas to add to the
        simulation starting time for AEO processing errors
        :type aeo_processing_errors: `list`[:class:`timedelta`]
        """
        results = PVPerformanceResults()
        results.time_start = starting_time
        results_dicts = [
            ResultsDict(
                field=error_name,
                timestamp=(starting_time + time_delta).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                ),
            )
            for error_name, error_list in zip(
                ["AER_file_process_error", "AEO_file_process_error"],
                [aer_processing_errors, aeo_processing_errors],
            )
            for time_delta in error_list
        ]
        expected_bins = {}
        for error_name, error_list in zip(
            ["AER_file_process_error", "AEO_file_process_error"],
            [aer_processing_errors, aeo_processing_errors],
        ):
            for time_delta in error_list:
                bin_number = math.floor(
                    time_delta.total_seconds() / results.binning_window
                )
                if bin_number not in expected_bins:
                    expected_bins[bin_number] = ProcessErrorDataDict(
                        AER_file_process_error=0, AEO_file_process_error=0
                    )
                expected_bins[bin_number][error_name] += 1
        expected_time_series = pd.DataFrame.from_dict(
            expected_bins,
            orient="index",
            columns=["AER_file_process_error", "AEO_file_process_error"],
        ).reset_index(names="Time (s)")
        for result in results_dicts:
            results.add_error_process_field(result)
        actual_time_series = results.calc_processing_errors_time_series()
        assert len(expected_time_series) == len(actual_time_series)
        for idx, row in expected_time_series.iterrows():
            assert actual_time_series.loc[idx, "Time (s)"] == row["Time (s)"]
            assert (
                actual_time_series.loc[idx, "AER_file_process_error"]
                == row["AER_file_process_error"]
            )
            assert (
                actual_time_series.loc[idx, "AEO_file_process_error"]
                == row["AEO_file_process_error"]
            )

    @staticmethod
    def test_read_groked_string(
        start_time: datetime,
        event_job_response_time_dicts: list[dict[str, str | datetime]],
    ) -> None:
        """Tests :class:`PVPerformanceResults`.`update_read_groked_string`

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
        results = PVPerformanceResults()
        results.results = DictResultsHolder()
        results.time_start = start_time
        for event_job_response_time_dict in event_job_response_time_dicts:
            results.add_first_event_data(**event_job_response_time_dict)
        results.read_groked_string_io(groked_string_io)
        assert (
            "AER_start"
            in results.results["205d5d7e-4eb7-4b8a-a638-1bd0a2ae6497"]
        )
        for event_id, values in results.results.items():
            if event_id != "205d5d7e-4eb7-4b8a-a638-1bd0a2ae6497":
                assert "AER_start" not in values
            for col in results.data_fields[-3:]:
                assert col not in values

    @staticmethod
    def test_get_and_read_grok_metrics(
        start_time: datetime,
        event_job_response_time_dicts: list[dict[str, str | datetime]],
    ) -> None:
        """Tests :class:`PVPerformanceResults`.`get_an_read_grok_metrics`

        :param start_time: Fixture providing a starttime
        :type start_time: :class:`datetime`
        :param event_job_response_time_dicts: Fixture providing event ids, job
        ids, responses and times
        :type event_job_response_time_dicts: `list`[`dict`[`str`, `str`  |
        :class:`datetime`]]
        """
        results = PVPerformanceResults()
        results.time_start = start_time
        for event_job_response_time_dict in event_job_response_time_dicts:
            results.add_first_event_data(**event_job_response_time_dict)
        results.get_and_read_grok_metrics(grok_file)
        for values in results.results.values():
            for col in results.data_fields[-4:]:
                assert col in values

    @staticmethod
    def test_create_response_time_fields(
        results_dataframe: pd.DataFrame,
    ) -> None:
        """Tests :class:`PVPerformanceResults`.`create_response_time_fields`

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        """
        results = PVPerformanceResults()
        results.results = results_dataframe
        results.create_response_time_fields()

        assert (
            len(
                set(["full_response_time", "queue_time"]).difference(
                    set(results.results.columns)
                )
            )
            == 0
        )
        assert all(results.results["full_response_time"] == 4.0)
        assert all(results.results["queue_time"] == 1.0)

    @staticmethod
    def test_calculate_failures_no_failures(
        results_dataframe: pd.DataFrame,
    ) -> None:
        """Tests :class:`PVPerformanceResults`.`calculate_failures` with no
        failures

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        """
        results = PVPerformanceResults()
        results.results = results_dataframe
        results.create_response_time_fields()
        failures = results.calculate_failures()
        assert failures["num_errors"] == 0
        assert failures["num_failures"] == 0
        assert failures["num_tests"] == 10

    @staticmethod
    @given(num_to_change=st.integers(0, 10))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_calculate_failures_th_failures(
        results_dataframe: pd.DataFrame, num_to_change: int
    ) -> None:
        """Tests :class:`PVPerformanceResults`.`calculate_failures` with a th
        failure

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        :param num_to_change: The number of entries to set to "error response"
        in the column "response"
        :type num_to_change: `int`
        """
        results = PVPerformanceResults()
        test_dataframe = deepcopy(results_dataframe)
        test_dataframe["response"].iloc[0:num_to_change] = "error response"
        results.results = test_dataframe
        results.create_response_time_fields()
        failures = results.calculate_failures()
        assert failures["num_errors"] == num_to_change
        assert failures["num_failures"] == 0
        assert failures["num_tests"] == 10

    @staticmethod
    @given(num_to_change=st.integers(0, 10))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_calculate_failures_pv_failures(
        results_dataframe: pd.DataFrame, num_to_change: int
    ) -> None:
        """Tests :class:`PVPerformanceResults`.`calculate_failures` with a pv
        failure

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        :param num_to_change: The number of entries to set to None in the
        column "AEOSVDC"
        :type num_to_change: `int`
        """
        results = PVPerformanceResults()
        test_dataframe = deepcopy(results_dataframe)
        test_dataframe["AEOSVDC_end"].iloc[0:num_to_change] = None
        results.results = test_dataframe
        results.create_response_time_fields()
        failures = results.calculate_failures()
        assert failures["num_errors"] == 0
        assert failures["num_failures"] == num_to_change
        assert failures["num_tests"] == 10

    @staticmethod
    def test_calc_end_times_no_nans(results_dataframe: pd.DataFrame) -> None:
        """Tests :class:`PVPerformanceResults`.`calc_end_times` with no nan
        entries

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        """
        results = PVPerformanceResults()
        results.results = results_dataframe
        results.create_response_time_fields()
        end_times = results.calc_end_times()
        assert end_times["th_end"] == 9.0
        assert end_times["pv_end"] == 13.0
        assert end_times["aer_end"] == 11.0

    @staticmethod
    def test_calc_end_times_nans(results_dataframe: pd.DataFrame) -> None:
        """Tests :class:`PVPerformanceResults`.`calc_end_times` with nan
        entries

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        """
        results = PVPerformanceResults()
        results_dataframe.loc["event_9", "AEOSVDC_end"] = None
        results.results = results_dataframe
        results.create_response_time_fields()
        end_times = results.calc_end_times()
        assert end_times["th_end"] == 9.0
        assert end_times["pv_end"] == 12.0
        assert end_times["aer_end"] == 11.0

    @staticmethod
    def test_calc_full_averages(results_dataframe: pd.DataFrame) -> None:
        """Tests :class:`PVPerformanceResults`.`calc_full_averages`

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        """
        results = PVPerformanceResults()
        results.results = results_dataframe
        results.create_response_time_fields()
        results.end_times = results.calc_end_times()
        averages = results.calc_full_averages()
        assert averages["average_sent_per_sec"] == 10 / 9
        assert averages["average_processed_per_sec"] == 10 / 13.0
        assert averages["average_queue_time"] == 1.0
        assert averages["average_response_time"] == 4.0

    @staticmethod
    def test_calc_reception_counts(results_dataframe: pd.DataFrame) -> None:
        """Tests :class:`PVPerformanceResults`.`calc_reception_counts`

        :param results_dataframe: Fixture providing a results dataframe
        :type results_dataframe: :class:`pd`.`DataFrame`
        """
        results = PVPerformanceResults()
        results.results = results_dataframe
        results.create_response_time_fields()
        reception_counts = results.calc_reception_counts()
        assert reception_counts["num_aer_start"] == 10
        assert reception_counts["num_aer_end"] == 10

    @staticmethod
    def test_calculate_aggregated_results_dataframe(
        results_dataframe: pd.DataFrame,
    ) -> None:
        """Tests
        :class:`PVPerformanceResults`.`calculate_aggregated_results_dataframe`

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        """
        results = PVPerformanceResults()
        results.results = results_dataframe
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
        expected_agg_aer_events_per_second = [0.0] * 2 + [1.0] * 10 + [0.0]
        check_numpy_expected_vs_actual(
            expected_agg_aer_events_per_second,
            aggregated_results["AER Events Processed (/s)"],
        )
        expected_agg_full_response_time = [4.0] * 10 + [np.nan] * 3
        check_numpy_expected_vs_actual(
            expected_agg_full_response_time,
            aggregated_results["Response Time (s)"],
        )
        expected_agg_queue_time = [1.0] * 10 + [np.nan] * 3
        check_numpy_expected_vs_actual(
            expected_agg_queue_time, aggregated_results["Queue Time (s)"]
        )
        expected_cum_sent_per_second = np.cumsum(expected_agg_sent_per_second)
        check_numpy_expected_vs_actual(
            expected_cum_sent_per_second,
            aggregated_results["Cumulative Events Sent"],
        )
        expected_cum_events_per_second = np.cumsum(
            expected_agg_events_per_second
        )
        check_numpy_expected_vs_actual(
            expected_cum_events_per_second,
            aggregated_results["Cumulative Events Processed"],
        )
        expected_cum_aer_events_per_second = np.cumsum(
            expected_agg_aer_events_per_second
        )
        check_numpy_expected_vs_actual(
            expected_cum_aer_events_per_second,
            aggregated_results["Cumulative AER Events Processed"],
        )

    @staticmethod
    def test_calc_all_results(results_dataframe: pd.DataFrame) -> None:
        """Tests :class:`PVPerformanceResults`.`calc_all_results`

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        """
        results = PVPerformanceResults()
        results.results = DictResultsHolder()
        for event_id, row in results_dataframe.iterrows():
            results.results[event_id] = row.to_dict()
        results.calc_all_results()
        assert results.end_times is not None
        assert results.failures is not None
        assert results.full_averages is not None
        assert results.reception_event_counts is not None
        assert results.agg_results is not None
        assert results.process_errors_counts is not None
        assert results.process_errors_agg_results is not None

    @staticmethod
    def test_add_results_from_log_files(
        pv_results: PVPerformanceResults,
        grok_priority_patterns: list[Grok],
        expected_verifier_pv_added_results: list[dict],
    ) -> None:
        """Tests `PVPerformanceResults`.`add_results_from_log_files`

        :param pv_results: Fixture providing a results holder instance with
        sent event data
        :type pv_results: :class:`PVPerformanceResults`
        :param grok_priority_patterns: Fixture providing list of grok patterns
        in priority order
        :type grok_priority_patterns: `list`[:class:`Grok`]
        :param expected_verifier_pv_added_results: Fixture providing expected
        added results for verifier logs
        :type expected_verifier_pv_added_results: `list`[`dict`]
        """
        pv_results.add_results_from_log_files(
            [test_files_path / "Verifier_test1.log"], grok_priority_patterns
        )
        for (
            expected_verifier_pv_added_result
        ) in expected_verifier_pv_added_results:
            assert not expected_verifier_pv_added_result[
                "event_ids"
            ].difference(
                set(
                    pv_results.job_id_event_id_map[
                        expected_verifier_pv_added_result["job_id"]
                    ]
                )
            )
            for event_id in expected_verifier_pv_added_result["event_ids"]:
                assert (
                    pv_results.results[event_id][
                        expected_verifier_pv_added_result["pv_data_field"]
                    ]
                    == expected_verifier_pv_added_result["pv_time"]
                )

    @staticmethod
    def test_add_verifier_results_from_log_files(
        pv_results: PVPerformanceResults,
        expected_verifier_pv_added_results: list[dict],
    ) -> None:
        """Tests `PVPerformanceResults`.`add_verifier_results_from_log_files`

        :param pv_results: Fixture providing a results holder instance with
        sent event data
        :type pv_results: :class:`PVPerformanceResults`
        :param expected_verifier_pv_added_results: Fixture providing expected
        added results for verifier logs
        :type expected_verifier_pv_added_results: `list`[`dict`]
        """
        pv_results.add_verifier_results_from_log_files(
            [test_files_path / "Verifier_test1.log"]
        )
        for (
            expected_verifier_pv_added_result
        ) in expected_verifier_pv_added_results:
            assert not expected_verifier_pv_added_result[
                "event_ids"
            ].difference(
                set(
                    pv_results.job_id_event_id_map[
                        expected_verifier_pv_added_result["job_id"]
                    ]
                )
            )
            for event_id in expected_verifier_pv_added_result["event_ids"]:
                assert (
                    pv_results.results[event_id][
                        expected_verifier_pv_added_result["pv_data_field"]
                    ]
                    == expected_verifier_pv_added_result["pv_time"]
                )

    @staticmethod
    def test_add_reception_results_from_log_files(
        pv_results: PVPerformanceResults,
        expected_reception_pv_added_results: list[dict],
    ) -> None:
        """Tests `PVPerformanceResults`.`add_reception_results_from_log_files`

        :param pv_results: Fixture providing a results holder instance with
        sent event data
        :type pv_results: :class:`PVPerformanceResults`
        :param expected_reception_pv_added_results: Fixture providing expected
        added results for reception logs
        :type expected_reception_pv_added_results: `list`[`dict`]
        """
        pv_results.add_reception_results_from_log_files(
            [test_files_path / "Reception_test1.log"]
        )
        for expected_pv_added_result in expected_reception_pv_added_results:
            assert (
                pv_results.results[expected_pv_added_result["event_id"]][
                    expected_pv_added_result["pv_data_field"]
                ]
                == expected_pv_added_result["pv_time"]
            )

    @staticmethod
    @pytest.mark.skip(reason="Deep copy not working due to sqlalchemy")
    def test_add_reception_verifier_result_grok_method_equivalency(
        pv_results: PVPerformanceResults,
    ) -> None:
        """Tests `PVPerformanceResults`.`add_verifier_results_from_log_files`
        and `PVPerformanceResults`.`add_reception_results_from_log_files` and
        the equivalency to the verified grok exporter method of parsing log
        files

        :param pv_results: Fixture providing :class:`PVPerformanceResults` with
        sent events data loaded
        :type pv_results: :class:`PVPerformanceResults`
        """
        pv_results_1 = copy(pv_results)
        pv_results_2 = copy(pv_results)
        pv_results_1.results = deepcopy(pv_results.results)
        pv_results_2.results = deepcopy(pv_results.results)
        # add log files to pv_results_1
        pv_results_1.add_verifier_results_from_log_files(
            [test_files_path / "Verifier_test1.log"]
        )
        pv_results_1.add_reception_results_from_log_files(
            [test_files_path / "Reception_test1.log"]
        )
        # add grok file to pv_results_2
        pv_results_2.get_and_read_grok_metrics(
            test_files_path / "grok_test1.txt"
        )
        check_dict_equivalency(pv_results_1.results, pv_results_2.results)


class TestPVResultsHandler:
    """Group of tests for :class:`PVResultsHandler`"""

    @staticmethod
    @pytest.mark.skip(reason="This passes intermittently - bug raised to fix")
    def test_events_cache_happy_path() -> None:
        """Tests the happy path for event caching using shelve.Shelf."""
        harness_config = ProtocolVerifierConfig(config_parser)
        results = PVFunctionalResults()
        with NamedTemporaryFile(suffix=".db") as tmp_file:
            with PVResultsHandler(
                results,
                harness_config.report_file_store,
                events_cache_file=tmp_file.name,
            ) as results_handler:
                for _ in range(10):
                    results_handler.handle_result(
                        result=PVResultsHandlerItem(
                            event_list=["id1", "id2"],
                            file_name="foo",
                            job_id="jobid1",
                            job_info=None,
                            response="response1",
                            time_completed=datetime.utcnow(),
                        )
                    )

            with PVResultsHandler(
                results,
                harness_config.report_file_store,
                events_cache_file=tmp_file.name,
            ) as results_handler:
                assert len(results_handler.results_holder.responses) == 10
                # TODO more testing around this functionality.

    @staticmethod
    def test___enter__() -> None:
        """Tests :class:`PVResultsHandler`.`__enter__`"""
        harness_config = ProtocolVerifierConfig(config_parser)
        results = PVFunctionalResults()
        results_handler = PVResultsHandler(
            results, harness_config.report_file_store
        )
        results_handler.__enter__()
        assert results_handler.daemon_thread.is_alive()

    @staticmethod
    def test___exit__() -> None:
        """Tests :class:`PVResultsHandler`.`__exit__`"""
        harness_config = ProtocolVerifierConfig(config_parser)
        results = PVFunctionalResults()
        results_handler = PVResultsHandler(
            results, harness_config.report_file_store
        )
        results_handler.__enter__()
        results_handler.__exit__(None, None, None)
        assert not results_handler.daemon_thread.is_alive()

    @staticmethod
    def test___exit___error() -> None:
        """Tests
        :class:`PVResultsHandler`.`__exit__` when an error is thrown
        """
        harness_config = ProtocolVerifierConfig(config_parser)
        results = PVFunctionalResults()
        results_handler = PVResultsHandler(
            results, harness_config.report_file_store
        )
        results_handler.__enter__()
        with pytest.raises(RuntimeError) as e_info:
            error = RuntimeError("An error")
            results_handler.__exit__(type(error), error, error.__traceback__)
        assert e_info.value.args[0] == "An error"

    @staticmethod
    def test_context_manager_error() -> None:
        """Tests :class:`PVResultsHandler` context manager when an error is
        thrown
        """
        harness_config = ProtocolVerifierConfig(config_parser)
        results = PVFunctionalResults()
        with pytest.raises(RuntimeError) as e_info:
            with PVResultsHandler(results, harness_config.report_file_store):
                raise RuntimeError("An error")
        assert e_info.value.args[0] == "An error"

    @staticmethod
    def test_handle_result() -> None:
        """Tests :class:`PVResultsHandler`.`handle_result`"""
        harness_config = ProtocolVerifierConfig(config_parser)
        results = PVFunctionalResults()
        results_handler = PVResultsHandler(
            results, harness_config.report_file_store
        )
        assert results_handler.queue.qsize() == 0
        object_in_queue = {}
        results_handler.handle_result({})
        assert results_handler.queue.qsize() == 1
        assert results_handler.queue.get() == object_in_queue

    @staticmethod
    def test_handle_item_from_queue_no_save() -> None:
        """Tests :class:`PVResultsHandler`.`handle_item_from_queue`
        with no save
        """
        harness_config = ProtocolVerifierConfig(config_parser)
        results = PVFunctionalResults()
        results_handler = PVResultsHandler(
            results, harness_config.report_file_store
        )
        job_info = {"info": "some_info"}
        named_items = ["a_file_name", "jobId", job_info, "", None]
        attributes = [
            "file_names",
            "job_ids",
            "jobs_info",
            "responses",
            "time_completed",
        ]
        result_item = ([{}],) + tuple(named_items)
        results_handler.handle_item_from_queue(result_item)
        for attr_name, item in zip(attributes[:-1], named_items[:-1]):
            attr = getattr(results, attr_name)
            assert len(attr) == 1
            assert attr[0] == item

    @staticmethod
    def test_handle_item_from_queue_with_save() -> None:
        """Tests :class:`PVResultsHandler`.`handle_item_from_queue`
        with save
        """
        harness_config = ProtocolVerifierConfig(config_parser)
        results = PVFunctionalResults()
        results_handler = PVResultsHandler(
            results, harness_config.report_file_store, save_files=True
        )
        job_info = {"info": "some_info"}
        named_items = ["a_file_name", "jobId", job_info, "", None]
        attributes = [
            "file_names",
            "job_ids",
            "jobs_info",
            "responses",
            "time_completed",
        ]
        result_item = ([{}],) + tuple(named_items)
        results_handler.handle_item_from_queue(result_item)
        for attr_name, item in zip(attributes[:-1], named_items[:-1]):
            attr = getattr(results, attr_name)
            assert len(attr) == 1
            assert attr[0] == item
        files_to_remove = ["a_file_name"]
        for file_name in files_to_remove:
            path = os.path.join(harness_config.report_file_store, file_name)
            assert os.path.exists(path)
            os.remove(path)
        assert not glob.glob("*.*", root_dir=harness_config.report_file_store)


def test_send_test_files_functional() -> None:
    """Tests :class:`FunctionalTest`.`send_test_files`"""
    harness_config = ProtocolVerifierConfig(config_parser)
    test_config = TestConfig()
    test_config.parse_from_dict({"event_gen_options": {"invalid": False}})
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        test = FunctionalTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
        )
        with PVResultsHandler(
            test.results, test.test_output_directory, test.save_files
        ) as pv_results_handler:
            asyncio.run(test.send_test_files(pv_results_handler))
        assert len(test.results.responses) == 1


@responses.activate
def test_run_test_functional() -> None:
    """Tests :class:`FunctionalTest`.`run_test`"""
    harness_config = ProtocolVerifierConfig(config_parser)
    test_config = TestConfig()
    test_config.parse_from_dict({"event_gen_options": {"invalid": False}})
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        test = FunctionalTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
        )
        asyncio.run(test.run_test())
        assert len(test.results.responses) == 1
        assert test.pv_file_inspector.file_names["aer"][0] == "Reception.log"
        assert test.pv_file_inspector.file_names["ver"][0] == "Verifier.log"
        os.remove(os.path.join(harness_config.log_file_store, "Reception.log"))
        os.remove(os.path.join(harness_config.log_file_store, "Verifier.log"))


@responses.activate
def test_calc_results_functional() -> None:
    """Tests :class:`FunctionalTest`.`calc_results`"""
    harness_config = ProtocolVerifierConfig(config_parser)
    test_config = TestConfig()
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        test = FunctionalTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
            test_output_directory=harness_config.report_file_store,
        )
        asyncio.run(test.run_test())
        test.calc_results()
        os.remove(os.path.join(harness_config.log_file_store, "Reception.log"))
        os.remove(os.path.join(harness_config.log_file_store, "Verifier.log"))
        files_to_remove = glob.glob(
            "*.*", root_dir=harness_config.report_file_store
        )
        for file_name in files_to_remove:
            os.remove(
                os.path.join(harness_config.report_file_store, file_name)
            )


@responses.activate
def test_calc_results_functional_different_prefix() -> None:
    """Tests :class:`FunctionalTest`.`calc_results` for a different prefix for
    the verifier log domain"""
    harness_config = ProtocolVerifierConfig(config_parser)
    harness_config.log_urls["ver"]["prefix"] = "pv"
    test_config = TestConfig()
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        test = FunctionalTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
            test_output_directory=harness_config.report_file_store,
        )
        asyncio.run(test.run_test())
        test.calc_results()
        os.remove(os.path.join(harness_config.log_file_store, "Reception.log"))
        os.remove(os.path.join(harness_config.log_file_store, "pv.log"))
        files_to_remove = glob.glob(
            "*.*", root_dir=harness_config.report_file_store
        )
        for file_name in files_to_remove:
            os.remove(
                os.path.join(harness_config.report_file_store, file_name)
            )


def test_send_test_files_performance() -> None:
    """Tests :class:`PerformanceTests`.`send_test_files`"""
    harness_config = ProtocolVerifierConfig(config_parser)
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 3, "total_jobs": 2},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
            test_output_directory=harness_config.report_file_store,
        )

        with PVResultsHandler(
            test.results, test.test_output_directory, test.save_files
        ) as pv_results_handler:
            asyncio.run(test.send_test_files(pv_results_handler))
        assert len(test.results) == 6


def test_send_test_files_with_simulator_sliced_delays() -> None:
    """Tests :class:`PerformanceTests`.`send_test_files`"""
    harness_config = ProtocolVerifierConfig(config_parser)
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 3, "total_jobs": 2},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
            test_output_directory=harness_config.report_file_store,
        )

        with PVResultsHandler(
            test.results, test.test_output_directory, test.save_files
        ) as pv_results_handler:
            with TestHarnessPbar() as pbar:
                test.time_start = datetime.now()
                test.results.time_start = test.time_start

                async def run():
                    await asyncio.gather(
                        test.send_test_files_with_simulator(
                            pv_results_handler,
                            test.sim_data_generator,
                            test.delay_times[0::2],
                            harness_config,
                            pbar,
                        ),
                        test.send_test_files_with_simulator(
                            pv_results_handler,
                            test.sim_data_generator,
                            test.delay_times[1::2],
                            harness_config,
                            pbar,
                        ),
                    )

                asyncio.run(run())
        assert len(test.results) == 6


@responses.activate
def test_run_test_performance() -> None:
    """Tests :class:`PerformanceTests`.`run_tests`"""
    harness_config = ProtocolVerifierConfig(config_parser)
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 3, "total_jobs": 2},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
        )
        asyncio.run(test.run_test())
        assert len(test.results) == 6
        assert test.pv_file_inspector.file_names["aer"][0] == "Reception.log"
        assert test.pv_file_inspector.file_names["ver"][0] == "Verifier.log"
        os.remove(os.path.join(harness_config.log_file_store, "Reception.log"))
        os.remove(os.path.join(harness_config.log_file_store, "Verifier.log"))


@responses.activate
def test_run_test_performance_different_prefix() -> None:
    """Tests :class:`PerformanceTests`.`run_tests` but with a different prefix
    for the verifier log domain"""
    harness_config = ProtocolVerifierConfig(config_parser)
    harness_config.log_urls["ver"]["prefix"] = "pv"
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 3, "total_jobs": 2},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
        )
        asyncio.run(test.run_test())
        assert len(test.results) == 6
        assert test.pv_file_inspector.file_names["aer"][0] == "Reception.log"
        assert test.pv_file_inspector.file_names["ver"][0] == "pv.log"
        os.remove(os.path.join(harness_config.log_file_store, "Reception.log"))
        os.remove(os.path.join(harness_config.log_file_store, "pv.log"))


@responses.activate
def test_run_test_performance_multi_process() -> None:
    """Tests :class:`PerformanceTests`.`run_tests` when performing a stop in
    the middle of a multi process test

    :param caplog: Fixture to capture logs
    :type caplog: :class:`pytest.LogCaptureFixture`
    """
    harness_config = ProtocolVerifierConfig(config_parser)
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 3, "total_jobs": 2},
            "num_workers": 2,
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        test_stopper = AsyncTestStopper()
        with TestHarnessPbar() as pbar:
            test = PerformanceTest(
                test_file_generators=test_events,
                test_config=test_config,
                harness_config=harness_config,
                test_graceful_kill_functions=[test_stopper.stop],
                pbar=pbar,
            )
            asyncio.run(test.run_test())
        assert len(test.results) == 6
        assert test.pv_file_inspector.file_names["aer"][0] == "Reception.log"
        assert test.pv_file_inspector.file_names["ver"][0] == "Verifier.log"
        clean_directories(
            [harness_config.report_file_store, harness_config.log_file_store]
        )


@responses.activate
def test_run_test_performance_zero_gap_jobs() -> None:
    """Tests :class:`PerformanceTests`.`run_tests` when the job event gap is
    set to zero meaning that all jobs are sequenced in order with no overlap
    """
    harness_config = ProtocolVerifierConfig(config_parser)
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {
                "num_files_per_sec": 3,
                "total_jobs": 4,
                "job_event_gap": 0,
                "shard": True,
            },
            "test_finish": {"finish_interval": 5},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
        )
        asyncio.run(test.run_test())
        counter = 0
        job_ids = set()
        for _, event in test.results.results.items():
            if counter % 3 == 0:
                job_id_set = set()
            job_id_set.add(event["job_id"])
            if counter % 3 == 2:
                assert len(job_id_set) == 1
                job_ids.add(job_id_set.pop())
            counter += 1
        assert len(job_ids) == 4
        assert len(test.results) == 12
        os.remove(os.path.join(harness_config.log_file_store, "Reception.log"))
        os.remove(os.path.join(harness_config.log_file_store, "Verifier.log"))


@responses.activate
def test_run_test_performance_round_robin_zero_gap() -> None:
    """Tests :class:`PerformanceTests`.`run_tests` when the job event gap is
    set to zero meaning that all jobs are sequenced in order with no overlap
    and the round robin option is set to true.

    Uses two puml files to test the round robin functionality one with events
    A -> B and the other with events C -> D
    """
    harness_config = ProtocolVerifierConfig(config_parser)
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {
                "num_files_per_sec": 4,
                "total_jobs": 4,
                "job_event_gap": 0,
                "shard": True,
                "round_robin": True,
            },
            "test_finish": {"finish_interval": 3},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [
            test_files_path / "test_uml_1.puml",
            test_files_path / "test_uml_2.puml",
        ],
        test_config=test_config,
    )
    events = []

    def callback(url, **kwargs) -> CallbackResult:
        io_data = kwargs["data"]._parts[0][0]._value
        bytes_data = io_data.read()
        # check the data is as expected
        json_bytes = json.loads(bytes_data)
        events.append(json_bytes[0])
        return CallbackResult(
            status=200,
        )

    with mock_pv_http_interface(harness_config, callback):
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
        )
        asyncio.run(test.run_test())
        assert len(events) == 8
        expected_event_sequence = ["A", "B", "C", "D"] * 2
        for event, expected_event in zip(events, expected_event_sequence):
            assert event["eventType"] == expected_event
        os.remove(os.path.join(harness_config.log_file_store, "Reception.log"))
        os.remove(os.path.join(harness_config.log_file_store, "Verifier.log"))


@pytest.mark.skip(
    reason="Will implement when functionality is working correctly"
)
@responses.activate
def test_send_test_files_with_simulator_process_safe() -> None:
    """Tests :class:`PerformanceTests`.`send_test_files_with_simulator`
    using process safe generators for sim data and delay times
    """
    harness_config = ProtocolVerifierConfig(config_parser)
    harness_config.pv_finish_interval = 8
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 3, "total_jobs": 2},
            "num_workers": 1,
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        with TestHarnessPbar() as pbar:
            test = PerformanceTest(
                test_file_generators=test_events,
                test_config=test_config,
                harness_config=harness_config,
                pbar=pbar,
            )
            with PVResultsHandler(
                test.results, test.test_output_directory, test.save_files
            ) as pv_results_adder:
                with ProcessGeneratorManager(
                    test.sim_data_generator
                ) as process_safe_sim_data_generator:
                    with ProcessGeneratorManager(
                        iter(test.delay_times)
                    ) as process_safe_delay_times:
                        pbar.total = test.total_number_of_events
                        test.time_start = datetime.now()
                        test.results.time_start = test.time_start
                        asyncio.run(
                            test.send_test_files_with_simulator(
                                pv_results_adder,
                                process_safe_sim_data_generator,
                                process_safe_delay_times,
                                harness_config,
                                pbar,
                            )
                        )
        assert len(test.results) == 6


@responses.activate
def test_run_test_performance_kafka(kafka_producer_mock: None) -> None:
    """Tests :class:`PerformanceTests`.`run_tests` with a kafka message bus
    mocked out

    :param kafka_producer_mock: Fixture providing a mocked kafka producer
    :type kafka_producer_mock: `None`
    """
    harness_config = ProtocolVerifierConfig(config_parser)
    harness_config.message_bus_protocol = "KAFKA"
    harness_config.kafka_message_bus_host = "localhost:9092"
    harness_config.kafka_message_bus_topic = "test"
    harness_config.pv_send_as_pv_bytes = True
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 3, "total_jobs": 2},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
        )
        asyncio.run(test.run_test())
        assert len(test.results) == 6
        assert test.pv_file_inspector.file_names["aer"][0] == "Reception.log"
        assert test.pv_file_inspector.file_names["ver"][0] == "Verifier.log"
        os.remove(os.path.join(harness_config.log_file_store, "Reception.log"))
        os.remove(os.path.join(harness_config.log_file_store, "Verifier.log"))


@responses.activate
def test_run_test_performance_kafka_with_errors(
    sync_kafka_producer_mock: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tests :class:`PerformanceTests`.`run_tests` with a kafka message bus
    mocked out

    :param sync_kafka_producer_mock: Fixture providing a mocked kafka producer
    :type sync_kafka_producer_mock: `None`
    :param monkeypatch: Fixture to patch the kafka producer send method
    :type monkeypatch: :class:`pytest.MonkeyPatch`
    """
    timeout_error = KafkaTimeoutError3("timeout")

    def mock_send(*args, **kwargs):
        sync_kafka_producer_mock.append("send")
        future = Future()
        future.failure(timeout_error)
        return future

    monkeypatch.setattr(kafka3.KafkaProducer, "send", mock_send)
    harness_config = ProtocolVerifierConfig(config_parser)
    harness_config.message_bus_protocol = "KAFKA3"
    harness_config.kafka_message_bus_host = "localhost:9092"
    harness_config.kafka_message_bus_topic = "test"
    harness_config.pv_send_as_pv_bytes = True
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 3, "total_jobs": 2},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
        )
        asyncio.run(test.run_test())
        assert len(test.results) == 6
        error_files = glob.glob(
            os.path.join(
                harness_config.log_file_store, ERROR_LOG_FILE_PREFIX + "*"
            )
        )
        assert error_files
        error_count = 0
        for error_file in error_files:
            with open(error_file, "r", encoding="utf-8") as file:
                for line in file.readlines():
                    error_count += 1
                    assert str(timeout_error) in line
        test.get_all_simulation_data()
        assert test.results.failures["num_errors"] == 6
        clean_directories(
            [
                harness_config.report_file_store,
                harness_config.log_file_store,
            ]
        )


@responses.activate
def test_run_test_performance_calc_results(grok_exporter_string: str) -> None:
    """Tests :class:`PerformanceTests`.`calc_results`"""
    harness_config = ProtocolVerifierConfig(config_parser)
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 3, "total_jobs": 2},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        responses.add(
            responses.GET,
            harness_config.pv_grok_exporter_url,
            body=grok_exporter_string.encode("utf-8"),
            status=200,
            headers={
                "Content-Type": "text/plain; version=0.0.4; charset=utf-8"
            },
        )
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
            test_output_directory=harness_config.report_file_store,
        )
        asyncio.run(test.run_test())
        test.calc_results()
        clean_directories(
            [
                harness_config.report_file_store,
                harness_config.log_file_store,
            ]
        )


@responses.activate
def test_run_test_performance_profile_job_batch() -> None:
    """Tests :class:`PerformanceTests`.`run_tests`"""
    harness_config = ProtocolVerifierConfig(config_parser)
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    profile = Profile(
        pd.DataFrame([[0, 3], [1, 3], [2, 3]], columns=["Time", "Number"])
    )
    with mock_pv_http_interface(harness_config):
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
            test_profile=profile,
        )
        asyncio.run(test.run_test())
        assert len(test.results) == 6
        assert test.pv_file_inspector.file_names["aer"][0] == "Reception.log"
        assert test.pv_file_inspector.file_names["ver"][0] == "Verifier.log"
        os.remove(os.path.join(harness_config.log_file_store, "Reception.log"))
        os.remove(os.path.join(harness_config.log_file_store, "Verifier.log"))


@responses.activate
def test_run_test_performance_profile_shard() -> None:
    """Tests :class:`PerformanceTests`.`run_tests` with the test timeout hit"""
    harness_config = ProtocolVerifierConfig(config_parser)
    harness_config.pv_finish_interval = 5
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {
                "shard": True,
            },
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    profile = Profile(
        pd.DataFrame([[0, 3], [1, 3], [2, 3]], columns=["Time", "Number"])
    )
    with mock_pv_http_interface(harness_config):
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
            test_profile=profile,
        )
        asyncio.run(test.run_test())
        assert len(test.results) == 6
        assert test.pv_file_inspector.file_names["aer"][0] == "Reception.log"
        assert test.pv_file_inspector.file_names["ver"][0] == "Verifier.log"
        os.remove(os.path.join(harness_config.log_file_store, "Reception.log"))
        os.remove(os.path.join(harness_config.log_file_store, "Verifier.log"))


@responses.activate
def test_get_report_files_from_results(
    results_dataframe: pd.DataFrame,
) -> None:
    """Tests :class:`PerformanceTests`.`get_report_files_from_results`
    :param results_dataframe: Fixture providing a results dataframe with
    pv results and th results
    :type results_dataframe: :class:`pd`.`DataFrame`
    """
    harness_config = ProtocolVerifierConfig(config_parser)
    test_config = TestConfig()
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    test = PerformanceTest(
        test_file_generators=test_events,
        test_config=test_config,
        harness_config=harness_config,
        # test_profile=profile,
    )
    results_holder = DictResultsHolder()
    for key, row in results_dataframe.iterrows():
        results_holder[key] = row.to_dict()
    test.results.results = results_holder
    test.results.calc_all_results()
    # start and end times for test
    test.time_start = datetime.now()
    test.time_end = test.time_start + timedelta(seconds=10)
    _, xml = test.get_report_files_from_results()
    # get xml tree
    xml_tree = ET.fromstring(xml)
    # check there is one test suite and its attributes are correct
    children = list(xml_tree)
    assert len(children) == 1
    test_suite = children[0]
    expected_attribs = {
        "name": "Performance test run",
        "tests": "10",
        "failures": "0",
        "errors": "0",
    }
    check_dict_equivalency(expected_attribs, test_suite.attrib)
    # get and check children
    children = list(test_suite)
    assert len(children) == 2
    properties = children[0]
    test_case = children[1]
    # check properties
    assert properties.tag == "properties"
    children = list(properties)
    assert len(children) == 16
    expected_properties = {
        "num_tests": "10",
        "num_failures": "0",
        "num_errors": "0",
        "th_end": "9.0",
        "aer_end": "11.0",
        "pv_end": "13.0",
        "average_sent_per_sec": str(10 / 9),
        "average_processed_per_sec": str(10 / 13),
        "average_queue_time": "1.0",
        "average_response_time": "4.0",
        "num_aer_start": "10",
        "num_aer_end": "10",
        "AER_file_process_error": "0",
        "AEO_file_process_error": "0",
        "test_start_time": test.time_start.strftime("%Y/%m/%d, %H:%M:%S"),
        "test_end_time": test.time_end.strftime("%Y/%m/%d, %H:%M:%S"),
    }
    for prop in children:
        assert expected_properties[prop.attrib["name"]] == prop.attrib["value"]
    # check test case
    assert test_case.tag == "testcase"
    assert test_case.attrib["name"] == "Run Result"
    assert test_case.attrib["classname"] == "Performance test run"


@responses.activate
def test_run_test_performance_stop_test(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tests :class:`PerformanceTests`.`run_tests`"""
    harness_config = ProtocolVerifierConfig(config_parser)
    # make stop test timeout 1 second
    harness_config.pv_test_timeout = 1
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 3, "total_jobs": 2},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    caplog.set_level(logging.INFO)
    with mock_pv_http_interface(harness_config):
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
        )
        asyncio.run(test.run_test())
        assert (
            "Protocol Verifier failed to finish within the test timeout of "
            f"{harness_config.pv_test_timeout} seconds.\nResults will "
            "be calculated at this point" in caplog.text
        )
        clean_directories(
            [harness_config.report_file_store, harness_config.log_file_store]
        )


@responses.activate
def test_run_test_performance_stop_test_async_test_stopper(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tests :class:`PerformanceTests`.`run_tests`"""
    harness_config = ProtocolVerifierConfig(config_parser)
    # make stop test timeout 1 second
    harness_config.pv_test_timeout = 100000
    harness_config.pv_finish_interval = 10000
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 3, "total_jobs": 2},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    caplog.set_level(logging.INFO)
    with mock_pv_http_interface(harness_config):
        test_stopper = AsyncTestStopper()
        test_stopper.set()
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
            test_graceful_kill_functions=[test_stopper.stop],
        )
        t1 = time.time()
        asyncio.run(asyncio.wait_for(test.run_test(), 10))
        t2 = time.time()
        assert "Test stopped" in caplog.text
        assert t2 - t1 < 10
        clean_directories(
            [harness_config.report_file_store, harness_config.log_file_store]
        )


@responses.activate
@pytest.mark.asyncio
async def test_run_test_performance_stop_test_async_test_stopper_multi_process(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tests :class:`PerformanceTests`.`run_tests` when performing a stop in
    the middle of a multi process test

    :param caplog: Fixture to capture logs
    :type caplog: :class:`pytest.LogCaptureFixture`
    """
    harness_config = ProtocolVerifierConfig(config_parser)
    # make stop test timeout 1 second
    harness_config.pv_test_timeout = 100000
    harness_config.pv_finish_interval = 10000
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 3, "total_jobs": 50},
            "num_workers": 2,
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    caplog.set_level(logging.INFO)
    with mock_pv_http_interface(harness_config):
        test_stopper = AsyncTestStopper()
        with TestHarnessPbar() as pbar:
            test = PerformanceTest(
                test_file_generators=test_events,
                test_config=test_config,
                harness_config=harness_config,
                test_graceful_kill_functions=[test_stopper.stop],
                pbar=pbar,
            )

            async def async_wait_stop():
                await asyncio.sleep(2)
                test_stopper.set()

            t1 = time.time()
            await asyncio.gather(
                asyncio.wait_for(test.run_test(), 10), async_wait_stop()
            )
        t2 = time.time()
        assert "Test stopped" in caplog.text
        assert t2 - t1 < 10
        clean_directories(
            [harness_config.report_file_store, harness_config.log_file_store]
        )


@responses.activate
def test_run_test_performance_no_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tests :class:`PerformanceTests`.`run_tests` not grabbing logs"""
    harness_config = ProtocolVerifierConfig(config_parser)
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {
                "num_files_per_sec": 30,
                "total_jobs": 20,
                "save_logs": False,
            },
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    caplog.set_level(logging.INFO)
    with mock_pv_http_interface(harness_config):
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
        )
        asyncio.run(test.run_test())

        assert not os.path.exists(
            os.path.join(harness_config.log_file_store, "Reception.log")
        )
        assert not os.path.exists(
            os.path.join(harness_config.log_file_store, "Verifier.log")
        )
        clean_directories(
            [harness_config.report_file_store, harness_config.log_file_store]
        )


@responses.activate
def test_run_test_performance_kafka_get_metrics_from_kafka(
    kafka_producer_mock: None, kafka_consumer_mock: None
) -> None:
    """Tests :class:`PerformanceTests`.`run_tests` with a kafka message bus
    mocked out

    :param kafka_producer_mock: Fixture providing a mocked kafka producer
    :type kafka_producer_mock: `None`
    :param kafka_consumer_mock: Fixture providing a mocked kafka consumer
    :type kafka_consumer_mock: `None`
    """
    harness_config = ProtocolVerifierConfig(config_parser)
    harness_config.message_bus_protocol = "KAFKA"
    harness_config.kafka_message_bus_host = "localhost:9092"
    harness_config.kafka_message_bus_topic = "test"
    harness_config.pv_send_as_pv_bytes = True
    harness_config.metrics_from_kafka = True
    test_config = TestConfig()

    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 3, "total_jobs": 2},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
        )
        asyncio.run(test.run_test())
        assert len(test.results) == 6
        for event_metrics in test.results.results.values():
            for field in [
                "time_sent",
                "AER_start",
                "AER_end",
                "AEOSVDC_start",
                "AEOSVDC_end",
            ]:
                assert field in event_metrics
                assert isinstance(event_metrics[field], float)
            assert event_metrics["response"] == ""
        clean_directories(
            [harness_config.report_file_store, harness_config.log_file_store]
        )


@responses.activate
def test_run_test_performance_kafka_get_metrics_from_kafka_no_length(
    kafka_producer_mock_no_length: None, kafka_consumer_mock_no_length: None
) -> None:
    """Tests :class:`PerformanceTests`.`run_tests` with a kafka message bus
    mocked out

    :param kafka_producer_mock: Fixture providing a mocked kafka producer
    :type kafka_producer_mock: `None`
    :param kafka_consumer_mock: Fixture providing a mocked kafka consumer
    :type kafka_consumer_mock: `None`
    """
    harness_config = ProtocolVerifierConfig(config_parser)
    harness_config.send_json_without_length_prefix = True
    harness_config.message_bus_protocol = "KAFKA"
    harness_config.kafka_message_bus_host = "localhost:9092"
    harness_config.kafka_message_bus_topic = "test"
    harness_config.pv_send_as_pv_bytes = True
    harness_config.metrics_from_kafka = True
    test_config = TestConfig()

    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 3, "total_jobs": 2},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
        )
        asyncio.run(test.run_test())
        assert len(test.results) == 6
        for event_metrics in test.results.results.values():
            for field in [
                "time_sent",
                "AER_start",
                "AER_end",
                "AEOSVDC_start",
                "AEOSVDC_end",
            ]:
                assert field in event_metrics
                assert isinstance(event_metrics[field], float)
            assert event_metrics["response"] == ""
        clean_directories(
            [harness_config.report_file_store, harness_config.log_file_store]
        )


@responses.activate
def test_run_test_performance_agg_during_test(
    kafka_producer_mock: None, kafka_consumer_mock: None
) -> None:
    """Tests :class:`PerformanceTests`.`run_tests` with a kafka message bus
    mocked out

    :param kafka_producer_mock: Fixture providing a mocked kafka producer
    :type kafka_producer_mock: `None`
    :param kafka_consumer_mock: Fixture providing a mocked kafka consumer
    :type kafka_consumer_mock: `None`
    """
    harness_config = ProtocolVerifierConfig(config_parser)
    harness_config.message_bus_protocol = "KAFKA"
    harness_config.kafka_message_bus_host = "localhost:9092"
    harness_config.kafka_message_bus_topic = "test"
    harness_config.pv_send_as_pv_bytes = True
    harness_config.metrics_from_kafka = True
    test_config = TestConfig()

    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 12, "total_jobs": 8},
            "aggregate_during": True,
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
        )
        asyncio.run(test.run_test())
        assert len(test.results) == 24
        for event_metrics in test.results.results.values():
            for field in [
                "time_sent",
                "AER_start",
                "AER_end",
                "AEOSVDC_start",
                "AEOSVDC_end",
            ]:
                assert field in event_metrics
                assert isinstance(event_metrics[field], float)
            assert event_metrics["response"] == ""
        # mirror results holder in a new instance of PVResults with
        # agg_during_test set to False
        mirrored_results = PVPerformanceResults()
        mirrored_results.results = test.results.results
        test.results.calc_all_results()
        mirrored_results.calc_all_results()
        for index, row in test.results.agg_results.iterrows():
            mirrored_row = mirrored_results.agg_results.loc[index]
            for field in row.index:
                if np.isnan(row[field]):
                    assert np.isnan(mirrored_row[field])
                else:
                    assert row[field] == mirrored_row[field]
        clean_directories(
            [harness_config.report_file_store, harness_config.log_file_store]
        )


@responses.activate
def test_run_test_performance_agg_during_test_sample(
    kafka_producer_mock: None, kafka_consumer_mock: None
) -> None:
    """Tests :class:`PerformanceTests`.`run_tests` with a kafka message bus
    mocked out

    :param kafka_producer_mock: Fixture providing a mocked kafka producer
    :type kafka_producer_mock: `None`
    :param kafka_consumer_mock: Fixture providing a mocked kafka consumer
    :type kafka_consumer_mock: `None`
    """
    harness_config = ProtocolVerifierConfig(config_parser)
    harness_config.message_bus_protocol = "KAFKA"
    harness_config.kafka_message_bus_host = "localhost:9092"
    harness_config.kafka_message_bus_topic = "test"
    harness_config.pv_send_as_pv_bytes = True
    harness_config.metrics_from_kafka = True
    harness_config.pv_finish_interval = 8
    test_config = TestConfig()

    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 10, "total_jobs": 20},
            "aggregate_during": True,
            "sample_rate": 2,
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
        )
        asyncio.run(test.run_test())
        assert len(test.results) < 60
        test.results.calc_all_results()
        test.results.failures["num_tests"] = 60
        test.results.failures["num_failures"] = 0
        test.results.failures["num_errors"] = 0
        clean_directories(
            [harness_config.report_file_store, harness_config.log_file_store]
        )


@responses.activate
def test_run_test_performance_low_memory(
    kafka_producer_mock: None, kafka_consumer_mock: None
) -> None:
    """Tests :class:`PerformanceTests`.`run_tests` with a kafka message bus
    mocked out

    :param kafka_producer_mock: Fixture providing a mocked kafka producer
    :type kafka_producer_mock: `None`
    :param kafka_consumer_mock: Fixture providing a mocked kafka consumer
    :type kafka_consumer_mock: `None`
    """
    harness_config = ProtocolVerifierConfig(config_parser)
    harness_config.message_bus_protocol = "KAFKA"
    harness_config.kafka_message_bus_host = "localhost:9092"
    harness_config.kafka_message_bus_topic = "test"
    harness_config.pv_send_as_pv_bytes = True
    harness_config.metrics_from_kafka = True
    harness_config.pv_finish_interval = 8
    test_config = TestConfig()

    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 10, "total_jobs": 20},
            "low_memory": True,
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with mock_pv_http_interface(harness_config):
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
        )
        asyncio.run(test.run_test())
        assert len(test.results) == 0
        test.results.calc_all_results()
        test.results.failures["num_tests"] = 60
        test.results.failures["num_failures"] = 0
        test.results.failures["num_errors"] = 0
        clean_directories(
            [harness_config.report_file_store, harness_config.log_file_store]
        )


def test_use_harness_config_instead_of_test_config() -> None:
    """Tests :class:`PerformanceTests` using test_finish parameters in
    ProtocolVerifierConfig
    """
    harness_config = ProtocolVerifierConfig(config_parser)
    test_config = TestConfig()
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    assert all(
        field not in test_config.test_finish
        for field in ["timeout", "finish_interval", "metric_get_interval"]
    )
    PerformanceTest(
        test_file_generators=test_events,
        test_config=test_config,
        harness_config=harness_config,
    )
    assert test_config.test_finish["timeout"] == harness_config.pv_test_timeout
    assert test_config.test_finish["finish_interval"] == (
        harness_config.pv_finish_interval
    )
    assert test_config.test_finish["metric_get_interval"] == (
        harness_config.log_calc_interval_time
    )


def test_use_test_config_instead_of_harness_config() -> None:
    """Tests :class:`PerformanceTests` using test_finish parameters in
    TestConfig
    """
    harness_config = ProtocolVerifierConfig(config_parser)
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "test_finish": {
                "timeout": 51,
                "finish_interval": 53,
                "metric_get_interval": 54,
            }
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    PerformanceTest(
        test_file_generators=test_events,
        test_config=test_config,
        harness_config=harness_config,
    )
    assert test_config.test_finish["timeout"] == 51
    assert test_config.test_finish["timeout"] != harness_config.pv_test_timeout
    assert test_config.test_finish["finish_interval"] == 53
    assert test_config.test_finish["finish_interval"] != (
        harness_config.pv_finish_interval
    )
    assert test_config.test_finish["metric_get_interval"] == 54
    assert test_config.test_finish["metric_get_interval"] != (
        harness_config.log_calc_interval_time
    )
