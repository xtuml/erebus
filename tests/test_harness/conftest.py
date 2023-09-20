# pylint: disable=redefined-outer-name
# pylint: disable=C0413
"""
Fixtures for Test Harness
"""

import sys
from os.path import abspath
from pathlib import Path
from typing import Generator
from datetime import datetime

import pandas as pd
import pytest
from flask.testing import FlaskClient, FlaskCliRunner

from test_harness.protocol_verifier.tests import PVPerformanceResults

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
    with open(grok_file_path, 'r', encoding="utf-8") as file:
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
            [
                f"job_{i}",
                0.0 + i,
                "",
                1.0 + i,
                2.0 + i,
                3.0 + i,
                4.0 + i
            ]
            for i in range(10)
        ],
        index=[f"event_{i}" for i in range(10)],
        columns=PVPerformanceResults.data_fields
    )
