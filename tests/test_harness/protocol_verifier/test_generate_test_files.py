"""Tests generate_test_files.py
"""
from pathlib import Path
import json

from test_harness.protocol_verifier.generate_test_files import (
    generate_test_events_from_puml_file,
    generate_test_events_from_puml_files,
    load_test_file_data_json_into_test_file_holder,
    get_test_events_from_test_file_jsons
)
from test_harness.config.config import TestConfig
from test_harness.utils import check_dict_equivalency

# test file resources folder
test_file_resources = Path(__file__).parent.parent / "test_files"


def test_generate_test_events_from_puml_file_default_config() -> None:
    """Tests `generate_test_events_from_puml_file`
    """
    test_config = TestConfig()
    test_file_path = test_file_resources / "test_uml_job_def.puml"
    test_events = generate_test_events_from_puml_file(
        test_file_path,
        test_config
    )
    assert len(test_events) == 1
    assert "test_uml" in test_events
    job_events = test_events["test_uml"]
    assert len(job_events) == 8
    for category in [
        "ValidSols",
        "StackedSolutions",
        "MissingEvents",
        "SpyEvents",
        "MissingEdges",
        "GhostEvents",
        "XORConstraintBreaks",
        "ANDConstraintBreaks"
    ]:
        assert category in job_events


def test_generate_test_events_from_puml_file_custom_config() -> None:
    """Tests `generate_test_events_from_puml_file`
    """
    test_config = TestConfig()
    invalid_types = [
        "StackedSolutions",
        "MissingEvents",
        "SpyEvents"
    ]
    test_config.parse_from_dict(
        {
            "event_gen_options": {
                "invalid_types": invalid_types,
                "solution_limit": 0
            }
        }
    )
    test_file_path = test_file_resources / "test_uml_job_def.puml"
    test_events = generate_test_events_from_puml_file(
        test_file_path,
        test_config
    )
    assert len(test_events) == 1
    assert "test_uml" in test_events
    job_events = test_events["test_uml"]
    assert len(job_events) == 4
    counter = 0
    for category in [
        "ValidSols",
        "StackedSolutions",
        "MissingEvents",
        "SpyEvents",
    ]:
        assert category in job_events
        for _ in job_events[category][0]:
            counter += 1
    assert counter == 0


def test_generate_test_events_from_puml_files() -> None:
    """Tests `generate_test_events_from_puml_files` with default config
    """
    test_config = TestConfig()
    test_file_paths = [
        test_file_resources / "test_uml_1.puml",
        test_file_resources / "test_uml_2.puml",
    ]
    test_events = generate_test_events_from_puml_files(
        test_file_paths,
        test_config
    )
    assert len(test_events) == 2
    assert "test_uml_1" in test_events
    assert "test_uml_2" in test_events


def test_load_test_file_data_json_into_test_file_holder() -> None:
    """Tests `load_test_file_data_json_into_test_file_holder` with one file
    """
    test_file_path = test_file_resources / "test_uml_1_events.json"
    with open(test_file_path, 'r', encoding="utf-8") as file:
        test_file = json.load(file)
    test_file_holder = {}
    load_test_file_data_json_into_test_file_holder(
        test_file_path,
        test_file_holder
    )
    assert test_file_holder
    assert len(test_file_holder) == 1
    assert "test_uml_1" in test_file_holder
    assert test_file_holder["test_uml_1"]
    assert len(test_file_holder["test_uml_1"]) == 1
    assert "ValidSols" in test_file_holder["test_uml_1"]
    assert test_file_holder["test_uml_1"]["ValidSols"][1]
    job_tuples = [*test_file_holder["test_uml_1"]["ValidSols"][0]]
    assert len(job_tuples) == 1
    check_dict_equivalency(
        job_tuples[0][0],
        test_file["job_file"]
    )


def test_load_test_file_data_json_into_test_file_holder_two_files() -> None:
    """Tests `load_test_file_data_json_into_test_file_holder` with two files
    """
    test_file_path_1 = test_file_resources / "test_uml_1_events.json"
    test_file_path_2 = test_file_resources / "test_uml_2_events.json"
    with open(test_file_path_1, 'r', encoding="utf-8") as file:
        test_file_1 = json.load(file)
    with open(test_file_path_2, 'r', encoding="utf-8") as file:
        test_file_2 = json.load(file)
    test_file_holder = {}
    load_test_file_data_json_into_test_file_holder(
        test_file_path_1,
        test_file_holder
    )
    load_test_file_data_json_into_test_file_holder(
        test_file_path_2,
        test_file_holder
    )
    assert test_file_holder
    assert len(test_file_holder) == 1
    assert "test_uml_1" in test_file_holder
    assert test_file_holder["test_uml_1"]
    assert len(test_file_holder["test_uml_1"]) == 1
    assert "ValidSols" in test_file_holder["test_uml_1"]
    assert test_file_holder["test_uml_1"]["ValidSols"][1]
    job_tuples = [*test_file_holder["test_uml_1"]["ValidSols"][0]]
    assert len(job_tuples) == 2
    check_dict_equivalency(
        job_tuples[0][0],
        test_file_1["job_file"]
    )
    check_dict_equivalency(
        job_tuples[1][0],
        test_file_2["job_file"]
    )


def test_get_test_events_from_test_file_jsons() -> None:
    """Tests `get_test_events_from_test_file_jsons`
    """
    test_file_path_1 = test_file_resources / "test_uml_1_events.json"
    test_file_path_2 = test_file_resources / "test_uml_2_events.json"
    with open(test_file_path_1, 'r', encoding="utf-8") as file:
        test_file_1 = json.load(file)
    with open(test_file_path_2, 'r', encoding="utf-8") as file:
        test_file_2 = json.load(file)
    test_file_holder = get_test_events_from_test_file_jsons(
        [test_file_path_1, test_file_path_2]
    )
    assert test_file_holder
    assert len(test_file_holder) == 1
    assert "test_uml_1" in test_file_holder
    assert test_file_holder["test_uml_1"]
    assert len(test_file_holder["test_uml_1"]) == 1
    assert "ValidSols" in test_file_holder["test_uml_1"]
    assert test_file_holder["test_uml_1"]["ValidSols"][1]
    job_tuples = [*test_file_holder["test_uml_1"]["ValidSols"][0]]
    assert len(job_tuples) == 2
    check_dict_equivalency(
        job_tuples[0][0],
        test_file_1["job_file"]
    )
    check_dict_equivalency(
        job_tuples[1][0],
        test_file_2["job_file"]
    )


def test_load_test_file_data_json_into_test_file_holder_options() -> None:
    """Tests `load_test_file_data_json_into_test_file_holder` with one file
    and options given in the file
    """
    test_file_path = test_file_resources / "test_event_file_EINV_options.json"
    with open(test_file_path, 'r', encoding="utf-8") as file:
        test_file = json.load(file)
    test_file_holder = {}
    load_test_file_data_json_into_test_file_holder(
        test_file_path,
        test_file_holder
    )
    assert test_file_holder
    assert len(test_file_holder) == 1
    assert "test_uml_1 + test_uml_2" in test_file_holder
    jobs_data = test_file_holder["test_uml_1 + test_uml_2"]
    assert jobs_data
    assert len(jobs_data) == 1
    assert "UnMatchedEINVS" in jobs_data
    job_data = jobs_data["UnMatchedEINVS"]
    assert job_data
    assert not job_data[1]
    job_tuples = [*job_data[0]]
    assert len(job_tuples) == 1
    check_dict_equivalency(
        job_tuples[0][0],
        test_file["job_file"]
    )
    options = job_data[2]
    assert options
    assert options["invariant_matched"] is False
    assert options["invariant_length"] == 2
