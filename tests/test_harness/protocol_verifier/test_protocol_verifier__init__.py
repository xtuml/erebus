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

import pytest
import responses
from aioresponses import aioresponses
import pandas as pd

from test_harness.config.config import TestConfig, HarnessConfig
from test_harness.protocol_verifier import (
    puml_files_test,
    get_test_profile
)
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

# get path of test csv file
test_csv_file_path_2 = os.path.join(
    Path(__file__).parent.parent / "test_files",
    "test_profile_2.csv"
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
            "Results_Aggregated.html"
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
def test_puml_files_performance_with_input_profile() -> None:
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
            "Basic_Stats.csv",
            "PV_File_IO.csv",
            "PV_File_IO.html",
        ]
        for file in files:
            file_in_files = file in expected_files
            is_uuid = bool(uuid4hex.match(
                    file.replace("-", "").replace(".json", "")
                ))
            assert file_in_files ^ is_uuid

        results = pd.read_csv(os.path.join(
            harness_config.report_file_store, "Basic_Stats.csv",
        ), index_col="Data Field")
        assert pytest.approx(results.loc["num_jobs", '0']) == 25
        assert pytest.approx(results.loc["num_events", '0']) == 75
        assert pytest.approx(results.loc["reception_end_time", '0']) == 3
        assert pytest.approx(results.loc["verifier_end_time", '0']) == 3
        assert pytest.approx(
            results.loc["average_jobs_per_sec", '0']
        ) == 25 / 3
        assert pytest.approx(
            results.loc["average_events_per_sec", '0']
        ) == 75 / 3
        clean_directories([harness_config.report_file_store])
