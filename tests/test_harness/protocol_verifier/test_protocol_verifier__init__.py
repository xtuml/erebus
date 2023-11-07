# pylint: disable=R0801
"""Tests for __init__.py
"""

from pathlib import Path
import os
import glob
import re
import shutil
import json
from tempfile import NamedTemporaryFile
import logging
from typing import Callable, Literal

import pytest
import responses
from aioresponses import aioresponses, CallbackResult
import pandas as pd
import aiohttp

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

# get path of umls and events file for extra job invariants test
test_uml_1_einv_path = os.path.join(
    Path(__file__).parent.parent / "test_files",
    "test_uml_1_EINV.puml"
)
test_uml_2_einv_path = os.path.join(
    Path(__file__).parent.parent / "test_files",
    "test_uml_2_EINV.puml"
)
test_file_path_einv = os.path.join(
    Path(__file__).parent.parent / "test_files",
    "test_event_file_EINV.json"
)
test_file_path_einv_options = os.path.join(
    Path(__file__).parent.parent / "test_files",
    "test_event_file_EINV_options.json"
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


@responses.activate
def test_puml_files_test_send_as_pv_bytes() -> None:
    """Tests method `puml_test_files` with send as pv bytes set to true
    """
    harness_config = HarnessConfig(test_config_path)
    harness_config.pv_send_as_pv_bytes = True
    test_config = TestConfig()
    test_config.parse_from_dict({
        "event_gen_options": {
            "invalid": False
        }
    })
    form_payloads: list[aiohttp.MultipartWriter] = []

    # callback function to grab data
    def call_back(url, **kwargs) -> CallbackResult:
        form_payloads.append(kwargs["data"])
        print("called back")
        return CallbackResult(
            status=200,
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
            repeat=True,
            callback=call_back
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
        puml_files_test(
            puml_file_paths=[test_file_path],
            test_output_directory=harness_config.report_file_store,
            harness_config=harness_config,
            test_config=test_config
        )
        for form_payload in form_payloads:
            io_data = form_payload._parts[0][0]._value
            bytes_data = io_data.read()
            # check the data is as expected
            msg_length = int.from_bytes(bytes_data[:4], "big")
            json_bytes = bytes_data[4:]
            assert msg_length == len(json_bytes)

        clean_directories([harness_config.report_file_store])


@responses.activate
def test_puml_files_test_job_file_with_options() -> None:
    """Tests method `puml_test_files` with an input job file containing options
    for Extra job invariants with mismatched invariants and length set to 2
    """
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
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
        puml_files_test(
            puml_file_paths=[test_uml_1_einv_path, test_uml_2_einv_path],
            test_output_directory=harness_config.report_file_store,
            harness_config=harness_config,
            test_config=test_config,
            test_file_paths=[test_file_path_einv_options]
        )
        files = glob.glob("*.*", root_dir=harness_config.report_file_store)
        events_list = []
        for file in files:
            is_uuid = bool(uuid4hex.match(
                    file.replace("-", "").replace(".json", "")
                ))
            if is_uuid:
                with open(
                    os.path.join(
                        harness_config.report_file_store,
                        file
                    ),
                    "r"
                ) as json_file:
                    events_list.extend(json.load(json_file))
        assert "testEINV" in events_list[0] and "testEINV" in events_list[2]
        assert events_list[0]["testEINV"] != events_list[2]["testEINV"]
        assert events_list[0]["testEINV"][:36] == (
            events_list[0]["testEINV"][36:]
        )
        assert events_list[2]["testEINV"][:36] == (
            events_list[2]["testEINV"][36:]
        )
        clean_directories([harness_config.report_file_store])


@responses.activate
def test_puml_files_test_functional_extra_job_invariants() -> None:
    """Tests method `puml_test_files` functional test with extra job
    invariants
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
        puml_files_test(
            puml_file_paths=[test_uml_1_einv_path, test_uml_2_einv_path],
            test_output_directory=harness_config.report_file_store,
            harness_config=harness_config,
            test_config=test_config,
            test_file_paths=[test_file_path_einv]
        )
        results = pd.read_csv(
            os.path.join(harness_config.report_file_store, "Results.csv")
        )
        assert len(results) == 2
        assert results.loc[0, "SequenceName"] == "test_uml_1 + test_uml_2"
        assert results.loc[1, "SequenceName"] == "test_uml_1 + test_uml_2"
        assert results.loc[0, "JobId"] != results.loc[1, "JobId"]
        files = glob.glob("*.*", root_dir=harness_config.report_file_store)
        # check if the invariant in the files are correct
        invariants = []
        event_types = []
        for file in files:
            is_uuid = bool(uuid4hex.match(
                    file.replace("-", "").replace(".json", "")
                ))
            if is_uuid:
                with open(
                    os.path.join(
                        harness_config.report_file_store,
                        file
                    ),
                    "r"
                ) as json_file:
                    data = json.load(json_file)
                    for event in data:
                        if "testEINV" in event:
                            invariants.append(event["testEINV"])
                            event_types.append(event["eventType"])
        assert len(invariants) == 2
        assert len(set(invariants)) == 1
        clean_directories([harness_config.report_file_store])


@responses.activate
def test_puml_files_test_performance_extra_job_invariants() -> None:
    """Tests method `puml_test_files` performance test with extra job
    invariants
    """
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    test_config.parse_from_dict(
        {
            "type": "Performance",
            "event_gen_options": {"invalid": False},
            "performance_options": {"num_files_per_sec": 40, "total_jobs": 20},
        }
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
        puml_files_test(
            puml_file_paths=[test_uml_1_einv_path, test_uml_2_einv_path],
            test_output_directory=harness_config.report_file_store,
            harness_config=harness_config,
            test_config=test_config,
            test_file_paths=[test_file_path_einv]
        )
        results = pd.read_csv(
            os.path.join(
                harness_config.report_file_store,
                "AggregatedResults.csv"
            )
        )
        assert results.iloc[-1]["Cumulative Events Sent"] == 80.0
        clean_directories([harness_config.report_file_store])


@responses.activate
def test_puml_files_test_with_location_log_urls(
    get_log_file_names_call_back: Callable[
        ...,
        tuple[Literal[400], dict, Literal["Error response"]]
        | tuple[Literal[400], dict, str]
        | tuple[Literal[200], dict, str],
    ]
) -> None:
    """Tests method `puml_test_files` with location log files urls added

    :param get_log_file_names_call_back: Fixture to provide a call back
    request function
    :type get_log_file_names_call_back: :class:`Callable`[
        `...`,
        `tuple`[:class:`Literal`[`400`], `dict`, :class:`Literal`[
            `"Error response"`
        ]]
        | `tuple`[:class:`Literal`[`400`], `dict`, `str`]
        | `tuple`[:class:`Literal`[`200`], `dict`, `str`],
    ]
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
        responses.post(
            url=harness_config.log_urls["location"]["getFile"],
            body=b'test log',
        )
        responses.add_callback(
            method="POST",
            url=harness_config.log_urls["location"]["getFileNames"],
            callback=get_log_file_names_call_back,
            content_type="application/json"
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
            "AEReception.log", "AEOrdering.log",
            "AESequenceDC.log", "IStore.log"
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
        profile = Profile()
        profile.load_raw_profile_from_file_path(test_csv_file_path_1)
        with NamedTemporaryFile(suffix='.db') as db_file:
            os.environ["PV_RESULTS_DB_ADDRESS"] = f"sqlite:///{db_file.name}"
            puml_files_test(
                puml_file_paths=[test_file_path],
                test_output_directory=harness_config.report_file_store,
                harness_config=harness_config,
                test_config=test_config,
                profile=profile
            )
        files = glob.glob("*.*", root_dir=harness_config.report_file_store)
        expected_files = [
            "CumulativeEventsSentVSProcessed.html",
            "Verifier.log",
            "Reception.log",
            "grok.txt",
            "Report.xml",
            "Report.html",
            "EventsSentVSProcessed.html",
            "ResponseAndQueueTime.html",
            "AggregatedResults.csv",
            "ProcessingErrors.html",
            "AggregatedErrors.csv"
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


@responses.activate
def test_puml_files_test_functional_test_timeout(
    caplog: pytest.LogCaptureFixture
) -> None:
    """Tests method `puml_test_files` with a functonal test with a timeout
    """
    harness_config = HarnessConfig(test_config_path)
    harness_config.pv_test_timeout = 2
    test_config = TestConfig()
    test_config.parse_from_dict({
        "event_gen_options": {
            "invalid": False
        }
    })
    caplog.set_level(logging.INFO)
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
        puml_files_test(
            puml_file_paths=[test_file_path],
            test_output_directory=harness_config.report_file_store,
            harness_config=harness_config,
            test_config=test_config
        )
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


@responses.activate
def test_puml_files_performance_test_timeout(
    caplog: pytest.LogCaptureFixture,
    grok_exporter_string: str
) -> None:
    """Tests method `puml_test_files` for a performance test that times out
    """
    harness_config = HarnessConfig(test_config_path)
    harness_config.pv_test_timeout = 2
    harness_config.pv_finish_interval = 8
    test_config = TestConfig()
    test_config.parse_from_dict({
        "type": "Performance",
        "event_gen_options": {
            "invalid": False
        }
    })
    caplog.set_level(logging.INFO)
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
        profile = Profile()
        profile.load_raw_profile_from_file_path(test_csv_file_path_1)
        with NamedTemporaryFile(suffix='.db') as db_file:
            os.environ["PV_RESULTS_DB_ADDRESS"] = f"sqlite:///{db_file.name}"
            puml_files_test(
                puml_file_paths=[test_file_path],
                test_output_directory=harness_config.report_file_store,
                harness_config=harness_config,
                test_config=test_config,
                profile=profile
            )
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
