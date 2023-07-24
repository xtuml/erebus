# pylint: disable=C0103
# pylint: disable=R0801
"""Main flask runner for app
"""
import threading
import logging
import sys
import os

from test_harness import create_app, create_test_output_directory
from test_harness.config.config import HarnessConfig, TestConfig
from test_harness.process_manager import (
    harness_test_manager,
    puml_files_test,
    get_puml_file_paths
)
from test_harness.utils import clean_directories

logging.basicConfig(level=logging.INFO)


def run_harness_app(
    harness_config_path: HarnessConfig | None = None
) -> None:
    """Function to run test harness

    :param harness_config_path: Path to test harness config, defaults to `None`
    :type harness_config_path: :class:`HarnessConfig` | `None`, optional
    """
    harness_app = create_app(
        harness_config_path=harness_config_path
    )
    thread = threading.Thread(
        target=harness_app.run,
        kwargs={
            "debug": False,
            "port": 8800,
            "host": "0.0.0.0"
        }
    )
    thread.daemon = True
    thread.start()
    logging.getLogger().info("Test Harness Listener started")
    try:
        while True:
            if not harness_app.test_to_run:
                continue
            test_to_run: dict = harness_app.test_to_run
            harness_app.test_to_run = {}
            success, _ = harness_test_manager(
                harness_config=harness_app.harness_config,
                test_config=test_to_run["TestConfig"],
                test_output_directory=test_to_run[
                    "TestOutputDirectory"
                ]
            )
            if success:
                logging.getLogger().info(
                    "Test Harness test run completed successfully"
                )
    except KeyboardInterrupt:
        sys.exit()


def main(
    puml_file_paths: list[str] | None = None,
    harness_config_path: str | None = None,
    test_config_yaml_path: str | None = None,
    test_output_directory: str | None = None
) -> None:
    """Method to run test harness from command line

    :param puml_file_paths: List of puml file paths, defaults to `None`
    :type puml_file_paths: `list`[`str`] | `None`, optional
    :param harness_config_path: Path of the harness config, defaults to `None`
    :type harness_config_path: `str` | `None`, optional
    :param test_config_yaml_path: Path of the test config yaml, defaults to
    `None`
    :type test_config_yaml_path: `str` | `None`, optional
    :param test_output_directory: Directory to output tests report data into,
    defaults to `None`
    :type test_output_directory: `str` | `None`, optional
    :raises error: Raises an error if an error is raised in sub functions but
    cleans directories first before re-raising
    """
    harness_config = HarnessConfig(
        harness_config_path
    )
    test_config = TestConfig()
    if test_config_yaml_path:
        test_config.parse_from_yaml(test_config_yaml_path)
    if not test_output_directory:
        _, test_output_directory = create_test_output_directory(
            harness_config=harness_config
        )
        print(f"Saving output files in {test_output_directory}")
    if not puml_file_paths:
        puml_file_paths = get_puml_file_paths(
            harness_config.uml_file_store
        )
    try:
        puml_files_test(
            puml_file_paths=puml_file_paths,
            test_output_directory=test_output_directory,
            harness_config=harness_config,
            test_config=test_config
        )
    except Exception as error:
        clean_directories(
            [harness_config.log_file_store]
        )
        raise error


if __name__ == "__main__":
    args = sys.argv
    cli_harness_config_path = None
    if "--harness-config-path" in args:
        given_path = args[args.index("--harness-config-path")]
        if os.path.exists(given_path):
            cli_harness_config_path = given_path
        else:
            logging.getLogger().warning(
                "Given harness config path does not exist"
                ": %s",
                given_path
            )
    run_harness_app(
        harness_config_path=cli_harness_config_path
    )
