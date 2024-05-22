<<<<<<< HEAD
from configparser import ConfigParser
from pathlib import Path
import sys
=======
import sys
from configparser import ConfigParser
from pathlib import Path
>>>>>>> 6251c3e (update config.py)
from typing import Optional

# Determine the project root and add it to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
<<<<<<< HEAD

=======
>>>>>>> 6251c3e (update config.py)
from test_harness.config.config import HarnessConfig


class ProtocolVerifierConfig(HarnessConfig):
    def __init__(self, config_path: Optional[str] = None) -> None:
<<<<<<< HEAD
        # Initialize the parent class
=======
        # Initialise HarnessConfig to inherit attributes
>>>>>>> 6251c3e (update config.py)
        super().__init__(config_path)

        self.config_parser = ConfigParser()
        self.config_path = config_path
        self.parse_pv_config()

    def parse_pv_config(self):
        if self.config_path is None:
            self.config_path = str(Path(__file__).parent / "default_config.config")
        self.config_parser.read(self.config_path)
        self.parse_pv_config_to_attributes()

    def parse_pv_config_to_attributes(self):
<<<<<<< HEAD
        # parse config log retrieval
        self.parse_log_retrieval_config()
        # message bus
        self.parse_pv_message_bus_config()
        # url send pv job defs
=======
        self.parse_log_retrieval_config()
        self.parse_pv_message_bus_config()
>>>>>>> 6251c3e (update config.py)
        self.pv_send_job_defs_url = self.config_parser["non-default"][
            "pv_send_job_defs_url"
        ]
        self.pv_config_update_time = int(
            self.config_parser["non-default"]["pv_config_update_time"]
        )
        self.pv_clean_folders_url = self.config_parser["non-default"][
            "pv_clean_folders_url"
        ]
        self.pv_clean_folders_read_timeout = int(
            self.config_parser["non-default"]["pv_clean_folders_read_timeout"]
        )
<<<<<<< HEAD
        # test timeout
        self.pv_test_timeout = int(self.config_parser["non-default"]["pv_test_timeout"])

    def parse_log_retrieval_config(self):
        """TODO docstring."""
=======
        self.pv_test_timeout = int(self.config_parser["non-default"]["pv_test_timeout"])

    def parse_log_retrieval_config(self):
        """Method to parse log retrieval config from config file"""
>>>>>>> 6251c3e (update config.py)
        self.pv_finish_interval = int(
            self.config_parser["non-default"]["pv_finish_interval"]
        )
        self.log_calc_interval_time = int(
            self.config_parser["non-default"]["log_calc_interval_time"]
        )
        self.log_urls = {
            "aer": {
                "getFile": self.config_parser["non-default"]["get_log_file_url"],
                "getFileNames": self.config_parser["non-default"][
                    "get_log_file_names_url"
                ],
                "location": "RECEPTION",
                "prefix": self.config_parser["non-default"]["aer_log_file_prefix"],
            },
            "ver": {
                "getFile": self.config_parser["non-default"]["get_log_file_url"],
                "getFileNames": self.config_parser["non-default"][
                    "get_log_file_names_url"
                ],
                "location": "VERIFIER",
                "prefix": self.config_parser["non-default"]["ver_log_file_prefix"],
            },
            "location": {
                "getFile": self.config_parser["non-default"]["get_log_file_url"],
                "getFileNames": self.config_parser["non-default"][
                    "get_log_file_names_url"
                ],
            },
        }
        self.pv_grok_exporter_url = self.config_parser["non-default"][
            "pv_grok_exporter_url"
        ]

    def parse_pv_message_bus_config(self) -> None:
        """Method to parse message bus config from config file"""
        pv_send_as_pv_bytes_raw = self.config_parser["non-default"][
            "pv_send_as_pv_bytes"
        ]
        send_json_without_length_prefix_raw = self.config_parser["non-default"][
            "send_json_without_length_prefix"
        ]
        self.pv_send_as_pv_bytes = (
            True if pv_send_as_pv_bytes_raw.lower() == "true" else False
        )
        self.send_json_without_length_prefix = (
            True if send_json_without_length_prefix_raw.lower() == "true" else False
        )
        match self.message_bus_protocol:
            case "KAFKA" | "KAFKA3":
                self.pv_send_as_pv_bytes = True
            case "HTTP":
                self.pv_send_url = self.config_parser["non-default"]["pv_send_url"]
            case _:
                raise ValueError(
                    f"Invalid message bus protocol '{self.message_bus_protocol}'"
                )


if __name__ == "__main__":
    pv_config = ProtocolVerifierConfig()
    print(pv_config.config_path)
    print("done")
