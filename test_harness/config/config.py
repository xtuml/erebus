"""
Config class for test harness
"""
import os
from typing import Optional
from configparser import ConfigParser
from pathlib import Path

import yaml


class HarnessConfig:
    """Class to hold the config for the Test Harness

    :param config_path: The path to the config file, defaults to None
    :type config_path: Optional[str], optional
    """
    def __init__(
        self,
        config_path: Optional[str] = None
    ) -> None:
        """Constructor method
        """
        self.config_path = config_path
        self.config_parser = ConfigParser()
        self.parse_config()

    def parse_config(self):
        """Method to parse the config. Defaults to
        default_config.config in same directory
        """
        if not self.config_path:
            self.config_path = str(
                Path(__file__).parent / "default_config.config"
            )
        self.config_parser.read(self.config_path)
        self.parse_config_to_attributes()

    def parse_config_to_attributes(self) -> None:
        """Method to parse config to attributes
        """
        # parse uml file store
        uml_file_store_path = self.config_parser[
            "non-default"
        ]["uml_file_store"]
        self.uml_file_store = self.calc_path(
            uml_file_store_path,
            "uml_file_store"
        )
        # parse report filestore path
        report_file_store_path = self.config_parser[
            "non-default"
        ]["report_file_store"]
        self.report_file_store = self.calc_path(
            report_file_store_path,
            "report_file_store"
        )
        # parse log filestore path
        log_file_store_path = self.config_parser[
            "non-default"
        ]["log_file_store"]
        self.log_file_store = self.calc_path(
            log_file_store_path,
            "report_file_store"
        )
        # parse config for request to server
        self.parse_requests_config()
        # parse config for io tracking
        self.parse_io_tracking_config()
        # parse config log retrieval
        self.parse_log_retrieval_config()
        # max files in memory
        self.max_files_in_memory = int(self.config_parser[
            "non-default"
        ]["max_files_in_memory"])
        # url send pv files
        self.pv_send_url = self.config_parser[
            "non-default"
        ]["pv_send_url"]
        self.pv_send_job_defs_url = self.config_parser[
            "non-default"
        ]["pv_send_job_defs_url"]
        self.pv_config_update_time = int(self.config_parser[
            "non-default"
        ]["pv_config_update_time"])

    def parse_requests_config(self) -> None:
        """Method to parse requests to pv server config
        """
        self.requests_max_retries = int(self.config_parser[
            "non-default"
        ]["requests_max_retries"])
        self.requests_timeout = int(self.config_parser[
            "non-default"
        ]["requests_timeout"])

    def parse_io_tracking_config(self):
        self.io_calc_interval_time = int(self.config_parser[
            "non-default"
        ]["io_calc_interval_time"])
        aer_io_url = self.config_parser[
            "non-default"
        ]["aer_io_url"]
        ver_io_url = self.config_parser[
            "non-default"
        ]["ver_io_url"]
        self.io_urls = {
            "aer": aer_io_url,
            "ver": ver_io_url,
        }

    def parse_log_retrieval_config(self):
        self.pv_finish_interval = int(self.config_parser[
            "non-default"
        ]["pv_finish_interval"])
        self.log_calc_interval_time = int(self.config_parser[
            "non-default"
        ]["log_calc_interval_time"])
        self.log_urls = {
            "aer": {
                "getFile": self.config_parser[
                    "non-default"
                ]["aer_get_file_url"],
                "getFileNames": self.config_parser[
                    "non-default"
                ]["aer_get_file_names_url"]
            },
            "ver": {
                "getFile": self.config_parser[
                    "non-default"
                ]["ver_get_file_url"],
                "getFileNames": self.config_parser[
                    "non-default"
                ]["ver_get_file_names_url"]
            }
        }

    @staticmethod
    def calc_path(
        given_path: str,
        config_field: str
    ) -> str:
        """Method to get the absolute path given either an absolute or
        relative path

        :param given_path: The path given
        :type given_path: `str`
        :param config_field: The config field
        :type config_field: `str`
        :raises RuntimeError: Raises a :class:`RuntimeError` is the path
        doesn't exist
        :return: Returns the calculated absolute path
        :rtype: `str`
        """
        if os.path.isabs(given_path):
            calculated_path = given_path
        else:
            calculated_path = str(
                Path(
                    __file__
                ).parent.parent.parent / given_path
            )
        if not os.path.exists(calculated_path):
            raise RuntimeError(
                f"The given path '{given_path}' does not exist for the config "
                f"field '{config_field}'"
            )
        return calculated_path


class TestConfig:
    """Class to hold test configuration
    """
    def __init__(self) -> None:
        self.set_default_config()

    # TODO: parse config in yaml file
    def parse_from_yaml(self, yaml_file_path: str) -> None:
        """Method to parse test config from a yaml file

        :param yaml_file_path: The path to the yaml file
        :type yaml_file_path: `str`
        """
        with open(yaml_file_path, 'r', encoding="utf-8") as file:
            test_config = yaml.safe_load(
                file
            )
        self.parse_from_dict(test_config)

    def parse_from_dict(self, test_config: dict[str, str | dict]) -> None:
        """Method to update the config from a test config dictionary

        :param test_config: Dictionary holding test config options.
        Can accept the following dictionary and parameters:
        {
            "type": `str`, "Functional" | "Performance";
            "max_different_sequences": `int` => 0,
            "event_gen_options" : `dict`, {
                "solution_limit": `int` => 0, defaults 100;
                "max_sol_time": `int` => 0, defaults 120;
                "invalid": `bool`, defaults True;
                "invalid_types", `list`[
                    "StackedSolutions" | "MissingEvents" | "MissingEdges" |
                    "GhostEvents" | "SpyEvents" | "XORConstraintBreaks" |
                    "ANDConstraintBreaks"
                ], optional
            },
            "performance_options": `dict`, {
                "num_files_per_sec": `int` > 0, defaults to 100;
                "shard": `bool`, defaults to `False`;
                "total_jobs": `int` => 0, defaults to 10000;
            }
        }
        :type test_config: `dict`[`str`, `str` | `dict`]
        """
        for attr_name in vars(self).keys():
            if attr_name not in test_config:
                continue
            if isinstance(test_config[attr_name], dict):
                for option, option_value in test_config[attr_name].items():
                    getattr(self, attr_name)[option] = option_value
            else:
                setattr(self, attr_name, test_config[attr_name])

    def set_default_config(self) -> None:
        """Method to set default config options
        """
        self.type = "Functional"
        self.max_different_sequences = 200
        self.event_gen_options = {
            "solution_limit": 100,
            "max_sol_time": 120,
            "invalid": True
        }
        self.performance_options = {
            "num_files_per_sec": 100,
            "shard": False,
            "total_jobs": 10000,
        }

    def config_to_dict(self) -> dict:
        config_dict_to_return = {
            "type": self.type,
            "max_different_sequences": 200,
            "event_gen_options": self.event_gen_options
        }
        if self.type != "Functional":
            config_dict_to_return["performance_options"] = (
                self.performance_options
            )
        return config_dict_to_return


if __name__ == "__main__":
    config = HarnessConfig()
    print("Done")
