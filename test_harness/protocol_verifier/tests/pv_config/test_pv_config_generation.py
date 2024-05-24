"""Tests for Protocol Verifier Job def creation"""

from pathlib import Path
import os
import json

import pytest

from test_harness.pv_config.pv_config_generation import (
    get_job_defs_from_uml_files,
)
from test_harness.utils import check_dict_equivalency

# get resources folder in tests folder
test_file_path = os.path.join(
    Path(__file__).parent.parent.parent.parent.parent / "test_files",
    "test_uml_job_def.puml",
)
test_file_path_error = os.path.join(
    Path(__file__).parent.parent.parent.parent.parent / "test_files",
    "test_uml_job_def_error.puml",
)
test_file_unhappy_puml_path = os.path.join(
    Path(__file__).parent.parent.parent.parent.parent / "test_files",
    "unhappy_job.puml",
)
test_file_unhappy_job_def_path = os.path.join(
    Path(__file__).parent.parent.parent.parent.parent / "test_files",
    "unhappy_job_job_def.json",
)


def test_get_job_defs_from_uml_files(expected_job_def_string: str) -> None:
    """Test for `get_job_def_from_uml`

    :param expected_job_def_string: Fixture providing expected job definition
    string
    :type expected_job_def_string: str
    """
    job_string = get_job_defs_from_uml_files(
        [test_file_path],
    )
    assert job_string[0] == expected_job_def_string


def test_get_job_def_from_uml_error() -> None:
    """Test for `get_job_def_from_uml` with error"""
    with pytest.raises(RuntimeError) as e_info:
        get_job_defs_from_uml_files(
            [test_file_path_error],
        )
    assert e_info.value.args[0] == (
        "Plus2json found the following errors that should be rectified:\n"
        "test_uml_job_def_error.puml[8:18]:  mismatched input '1' expecting "
        "{StringLiteral, IDENT}"
    )


def test_get_job_defs_from_uml_files_unhappy() -> None:
    """Test for `get_job_def_from_uml` for an unhappy job"""
    job_string = get_job_defs_from_uml_files(
        [test_file_unhappy_puml_path],
    )
    actual_job_def = json.loads(job_string[0])
    with open(test_file_unhappy_job_def_path, "r") as test_file:
        expected_job_def = json.load(test_file)
    check_dict_equivalency(actual_job_def, expected_job_def)
