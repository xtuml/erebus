# pylint: disable=redefined-outer-name
# pylint: disable=C0413
# pylint: disable=R1735
"""
Fixtures for Test Harness
"""

import sys
from os.path import abspath
from pathlib import Path
from typing import Generator, Literal, Callable
from datetime import datetime
import json

import pandas as pd
import pytest
from flask.testing import FlaskClient, FlaskCliRunner
from pygrok import Grok
from requests import PreparedRequest

from test_harness.protocol_verifier.tests import (
    PVPerformanceResults,
    PVResultsDataFrame,
)

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
    app = create_app(
        harness_config_path=str(
            Path(__file__).parent / "config/test_config.config"
        )
    )
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
def grok_exporter_string() -> str:
    """Fixture to provide a grok file string

    :return: Returns the grok file string
    :rtype: `str`
    """
    with open(grok_file_path, "r", encoding="utf-8") as file:
        file_string = file.read()
    return file_string


@pytest.fixture
def event_job_response_time_dicts() -> list[dict[str, str | datetime]]:
    """Fixture to provide event ids job ids responses and times for tests

    :return: Returns the fixture list
    :rtype: `list`[`dict`[`str`, `str` | :class:`datetime`]]
    """
    return [
        {
            "event_id": "205d5d7e-4eb7-4b8a-a638-1bd0a2ae6497",
            "job_id": "b5f33fff-9092-4f54-ad1f-936142f5334d",
            "time_completed": datetime.strptime(
                "2023-09-04T10:40:37.457652Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "response": "",
        },
        {
            "event_id": "440e1eac-0e7b-483d-9127-36ad46edc933",
            "job_id": "6f04f70a-9d21-477f-a3a8-2d5ad06b2448",
            "time_completed": datetime.strptime(
                "2023-09-04T10:40:40.616374Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "response": "",
        },
        {
            "event_id": "4d5db059-982c-4c62-be9c-2c7f55f9bedb",
            "job_id": "c275fa8b-4b36-49e9-9008-24cef2359753",
            "time_completed": datetime.strptime(
                "2023-09-04T10:40:39.551530Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "response": "",
        },
        {
            "event_id": "69db1f74-3361-4945-8d03-7ccd3307753c",
            "job_id": "d8e10841-69a5-48af-bd30-32f85200df75",
            "time_completed": datetime.strptime(
                "2023-09-04T10:40:38.503551Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "response": "",
        },
        {
            "event_id": "8453e572-09ce-4373-95fb-7a2c004d57d2",
            "job_id": "d8e10841-69a5-48af-bd30-32f85200df75",
            "time_completed": datetime.strptime(
                "2023-09-04T10:40:38.505970Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "response": "",
        },
        {
            "event_id": "895e6183-4dc2-4397-958f-674802ff6a63",
            "job_id": "e572b05e-5cfd-4803-9905-16701ca540c4",
            "time_completed": datetime.strptime(
                "2023-09-04T10:40:36.407944Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "response": "",
        },
        {
            "event_id": "8bae7236-7696-4711-9c0b-5b4933a999a4",
            "job_id": "b5f33fff-9092-4f54-ad1f-936142f5334d",
            "time_completed": datetime.strptime(
                "2023-09-04T10:40:37.460824Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "response": "",
        },
        {
            "event_id": "9912ba48-8395-4aa5-810e-0b495375be0d",
            "job_id": "e572b05e-5cfd-4803-9905-16701ca540c4",
            "time_completed": datetime.strptime(
                "2023-09-04T10:40:36.404928Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "response": "",
        },
        {
            "event_id": "c127aeea-fb77-4946-8745-5ee6ec51a614",
            "job_id": "6f04f70a-9d21-477f-a3a8-2d5ad06b2448",
            "time_completed": datetime.strptime(
                "2023-09-04T10:40:40.611048Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "response": "",
        },
        {
            "event_id": "ce5cbc80-5415-433c-8b80-e6792b2dac9a",
            "job_id": "6f04f70a-9d21-477f-a3a8-2d5ad06b2448",
            "time_completed": datetime.strptime(
                "2023-09-04T10:40:40.607801Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "response": "",
        },
        {
            "event_id": "cee6f593-9b0a-4156-8e74-a5ffdb8f90d6",
            "job_id": "c275fa8b-4b36-49e9-9008-24cef2359753",
            "time_completed": datetime.strptime(
                "2023-09-04T10:40:39.554370Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "response": "",
        },
        {
            "event_id": "d91c48bf-c3e0-4a38-aa71-f30d9ad71117",
            "job_id": "b5f33fff-9092-4f54-ad1f-936142f5334d",
            "time_completed": datetime.strptime(
                "2023-09-04T10:40:37.455387Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "response": "",
        },
        {
            "event_id": "ef1ed7ff-03b7-4db8-90a7-9950281c5210",
            "job_id": "d8e10841-69a5-48af-bd30-32f85200df75",
            "time_completed": datetime.strptime(
                "2023-09-04T10:40:38.509000Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "response": "",
        },
        {
            "event_id": "f2b1aee1-8c4b-435d-bb8c-6cc28ea370ff",
            "job_id": "e572b05e-5cfd-4803-9905-16701ca540c4",
            "time_completed": datetime.strptime(
                "2023-09-04T10:40:36.406471Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "response": "",
        },
        {
            "event_id": "fa835a85-8257-44e8-9641-489111b99bc2",
            "job_id": "c275fa8b-4b36-49e9-9008-24cef2359753",
            "time_completed": datetime.strptime(
                "2023-09-04T10:40:39.559083Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "response": "",
        },
    ]


@pytest.fixture
def start_time() -> datetime:
    """Fixture providing a start time for tests

    :return: The start time as a dattime object
    :rtype: :class:`datetime`
    """
    return datetime.strptime(
        "2023-09-04T10:40:36.406471Z", "%Y-%m-%dT%H:%M:%S.%fZ"
    )


@pytest.fixture
def results_dataframe() -> pd.DataFrame:
    """Fixture providing a results dataframe for testing

    :return: Returns the dataframe
    :rtype: :class:`pd`.`DataFrame`
    """
    return pd.DataFrame(
        [
            [f"job_{i}", 0.0 + i, "", 1.0 + i, 2.0 + i, 3.0 + i, 4.0 + i]
            for i in range(10)
        ],
        index=[f"event_{i}" for i in range(10)],
        columns=PVPerformanceResults.data_fields,
    )


@pytest.fixture
def log_file_string() -> (
    Literal["2023-09-28T19:27:23.434758Z 1 svdc_new_job_started…"]
):
    """Fixture providing a log file string

    :return: Returns the log file string
    :rtype: `str`
    """
    return (
        "2023-09-28T19:27:23.434758Z 1 svdc_new_job_started : JobId ="
        " eeba705f-eac4-467c-8826-bf31673e745f : EventId ="
        " 3cf78438-8084-494d-8d7b-efd7ea46f7d4 : EventType = A"
    )


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
def event_jobs() -> list[dict[str, str | datetime]]:
    """Fixture providing a list of dictionaries of sent events that can be
    loaded into a :class:`PVResults` instance

    :return: Returns a list of sent events data
    :rtype: `list`[`dict`[`str`, `str` | :class:`datetime`]]
    """
    return [
        dict(
            event_id="1c9c37f7-b61a-4c05-a841-00c1276a22e0",
            job_id="b87dc318-b714-43ce-9ca0-0aac712f03e2",
            time_completed=datetime.strptime(
                "2023-10-04T17:50:57.770134Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            response="",
        ),
        dict(
            event_id="7b5f2070-0f4d-443b-875c-6ef89a2e7993",
            job_id="b87dc318-b714-43ce-9ca0-0aac712f03e2",
            time_completed=datetime.strptime(
                "2023-10-04T17:50:57.791624Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            response="",
        ),
        dict(
            event_id="b4696f92-da3f-4c4c-936a-1266741b1fb7",
            job_id="fdd29d17-79b4-4fc4-bd41-39b1a4c4a05b",
            time_completed=datetime.strptime(
                "2023-10-04T17:50:56.737302Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            response="",
        ),
        dict(
            event_id="d1c33411-fa6d-4968-ae0d-265b911faba1",
            job_id="fdd29d17-79b4-4fc4-bd41-39b1a4c4a05b",
            time_completed=datetime.strptime(
                "2023-10-04T17:50:57.804237Z", "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            response="",
        ),
    ]


@pytest.fixture
def pv_results(
    event_jobs: list[dict[str, str | datetime]]
) -> PVResultsDataFrame:
    """An instance of :class:`PVResultsDataFrame` with loaded sent events data

    :param event_jobs: Fixture providing sent events data
    :type event_jobs: `list`[`dict`]
    :return: Returns the instance of :class:`PvResultsDataFrame`
    :rtype: :class:`PVResultsDataFrame`
    """
    results = PVResultsDataFrame()
    results.time_start = datetime.strptime(
        "2023-10-04T17:50:57.770134Z", "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    for event_entry in event_jobs:
        results.add_first_event_data(**event_entry)
    return results


@pytest.fixture
def expected_reception_pv_added_results() -> list[dict[str, str | float]]:
    """Fixture providing the expected results loaded from reception log file

    :return: Returns a dictionary of the expected results
    :rtype: `list`[`dict`[`str`, `str` | `float`]]
    """
    time_start = datetime.strptime(
        "2023-10-04T17:50:57.770134Z", "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    return [
        dict(
            pv_data_field=PVResultsDataFrame.pv_grok_map[
                "reception_event_received"
            ],
            event_id="1c9c37f7-b61a-4c05-a841-00c1276a22e0",
            pv_time=(
                datetime.strptime(
                    "2023-10-04T17:50:57.770134Z", "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                - time_start
            ).total_seconds(),
        ),
        dict(
            pv_data_field=PVResultsDataFrame.pv_grok_map[
                "reception_event_received"
            ],
            event_id="7b5f2070-0f4d-443b-875c-6ef89a2e7993",
            pv_time=(
                datetime.strptime(
                    "2023-10-04T17:50:57.791624Z", "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                - time_start
            ).total_seconds(),
        ),
        dict(
            pv_data_field=PVResultsDataFrame.pv_grok_map[
                "reception_event_received"
            ],
            event_id="b4696f92-da3f-4c4c-936a-1266741b1fb7",
            pv_time=(
                datetime.strptime(
                    "2023-10-04T17:50:56.737302Z", "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                - time_start
            ).total_seconds(),
        ),
        dict(
            pv_data_field=PVResultsDataFrame.pv_grok_map[
                "reception_event_received"
            ],
            event_id="d1c33411-fa6d-4968-ae0d-265b911faba1",
            pv_time=(
                datetime.strptime(
                    "2023-10-04T17:50:57.804237Z", "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                - time_start
            ).total_seconds(),
        ),
        dict(
            pv_data_field=PVResultsDataFrame.pv_grok_map[
                "reception_event_written"
            ],
            event_id="1c9c37f7-b61a-4c05-a841-00c1276a22e0",
            pv_time=(
                datetime.strptime(
                    "2023-10-04T17:50:57.784209Z", "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                - time_start
            ).total_seconds(),
        ),
        dict(
            pv_data_field=PVResultsDataFrame.pv_grok_map[
                "reception_event_written"
            ],
            event_id="7b5f2070-0f4d-443b-875c-6ef89a2e7993",
            pv_time=(
                datetime.strptime(
                    "2023-10-04T17:50:57.799078Z", "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                - time_start
            ).total_seconds(),
        ),
        dict(
            pv_data_field=PVResultsDataFrame.pv_grok_map[
                "reception_event_written"
            ],
            event_id="b4696f92-da3f-4c4c-936a-1266741b1fb7",
            pv_time=(
                datetime.strptime(
                    "2023-10-04T17:50:56.750974Z", "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                - time_start
            ).total_seconds(),
        ),
        dict(
            pv_data_field=PVResultsDataFrame.pv_grok_map[
                "reception_event_written"
            ],
            event_id="d1c33411-fa6d-4968-ae0d-265b911faba1",
            pv_time=(
                datetime.strptime(
                    "2023-10-04T17:50:57.810939Z", "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                - time_start
            ).total_seconds(),
        ),
    ]


@pytest.fixture
def expected_verifier_pv_added_results() -> (
    list[dict[str, str | set[str] | float]]
):
    """Fixture providing the expected results loaded from verifier log file

    :return: Returns a list of dictionaries of the expected results
    :rtype: `list`[`dict`[`str`, `str` | `set`[`str`] | `float`]]
    """
    time_start = datetime.strptime(
        "2023-10-04T17:50:57.770134Z", "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    return [
        dict(
            pv_data_field=PVResultsDataFrame.pv_grok_map[
                "aeordering_events_processed"
            ],
            event_ids=set(["1c9c37f7-b61a-4c05-a841-00c1276a22e0"]),
            job_id="b87dc318-b714-43ce-9ca0-0aac712f03e2",
            pv_time=(
                datetime.strptime(
                    "2023-10-04T17:50:58.274324Z", "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                - time_start
            ).total_seconds(),
        ),
        dict(
            pv_data_field=PVResultsDataFrame.pv_grok_map[
                "aeordering_events_processed"
            ],
            event_ids=set(["7b5f2070-0f4d-443b-875c-6ef89a2e7993"]),
            job_id="b87dc318-b714-43ce-9ca0-0aac712f03e2",
            pv_time=(
                datetime.strptime(
                    "2023-10-04T17:50:58.281972Z", "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                - time_start
            ).total_seconds(),
        ),
        dict(
            pv_data_field=PVResultsDataFrame.pv_grok_map[
                "aeordering_events_processed"
            ],
            event_ids=set(["b4696f92-da3f-4c4c-936a-1266741b1fb7"]),
            job_id="fdd29d17-79b4-4fc4-bd41-39b1a4c4a05b",
            pv_time=(
                datetime.strptime(
                    "2023-10-04T17:50:57.164510Z", "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                - time_start
            ).total_seconds(),
        ),
        dict(
            pv_data_field=PVResultsDataFrame.pv_grok_map[
                "aeordering_events_processed"
            ],
            event_ids=set(["d1c33411-fa6d-4968-ae0d-265b911faba1"]),
            job_id="fdd29d17-79b4-4fc4-bd41-39b1a4c4a05b",
            pv_time=(
                datetime.strptime(
                    "2023-10-04T17:50:58.198180Z", "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                - time_start
            ).total_seconds(),
        ),
        dict(
            pv_data_field=PVResultsDataFrame.pv_grok_map["svdc_job_success"],
            job_id="b87dc318-b714-43ce-9ca0-0aac712f03e2",
            pv_time=(
                datetime.strptime(
                    "2023-10-04T17:50:59.289109Z", "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                - time_start
            ).total_seconds(),
            event_ids=set(
                [
                    "1c9c37f7-b61a-4c05-a841-00c1276a22e0",
                    "7b5f2070-0f4d-443b-875c-6ef89a2e7993",
                ]
            ),
        ),
        dict(
            pv_data_field=PVResultsDataFrame.pv_grok_map["svdc_job_success"],
            job_id="fdd29d17-79b4-4fc4-bd41-39b1a4c4a05b",
            pv_time=(
                datetime.strptime(
                    "2023-10-04T17:50:59.210438Z", "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                - time_start
            ).total_seconds(),
            event_ids=set(
                [
                    "b4696f92-da3f-4c4c-936a-1266741b1fb7",
                    "d1c33411-fa6d-4968-ae0d-265b911faba1",
                ]
            ),
        ),
    ]


@pytest.fixture
def get_log_file_names_call_back() -> (
    Callable[
        ...,
        tuple[Literal[400], dict, Literal["Error response"]]
        | tuple[Literal[400], dict, str]
        | tuple[Literal[200], dict, str],
    ]
):
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
                        pass
            case "VERIFIER":
                match payload["file_prefix"]:
                    case "AEOrdering":
                        file_names.append("AEOrdering.log")
                    case "AESequenceDC":
                        file_names.append("AESequenceDC.log")
                    case "IStore":
                        file_names.append("IStore.log")
                    case _:
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
