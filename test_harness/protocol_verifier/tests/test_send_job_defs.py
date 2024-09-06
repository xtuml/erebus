"""Tests for send_job_defs.py"""

import copy
from pathlib import Path
import os
from configparser import ConfigParser
from unittest.mock import patch

import responses
from responses.matchers import multipart_matcher
import pytest

from test_harness.config.config import HarnessConfig
from test_harness.protocol_verifier.config.config import ProtocolVerifierConfig
from test_harness.utils import create_file_io_file_name_tuple
from test_harness.protocol_verifier.send_job_defs import (
    send_job_defs_from_file_io_file_name_tuples,
    send_job_defs_from_uml,
    get_job_defs_from_jsons,
    send_job_defs_from_json,
    handle_send_job_defs,
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

class TestSendJobDefsFromJson:
    @staticmethod
    def json_string() -> str:
        return (
            '{\n'
            '    "JobDefinitionName": "test_uml_1",\n'
            '    "Events": [\n'
            '        {\n'
            '            "EventName": "A",\n'
            '            "OccurrenceId": 0,\n'
            '            "SequenceName": "test_uml_1",\n'
            '            "Application": "default_application_name",\n'
            '            "SequenceStart": true\n'
            '        },\n'
            '        {\n'
            '            "EventName": "B",\n'
            '            "OccurrenceId": 0,\n'
            '            "SequenceName": "test_uml_1",\n'
            '            "Application": "default_application_name",\n'
            '            "SequenceEnd": true,\n'
            '            "PreviousEvents": [\n'
            '                {\n'
            '                    "PreviousEventName": "A",\n'
            '                    "PreviousOccurrenceId": 0\n'
            '                }\n'
            '            ]\n'
            '        }\n'
            '    ]\n'
            '}\n'
        )
    

    def test_get_job_defs_from_jsons(self) -> None:
        """Tests get_job_defs_from_jsons"""
        test_json_file_path_1 = os.path.join(test_file_resources, "test_uml_1_jobdef.json")
        test_json_file_path_2 = os.path.join(test_file_resources, "test_uml_1_jobdef.json")
        job_defs = get_job_defs_from_jsons(
            json_file_paths=[test_json_file_path_1, test_json_file_path_2]
        )
        json_string = self.json_string
        assert all(json_string == job_def for job_def in job_defs)

    @responses.activate
    def test_send_job_defs_from_jsons(self) -> None:
        url = "http://mockserver.com/job-definitions"
        responses.post(
            url, status=200,
            match=[multipart_matcher(
                files={
                    "upload": (
                        "test_uml_1_jobdef.json",
                        self.json_string().encode("utf-8"),
                        "application/octet-stream"
                    )
                }
            )]
        )
        harness_config = HarnessConfig(config_parser)
        test_json_file_path_1 = os.path.join(test_file_resources, "test_uml_1_jobdef.json")
        send_job_defs_from_json(
            url=url,
            json_file_paths=[test_json_file_path_1],
            harness_config=harness_config
        )


def test_handle_send_job_defs() -> None:
    """Tests handle_send_job_defs"""
    harness_config = ProtocolVerifierConfig(config_parser)
    test_json_file_path_1 = os.path.join(test_file_resources, "test_uml_1_jobdef.json")
    test_uml_file_path_1 = os.path.join(test_file_resources, "test_uml_1.puml")
    with patch("test_harness.protocol_verifier.send_job_defs.send_job_defs_from_json") as mock:
        handle_send_job_defs(
            file_paths=[test_json_file_path_1, test_uml_file_path_1],
            harness_config=harness_config,
            file_type="json"
        )
        mock.assert_called_once()
    with patch("test_harness.protocol_verifier.send_job_defs.send_job_defs_from_uml") as mock:
        handle_send_job_defs(
            file_paths=[test_json_file_path_1, test_uml_file_path_1],
            harness_config=harness_config,
            file_type="uml"
        )
        mock.assert_called_once()
    with pytest.raises(ValueError) as e_info:
        handle_send_job_defs(
            file_paths=[test_json_file_path_1, test_uml_file_path_1],
            harness_config=harness_config,
            file_type="invalid"
        )
    assert e_info.value.args[0] == "Invalid file type: invalid"