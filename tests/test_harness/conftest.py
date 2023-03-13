"""
Fixtures for Test Harness
"""

import sys
from os.path import abspath
from pathlib import Path

import pytest
from flask import Flask
# insert root directory into path
package_path = abspath(Path(__file__).parent.parent.parent)
sys.path.insert(0, package_path)
from test_harness.__init__ import create_app # noqa


@pytest.fixture()
def app():
    app = create_app()
    app.config.update(
        {
            "TESTING": True
        }
    )

    yield app


@pytest.fixture()
def client(app: Flask):
    return app.test_client()


@pytest.fixture()
def runner(app: Flask):
    return app.test_cli_runner()
