# pylint: disable=W0718
# pylint: disable=R0801
"""Full end to end process manager
"""
import logging
from typing import Literal
import traceback
import sys
from multiprocessing import Value as multiValue

from test_harness.config.config import TestConfig, HarnessConfig
from test_harness.protocol_verifier import full_pv_test
from test_harness.utils import clean_directories


def harness_test_manager(
    harness_config: HarnessConfig,
    test_config: TestConfig,
    test_output_directory: str,
    is_test_running: multiValue
) -> tuple[Literal[True], Literal['']] | tuple[Literal[False], str]:
    """Test Harness manager that trys to execute a test but if a failure is
    encounterd will log the error and return the error to the function user

    :param harness_config: The config for the test harness
    :type harness_config: :class:`HarnessConfig`
    :param test_config: The config for the specific test
    :type test_config: :class:`TestConfig`
    :param test_output_directory: The directory where output files are stored
    :type test_output_directory: `str`
    :return: Returns a tuple with
    * a boolean indicating whether the test executed incorrectly
    * a string representing the error message if there was one

    :rtype: `tuple`[:class:`Literal`[`True`], :class:`Literal`['']] |
    `tuple`[:class:`Literal`[`False`], `str`]
    """
    try:
        full_pv_test(
            harness_config=harness_config,
            test_config=test_config,
            test_output_directory=test_output_directory,
            is_test_running=is_test_running
        )
        return (True, "")

    except Exception as error:
        clean_directories([
            harness_config.uml_file_store,
            harness_config.profile_store,
            harness_config.log_file_store,
            harness_config.test_file_store
        ])
        logging.getLogger().error(
            "Error was: %s; traceback to follow",
            str(error)
        )
        traceback.print_exc(file=sys.stdout)
        return (False, str(error))
