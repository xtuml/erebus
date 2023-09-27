# pylint: disable=R0801
"""Tests for __init__.py
"""

from pathlib import Path
import os
import glob
import re
import shutil

import responses
from aioresponses import aioresponses

from test_harness.config.config import TestConfig, HarnessConfig
from test_harness.process_manager import (
    harness_test_manager
)
from test_harness.utils import clean_directories

# get test config
test_config_path = os.path.join(
    Path(__file__).parent.parent,
    "config/test_config.config"
)

# get path of tests uml file
test_file_path = os.path.join(
    Path(__file__).parent.parent / "test_files",
    "test_uml_job_def.puml"
)

uuid4hex = re.compile(
            '[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}\\Z', re.I
        )


@responses.activate
def test_harness_test_manager_uml_exists() -> None:
    """Tests `harness_test_manager` when uml exists in the uml file store
    """
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    shutil.copy(test_file_path, harness_config.uml_file_store)
    with aioresponses() as mock:
        responses.get(
            url=harness_config.pv_clean_folders_url
        )
        responses.post(
            url=harness_config.pv_send_job_defs_url
        )
        mock.post(
            url=harness_config.pv_send_url,
            repeat=True
        )
        responses.get(
            url=harness_config.log_urls["aer"]["getFileNames"],
            json={
                "fileNames": ["Reception.log"]
            },
        )
        responses.post(
            url=harness_config.log_urls["aer"]["getFile"],
            body=b'test log',
        )
        responses.get(
            url=harness_config.log_urls["ver"]["getFileNames"],
            json={
                "fileNames": ["Verifier.log"]
            },
        )
        responses.post(
            url=harness_config.log_urls["ver"]["getFile"],
            body=b'test log',
        )
        success, _ = harness_test_manager(
            harness_config=harness_config,
            test_config=test_config,
            test_output_directory=harness_config.report_file_store
        )
    assert success
    files = glob.glob("*.*", root_dir=harness_config.report_file_store)
    expected_files = [
        "Results.csv", "Results.html", "Results.xml",
        "Results_Aggregated.html",
        "Verifier.log", "Reception.log",
    ]
    for file in files:
        file_in_files = file in expected_files
        is_uuid = bool(uuid4hex.match(
                file.replace("-", "").replace(".json", "")
            ))
        assert any([file_in_files, is_uuid])

    clean_directories([
        harness_config.report_file_store,
        harness_config.uml_file_store
    ])


def test_harness_test_manager_no_uml() -> None:
    """Tests `harness_test_manager` when uml does not exist in the uml file
    store
    """
    harness_config = HarnessConfig(test_config_path)
    test_config = TestConfig()
    success, message = harness_test_manager(
        harness_config=harness_config,
        test_config=test_config,
        test_output_directory=harness_config.report_file_store
    )
    assert not success
    assert message == "There are no puml files within the uml file store path"
