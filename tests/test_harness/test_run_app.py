"""Tests for `test_harness.run_app` module
"""
from pathlib import Path
import os
from threading import Thread
import time
import json
from io import BytesIO
from typing import Literal, Any
import glob
import re
from multiprocessing import Manager, Process

from aioresponses import CallbackResult
import responses
import requests
import aiohttp
import pandas as pd

from test_harness.run_app import run_harness_app
from test_harness.config.config import HarnessConfig, TestConfig
from test_harness.requests_th.send_config import post_config_form_upload
from test_harness.utils import (
    clean_directories, check_dict_equivalency
)
from test_harness.protocol_verifier.tests.mock_pv_http_interface \
      import mock_pv_http_interface
# get test config
test_config_path = os.path.join(
    Path(__file__).parent,
    "config/run_app_test.config"
)

# get path of tests uml file
test_file_path = os.path.join(
    Path(__file__).parent / "test_files",
    "test_uml_1.puml"
)

# get path of test zip file
test_file_zip_path = os.path.join(
    Path(__file__).parent / "test_files",
    "test_zip_file.zip"
)

uuid4hex = re.compile(
            '[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}\\Z', re.I
        )


def run_performance_test_requests(
    results_capture: dict,
    job_def_wait_time: int,
    length_of_post_send_wait_time: int,
    test_config: dict[str, Any]
) -> None:
    """Function to run performance test using requests

    :param results_capture: The dictionary to capture results
    :type results_capture: `dict`
    :param job_def_wait_time: The time to wait for job defs to be sent
    :type job_def_wait_time: `int`
    :param length_of_post_send_wait_time: The time to wait after sending
    performance test requests
    :type length_of_post_send_wait_time: `int`
    :param test_config: The test config
    :type test_config: `dict`[`str`, `Any`]
    """
    response = requests.get(
        url="http://localhost:8800/isTestRunning"
    )
    results_capture["first_is_running_check"] = response.json()
    post_config_form_upload(
        file_bytes_file_names=[
            (open(test_file_path, 'rb'), "test_uml_1.puml")
        ],
        url="http://localhost:8800/uploadUML"
    )
    requests.post(
        url="http://localhost:8800/startTest",
        json={
            "TestName": "PerformanceTest",
            "TestConfig": test_config
        }
    )
    time.sleep(1)
    response = requests.get(
        url="http://localhost:8800/isTestRunning"
    )
    results_capture["second_is_running_check"] = response.json()
    results_capture["intermediate_is_running_check"] = []
    time.sleep(job_def_wait_time)
    for _ in range(round((50 * 2) / 10)):
        time.sleep(1)
        response = requests.get(
            url="http://localhost:8800/isTestRunning"
        )
        results_capture["intermediate_is_running_check"].append(
            response.json()
        )
    time.sleep(length_of_post_send_wait_time + 5)
    response = requests.get(
        url="http://localhost:8800/isTestRunning"
    )
    results_capture["final_is_running_check"] = response.json()


@responses.activate
def test_run_harness_app() -> None:
    """Test the `run_harness_app` function.

    This function sets up a test environment for the `run_harness_app`
    function, which is responsible for running a performance testing harness.
    The test environment includes a mock server that simulates the performance
    testing requests, and a callback function that logs the events received by
    the server. The function then starts two threads: one that runs the
    `run_harness_app` function, and another that sends performance testing
    requests to the mock server. The function waits for the second thread to
    finish, and then prints a message to indicate that the test is complete.

    Raises:
        AssertionError: If the test fails.
    """
    harness_config = HarnessConfig(test_config_path)
    manager = Manager()
    reception_file = manager.list()

    def call_back(url, **kwargs) -> CallbackResult:
        """
        Callback function that extracts the event payload from the
        multipart data and appends it to the reception file.

        :param url: The URL to call back to.
        :type url: `str`
        :param **kwargs: Arbitrary keyword arguments.
        :type **kwargs: `dict`
        :return: Returns a callback result
        :rtype: `CallbackResult`
        """
        data: aiohttp.multipart.MultipartWriter = kwargs["data"]
        io_data: BytesIO = data._parts[0][0]._value
        json_payload_list = json.load(io_data)
        event_payload = json_payload_list[0]
        reception_file.append(
            f"reception_event_valid : EventId = {event_payload['eventId']}"
        )

        return CallbackResult(
            status=200,
        )

    def reception_log_call_back(
        *args, **kwargs
    ) -> tuple[Literal[200], dict, bytes]:
        return (
            200,
            {},
            "\n".join(reception_file).encode("utf-8")
        )
    responses.add_passthru("http://localhost:8800")
    with mock_pv_http_interface(
        harness_config, call_back, reception_log_call_back
    ):
        response_results = {}
        thread_1 = Process(
            target=run_harness_app,
            args=(
                test_config_path,
            ),
        )
        thread_2 = Thread(
            target=run_performance_test_requests,
            args=(
                response_results,
                harness_config.pv_config_update_time,
                harness_config.pv_finish_interval,
                {
                    "type": "Performance",
                    "performance_options": {
                        "num_files_per_sec": 10,
                        "shard": True,
                        "total_jobs": 50
                    },
                    "event_gen_options": {
                        "invalid": False,
                    }
                }
            )
        )
        thread_1.start()
        time.sleep(5)
        thread_2.start()
        thread_2.join()
        thread_1.terminate()
        assert not response_results["first_is_running_check"]["running"]
        assert response_results["second_is_running_check"]["running"]
        assert float(
            response_results[
                "second_is_running_check"
            ]["details"]["percent_done"]
        ) == 0
        assert not response_results["final_is_running_check"]["running"]
    data = pd.read_csv(
        os.path.join(
            harness_config.report_file_store,
            "PerformanceTest",
            "AggregatedResults.csv"
        )
    )
    assert data["Cumulative Events Sent"].iloc[-1] == 100
    clean_directories([
        harness_config.report_file_store,
        harness_config.uml_file_store
    ])


def run_performance_test_requests_zip_file_upload(
    results_capture: dict,
) -> None:
    """Function to run performance test using requests for uploaded
    zip file functionality

    :param results_capture: The dictionary to capture results
    :type results_capture: `dict`
    """
    # this will post the file under the name "upload"
    response = post_config_form_upload(
        file_bytes_file_names=[
            (open(test_file_zip_path, 'rb'), "test_zip_file.zip")
        ],
        url="http://localhost:8800/upload/named-zip-files"
    )[2]
    results_capture["upload zip response status"] = response.status_code
    time.sleep(2)
    response = requests.post(
        url="http://localhost:8800/startTest",
        json={
            "TestName": "upload",
        }
    )
    results_capture["start test json"] = response.json()
    time.sleep(2)
    while True:
        response = requests.get(
            url="http://localhost:8800/isTestRunning"
        )
        if not response.json()["running"]:
            break
        time.sleep(1)


@responses.activate
def test_run_harness_app_uploaded_zip_file() -> None:
    """Test the `run_harness_app` function.

    This function sets up a test environment for the `run_harness_app`
    function, which is responsible for running a performance testing harness.
    The test environment includes a mock server that simulates the performance
    testing requests, and a callback function that logs the events received by
    the server. The function then starts two threads: one that runs the
    `run_harness_app` function, and another that sends performance testing
    requests to the mock server. The function waits for the second thread to
    finish, and then prints a message to indicate that the test is complete.

    This is a test fro specifically checking that an uploaded zip file can
    start a performance test

    Raises:
        AssertionError: If the test fails.
    """
    harness_config = HarnessConfig(test_config_path)
    manager = Manager()
    reception_file = manager.list()

    def call_back(url, **kwargs) -> CallbackResult:
        """
        Callback function that extracts the event payload from the
        multipart data and appends it to the reception file.

        :param url: The URL to call back to.
        :type url: `str`
        :param **kwargs: Arbitrary keyword arguments.
        :type **kwargs: `dict`
        :return: Returns a callback result
        :rtype: `CallbackResult`
        """
        data: aiohttp.multipart.MultipartWriter = kwargs["data"]
        io_data: BytesIO = data._parts[0][0]._value
        json_payload_list = json.load(io_data)
        event_payload = json_payload_list[0]
        reception_file.append(
            f"reception_event_valid : EventId = {event_payload['eventId']}"
        )

        return CallbackResult(
            status=200,
        )

    def reception_log_call_back(
        *args, **kwargs
    ) -> tuple[Literal[200], dict, bytes]:
        return (
            200,
            {},
            "\n".join(reception_file).encode("utf-8")
        )
    responses.add_passthru("http://localhost:8800")
    with mock_pv_http_interface(
        harness_config, call_back, reception_log_call_back
    ):
        response_results = {}
        thread_1 = Process(
            target=run_harness_app,
            args=(
                test_config_path,
            ),
        )
        thread_2 = Thread(
            target=run_performance_test_requests_zip_file_upload,
            args=(
                response_results,
            )
        )
        thread_1.start()
        time.sleep(5)
        thread_2.start()
        thread_2.join()
        thread_1.terminate()
    assert response_results["upload zip response status"] == 200
    start_test_json = response_results["start test json"]
    actual_test_config_dict = start_test_json["TestConfig"]
    actual_output_folder_string = start_test_json["TestOutputFolder"]
    test_output_path = os.path.join(
        harness_config.report_file_store,
        "upload"
    )
    assert actual_output_folder_string == (
        f"Tests under name upload in the directory"
        f"{test_output_path}"
    )
    for folder, file in zip(
        ["uml_file_store", "test_file_store", "profile_store"],
        ["test_uml_1.puml", "test_uml_1_events.json", "test_profile.csv"]
    ):
        path = os.path.join(test_output_path, folder, file)
        assert os.path.exists(path)
    assert os.path.exists(
        os.path.join(test_output_path, "test_config.yaml")
    )
    expected_test_config = TestConfig()
    expected_test_config.parse_from_yaml(
        os.path.join(test_output_path, "test_config.yaml")
    )
    expected_test_config_dict = expected_test_config.config_to_dict()
    check_dict_equivalency(
        actual_test_config_dict,
        expected_test_config_dict
    )
    files = glob.glob("*.*", root_dir=test_output_path)
    expected_files = [
        "CumulativeEventsSentVSProcessed.html",
        "Verifier.log",
        "Reception.log",
        "Report.xml",
        "Report.html",
        "EventsSentVSProcessed.html",
        "ResponseAndQueueTime.html",
        "AggregatedResults.csv",
        "ProcessingErrors.html",
        "AggregatedErrors.csv",
        "used_config.yaml",
        "test_config.yaml",
    ]
    data = pd.read_csv(
        os.path.join(
            test_output_path,
            "AggregatedResults.csv"
        )
    )
    assert data["Cumulative Events Sent"].iloc[-1] == 76
    # load in json file from test output directory
    with open(
        os.path.join(
            test_output_path,
            "test_file_store",
            "test_uml_1_events.json"
        ),
        "r"
    ) as file:
        template_json_file = json.load(file)["job_file"]
    for file in files:
        file_in_files = file in expected_files
        is_uuid = bool(uuid4hex.match(
                file.replace("-", "").replace(".json", "")
            ))
        assert file_in_files ^ is_uuid
        if is_uuid:
            with open(
                os.path.join(
                    test_output_path,
                    file
                ),
                "r"
            ) as file:
                json_file = json.load(file)
            for temp_event, actual_event in zip(
                template_json_file,
                json_file
            ):
                assert temp_event["eventType"] == (
                    actual_event["eventType"]
                )
    clean_directories([
        harness_config.report_file_store,
        harness_config.uml_file_store
    ])


@responses.activate
def test_run_harness_app_2_workers() -> None:
    """Test the `run_harness_app` function.

    This function sets up a test environment for the `run_harness_app`
    function, which is responsible for running a performance testing harness.
    The test environment includes a mock server that simulates the performance
    testing requests, and a callback function that logs the events received by
    the server. The function then starts two threads: one that runs the
    `run_harness_app` function, and another that sends performance testing
    requests to the mock server. The function waits for the second thread to
    finish, and then prints a message to indicate that the test is complete.

    This test is to specifically test using more than 1 worker

    Raises:
        AssertionError: If the test fails.
    """
    harness_config = HarnessConfig(test_config_path)

    manager = Manager()
    reception_file = manager.list()

    def call_back(url, **kwargs) -> CallbackResult:
        """
        Callback function that extracts the event payload from the
        multipart data and appends it to the reception file.

        :param url: The URL to call back to.
        :type url: `str`
        :param **kwargs: Arbitrary keyword arguments.
        :type **kwargs: `dict`
        :return: Returns a callback result
        :rtype: `CallbackResult`
        """
        data: aiohttp.multipart.MultipartWriter = kwargs["data"]
        io_data: BytesIO = data._parts[0][0]._value
        json_payload_list = json.load(io_data)
        event_payload = json_payload_list[0]
        reception_file.append(
            f"reception_event_valid : EventId = {event_payload['eventId']}"
        )

        return CallbackResult(
            status=200,
        )

    def reception_log_call_back(
        *args, **kwargs
    ) -> tuple[Literal[200], dict, bytes]:
        return (
            200,
            {},
            "\n".join(reception_file).encode("utf-8")
        )
    responses.add_passthru("http://localhost:8800")
    with mock_pv_http_interface(
        harness_config, call_back, reception_log_call_back
    ):
        response_results = {}
        thread_1 = Process(
            target=run_harness_app,
            args=(
                test_config_path,
            ),
        )
        thread_2 = Thread(
            target=run_performance_test_requests,
            args=(
                response_results,
                harness_config.pv_config_update_time,
                harness_config.pv_finish_interval,
                {
                    "type": "Performance",
                    "performance_options": {
                        "num_files_per_sec": 10,
                        "shard": True,
                        "total_jobs": 50
                    },
                    "event_gen_options": {
                        "invalid": False,
                    },
                    "num_workers": 2
                }
            )
        )
        thread_1.start()
        time.sleep(5)
        thread_2.start()
        thread_2.join()
        thread_1.terminate()
        assert not response_results["first_is_running_check"]["running"]
        assert response_results["second_is_running_check"]["running"]
        assert float(
            response_results[
                "second_is_running_check"
            ]["details"]["percent_done"]
        ) == 0
        assert not response_results["final_is_running_check"]["running"]
    data = pd.read_csv(
        os.path.join(
            harness_config.report_file_store,
            "PerformanceTest",
            "AggregatedResults.csv"
        )
    )
    assert data["Cumulative Events Sent"].iloc[-1] == 100
    clean_directories([
        harness_config.report_file_store,
        harness_config.uml_file_store
    ])


@responses.activate
def test_run_harness_app_stop_test() -> None:
    """Test the `run_harness_app` function with a stop test request.

    This function sets up a test environment for the `run_harness_app`
    function, which is responsible for running a performance testing harness.
    The test environment includes a mock server that simulates the performance
    testing requests, and a callback function that logs the events received by
    the server. The function then starts two threads: one that runs the
    `run_harness_app` function, and another that sends performance testing
    requests to the mock server. The function waits for the second thread to
    finish, and then prints a message to indicate that the test is complete.

    Raises:
        AssertionError: If the test fails.
    """
    harness_config = HarnessConfig(test_config_path)
    manager = Manager()
    reception_file = manager.list()

    def call_back(url, **kwargs) -> CallbackResult:
        """
        Callback function that extracts the event payload from the
        multipart data and appends it to the reception file.

        :param url: The URL to call back to.
        :type url: `str`
        :param **kwargs: Arbitrary keyword arguments.
        :type **kwargs: `dict`
        :return: Returns a callback result
        :rtype: `CallbackResult`
        """
        data: aiohttp.multipart.MultipartWriter = kwargs["data"]
        io_data: BytesIO = data._parts[0][0]._value
        json_payload_list = json.load(io_data)
        event_payload = json_payload_list[0]
        reception_file.append(
            f"reception_event_valid : EventId = {event_payload['eventId']}"
        )

        return CallbackResult(
            status=200,
        )

    def reception_log_call_back(
        *args, **kwargs
    ) -> tuple[Literal[200], dict, bytes]:
        return (
            200,
            {},
            "\n".join(reception_file).encode("utf-8")
        )
    responses.add_passthru("http://localhost:8800")
    with mock_pv_http_interface(
        harness_config, call_back, reception_log_call_back
    ):
        response_results = {}
        thread_1 = Process(
            target=run_harness_app,
            args=(
                test_config_path,
            ),
        )
        thread_2 = Thread(
            target=run_performance_test_requests,
            args=(
                response_results,
                harness_config.pv_config_update_time,
                harness_config.pv_finish_interval,
                {
                    "type": "Performance",
                    "performance_options": {
                        "num_files_per_sec": 10,
                        "shard": True,
                        "total_jobs": 50
                    },
                    "event_gen_options": {
                        "invalid": False,
                    }
                }
            )
        )
        thread_1.start()
        time.sleep(5)
        thread_2.start()
        time.sleep(2)
        requests.post(
            url="http://localhost:8800/stopTest",
            json={}
        )
        thread_2.join()
        thread_1.terminate()
    data = pd.read_csv(
        os.path.join(
            harness_config.report_file_store,
            "PerformanceTest",
            "AggregatedResults.csv"
        )
    )
    assert data["Cumulative Events Sent"].iloc[-1] > 0
    assert data["Cumulative Events Sent"].iloc[-1] < 100
    clean_directories([
        harness_config.report_file_store,
        harness_config.uml_file_store
    ])


@responses.activate
def test_run_harness_app_2_workers_stop_test() -> None:
    """Test the `run_harness_app` function with two workers and stopping a
    test before it should end

    This function sets up a test environment for the `run_harness_app`
    function, which is responsible for running a performance testing harness.
    The test environment includes a mock server that simulates the performance
    testing requests, and a callback function that logs the events received by
    the server. The function then starts two threads: one that runs the
    `run_harness_app` function, and another that sends performance testing
    requests to the mock server. The function waits for the second thread to
    finish, and then prints a message to indicate that the test is complete.

    This test is to specifically test using more than 1 worker

    Raises:
        AssertionError: If the test fails.
    """
    harness_config = HarnessConfig(test_config_path)

    manager = Manager()
    reception_file = manager.list()

    def call_back(url, **kwargs) -> CallbackResult:
        """
        Callback function that extracts the event payload from the
        multipart data and appends it to the reception file.

        :param url: The URL to call back to.
        :type url: `str`
        :param **kwargs: Arbitrary keyword arguments.
        :type **kwargs: `dict`
        :return: Returns a callback result
        :rtype: `CallbackResult`
        """
        data: aiohttp.multipart.MultipartWriter = kwargs["data"]
        io_data: BytesIO = data._parts[0][0]._value
        json_payload_list = json.load(io_data)
        event_payload = json_payload_list[0]
        reception_file.append(
            f"reception_event_valid : EventId = {event_payload['eventId']}"
        )

        return CallbackResult(
            status=200,
        )

    def reception_log_call_back(
        *args, **kwargs
    ) -> tuple[Literal[200], dict, bytes]:
        return (
            200,
            {},
            "\n".join(reception_file).encode("utf-8")
        )
    responses.add_passthru("http://localhost:8800")
    with mock_pv_http_interface(
        harness_config, call_back, reception_log_call_back
    ):
        response_results = {}
        thread_1 = Process(
            target=run_harness_app,
            args=(
                test_config_path,
            ),
        )
        thread_2 = Thread(
            target=run_performance_test_requests,
            args=(
                response_results,
                harness_config.pv_config_update_time,
                harness_config.pv_finish_interval,
                {
                    "type": "Performance",
                    "performance_options": {
                        "num_files_per_sec": 10,
                        "shard": True,
                        "total_jobs": 50
                    },
                    "event_gen_options": {
                        "invalid": False,
                    },
                    "num_workers": 2
                }
            )
        )
        thread_1.start()
        time.sleep(5)
        thread_2.start()
        time.sleep(2)
        requests.post(
            url="http://localhost:8800/stopTest",
            json={}
        )
        thread_2.join()
        thread_1.terminate()
    data = pd.read_csv(
        os.path.join(
            harness_config.report_file_store,
            "PerformanceTest",
            "AggregatedResults.csv"
        )
    )
    assert data["Cumulative Events Sent"].iloc[-1] > 0
    assert data["Cumulative Events Sent"].iloc[-1] < 100
    clean_directories([
        harness_config.report_file_store,
        harness_config.uml_file_store
    ])
