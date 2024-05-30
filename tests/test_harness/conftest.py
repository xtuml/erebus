# pylint: disable=redefined-outer-name
# pylint: disable=C0413
# pylint: disable=R1735
"""
Fixtures for Test Harness
"""

from configparser import ConfigParser
import sys
from os.path import abspath
from pathlib import Path
from typing import Generator, Literal, Callable
import json
import pytest
from flask.testing import FlaskClient, FlaskCliRunner
from pygrok import Grok
from requests import PreparedRequest

# insert root directory into path
package_path = abspath(Path(__file__).parent.parent.parent)
sys.path.insert(0, package_path)
from test_harness.__init__ import create_app, HarnessApp  # noqa

# grok file path
grok_file_path = Path(__file__).parent / "test_files" / "grok_file.txt"


@pytest.fixture()
def test_app() -> Generator[HarnessApp, None, None]:
    """Fixture to create app for testing

    :yield: Yields the Harness app
    :rtype: :class:`Generator`[:class:`HarnessApp`, None, None]
    """
    config_parser = ConfigParser()
    harness_config_path = str(
        Path(__file__).parent / "config/test_config.config"
    )
    try:
        config_parser.read(harness_config_path)
    except Exception as error:
        print(f"Unable to find config at the specified location: {error}")
        sys.exit()
    app = create_app(config_parser=config_parser)
    app.config.update({"TESTING": True})

    yield app


@pytest.fixture()
def client(test_app: HarnessApp) -> FlaskClient:
    """Fixture to create the Flask test client

    :param test_app: The Harness app to be tested
    :type test_app: :class:`HarnessApp`
    :return: Flask test client
    :rtype: :class:`FlaskClient`
    """
    return test_app.test_client()


@pytest.fixture()
def runner(test_app: HarnessApp) -> FlaskCliRunner:
    """Fixture to create the runner for the test client

    :param test_app: The flask app to be tested
    :type test_app: :class:`HarnessApp`
    :return: Flask test client runner
    :rtype: :class:`FlaskCliRunner`
    """
    return test_app.test_cli_runner()


@pytest.fixture
def grok_priority_patterns() -> list[Grok]:
    """Fixture providing a list of grok patterns in priority order

    :return: List of grok patterns
    :rtype: `list`[:class:`Grok`]
    """
    return [
        Grok(
            "%{TIMESTAMP_ISO8601:timestamp} %{NUMBER} %{WORD:field} :"
            " JobId = %{UUID} : EventId = %{UUID:event_id} : "
            "EventType = %{WORD}"
        ),
        Grok(
            "%{TIMESTAMP_ISO8601:timestamp} %{NUMBER} %{WORD:field} :"
            " JobId = %{UUID:job_id}"
        ),
    ]


@pytest.fixture
def expected_verifier_grok_results() -> list[dict[str, str]]:
    """Fixture providing expected verifier groked results

    :return: Returns a list of groked results
    :rtype: `list`[`dict`[`str`, `str`]]
    """
    return [
        {
            "timestamp": "2023-09-28T19:27:23.434758Z",
            "field": "svdc_new_job_started",
            "event_id": "3cf78438-8084-494d-8d7b-efd7ea46f7d4",
        },
        {
            "timestamp": "2023-09-28T19:27:23.514683Z",
            "field": "aeordering_job_processed",
            "job_id": "4cdbe6d0-424a-4a96-9357-3b19144ee07b",
        },
        {
            "timestamp": "2023-09-28T19:27:23.514745Z",
            "field": "aeordering_events_processed",
            "event_id": "7a231b76-8062-47da-a2c9-0a764dfa3dd9",
        },
        {
            "timestamp": "2023-09-28T19:27:23.515067Z",
            "field": "aeordering_events_blocked",
            "event_id": "7a231b76-8062-47da-a2c9-0a764dfa3dd9",
        },
        {
            "timestamp": "2023-09-28T19:10:57.012539Z",
            "field": "svdc_job_success",
            "job_id": "85619f16-f04f-4f60-8525-2f643c6b417e",
        },
    ]


@pytest.fixture
def get_log_file_names_call_back() -> Callable[
    ...,
    tuple[Literal[400], dict, Literal["Error response"]]
    | tuple[Literal[400], dict, str]
    | tuple[Literal[200], dict, str],
]:
    """Fixture to provide a call back request function for a
    POST request endpoint to get the file names for a domain location of the
    PV with specified file prefix. The request contains a json payload
    containing:
    * "location" - Domain location of the log files to get
    * "file_prefix" - The file prefix of the log file names to get

    :return: Returns the fixture
    :rtype: :class:`Callable`[
        `...`,
        `tuple`[:class:`Literal`[`400`], `dict`, :class:`Literal`[
            `"Error response"`
        ]]
        | `tuple`[:class:`Literal`[`400`], `dict`, `str`]
        | `tuple`[:class:`Literal`[`200`], `dict`, `str`],
    ]
    """

    def request_callback(
        request: PreparedRequest,
    ) -> (
        tuple[Literal[400], dict, Literal["Error response"]]
        | tuple[Literal[400], dict, str]
        | tuple[Literal[200], dict, str]
    ):
        payload = json.loads(request.body)
        headers = {}
        file_names = []
        if set(["location", "file_prefix"]) != set(payload.keys()):
            return (400, headers, "Error response")
        match payload["location"]:
            case "RECEPTION":
                match payload["file_prefix"]:
                    case "AEReception":
                        file_names.append("AEReception.log")
                    case _:
                        file_names.append("Reception.log")
            case "VERIFIER":
                match payload["file_prefix"]:
                    case "AEOrdering":
                        file_names.append("AEOrdering.log")
                    case "AESequenceDC":
                        file_names.append("AESequenceDC.log")
                    case "IStore":
                        file_names.append("IStore.log")
                    case _:
                        file_names.append("Verifier.log")
                        pass
            case _:
                return (
                    400,
                    headers,
                    (
                        "Request error: the input key"
                        f" {payload['location']} does not exist"
                    ),
                )
        resp_body = {"fileNames": file_names}

        return (200, headers, json.dumps(resp_body))

    return request_callback
