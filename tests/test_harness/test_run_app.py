"""Tests for `test_harness.run_app` module
"""
from pathlib import Path
import os
from threading import Thread
import shutil
import time
import json
from io import BytesIO
from typing import Literal

from aioresponses import aioresponses, CallbackResult
import responses
import requests
import aiohttp

from test_harness.run_app import run_harness_app
from test_harness.config.config import HarnessConfig
from test_harness.requests.send_config import post_config_form_upload

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


def run_performance_test_requests(
    results_capture: dict,
    job_def_wait_time: int,
    length_of_post_send_wait_time: int
):
    """Function to run performance test using requests
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
            "TestConfig": {
                "type": "Performance",
                "performance_options": {
                    "num_files_per_sec": 10,
                    "shard": True,
                    "total_jobs": 50
                }
            }
        }
    )
    response = requests.get(
        url="http://localhost:8800/isTestRunning"
    )
    results_capture["second_is_running_check"] = response.json()
    results_capture["intermediate_is_running_check"] = []
    time.sleep(job_def_wait_time + 1)
    for _ in range(round((50 * 2) / 10)):
        response = requests.get(
            url="http://localhost:8800/isTestRunning"
        )
        results_capture["intermediate_is_running_check"].append(
            response.json()
        )
        time.sleep(1)
    response = requests.get(
        url="http://localhost:8800/isTestRunning"
    )
    time.sleep(length_of_post_send_wait_time + 5)
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
    shutil.copy(test_file_path, harness_config.uml_file_store)
    reception_file = []

    def call_back(url, **kwargs) -> CallbackResult:
        """
        Callback function that extracts the event payload from the
        multipart data and appends it to the reception file.

        Args:
            url (str): The URL to call back to.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            CallbackResult: The result of the callback.
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
    with aioresponses() as mock:
        responses.get(
            url=harness_config.pv_clean_folders_url
        )
        responses.post(
            url=harness_config.pv_send_job_defs_url
        )
        mock.post(
            url=harness_config.pv_send_url,
            repeat=True,
            callback=call_back
        )
        responses.get(
            url=harness_config.log_urls["aer"]["getFileNames"],
            json={
                "fileNames": ["Reception.log"]
            },
        )
        responses.add_callback(
            responses.POST,
            url=harness_config.log_urls["aer"]["getFile"],
            callback=reception_log_call_back
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
        response_results = {}
        thread_1 = Thread(
            target=run_harness_app,
            args=(
                test_config_path,
            ),
            daemon=True
        )
        thread_2 = Thread(
            target=run_performance_test_requests,
            args=(
                response_results,
                harness_config.pv_config_update_time,
                harness_config.pv_finish_interval
            )
        )
        thread_1.start()
        time.sleep(5)
        thread_2.start()
        thread_2.join()
        print("here")
