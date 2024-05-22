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
        config_path: Optional[str] = None,
        store_config_path: Optional[str] = None,
    ) -> None:
        """Constructor method"""
        self.config_path = config_path
        self.store_config_path = store_config_path
        self.config_parser = ConfigParser()
        self.parse_config()

    def parse_config(self):
        """Method to parse the config. Defaults to
        default_config.config in same directory
        """
        if not self.config_path:
            self.config_path = str(Path(__file__).parent / "default_config.config")
        if not self.store_config_path:
            self.store_config_path = str(Path(__file__).parent / "store_config.config")
        self.config_parser.read([self.config_path, self.store_config_path])
        self.parse_config_to_attributes()

    def parse_config_to_attributes(self) -> None:
        """Method to parse config to attributes"""
        # parse uml file store
        uml_file_store_path = self.config_parser["non-default"]["uml_file_store"]
        self.uml_file_store = self.calc_path(uml_file_store_path, "uml_file_store")
        # parse uml file store
        profile_store_path = self.config_parser["non-default"]["profile_store"]
        self.profile_store = self.calc_path(profile_store_path, "profile_store")
        # parse report filestore path
        report_file_store_path = self.config_parser["non-default"]["report_file_store"]
        self.report_file_store = self.calc_path(
            report_file_store_path, "report_file_store"
        )
        # parse log filestore path
        log_file_store_path = self.config_parser["non-default"]["log_file_store"]
        self.log_file_store = self.calc_path(log_file_store_path, "log_file_store")
        # parse test filestore path
        test_file_store_path = self.config_parser["non-default"]["test_file_store"]
        self.test_file_store = self.calc_path(test_file_store_path, "test_file_store")

        # parse config for request to server
        self.parse_requests_config()
        # parse config for message bus
        self.parse_message_bus_config()
        # parse config for kafka metrics
        self.parse_kafka_metrics_config()

    def parse_kafka_metrics_config(self) -> None:
        """Method to parse kafka metrics config from config file"""
        # flag to get metrics from kafka
        metrics_from_kafka_raw = self.config_parser["non-default"]["metrics_from_kafka"]
        self.metrics_from_kafka = (
            True if metrics_from_kafka_raw.lower() == "true" else False
        )
        self.kafka_metrics_host = self.config_parser["non-default"][
            "kafka_metrics_host"
        ]
        self.kafka_metrics_topic = self.config_parser["non-default"][
            "kafka_metrics_topic"
        ]
        self.kafka_metrics_collection_interval = int(
            self.config_parser["non-default"]["kafka_metrics_collection_interval"]
        )

    def parse_message_bus_config(self) -> None:
        """Method to parse message bus config from config file"""
        message_bus_protocol = self.config_parser["non-default"][
            "message_bus_protocol"
        ].upper()
        match message_bus_protocol:
            case "KAFKA" | "KAFKA3":
                self.message_bus_protocol = message_bus_protocol
                self.kafka_message_bus_host = self.config_parser["non-default"][
                    "kafka_message_bus_host"
                ]
                self.kafka_message_bus_topic = self.config_parser["non-default"][
                    "kafka_message_bus_topic"
                ]
            case "HTTP":
                self.message_bus_protocol = message_bus_protocol
            case _:
                raise ValueError(
                    f"Invalid message bus protocol '{message_bus_protocol}'"
                )
        # else:
        #     self.message_bus_protocol = "HTTP"
        #     self.pv_send_url = self.config_parser["non-default"][
        #         "pv_send_url"
        #     ]

    def parse_requests_config(self) -> None:
        """Method to parse requests to pv server config"""
        self.requests_max_retries = int(
            self.config_parser["non-default"]["requests_max_retries"]
        )
        self.requests_timeout = int(
            self.config_parser["non-default"]["requests_timeout"]
        )

    @staticmethod
    def calc_path(given_path: str, config_field: str) -> str:
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
            calculated_path = str(Path(__file__).parent.parent.parent / given_path)
        if not os.path.exists(calculated_path):
            raise RuntimeError(
                f"The given path '{given_path}' does not exist for the config "
                f"field '{config_field}'"
            )
        return calculated_path


class TestConfig:
    """Class to hold test configuration"""

    def __init__(self) -> None:
        self.set_default_config()

    # TODO: parse config in yaml file
    def parse_from_yaml(self, yaml_file_path: str) -> None:
        """Method to parse test config from a yaml file

        :param yaml_file_path: The path to the yaml file
        :type yaml_file_path: `str`
        """
        with open(yaml_file_path, "r", encoding="utf-8") as file:
            test_config = yaml.safe_load(file)
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
                "save_logs": `bool`, defaults to `True`;
                "job_event_gap": `int` => 0, defaults to 1;
                "round_robin": `bool`, defaults to `False`;
            },
            "functional_options": `dict`, {
                "log_domain": "ver" | "aer", defaults to "ver";
            },
            "num_workers": `int` => 0, defaults to 0;
            "aggregate_during": `bool`, defaults to `False`;
            "sample_rate": `int` => 0, defaults to 0;
            "low_memory": `bool`, defaults to `False`;
            "test_finish": `dict`, {
                "metric_get_interval": `int` => 0, defaults to 5;
                "finish_interval": `int` => 0, defaults to 30;
                "timeout": `int` => 0, defaults to 120;
            },
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
        """Method to set default config options"""
        self.type = "Functional"
        self.max_different_sequences = 200
        self.event_gen_options = {
            "solution_limit": 100,
            "max_sol_time": 120,
            "invalid": True,
        }
        self.performance_options = {
            "num_files_per_sec": 100,
            "shard": False,
            "total_jobs": 10000,
            "save_logs": True,
            "job_event_gap": 1,
            "round_robin": False,
        }
        self.functional_options = {"log_domain": "ver"}
        self.num_workers = 0
        self.aggregate_during = False
        self.sample_rate = 0
        self.low_memory = False
        self.test_finish = {}

    def config_to_dict(self) -> dict:
        """Provide config as a dictionary"""
        config_dict_to_return = {
            "type": self.type,
            "max_different_sequences": 200,
            "event_gen_options": self.event_gen_options,
            "num_workers": self.num_workers,
            "aggregate_during": self.aggregate_during,
            "sample_rate": self.sample_rate,
            "low_memory": self.low_memory,
            "test_finish": self.test_finish,
        }
        if self.type != "Functional":
            config_dict_to_return["performance_options"] = self.performance_options
        else:
            config_dict_to_return["functional_options"] = self.functional_options
        return config_dict_to_return


if __name__ == "__main__":
    config = HarnessConfig()
    print("Done")
