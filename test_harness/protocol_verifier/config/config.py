"""
Config class for the Protocol Verifier
"""

from configparser import ConfigParser

from test_harness.config.config import HarnessConfig


class ProtocolVerifierConfig(HarnessConfig):
    """Class to hold the config for the Protocol Verifier

    :param config_parser: holds a ConfigParser object
    :type config_parser: :class: ConfigParser
    """

    def __init__(self, config_parser: ConfigParser) -> None:
        # Initialise HarnessConfig to inherit attributes
        super().__init__(config_parser)

        self.config_parser = ConfigParser()
        self.parse_pv_config()

    def parse_pv_config(self):
        """
        Read from config file and set attributes
        """
        self.parse_pv_config_to_attributes()

    def parse_pv_config_to_attributes(self):
        """Method to set attributes from config file"""
        self.parse_log_retrieval_config()
        self.parse_pv_message_bus_config()
        self.pv_send_job_defs_url = self.config_parser["protocol-verifier"][
            "pv_send_job_defs_url"
        ]
        self.pv_config_update_time = int(
            self.config_parser["protocol-verifier"]["pv_config_update_time"]
        )
        self.pv_clean_folders_url = self.config_parser["protocol-verifier"][
            "pv_clean_folders_url"
        ]
        self.pv_clean_folders_read_timeout = int(
            self.config_parser["protocol-verifier"][
                "pv_clean_folders_read_timeout"
            ]
        )
        self.pv_test_timeout = int(
            self.config_parser["protocol-verifier"]["pv_test_timeout"]
        )

    def parse_log_retrieval_config(self):
        """Method to parse log retrieval config from config file"""
        self.pv_finish_interval = int(
            self.config_parser["protocol-verifier"]["pv_finish_interval"]
        )
        self.log_calc_interval_time = int(
            self.config_parser["protocol-verifier"]["log_calc_interval_time"]
        )
        self.log_urls = {
            "aer": {
                "getFile": self.config_parser["protocol-verifier"][
                    "get_log_file_url"
                ],
                "getFileNames": self.config_parser["protocol-verifier"][
                    "get_log_file_names_url"
                ],
                "location": "RECEPTION",
                "prefix": self.config_parser["protocol-verifier"][
                    "aer_log_file_prefix"
                ],
            },
            "ver": {
                "getFile": self.config_parser["protocol-verifier"][
                    "get_log_file_url"
                ],
                "getFileNames": self.config_parser["protocol-verifier"][
                    "get_log_file_names_url"
                ],
                "location": "VERIFIER",
                "prefix": self.config_parser["protocol-verifier"][
                    "ver_log_file_prefix"
                ],
            },
            "location": {
                "getFile": self.config_parser["protocol-verifier"][
                    "get_log_file_url"
                ],
                "getFileNames": self.config_parser["protocol-verifier"][
                    "get_log_file_names_url"
                ],
            },
        }
        self.pv_grok_exporter_url = self.config_parser["protocol-verifier"][
            "pv_grok_exporter_url"
        ]

    def parse_pv_message_bus_config(self) -> None:
        """Method to parse message bus config from config file"""
        pv_send_as_pv_bytes_raw = self.config_parser["protocol-verifier"][
            "pv_send_as_pv_bytes"
        ]
        send_json_without_length_prefix_raw = self.config_parser[
            "protocol-verifier"
        ]["send_json_without_length_prefix"]
        self.pv_send_as_pv_bytes = (
            True if pv_send_as_pv_bytes_raw.lower() == "true" else False
        )
        self.send_json_without_length_prefix = (
            True
            if send_json_without_length_prefix_raw.lower() == "true"
            else False
        )
        match self.message_bus_protocol:
            case "KAFKA" | "KAFKA3":
                self.pv_send_as_pv_bytes = True
            case "HTTP":
                self.pv_send_url = self.config_parser["protocol-verifier"][
                    "pv_send_url"
                ]
            case _:
                raise ValueError(
                    f"Invalid message bus protocol \
                        '{self.message_bus_protocol}'"
                )


if __name__ == "__main__":
    pv_config = ProtocolVerifierConfig()
    print(pv_config.config_path)
    print("done")
