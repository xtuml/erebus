"""
Config class for test harness
"""
import os
from typing import Optional
from configparser import ConfigParser
from pathlib import Path


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

    def parse_config_to_attributes(self):
        """Method to parse config to attributes
        """
        # parse uml file store
        uml_file_store_path = self.config_parser[
            "non-default"
        ]["uml_file_store"]
        if os.path.isabs(uml_file_store_path):
            self.uml_file_store = uml_file_store_path
        else:
            self.uml_file_store = str(
                Path(
                    __file__
                ).parent.parent.parent / uml_file_store_path
            )


if __name__ == "__main__":
    config = HarnessConfig()
    print("Done")
