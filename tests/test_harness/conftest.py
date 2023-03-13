# pylint: disable=redefined-outer-name
# pylint: disable=C0413
"""
Fixtures for Test Harness
"""

import sys
from os.path import abspath
from pathlib import Path
from typing import Generator

import pytest
from flask import Flask
from flask.testing import FlaskClient, FlaskCliRunner
# insert root directory into path
package_path = abspath(Path(__file__).parent.parent.parent)
sys.path.insert(0, package_path)
from test_harness.__init__ import create_app # noqa


@pytest.fixture()
def test_app() -> Generator[Flask, None, None]:
    """Fixture to create app for testing

    :yield: Yields the Flask app
    :rtype: :class:`Generator`[:class:`Flask`, None, None]
    """
    app = create_app()
    app.config.update(
        {
            "TESTING": True
        }
    )

    yield app


@pytest.fixture()
def client(test_app: Flask) -> FlaskClient:
    """Fixture to create the Flask test client

    :param test_app: The flask app to be tested
    :type test_app: :class:`Flask`
    :return: Flask test client
    :rtype: :class:`FlaskClient`
    """
    return test_app.test_client()


@pytest.fixture()
def runner(test_app: Flask) -> FlaskCliRunner:
    """Fixture to create the runner for the test client

    :param test_app: The flask app to be tested
    :type test_app: :class:`Flask`
    :return: Flask test client runner
    :rtype: :class:`FlaskCliRunner`
    """
    return test_app.test_cli_runner()
