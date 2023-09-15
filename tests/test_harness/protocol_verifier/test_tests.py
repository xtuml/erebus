# pylint: disable=W0613
# pylint: disable=R0801
# pylint: disable=C2801
"""Tests for tests.py
"""
from pathlib import Path
import os
import asyncio
import glob

import responses
from aioresponses import aioresponses
import pandas as pd
import pytest

from test_harness.config.config import TestConfig, HarnessConfig
from test_harness.protocol_verifier.tests import (
    PerformanceTest,
    FunctionalTest,
    PVResultsHandler,
    Results
)
from test_harness.protocol_verifier.generate_test_files import (
    generate_test_events_from_puml_files
)
from test_harness.simulator.simulator_profile import Profile

# get test config
test_config_path = os.path.join(
    Path(__file__).parent.parent,
    "config/test_config.config"
)

# get path of tests uml file
test_file_path = os.path.join(
    Path(__file__).parent.parent / "test_files",
    "test_uml_job_def.puml"
)


class TestPVResultsHandler:
    """Group of tests for :class:`PVResultsHandler`
    """
    @staticmethod
    def test___enter__() -> None:
        """Tests :class:`PVResultsHandler`.`__enter__`
        """
        harness_config = HarnessConfig(test_config_path)
        results = Results()
        results_handler = PVResultsHandler(
            results,
            harness_config.report_file_store
        )
        results_handler.__enter__()
        assert results_handler.daemon_thread.is_alive()

    @staticmethod
    def test___exit__() -> None:
        """Tests :class:`PVResultsHandler`.`__exit__`
        """
        harness_config = HarnessConfig(test_config_path)
        results = Results()
        results_handler = PVResultsHandler(
            results,
            harness_config.report_file_store
        )
        results_handler.__enter__()
        results_handler.__exit__(None, None, None)
        assert not results_handler.daemon_not_done
        assert not results_handler.daemon_thread.is_alive()

    @staticmethod
    def test___exit___error() -> None:
        """Tests :class:`PVResultsHandler`.`__exit__` when an error is thrown
        """
        harness_config = HarnessConfig(test_config_path)
        results = Results()
        results_handler = PVResultsHandler(
            results,
            harness_config.report_file_store
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
        results = Results()
        with pytest.raises(RuntimeError) as e_info:
            with PVResultsHandler(
                results,
                harness_config.report_file_store
            ):
                raise RuntimeError("An error")
        assert e_info.value.args[0] == "An error"

    @staticmethod
    def test_handle_result() -> None:
        """Tests :class:`PVResultsHandler`.`handle_result`
        """
        harness_config = HarnessConfig(test_config_path)
        results = Results()
        results_handler = PVResultsHandler(
            results,
            harness_config.report_file_store
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
        results = Results()
        results_handler = PVResultsHandler(
            results,
            harness_config.report_file_store
        )
        job_info = {
            "info": "some_info"
        }
        named_items = [
            "a_file_name",
            "jobId",
            job_info,
            ""
        ]
        attributes = [
            "file_names",
            "job_ids",
            "jobs_info",
            "responses",
        ]
        result_item = ([{}],) + tuple(named_items)
        results_handler.handle_item_from_queue(result_item)
        for attr_name, item in zip(
            attributes,
            named_items
        ):
            attr = getattr(results, attr_name)
            assert len(attr) == 1
            assert attr[0] == item

    @staticmethod
    def test_handle_item_from_queue_with_save() -> None:
        """Tests :class:`PVResultsHandler`.`handle_item_from_queue`
        with save
        """
        harness_config = HarnessConfig(test_config_path)
        results = Results()
        results_handler = PVResultsHandler(
            results,
            harness_config.report_file_store,
            save_files=True
        )
        job_info = {
            "info": "some_info"
        }
        named_items = [
            "a_file_name",
            "jobId",
            job_info,
            ""
        ]
        attributes = [
            "file_names",
            "job_ids",
            "jobs_info",
            "responses",
        ]
        result_item = ([{}],) + tuple(named_items)
        results_handler.handle_item_from_queue(result_item)
        for attr_name, item in zip(
            attributes,
            named_items
        ):
            attr = getattr(results, attr_name)
            assert len(attr) == 1
            assert attr[0] == item
        files_to_remove = ["a_file_name"]
        for file_name in files_to_remove:
            path = os.path.join(harness_config.report_file_store, file_name)
            assert os.path.exists(path)
            os.remove(
                path
            )
        assert not glob.glob(
            "*.*", root_dir=harness_config.report_file_store
        )


def test_send_test_files_functional() -> None:
    """Tests :class:`FunctionalTest`.`send_test_files`
    """
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_config.parse_from_dict({
        "event_gen_options": {
            "invalid": False
        }
    })
    test_events = generate_test_events_from_puml_files(
        [test_file_path],
        test_config=test_config
    )
    with aioresponses() as mock:
        mock.post(
            url=harness_config.pv_send_url
        )
        test = FunctionalTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
        )
        with PVResultsHandler(
            test.results,
            test.test_output_directory,
            test.save_files
        ) as pv_results_handler:
            asyncio.run(test.send_test_files(pv_results_handler))
        assert len(test.results.responses) == 1


@responses.activate
def test_run_test_functional() -> None:
    """Tests :class:`FunctionalTest`.`run_test`
    """
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_config.parse_from_dict({
        "event_gen_options": {
            "invalid": False
        }
    })
    test_events = generate_test_events_from_puml_files(
        [test_file_path],
        test_config=test_config
    )
    with aioresponses() as mock:
        mock.post(
            url=harness_config.pv_send_url
        )
        responses.get(
            url=harness_config.log_urls["aer"]["getFileNames"],
            json={
                "fileNames": ["Reception.log"]
            },
        )
        responses.post(
            url=harness_config.log_urls["aer"]["getFile"],
            body=b'test log',
        )
        responses.get(
            url=harness_config.log_urls["ver"]["getFileNames"],
            json={
                "fileNames": ["Verifier.log"]
            },
        )
        responses.post(
            url=harness_config.log_urls["ver"]["getFile"],
            body=b'test log',
        )
        mock.get(
            url=harness_config.io_urls["aer"],
            payload={
                "num_files": 2,
                "t": 1
            },
            repeat=True
        )
        mock.get(
            url=harness_config.io_urls["ver"],
            payload={
                "num_files": 2,
                "t": 1
            },
            repeat=True
        )
        test = FunctionalTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config
        )
        asyncio.run(test.run_test())
        assert len(test.results.responses) == 1
        assert test.pv_file_inspector.file_names["aer"][0] == "Reception.log"
        assert test.pv_file_inspector.file_names["ver"][0] == "Verifier.log"
        assert all(
            coord == (1, 2)
            for coord in test.pv_file_inspector.coords["aer"]
        )
        assert all(
            coord == (1, 2)
            for coord in test.pv_file_inspector.coords["ver"]
        )
        os.remove(os.path.join(harness_config.log_file_store, "Reception.log"))
        os.remove(os.path.join(harness_config.log_file_store, "Verifier.log"))


@responses.activate
def test_calc_results_functional():
    """Tests :class:`FunctionalTest`.`calc_results`
    """
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_events = generate_test_events_from_puml_files(
        [test_file_path],
        test_config=test_config
    )
    with aioresponses() as mock:
        mock.post(
            url=harness_config.pv_send_url,
            repeat=True
        )
        responses.get(
            url=harness_config.log_urls["aer"]["getFileNames"],
            json={
                "fileNames": ["Reception.log"]
            },
        )
        responses.post(
            url=harness_config.log_urls["aer"]["getFile"],
            body=b'test log',
        )
        responses.get(
            url=harness_config.log_urls["ver"]["getFileNames"],
            json={
                "fileNames": ["Verifier.log"]
            },
        )
        responses.post(
            url=harness_config.log_urls["ver"]["getFile"],
            body=b'test log',
        )
        mock.get(
            url=harness_config.io_urls["aer"],
            payload={
                "num_files": 2,
                "t": 1
            },
            repeat=True
        )
        mock.get(
            url=harness_config.io_urls["ver"],
            payload={
                "num_files": 2,
                "t": 1
            },
            repeat=True
        )
        test = FunctionalTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
            test_output_directory=harness_config.report_file_store
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
    """Tests :class:`PerformanceTests`.`send_test_files`
    """
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_config.parse_from_dict({
        "event_gen_options": {
            "invalid": False
        },
        "performance_options": {
            "num_files_per_sec": 30,
            "total_jobs": 20
        }
    })
    test_events = generate_test_events_from_puml_files(
        [test_file_path],
        test_config=test_config
    )
    with aioresponses() as mock:
        mock.post(
            url=harness_config.pv_send_url,
            repeat=True
        )
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
            test_output_directory=harness_config.report_file_store
        )

        with PVResultsHandler(
            test.results,
            test.test_output_directory,
            test.save_files
        ) as pv_results_handler:
            asyncio.run(test.send_test_files(pv_results_handler))
        assert len(test.results.responses) == 20
        for job_info in test.results.jobs_info:
            assert job_info["SequenceName"] == "test_uml"
            assert job_info["Category"] == "ValidSols"
            assert job_info["Validity"]


@responses.activate
def test_run_test_performance() -> None:
    """Tests :class:`PerformanceTests`.`run_tests`
    """
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_config.parse_from_dict({
        "event_gen_options": {
            "invalid": False
        },
        "performance_options": {
            "num_files_per_sec": 30,
            "total_jobs": 20
        }
    })
    test_events = generate_test_events_from_puml_files(
        [test_file_path],
        test_config=test_config
    )
    with aioresponses() as mock:
        mock.post(
            url=harness_config.pv_send_url,
            repeat=True
        )
        responses.get(
            url=harness_config.log_urls["aer"]["getFileNames"],
            json={
                "fileNames": ["Reception.log"]
            },
        )
        responses.post(
            url=harness_config.log_urls["aer"]["getFile"],
            body=b'test log',
        )
        responses.get(
            url=harness_config.log_urls["ver"]["getFileNames"],
            json={
                "fileNames": ["Verifier.log"]
            },
        )
        responses.post(
            url=harness_config.log_urls["ver"]["getFile"],
            body=b'test log',
        )
        mock.get(
            url=harness_config.io_urls["aer"],
            payload={
                "num_files": 2,
                "t": 1
            },
            repeat=True
        )
        mock.get(
            url=harness_config.io_urls["ver"],
            payload={
                "num_files": 2,
                "t": 1
            },
            repeat=True
        )
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
        )
        asyncio.run(test.run_test())
        assert len(test.results.responses) == 20
        assert test.pv_file_inspector.file_names["aer"][0] == "Reception.log"
        assert test.pv_file_inspector.file_names["ver"][0] == "Verifier.log"
        assert all(
            coord == (1, 2)
            for coord in test.pv_file_inspector.coords["aer"]
        )
        assert all(
            coord == (1, 2)
            for coord in test.pv_file_inspector.coords["ver"]
        )
        os.remove(os.path.join(harness_config.log_file_store, "Reception.log"))
        os.remove(os.path.join(harness_config.log_file_store, "Verifier.log"))


@responses.activate
def test_run_test_performance_calc_results() -> None:
    """Tests :class:`PerformanceTests`.`calc_results`
    """
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_config.parse_from_dict({
        "event_gen_options": {
            "invalid": False
        },
        "performance_options": {
            "num_files_per_sec": 30,
            "total_jobs": 20
        }
    })
    test_events = generate_test_events_from_puml_files(
        [test_file_path],
        test_config=test_config
    )
    with aioresponses() as mock:
        mock.post(
            url=harness_config.pv_send_url,
            repeat=True
        )
        responses.get(
            url=harness_config.log_urls["aer"]["getFileNames"],
            json={
                "fileNames": ["Reception.log"]
            },
        )
        responses.post(
            url=harness_config.log_urls["aer"]["getFile"],
            body=b'test log',
        )
        responses.get(
            url=harness_config.log_urls["ver"]["getFileNames"],
            json={
                "fileNames": ["Verifier.log"]
            },
        )
        responses.post(
            url=harness_config.log_urls["ver"]["getFile"],
            body=b'test log',
        )
        payload_aer = {
                "num_files": 2,
                "t": 0
            }
        payload_ver = {
                "num_files": 0,
                "t": 0
            }

        def callback_aer(*args, **kwargs) -> None:
            if payload_ver["num_files"] == 20:
                payload_aer["num_files"] = 0
            payload_aer["t"] += 1

        def callback_ver(url, **kwargs) -> None:
            if payload_ver["num_files"] < 20 and payload_ver["t"] > 0:
                payload_ver["num_files"] += 10
            payload_ver["t"] += 1

        mock.get(
            url=harness_config.io_urls["aer"],
            payload=payload_aer,
            repeat=True,
            callback=callback_aer
        )
        mock.get(
            url=harness_config.io_urls["ver"],
            payload=payload_ver,
            repeat=True,
            callback=callback_ver
        )
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
            test_output_directory=harness_config.report_file_store
        )
        asyncio.run(test.run_test())
        test.calc_results()
        os.remove(os.path.join(harness_config.log_file_store, "Reception.log"))
        os.remove(os.path.join(harness_config.log_file_store, "Verifier.log"))
        for file_name in [
            "Basic_Stats.csv",
            "PV_File_IO.csv",
            "PV_File_IO.html"
        ]:
            os.remove(
                os.path.join(harness_config.report_file_store, file_name)
            )


@responses.activate
def test_run_test_performance_profile_job_batch() -> None:
    """Tests :class:`PerformanceTests`.`run_tests`
    """
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_config.parse_from_dict({
        "event_gen_options": {
            "invalid": False
        },
        "performance_options": {
            "num_files_per_sec": 30,
            "total_jobs": 20
        }
    })
    test_events = generate_test_events_from_puml_files(
        [test_file_path],
        test_config=test_config
    )
    profile = Profile(pd.DataFrame(
            [
                [0, 30],
                [1, 30],
                [2, 30]
            ],
            columns=["Time", "Number"]
        )
    )
    with aioresponses() as mock:
        mock.post(
            url=harness_config.pv_send_url,
            repeat=True
        )
        responses.get(
            url=harness_config.log_urls["aer"]["getFileNames"],
            json={
                "fileNames": ["Reception.log"]
            },
        )
        responses.post(
            url=harness_config.log_urls["aer"]["getFile"],
            body=b'test log',
        )
        responses.get(
            url=harness_config.log_urls["ver"]["getFileNames"],
            json={
                "fileNames": ["Verifier.log"]
            },
        )
        responses.post(
            url=harness_config.log_urls["ver"]["getFile"],
            body=b'test log',
        )
        mock.get(
            url=harness_config.io_urls["aer"],
            payload={
                "num_files": 2,
                "t": 1
            },
            repeat=True
        )
        mock.get(
            url=harness_config.io_urls["ver"],
            payload={
                "num_files": 2,
                "t": 1
            },
            repeat=True
        )
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
            test_profile=profile
        )
        asyncio.run(test.run_test())
        assert len(test.results.responses) == 20
        assert test.pv_file_inspector.file_names["aer"][0] == "Reception.log"
        assert test.pv_file_inspector.file_names["ver"][0] == "Verifier.log"
        assert all(
            coord == (1, 2)
            for coord in test.pv_file_inspector.coords["aer"]
        )
        assert all(
            coord == (1, 2)
            for coord in test.pv_file_inspector.coords["ver"]
        )
        os.remove(os.path.join(harness_config.log_file_store, "Reception.log"))
        os.remove(os.path.join(harness_config.log_file_store, "Verifier.log"))


@responses.activate
def test_run_test_performance_profile_shard() -> None:
    """Tests :class:`PerformanceTests`.`run_tests`
    """
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_config.parse_from_dict({
        "event_gen_options": {
            "invalid": False
        },
        "performance_options": {
            "num_files_per_sec": 30,
            "total_jobs": 20,
            "shard": True
        }
    })
    test_events = generate_test_events_from_puml_files(
        [test_file_path],
        test_config=test_config
    )
    profile = Profile(pd.DataFrame(
            [
                [0, 30],
                [1, 30],
                [2, 30]
            ],
            columns=["Time", "Number"]
        )
    )
    with aioresponses() as mock:
        mock.post(
            url=harness_config.pv_send_url,
            repeat=True
        )
        responses.get(
            url=harness_config.log_urls["aer"]["getFileNames"],
            json={
                "fileNames": ["Reception.log"]
            },
        )
        responses.post(
            url=harness_config.log_urls["aer"]["getFile"],
            body=b'test log',
        )
        responses.get(
            url=harness_config.log_urls["ver"]["getFileNames"],
            json={
                "fileNames": ["Verifier.log"]
            },
        )
        responses.post(
            url=harness_config.log_urls["ver"]["getFile"],
            body=b'test log',
        )
        mock.get(
            url=harness_config.io_urls["aer"],
            payload={
                "num_files": 2,
                "t": 1
            },
            repeat=True
        )
        mock.get(
            url=harness_config.io_urls["ver"],
            payload={
                "num_files": 2,
                "t": 1
            },
            repeat=True
        )
        test = PerformanceTest(
            test_file_generators=test_events,
            test_config=test_config,
            harness_config=harness_config,
            test_profile=profile
        )
        asyncio.run(test.run_test())
        assert len(test.results.responses) == 60
        assert test.pv_file_inspector.file_names["aer"][0] == "Reception.log"
        assert test.pv_file_inspector.file_names["ver"][0] == "Verifier.log"
        assert all(
            coord == (1, 2)
            for coord in test.pv_file_inspector.coords["aer"]
        )
        assert all(
            coord == (1, 2)
            for coord in test.pv_file_inspector.coords["ver"]
        )
        os.remove(os.path.join(harness_config.log_file_store, "Reception.log"))
        os.remove(os.path.join(harness_config.log_file_store, "Verifier.log"))
