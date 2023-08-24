# pylint: disable=W0718
# pylint: disable=R0801
"""Full end to end process manager
"""
import glob
import os
import asyncio
import logging
from typing import Literal
import time

from test_harness.config.config import TestConfig, HarnessConfig
from test_harness.process_manager.generate_test_files import (
    generate_test_events_from_puml_files
)
from test_harness.process_manager.send_job_defs import send_job_defs_from_uml
from test_harness.process_manager.tests import FunctionalTest, PerformanceTest


def harness_test_manager(
    harness_config: HarnessConfig,
    test_config: TestConfig,
    test_output_directory: str
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
        puml_file_paths = get_puml_file_paths(
            harness_config.uml_file_store
        )

        puml_files_test(
            puml_file_paths=puml_file_paths,
            test_output_directory=test_output_directory,
            harness_config=harness_config,
            test_config=test_config
        )
        return (True, "")

    except Exception as error:
        logging.getLogger().error(
            str(error)
        )
        return (False, str(error))


def puml_files_test(
    puml_file_paths: list[str],
    test_output_directory: str,
    harness_config: HarnessConfig,
    test_config: TestConfig
) -> None:
    """Method to perform and end to end test

    :param puml_file_paths: List of puml file paths to include in the test
    :type puml_file_paths: `list`[`str`]
    :param test_output_directory: The directory where output files are stored
    :type test_output_directory: `str`
    :param harness_config: The config for the test harness
    :type harness_config: :class:`HarnessConfig`
    :param test_config: The config for the specific test
    :type test_config: :class:`TestConfig`
    """
    # generate the test files with the test config
    test_events = generate_test_events_from_puml_files(
        puml_file_paths,
        test_config
    )

    # send job definitions to pv
    send_job_defs_from_uml(
        url=harness_config.pv_send_job_defs_url,
        uml_file_paths=puml_file_paths,
        harness_config=harness_config
    )
    logging.getLogger().info(
        "Waiting %ds for job defs to load",
        harness_config.pv_config_update_time
    )
    time.sleep(harness_config.pv_config_update_time)

    # choose test from test config and run test
    test_class = (
        FunctionalTest if test_config.type == "Functional"
        else PerformanceTest
    )

    # perform the test
    test = test_class(
        test_file_generators=test_events,
        harness_config=harness_config,
        test_config=test_config,
        test_output_directory=test_output_directory
    )
    logging.getLogger().info(
        "Beggining test"
    )
    asyncio.run(test.run_test())
    # calculate results
    logging.getLogger().info(
        "Post processing results"
    )
    test.calc_results()
    # clean directories ready for next test
    logging.getLogger().info(
        "Cleaning Test Harness and PV directories"
    )
    test.clean_directories()


def get_puml_file_paths(
    uml_file_store_path: str
) -> list[str]:
    """Method to get the file paths of puml files from the uml file store.
    Raises an exception if there are no files in the uml store

    :param uml_file_store_path: The path to the uml file store
    :type uml_file_store_path: `str`
    :raises RuntimeError: Raises a :class:`RuntimeError` if no files are
    present in the uml file store
    :return: Returns a list of the uml file paths
    :rtype: `list`[`str`]
    """
    puml_file_paths = [
        os.path.join(uml_file_store_path, file_name)
        for file_name in
        glob.glob("*.*", root_dir=uml_file_store_path)
    ]
    if not puml_file_paths:
        raise RuntimeError(
            "There are no puml files within the uml file store path"
        )
    return puml_file_paths
