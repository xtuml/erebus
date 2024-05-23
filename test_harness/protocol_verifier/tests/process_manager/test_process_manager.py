# pylint: disable=R0801
"""Tests for test_harness.process_manager.__init__.py"""

from pathlib import Path
import os
import glob
import re
import shutil

import responses

from test_harness.config.config import TestConfig
from test_harness.protocol_verifier.config.config import ProtocolVerifierConfig
from test_harness.process_manager import harness_test_manager
from test_harness.utils import clean_directories
from test_harness.protocol_verifier.mocks.mock_pv_http_interface import (
    mock_pv_http_interface,
)

# get test config
test_config_path = os.path.join(
    Path(__file__).parent.parent, "config/test_config.config"
)

# get path of tests uml file
test_file_path = os.path.join(
    Path(__file__).parent.parent / "test_files", "test_uml_job_def.puml"
)

uuid4hex = re.compile("[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}\\Z", re.I)


@responses.activate
def test_harness_test_manager_uml_exists() -> None:
    """Tests `harness_test_manager` when uml exists in the uml file store"""
    harness_config = ProtocolVerifierConfig(test_config_path)
    test_config = TestConfig()
    shutil.copy(test_file_path, harness_config.uml_file_store)
    with mock_pv_http_interface(harness_config):
        success, _ = harness_test_manager(
            harness_config=harness_config,
            test_config=test_config,
            test_output_directory=harness_config.report_file_store,
        )
    assert success
    files = glob.glob("*.*", root_dir=harness_config.report_file_store)
    expected_files = [
        "Results.csv",
        "Results.html",
        "Results.xml",
        "Results_Aggregated.html",
        "Verifier.log",
        "Reception.log",
    ]
    for file in files:
        file_in_files = file in expected_files
        is_uuid = bool(
            uuid4hex.match(file.replace("-", "").replace(".json", ""))
        )
        assert any([file_in_files, is_uuid])

    clean_directories(
        [harness_config.report_file_store, harness_config.uml_file_store]
    )


def test_harness_test_manager_no_uml() -> None:
    """Tests `harness_test_manager` when uml does not exist in the uml file
    store
    """
    harness_config = ProtocolVerifierConfig(test_config_path)
    test_config = TestConfig()
    success, message = harness_test_manager(
        harness_config=harness_config,
        test_config=test_config,
        test_output_directory=harness_config.report_file_store,
    )
    assert not success
    assert message == "There are no puml files within the uml file store path"
