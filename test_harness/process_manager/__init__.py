# pylint: disable=W0718
# pylint: disable=R0801
"""Full end to end process manager"""
import logging
from typing import Literal
import traceback
import sys

from tqdm import tqdm

from test_harness.config.config import TestConfig, HarnessConfig

try:
    from test_harness.protocol_verifier import full_pv_test
    from test_harness.protocol_verifier.config.config import (
        ProtocolVerifierConfig,
    )
except Exception:
    pass
from test_harness.utils import clean_directories
from test_harness import AsyncTestStopper


def harness_test_manager(
    harness_config: HarnessConfig,
    test_config: TestConfig,
    test_output_directory: str,
    pbar: tqdm | None = None,
    test_stopper: AsyncTestStopper | None = None,
) -> tuple[Literal[True], Literal[""]] | tuple[Literal[False], str]:
    """Test Harness manager that trys to execute a test but if a failure is
    encounterd will log the error and return the error to the function user

    :param harness_config: The config for the test harness
    :type harness_config: :class:`ProtocolVerifierConfig`
    :param test_config: The config for the specific test
    :type test_config: :class:`TestConfig`
    :param test_output_directory: The directory where output files are stored
    :type test_output_directory: `str`
    :param pbar: A progress bar to update, defaults to `None`
    :type pbar: :class:`tqdm` | `None`, optional
    :param test_stopper: A test stopper object to stop the test, defaults to
    `None`
    :type test_stopper: :class:`AsyncTestStopper` | `None`, optional
    :return: Returns a tuple with
    * a boolean indicating whether the test executed incorrectly
    * a string representing the error message if there was one

    :rtype: `tuple`[:class:`Literal`[`True`], :class:`Literal`['']] |
    `tuple`[:class:`Literal`[`False`], `str`]
    """
    # TODO: add generic test to else statement
    try:
        if isinstance(harness_config, ProtocolVerifierConfig):
            full_pv_test(
                harness_config=harness_config,
                test_config=test_config,
                test_output_directory=test_output_directory,
                pbar=pbar,
                test_stopper=test_stopper,
            )
        else:
            pass
        return (True, "")

    except Exception as error:
        clean_directories(
            [
                harness_config.uml_file_store,
                harness_config.profile_store,
                harness_config.log_file_store,
                harness_config.test_file_store,
            ]
        )
        logging.getLogger().error(
            "Error was: %s; traceback to follow", str(error)
        )
        traceback.print_exc(file=sys.stdout)
        return (False, str(error))
