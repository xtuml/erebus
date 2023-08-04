"""Tests for Protocol Verifier Job def creation
"""
from pathlib import Path
import os
import pytest
from test_harness.pv_config.pv_config_generation import (
    get_job_def_from_uml
)

# get resources folder in tests folder
test_file_path = os.path.join(
    Path(__file__).parent.parent / "test_files",
    "test_uml_job_def.puml"
)
test_file_path_error = os.path.join(
    Path(__file__).parent.parent / "test_files",
    "test_uml_job_def_error.puml"
)


def test_get_job_def_from_uml(
    expected_job_def_string: str
) -> None:
    """Test for `get_job_def_from_uml`

    :param expected_job_def_string: Fixture providing expected job definition
    string
    :type expected_job_def_string: str
    """
    job_string = get_job_def_from_uml(
        test_file_path,
    )
    assert job_string == expected_job_def_string


def test_get_job_def_from_uml_error(
) -> None:
    """Test for `get_job_def_from_uml` with error
    """
    with pytest.raises(RuntimeError) as e_info:
        get_job_def_from_uml(
            test_file_path_error,
        )
    assert e_info.value.args[0] == (
        "Plus2json found the following errors that should be rectified:\n"
        "line 8:18 mismatched input '1' expecting {StringLiteral, IDENT}\n"
        "line 10:18 mismatched input '2' expecting {StringLiteral, IDENT}\n"
    )
