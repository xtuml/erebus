# pylint: disable=W0613
# pylint: disable=R0801
# pylint: disable=C2801
# pylint: disable=C0302
"""Tests for tests.py
"""
from pathlib import Path
import os
import asyncio
import glob
from datetime import datetime
from io import StringIO
from typing import Iterable
from tempfile import NamedTemporaryFile
import logging

import responses
from aioresponses import aioresponses
import pandas as pd
import pytest
import numpy as np

from test_harness.config.config import TestConfig, HarnessConfig
from test_harness.protocol_verifier.tests import (
    PerformanceTest,
    FunctionalTest,
    PVResultsHandler,
    PVFunctionalResults,
)
from test_harness.protocol_verifier.pvresultsdataframe import (
    PVResultsDataFrame,
)
from test_harness.protocol_verifier.generate_test_files import (
    generate_test_events_from_puml_files,
)
from test_harness.simulator.simulator_profile import Profile
from test_harness.utils import clean_directories

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


class TestPVResultsDataFrame:
    """Group of tests for :class:`PVResultsDataFrame`"""

    @staticmethod
    def test_create_results_holder() -> None:
        """Tests :class:`PVResultsDataFrame`.`create_results_holder`"""
        results = PVResultsDataFrame()
        assert isinstance(results.results, pd.DataFrame)

    @staticmethod
    def test_create_event_result_row() -> None:
        """Tests :class:`PVResultsDataFrame`.`create_event_result_row`"""
        results = PVResultsDataFrame()
        results.create_event_result_row("event_id")
        assert len(results.results) == 1
        assert "event_id" in results.results.index
        assert set(results.data_fields) == set(results.results.columns)
        for col in results.results.columns:
            assert pd.isnull(results.results.loc["event_id", col])

    @staticmethod
    def test_update_event_results_with_event_id() -> None:
        """Tests
        :class:`PVResultsDataFrame`.`update_event_results_with_event_id`
        """
        results = PVResultsDataFrame()
        results.create_event_result_row("event_id")
        results.update_event_results_with_event_id(
            "event_id", {"job_id": "job_id"}
        )
        assert results.results.loc["event_id", "job_id"] == "job_id"

    @staticmethod
    def test_update_event_results_with_job_id() -> None:
        """Tests
        :class:`PVResultsDataFrame`.`update_event_results_with_job_id`
        """
        results = PVResultsDataFrame()
        results.create_event_result_row("event_id")
        results.update_event_results_with_event_id(
            "event_id", {"job_id": "job_id"}
        )
        results.update_event_results_with_job_id(
            "job_id", {"response": "a response"}
        )
        assert results.results.loc["event_id", "response"] == "a response"

    @staticmethod
    def test_add_first_event_data(
        start_time: datetime,
        event_job_response_time_dicts: list[dict[str, str | datetime]],
    ) -> None:
        """Tests :class:`PVResultsDataFrame`.`add_first_event_data`

        :param start_time: Fixture providing a starttime
        :type start_time: :class:`datetime`
        :param event_job_response_time_dicts: Fixture providing event ids, job
        ids, responses and times
        :type event_job_response_time_dicts: `list`[`dict`[`str`, `str`  |
        :class:`datetime`]]
        """
        results = PVResultsDataFrame()
        results.time_start = start_time
        for event_job_response_time_dict in event_job_response_time_dicts:
            results.add_first_event_data(**event_job_response_time_dict)
            event_id = event_job_response_time_dict["event_id"]
            job_id = event_job_response_time_dict["job_id"]
            time_sent = (
                event_job_response_time_dict["time_completed"] - start_time
            ).total_seconds()
            response = event_job_response_time_dict["response"]
            assert event_id in results.results.index
            assert results.results.loc[event_id, "job_id"] == job_id
            assert results.results.loc[event_id, "time_sent"] == time_sent
            assert results.results.loc[event_id, "response"] == response

    @staticmethod
    def test_update_from_sim(
        start_time: datetime,
        event_job_response_time_dicts: list[dict[str, str | datetime]],
    ) -> None:
        """Tests :class:`PVResultsDataFrame`.`update_from_sim`

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
        results = PVResultsDataFrame()
        results.time_start = start_time
        results.update_from_sim(events, job_id, response, time_completed)
        assert len(results.results) == 3
        assert set(results.results["job_id"]) == set(["job_id"])
        assert set(results.results["response"]) == set(["a response"])
        assert set(results.results["time_sent"]) == set(
            [(time_completed - start_time).total_seconds()]
        )
        assert set(results.results.index) == set(
            event["eventId"] for event in events
        )

    @staticmethod
    def test_update_pv_sim_time_field(
        start_time: datetime,
        event_job_response_time_dicts: list[dict[str, str | datetime]],
    ) -> None:
        """Tests :class:`PVResultsDataFrame`.`update_pv_sim_time_field`

        :param start_time: Fixture providing a starttime
        :type start_time: :class:`datetime`
        :param event_job_response_time_dicts: Fixture providing event ids, job
        ids, responses and times
        :type event_job_response_time_dicts: `list`[`dict`[`str`, `str`  |
        :class:`datetime`]]
        """
        results = PVResultsDataFrame()
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
        for _, row in results.results.iterrows():
            assert row["time_sent"] == row["AER_start"]

    @staticmethod
    def test_read_groked_string(
        start_time: datetime,
        event_job_response_time_dicts: list[dict[str, str | datetime]],
    ) -> None:
        """Tests :class:`PVResultsDataFrame`.`update_read_groked_string`

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
        results = PVResultsDataFrame()
        results.time_start = start_time
        for event_job_response_time_dict in event_job_response_time_dicts:
            results.add_first_event_data(**event_job_response_time_dict)
        results.read_groked_string_io(groked_string_io)
        assert not pd.isnull(
            results.results.loc[
                "205d5d7e-4eb7-4b8a-a638-1bd0a2ae6497", "AER_start"
            ]
        )
        assert all(
            pd.isnull(
                results.results.loc[
                    (
                        results.results.index
                        != "205d5d7e-4eb7-4b8a-a638-1bd0a2ae6497"
                    ),
                    "AER_start",
                ]
            )
        )
        for col in results.data_fields[-3:]:
            assert all(pd.isnull(results.results[col]))

    @staticmethod
    def test_get_and_read_grok_metrics(
        start_time: datetime,
        event_job_response_time_dicts: list[dict[str, str | datetime]],
    ) -> None:
        """Tests :class:`PVResultsDataFrame`.`get_an_read_grok_metrics`

        :param start_time: Fixture providing a starttime
        :type start_time: :class:`datetime`
        :param event_job_response_time_dicts: Fixture providing event ids, job
        ids, responses and times
        :type event_job_response_time_dicts: `list`[`dict`[`str`, `str`  |
        :class:`datetime`]]
        """
        results = PVResultsDataFrame()
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
        """Tests :class:`PVResultsDataFrame`.`create_respone_time_fields`

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        """
        results = PVResultsDataFrame()
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
        """Tests :class:`PVResultsDataFrame`.`calculate_failures` with no
        failures

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        """
        results = PVResultsDataFrame()
        results.results = results_dataframe
        results.create_response_time_fields()
        failures = results.calculate_failures()
        assert failures["num_errors"] == 0
        assert failures["num_failures"] == 0
        assert failures["num_tests"] == 10

    @staticmethod
    def test_calculate_failures_th_failures(
        results_dataframe: pd.DataFrame,
    ) -> None:
        """Tests :class:`PVResultsDataFrame`.`calculate_failures` with a th
        failure

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        """
        results = PVResultsDataFrame()
        results_dataframe.loc["event_0", "response"] = "error response"
        results.results = results_dataframe
        results.create_response_time_fields()
        failures = results.calculate_failures()
        assert failures["num_errors"] == 1
        assert failures["num_failures"] == 0
        assert failures["num_tests"] == 10

    @staticmethod
    def test_calculate_failures_pv_failures(
        results_dataframe: pd.DataFrame,
    ) -> None:
        """Tests :class:`PVResultsDataFrame`.`calculate_failures` with a pv
        failure

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        """
        results = PVResultsDataFrame()
        results_dataframe.loc[
            "event_0", ["AER_start", "AER_end", "AEOSVDC_start", "AEOSVDC_end"]
        ] = None
        results.results = results_dataframe
        results.create_response_time_fields()
        failures = results.calculate_failures()
        assert failures["num_errors"] == 0
        assert failures["num_failures"] == 1
        assert failures["num_tests"] == 10

    @staticmethod
    def test_calc_end_times_no_nans(results_dataframe: pd.DataFrame) -> None:
        """Tests :class:`PVResultsDataFrame`.`calc_end_times` with no nan
        entries

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        """
        results = PVResultsDataFrame()
        results.results = results_dataframe
        results.create_response_time_fields()
        end_times = results.calc_end_times()
        assert end_times["th_end"] == 9.0
        assert end_times["pv_end"] == 13.0
        assert end_times["aer_end"] == 11.0

    @staticmethod
    def test_calc_end_times_nans(results_dataframe: pd.DataFrame) -> None:
        """Tests :class:`PVResultsDataFrame`.`calc_end_times` with nan
        entries

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        """
        results = PVResultsDataFrame()
        results_dataframe.loc["event_9", "AEOSVDC_end"] = None
        results.results = results_dataframe
        results.create_response_time_fields()
        end_times = results.calc_end_times()
        assert end_times["th_end"] == 9.0
        assert end_times["pv_end"] == 12.0
        assert end_times["aer_end"] == 11.0

    @staticmethod
    def test_calc_full_averages(results_dataframe: pd.DataFrame) -> None:
        """Tests :class:`PVResultsDataFrame`.`calc_full_averages`

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        """
        results = PVResultsDataFrame()
        results.results = results_dataframe
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
        :class:`PVResultsDataFrame`.`calculate_aggregated_results_dataframe`

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        """
        results = PVResultsDataFrame()
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
        """Tests :class:`PVResultsDataFrame`.`calc_all_results`

        :param results_dataframe: Fixture providing a results dataframe with
        pv results and th results
        :type results_dataframe: :class:`pd`.`DataFrame`
        """
        results = PVResultsDataFrame()
        results.results = results_dataframe
        results.calc_all_results()
        assert results.end_times is not None
        assert results.failures is not None
        assert results.full_averages is not None
        assert results.agg_results is not None


class TestPVResultsHandler:
    """Group of tests for :class:`PVResultsHandler`"""

    @staticmethod
    def test___enter__() -> None:
        """Tests :class:`PVResultsHandler`.`__enter__`"""
        harness_config = HarnessConfig(test_config_path)
        results = PVFunctionalResults()
        results_handler = PVResultsHandler(
            results, harness_config.report_file_store
        )
        results_handler.__enter__()
        assert results_handler.daemon_thread.is_alive()

    @staticmethod
    def test___exit__() -> None:
        """Tests :class:`PVResultsHandler`.`__exit__`"""
        harness_config = HarnessConfig(test_config_path)
        results = PVFunctionalResults()
        results_handler = PVResultsHandler(
            results, harness_config.report_file_store
        )
        results_handler.__enter__()
        results_handler.__exit__(None, None, None)
        assert not results_handler.daemon_not_done
        assert not results_handler.daemon_thread.is_alive()

    @staticmethod
    def test___exit___error() -> None:
        """Tests
        :class:`PVResultsHandler`.`__exit__` when an error is thrown
        """
        harness_config = HarnessConfig(test_config_path)
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
        harness_config = HarnessConfig(test_config_path)
        results = PVFunctionalResults()
        with pytest.raises(RuntimeError) as e_info:
            with PVResultsHandler(results, harness_config.report_file_store):
                raise RuntimeError("An error")
        assert e_info.value.args[0] == "An error"

    @staticmethod
    def test_handle_result() -> None:
        """Tests :class:`PVResultsHandler`.`handle_result`"""
        harness_config = HarnessConfig(test_config_path)
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
        harness_config = HarnessConfig(test_config_path)
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
        harness_config = HarnessConfig(test_config_path)
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
        files_to_remove = [
            "a_file_name"
        ]
        for file_name in files_to_remove:
            path = os.path.join(harness_config.report_file_store, file_name)
            assert os.path.exists(path)
            os.remove(path)
        assert not glob.glob("*.*", root_dir=harness_config.report_file_store)


def test_send_test_files_functional() -> None:
    """Tests :class:`FunctionalTest`.`send_test_files`"""
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_config.parse_from_dict({"event_gen_options": {"invalid": False}})
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with aioresponses() as mock:
        mock.post(url=harness_config.pv_send_url)
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
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_config.parse_from_dict({"event_gen_options": {"invalid": False}})
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with aioresponses() as mock:
        mock.post(url=harness_config.pv_send_url)
        responses.get(
            url=harness_config.log_urls["aer"]["getFileNames"],
            json={"fileNames": ["Reception.log"]},
        )
        responses.post(
            url=harness_config.log_urls["aer"]["getFile"],
            body=b"test log",
        )
        responses.get(
            url=harness_config.log_urls["ver"]["getFileNames"],
            json={"fileNames": ["Verifier.log"]},
        )
        responses.post(
            url=harness_config.log_urls["ver"]["getFile"],
            body=b"test log",
        )
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
def test_calc_results_functional():
    """Tests :class:`FunctionalTest`.`calc_results`"""
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with aioresponses() as mock:
        mock.post(url=harness_config.pv_send_url, repeat=True)
        responses.get(
            url=harness_config.log_urls["aer"]["getFileNames"],
            json={"fileNames": ["Reception.log"]},
        )
        responses.post(
            url=harness_config.log_urls["aer"]["getFile"],
            body=b"test log",
        )
        responses.get(
            url=harness_config.log_urls["ver"]["getFileNames"],
            json={"fileNames": ["Verifier.log"]},
        )
        responses.post(
            url=harness_config.log_urls["ver"]["getFile"],
            body=b"test log",
        )
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


def test_send_test_files_performance() -> None:
    """Tests :class:`PerformanceTests`.`send_test_files`"""
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 30, "total_jobs": 20},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with aioresponses() as mock:
        mock.post(url=harness_config.pv_send_url, repeat=True)
        with NamedTemporaryFile(suffix=".db") as db_file:
            os.environ["PV_RESULTS_DB_ADDRESS"] = f"sqlite:///{db_file.name}"
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
            assert len(test.results) == 60


@responses.activate
def test_run_test_performance() -> None:
    """Tests :class:`PerformanceTests`.`run_tests`"""
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 30, "total_jobs": 20},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with aioresponses() as mock:
        mock.post(url=harness_config.pv_send_url, repeat=True)
        responses.get(
            url=harness_config.log_urls["aer"]["getFileNames"],
            json={"fileNames": ["Reception.log"]},
        )
        responses.post(
            url=harness_config.log_urls["aer"]["getFile"],
            body=b"test log",
        )
        responses.get(
            url=harness_config.log_urls["ver"]["getFileNames"],
            json={"fileNames": ["Verifier.log"]},
        )
        responses.post(
            url=harness_config.log_urls["ver"]["getFile"],
            body=b"test log",
        )
        with NamedTemporaryFile(suffix=".db") as db_file:
            os.environ["PV_RESULTS_DB_ADDRESS"] = f"sqlite:///{db_file.name}"
            test = PerformanceTest(
                test_file_generators=test_events,
                test_config=test_config,
                harness_config=harness_config,
            )
            asyncio.run(test.run_test())
            assert len(test.results) == 60
            assert (
                test.pv_file_inspector.file_names["aer"][0] == "Reception.log"
            )
            assert (
                test.pv_file_inspector.file_names["ver"][0] == "Verifier.log"
            )
            os.remove(
                os.path.join(harness_config.log_file_store, "Reception.log")
            )
            os.remove(
                os.path.join(harness_config.log_file_store, "Verifier.log")
            )


@responses.activate
def test_run_test_performance_calc_results(grok_exporter_string: str) -> None:
    """Tests :class:`PerformanceTests`.`calc_results`"""
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 30, "total_jobs": 20},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    with aioresponses() as mock:
        mock.post(url=harness_config.pv_send_url, repeat=True)
        responses.add(
            responses.GET,
            harness_config.pv_grok_exporter_url,
            body=grok_exporter_string.encode("utf-8"),
            status=200,
            headers={
                "Content-Type": "text/plain; version=0.0.4; charset=utf-8"
            },
        )
        responses.get(
            url=harness_config.log_urls["aer"]["getFileNames"],
            json={"fileNames": ["Reception.log"]},
        )
        responses.get(
            url=harness_config.log_urls["aer"]["getFileNames"],
            json={"fileNames": ["Reception.log"]},
        )
        responses.post(
            url=harness_config.log_urls["aer"]["getFile"],
            body=b"test log",
        )
        responses.get(
            url=harness_config.log_urls["ver"]["getFileNames"],
            json={"fileNames": ["Verifier.log"]},
        )
        responses.post(
            url=harness_config.log_urls["ver"]["getFile"],
            body=b"test log",
        )
        with NamedTemporaryFile(suffix=".db") as db_file:
            os.environ["PV_RESULTS_DB_ADDRESS"] = f"sqlite:///{db_file.name}"
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
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 30, "total_jobs": 20},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    profile = Profile(
        pd.DataFrame([[0, 30], [1, 30], [2, 30]], columns=["Time", "Number"])
    )
    with aioresponses() as mock:
        mock.post(url=harness_config.pv_send_url, repeat=True)
        responses.get(
            url=harness_config.log_urls["aer"]["getFileNames"],
            json={"fileNames": ["Reception.log"]},
        )
        responses.post(
            url=harness_config.log_urls["aer"]["getFile"],
            body=b"test log",
        )
        responses.get(
            url=harness_config.log_urls["ver"]["getFileNames"],
            json={"fileNames": ["Verifier.log"]},
        )
        responses.post(
            url=harness_config.log_urls["ver"]["getFile"],
            body=b"test log",
        )
        with NamedTemporaryFile(suffix=".db") as db_file:
            os.environ["PV_RESULTS_DB_ADDRESS"] = f"sqlite:///{db_file.name}"
            test = PerformanceTest(
                test_file_generators=test_events,
                test_config=test_config,
                harness_config=harness_config,
                test_profile=profile,
            )
            asyncio.run(test.run_test())
            assert len(test.results) == 60
            assert (
                test.pv_file_inspector.file_names["aer"][0] == "Reception.log"
            )
            assert (
                test.pv_file_inspector.file_names["ver"][0] == "Verifier.log"
            )
            os.remove(
                os.path.join(harness_config.log_file_store, "Reception.log")
            )
            os.remove(
                os.path.join(harness_config.log_file_store, "Verifier.log")
            )


@responses.activate
def test_run_test_performance_profile_shard() -> None:
    """Tests :class:`PerformanceTests`.`run_tests` with the test timeout hit"""
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {
                "num_files_per_sec": 30,
                "total_jobs": 20,
                "shard": True,
            },
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    profile = Profile(
        pd.DataFrame([[0, 30], [1, 30], [2, 30]], columns=["Time", "Number"])
    )
    with aioresponses() as mock:
        mock.post(url=harness_config.pv_send_url, repeat=True)
        responses.get(
            url=harness_config.log_urls["aer"]["getFileNames"],
            json={"fileNames": ["Reception.log"]},
        )
        responses.post(
            url=harness_config.log_urls["aer"]["getFile"],
            body=b"test log",
        )
        responses.get(
            url=harness_config.log_urls["ver"]["getFileNames"],
            json={"fileNames": ["Verifier.log"]},
        )
        responses.post(
            url=harness_config.log_urls["ver"]["getFile"],
            body=b"test log",
        )
        with NamedTemporaryFile(suffix=".db") as db_file:
            os.environ["PV_RESULTS_DB_ADDRESS"] = f"sqlite:///{db_file.name}"
            test = PerformanceTest(
                test_file_generators=test_events,
                test_config=test_config,
                harness_config=harness_config,
                test_profile=profile,
            )
            asyncio.run(test.run_test())
            assert len(test.results) == 60
            assert (
                test.pv_file_inspector.file_names["aer"][0] == "Reception.log"
            )
            assert (
                test.pv_file_inspector.file_names["ver"][0] == "Verifier.log"
            )
            os.remove(
                os.path.join(harness_config.log_file_store, "Reception.log")
            )
            os.remove(
                os.path.join(harness_config.log_file_store, "Verifier.log")
            )


@responses.activate
def test_run_test_performance_stop_test(
    caplog: pytest.LogCaptureFixture
) -> None:
    """Tests :class:`PerformanceTests`.`run_tests`"""
    harness_config = HarnessConfig(test_config_path)
    # make stop test timeout 1 second
    harness_config.pv_test_timeout = 1
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 30, "total_jobs": 20},
        }
    )
    test_events = generate_test_events_from_puml_files(
        [test_file_path], test_config=test_config
    )
    caplog.set_level(logging.INFO)
    with aioresponses() as mock:
        mock.post(url=harness_config.pv_send_url, repeat=True)
        responses.get(
            url=harness_config.log_urls["aer"]["getFileNames"],
            json={"fileNames": ["Reception.log"]},
        )
        responses.post(
            url=harness_config.log_urls["aer"]["getFile"],
            body=b"test log",
        )
        responses.get(
            url=harness_config.log_urls["ver"]["getFileNames"],
            json={"fileNames": ["Verifier.log"]},
        )
        responses.post(
            url=harness_config.log_urls["ver"]["getFile"],
            body=b"test log",
        )
        with NamedTemporaryFile(suffix=".db") as db_file:
            os.environ["PV_RESULTS_DB_ADDRESS"] = f"sqlite:///{db_file.name}"
            test = PerformanceTest(
                test_file_generators=test_events,
                test_config=test_config,
                harness_config=harness_config,
            )
            asyncio.run(test.run_test())
        assert (
            "Protocol Verifier failed to finish within the test timeout of "
            f"{harness_config.pv_test_timeout} seconds.\nResults will "
            "be calculated at this point"
        ) in caplog.text
        clean_directories(
            [
                harness_config.report_file_store,
                harness_config.log_file_store
            ]
        )
