"""Tests generate_test_files.py
"""
from pathlib import Path

from test_harness.process_manager.generate_test_files import (
    generate_test_events_from_puml_file,
    generate_test_events_from_puml_files
)
from test_harness.config.config import TestConfig

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
