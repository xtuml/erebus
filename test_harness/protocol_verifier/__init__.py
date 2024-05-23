# pylint: disable=W0718
# pylint: disable=R0801
# pylint: disable=R0913
"""Full end to end process manager"""
import glob
import os
import asyncio
import logging
import time

from tqdm import tqdm

from test_harness.config.config import TestConfig
from test_harness.protocol_verifier.config.config import ProtocolVerifierConfig
from test_harness.protocol_verifier.generate_test_files import (
    generate_test_events_from_puml_files,
    get_test_events_from_test_file_jsons,
)
from test_harness.protocol_verifier.send_job_defs import send_job_defs_from_uml
from test_harness.protocol_verifier.tests import (
    FunctionalTest,
    PerformanceTest,
)
from test_harness.simulator.simulator_profile import Profile
from test_harness import AsyncTestStopper


def full_pv_test(
    harness_config: ProtocolVerifierConfig,
    test_config: TestConfig,
    test_output_directory: str,
    pbar: tqdm | None = None,
    test_stopper: AsyncTestStopper | None = None,
) -> None:
    """Full protocol verifier test for the config provided

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
    """
    # select stores to use based on test output directory contents
    store_paths = select_store_paths(test_output_directory, harness_config)

    profile = get_test_profile(store_paths["profile_store"])

    test_file_paths = get_test_file_paths(store_paths["test_file_store"])

    puml_file_paths = get_puml_file_paths(store_paths["uml_file_store"])

    puml_files_test(
        puml_file_paths=puml_file_paths,
        test_output_directory=test_output_directory,
        harness_config=harness_config,
        test_config=test_config,
        profile=profile,
        test_file_paths=test_file_paths,
        pbar=pbar,
        test_stopper=test_stopper,
    )


def puml_files_test(
    puml_file_paths: list[str],
    test_output_directory: str,
    harness_config: ProtocolVerifierConfig,
    test_config: TestConfig,
    profile: Profile | None = None,
    test_file_paths: list[str] | None = None,
    pbar: tqdm | None = None,
    test_stopper: AsyncTestStopper | None = None,
) -> None:
    """Method to perform and end to end test

    :param puml_file_paths: List of puml file paths to include in the test
    :type puml_file_paths: `list`[`str`]
    :param test_output_directory: The directory where output files are stored
    :type test_output_directory: `str`
    :param harness_config: The config for the test harness
    :type harness_config: :class:`ProtocolVerifierConfig`
    :param test_config: The config for the specific test
    :type test_config: :class:`TestConfig`
    :param profile: Profile created from an uploaded file, defults to `None`
    :type profile: :class:`Profile` | `None`, optional
    :param test_file_paths: list of test file paths, defults to `None`
    :type test_file_paths: `list`[`str`] | `None`, optional
    :param pbar: A progress bar to update, defaults to `None`
    :type pbar: :class:`tqdm` | `None`, optional
    :param test_stopper: A test stopper object to stop the test, defaults to
    `None`
    :type test_stopper: :class:`AsyncTestStopper` | `None`, optional
    """
    # choose test from test config and run test
    test_class = (
        FunctionalTest if test_config.type == "Functional" else PerformanceTest
    )
    if test_class == FunctionalTest and profile:
        profile = None
        logging.getLogger().warning(
            "Input profile file will not be used as the test is functional"
        )

    # generate the test files with the test config
    if test_file_paths:
        test_events = get_test_events_from_test_file_jsons(
            test_file_paths=test_file_paths
        )
    else:
        try:
            test_events = generate_test_events_from_puml_files(
                puml_file_paths, test_config
            )
        except ImportError:
            raise ImportError(
                "The test_event_generator package is required to generate "
                "test files from puml files. Either reinstall or rebuild the "
                "test harness with the test_event_generator package or upload "
                "test files jsons as well as a puml file"
            )

    # send job definitions to pv
    send_job_defs_from_uml(
        url=harness_config.pv_send_job_defs_url,
        uml_file_paths=puml_file_paths,
        harness_config=harness_config,
    )
    logging.getLogger().info(
        "Waiting %ds for job defs to load",
        harness_config.pv_config_update_time,
    )
    time.sleep(harness_config.pv_config_update_time)

    # perform the test
    test = test_class(
        test_file_generators=test_events,
        harness_config=harness_config,
        test_config=test_config,
        test_output_directory=test_output_directory,
        test_profile=profile,
        pbar=pbar,
        test_graceful_kill_functions=(
            [test_stopper.stop] if test_stopper else None
        ),
    )
    logging.getLogger().info("Beggining test")
    asyncio.run(test.run_test())
    # calculate results
    logging.getLogger().info("Post processing results")
    test.calc_results()
    # grab all remaining log files
    test.get_all_remaining_log_files()
    # save pv log files to output folder
    test.save_log_files_to_test_output_directory()
    # clean directories ready for next test
    logging.getLogger().info("Cleaning Test Harness and PV directories")
    test.clean_directories()


def get_puml_file_paths(uml_file_store_path: str) -> list[str]:
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
        for file_name in glob.glob("*.*", root_dir=uml_file_store_path)
    ]
    if not puml_file_paths:
        raise RuntimeError(
            "There are no puml files within the uml file store path"
        )
    return puml_file_paths


def get_test_profile(profile_store_path: str) -> Profile | None:
    """Method to get the profile file and load it from the profile store

    :param profile_store_path: The path of the profile store
    :type profile_store_path: `str`
    :raises RuntimeError: Raises a :class:`RuntimeError` when too many profile
    files have been uploaded
    :return: Returns a profile created from the uploaded file and `None` if
    there were no files
    :rtype: :class:`Profile` | `None`
    """
    profile_paths = [
        os.path.join(profile_store_path, file_name)
        for file_name in glob.glob("*.*", root_dir=profile_store_path)
    ]
    if len(profile_paths) > 1:
        raise RuntimeError(
            "Too many profiles were uploaded. Only one profile can be uploaded"
        )
    if not profile_paths:
        return None
    # load the csv file as a DataFrame
    profile = Profile()
    profile.load_raw_profile_from_file_path(profile_paths[0])
    return profile


def get_test_file_paths(test_file_store_path: str) -> list[str] | None:
    """Method to return the paths of the uploaded test file if there are any

    :param test_file_store_path: The path of the test file store
    :type test_file_store_path: `str`
    :return: Returns a list of test file paths or `None` if none exist in the
    given store path
    :rtype: `list`[`str`] | `None`
    """
    test_file_paths = get_all_file_paths_in_folder(test_file_store_path)
    if test_file_paths:
        return test_file_paths
    return None


def get_all_file_paths_in_folder(folder_path: str) -> list[str]:
    """Method to get all file paths in a given folder

    :param folder_path: The path of the folder
    :type folder_path: `str`
    :return: Returns the list of file paths
    :rtype: `list`[`str`]
    """
    file_paths = [
        os.path.join(folder_path, file_name)
        for file_name in glob.glob("*.*", root_dir=folder_path)
    ]
    return file_paths


def select_store_paths(
    test_output_directory: str, harness_config: ProtocolVerifierConfig
) -> dict[str, str]:
    """Method to select the store paths to use based on the contents of the
    test output directory

    :param test_output_directory: The directory where output files are stored
    :type test_output_directory: `str`
    :param harness_config: The config for the test harness
    :type harness_config: :class:`ProtocolVerifierConfig`
    :return: Returns a dictionary of the store paths to use
    :rtype: `dict`[`str`, `str`]
    """
    store_paths = {}
    for folder in ["uml_file_store", "test_file_store", "profile_store"]:
        store_path = os.path.join(test_output_directory, folder)
        if os.path.exists(store_path):
            store_paths[folder] = store_path
        else:
            store_paths[folder] = getattr(harness_config, folder)
    return store_paths
