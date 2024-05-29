"""Tests for send_job_defs.py"""

import copy
from pathlib import Path
import os
from configparser import ConfigParser

import responses
import pytest

from test_harness.config.config import HarnessConfig
from test_harness.utils import create_file_io_file_name_tuple
from test_harness.protocol_verifier.send_job_defs import (
    send_job_defs_from_file_io_file_name_tuples,
    send_job_defs_from_uml,
)

# test file resources folder
test_file_resources = Path(__file__).parent / "test_files"

# get test config
test_config_path = os.path.join(
    Path(__file__).parent.parent.parent.parent
    / "tests/test_harness/config/test_config.config",
)

# set config_parser object
config_parser = ConfigParser()
config_parser.read(test_config_path)


@responses.activate
def test_send_job_defs_from_file_io_file_name_tuples_ok() -> None:
    """Tests `send_job_defs_from_file_io_file_name_tuples` when response
    is ok"""
    file_string = "test"
    file_name = "test_file"
    file_io_file_name_tuple = create_file_io_file_name_tuple(
        file_name=file_name, file_string=file_string
    )
    file_io_file_name_tuples = [
        file_io_file_name_tuple,
        copy.deepcopy(file_io_file_name_tuple),
    ]
    url = "http://mockserver.com/job-definitions"
    responses.add(responses.POST, url, status=200)
    send_job_defs_from_file_io_file_name_tuples(
        file_io_file_name_tuples=file_io_file_name_tuples,
        url=url,
        max_retries=5,
        timeout=10,
    )


@responses.activate
def test_send_job_defs_from_file_io_file_name_tuples_error() -> None:
    """Tests `send_job_defs_from_file_io_file_name_tuples` when response
    indicates error
    """
    file_string = "test"
    file_name = "test_file"
    file_io_file_name_tuple = create_file_io_file_name_tuple(
        file_name=file_name, file_string=file_string
    )
    file_io_file_name_tuples = [
        file_io_file_name_tuple,
        copy.deepcopy(file_io_file_name_tuple),
    ]
    url = "http://mockserver.com/job-definitions"
    responses.add(responses.POST, url, status=404)
    with pytest.raises(RuntimeError) as e_info:
        send_job_defs_from_file_io_file_name_tuples(
            file_io_file_name_tuples=file_io_file_name_tuples,
            url=url,
            max_retries=5,
            timeout=10,
        )
    assert e_info.value.args[0] == (
        "Error sending job defs to PV after 5 retries"
        " with code 404 and reason"
        " 'Not Found'. Determine the issue before"
        " retrying."
    )


@responses.activate
def test_send_job_defs_from_uml() -> None:
    """Tests send_job_defs_from_uml"""
    url = "http://mockserver.com/job-definitions"
    responses.add(responses.POST, url, status=200)
    harness_config = HarnessConfig(config_parser)
    test_uml_file_path_1 = os.path.join(test_file_resources, "test_uml_1.puml")
    test_uml_file_path_2 = os.path.join(test_file_resources, "test_uml_2.puml")
    send_job_defs_from_uml(
        url=url,
        uml_file_paths=[test_uml_file_path_1, test_uml_file_path_2],
        harness_config=harness_config,
    )
