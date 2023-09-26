# pylint: disable=R0801
"""Tests for __init__.py
"""

from pathlib import Path
import os
import glob
import re
import shutil
import threading
import time
import json

import pytest
import responses
from aioresponses import aioresponses
import pandas as pd

from test_harness.config.config import TestConfig, HarnessConfig
from test_harness.protocol_verifier import (
    puml_files_test,
    get_test_profile,
    get_test_file_paths
)
from test_harness.protocol_verifier.generate_test_files import TestJobFile
from test_harness.utils import clean_directories
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

# get path of test csv file
test_csv_file_path_1 = os.path.join(
    Path(__file__).parent.parent / "test_files",
    "test_profile.csv"
)

# get path of test file
test_csv_file_path_2 = os.path.join(
    Path(__file__).parent.parent / "test_files",
    "test_profile_2.csv"
)

# get path of tests uml file
test_uml_1_path = os.path.join(
    Path(__file__).parent.parent / "test_files",
    "test_uml_1.puml"
)
# get paths of test event json files
test_uml_1_events = os.path.join(
    Path(__file__).parent.parent / "test_files",
    "test_uml_1_events.json"
)
test_uml_2_events = os.path.join(
    Path(__file__).parent.parent / "test_files",
    "test_uml_2_events.json"
)

uuid4hex = re.compile(
            '[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}\\Z', re.I
        )


@responses.activate
def test_puml_files_test() -> None:
    """Tests method `puml_test_files`
    """
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_config.parse_from_dict({
        "event_gen_options": {
            "invalid": False
        }
    })
    with aioresponses() as mock:
        responses.get(
            url=harness_config.pv_clean_folders_url
        )
        responses.post(
            url=harness_config.pv_send_job_defs_url
        )
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
        puml_files_test(
            puml_file_paths=[test_file_path],
            test_output_directory=harness_config.report_file_store,
            harness_config=harness_config,
            test_config=test_config
        )
        files = glob.glob("*.*", root_dir=harness_config.report_file_store)
        expected_files = [
            "Results.csv", "Results.html", "Results.xml",
            "Results_Aggregated.html",
            "Verifier.log", "Reception.log",
        ]
        for file in files:
            file_in_files = file in expected_files
            is_uuid = bool(uuid4hex.match(
                    file.replace("-", "").replace(".json", "")
                ))
            assert any([file_in_files, is_uuid])

        clean_directories([harness_config.report_file_store])


def test_get_test_profile_one_file() -> None:
    """Tests `get_test_profile` when one file is present in the folder
    """
    harness_config = HarnessConfig(test_config_path)
    # prepare data
    shutil.copy(
        test_csv_file_path_1,
        harness_config.profile_store
    )
    profile = get_test_profile(harness_config.profile_store)
    assert isinstance(profile, Profile)
    clean_directories([harness_config.profile_store])


def test_get_test_profile_two_files() -> None:
    """Tests `get_test_profile` when two files are present in the folder
    """
    harness_config = HarnessConfig(test_config_path)
    # prepare data
    shutil.copy(
        test_csv_file_path_1,
        harness_config.profile_store
    )
    shutil.copy(
        test_csv_file_path_2,
        harness_config.profile_store
    )
    with pytest.raises(RuntimeError) as e_info:
        get_test_profile(harness_config.profile_store)
    clean_directories([harness_config.profile_store])
    assert e_info.value.args[0] == (
        "Too many profiles were uploaded. Only one profile can be uploaded"
    )


def test_get_test_profile_no_file() -> None:
    """Tests `get_test_profile` when no files are present in the folder
    """
    harness_config = HarnessConfig(test_config_path)
    profile = get_test_profile(harness_config.profile_store)
    assert profile is None


@responses.activate
def test_puml_files_performance_with_input_profile(
    grok_exporter_string: str
) -> None:
    """Tests method `puml_test_files` for a performance test using a profile
    """
    harness_config = HarnessConfig(test_config_path)
    harness_config.pv_finish_interval = 8
    test_config = TestConfig()
    test_config.parse_from_dict({
        "type": "Performance",
        "event_gen_options": {
            "invalid": False
        }
    })
    payload = {
        "num_files": 0,
        "t": 0
    }

    def update_payload(end_time: int) -> None:
        sim_time = 0
        while sim_time < end_time:
            time.sleep(2)
            payload["num_files"] += 1
            payload["t"] += 1
            sim_time += 1

    with aioresponses() as mock:
        responses.add(
            responses.GET,
            harness_config.pv_grok_exporter_url,
            body=grok_exporter_string.encode("utf-8"),
            status=200,
            headers={
                "Content-Type": "text/plain; version=0.0.4; charset=utf-8"
            }
        )
        responses.get(
            url=harness_config.pv_clean_folders_url
        )
        responses.post(
            url=harness_config.pv_send_job_defs_url
        )
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
            payload=payload,
            repeat=True
        )
        mock.get(
            url=harness_config.io_urls["ver"],
            payload=payload,
            repeat=True
        )
        profile = Profile()
        profile.load_raw_profile_from_file_path(test_csv_file_path_1)
        thread = threading.Thread(target=update_payload, args=[3], daemon=True)
        thread.start()
        puml_files_test(
            puml_file_paths=[test_file_path],
            test_output_directory=harness_config.report_file_store,
            harness_config=harness_config,
            test_config=test_config,
            profile=profile
        )
        thread.join()
        files = glob.glob("*.*", root_dir=harness_config.report_file_store)
        expected_files = [
            "Verifier.log",
            "Reception.log",
            "grok.txt",
            "Report.xml",
            "Report.html",
            "EventsSentVSProcessed.html",
            "ResponseAndQueueTime.html",
            "AggregatedResults.csv"
        ]
        for file in files:
            file_in_files = file in expected_files
            is_uuid = bool(uuid4hex.match(
                    file.replace("-", "").replace(".json", "")
                ))
            assert file_in_files ^ is_uuid
        clean_directories(
            [
                harness_config.report_file_store,
                harness_config.log_file_store
            ]
        )


def test_get_test_file_paths_two_files() -> None:
    """Tests `get_test_file_paths` with two files in the directory
    """
    harness_config = HarnessConfig(test_config_path)
    shutil.copy(
        test_uml_1_events,
        harness_config.test_file_store
    )
    shutil.copy(
        test_uml_2_events,
        harness_config.test_file_store
    )
    test_file_paths = get_test_file_paths(
        harness_config.test_file_store
    )
    assert len(test_file_paths) == 2
    expected_paths = [
        os.path.join(
            harness_config.test_file_store,
            os.path.basename(path)
        )
        for path in [test_uml_1_events, test_uml_2_events]
    ]
    assert set(expected_paths) == set(test_file_paths)
    clean_directories([harness_config.test_file_store])


def test_get_test_file_paths_no_files() -> None:
    """Tests `get_test_file_paths` with no files in the directory
    """
    harness_config = HarnessConfig(test_config_path)
    test_file_paths = get_test_file_paths(
        harness_config.test_file_store
    )
    assert test_file_paths is None


@responses.activate
def test_puml_files_test_with_test_files_uploaded() -> None:
    """Tests method `puml_test_files` with test files uploaded
    """
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    shutil.copy(
        test_uml_1_events,
        harness_config.test_file_store
    )
    with aioresponses() as mock:
        responses.get(
            url=harness_config.pv_clean_folders_url
        )
        responses.post(
            url=harness_config.pv_send_job_defs_url
        )
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
        puml_files_test(
            puml_file_paths=[test_uml_1_path],
            test_output_directory=harness_config.report_file_store,
            harness_config=harness_config,
            test_config=test_config,
            test_file_paths=[test_uml_1_events]
        )
        files = glob.glob("*.*", root_dir=harness_config.report_file_store)
        expected_files = [
            "Results.csv", "Results.html", "Results.xml",
            "Results_Aggregated.html",
            "Verifier.log", "Reception.log"
        ]
        for file in files:
            file_in_files = file in expected_files
            is_uuid = bool(uuid4hex.match(
                    file.replace("-", "").replace(".json", "")
                ))
            assert file_in_files ^ is_uuid

        # load the test file for comparisons
        with open(test_uml_1_events, 'r', encoding="utf-8") as file:
            test_uml_1_job_file: TestJobFile = json.load(file)
        # check that the saved job event list json has the same event types as
        # the input test file
        sent_file_names = [
            file for file in files if file not in expected_files
        ]
        assert len(sent_file_names) == 1
        with open(
            os.path.join(harness_config.report_file_store, sent_file_names[0]),
            'r',
            encoding="utf-8"
        ) as file:
            output_job_event_file: list[dict] = json.load(file)
        for expected_event, actual_event in zip(
            test_uml_1_job_file["job_file"],
            output_job_event_file
        ):
            assert expected_event["eventType"] == actual_event["eventType"]

        # load results csv and check there is 1 entry and check the relevant
        # fields Category Validity and SeqeunceName are correct
        results_csv = pd.read_csv(
            os.path.join(
                harness_config.report_file_store,
                "Results.csv"
            )
        )
        assert len(results_csv) == 1
        assert test_uml_1_job_file["job_name"] == results_csv.loc[
            0, "SequenceName"
        ]
        assert test_uml_1_job_file["sequence_type"] == results_csv.loc[
            0, "Category"
        ]
        assert test_uml_1_job_file["validity"] == results_csv.loc[
            0, "Validity"
        ]

        clean_directories(
            [
                harness_config.report_file_store,
                harness_config.test_file_store
            ]
        )
