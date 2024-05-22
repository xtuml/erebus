import json
from typing import Literal

from test_harness.protocol_verifier.config.config import ProtocolVerifierConfig


class PVLogFileNameCallback:
    """Class to create a callback for the log file name

    :param harness_config: The harness config
    :type harness_config: :class:`ProtocolVerifierConfig`"""

    def __init__(
        self,
        harness_config: ProtocolVerifierConfig,
    ) -> None:
        """Constructor method"""
        self.reception_log_file = harness_config.log_urls["aer"]["prefix"] + ".log"
        self.verifier_log_file = harness_config.log_urls["ver"]["prefix"] + ".log"

    def call_back(
        self, request
    ) -> tuple[Literal[200], dict, str] | tuple[Literal[404], dict, str]:
        """Method to create the callback"""
        payload = json.loads(request.body)
        if payload["location"] == "RECEPTION":
            return (200, {}, json.dumps({"fileNames": [self.reception_log_file]}))
        elif payload["location"] == "VERIFIER":
            return (200, {}, json.dumps({"fileNames": [self.verifier_log_file]}))
        else:
            return 404, {}, json.dumps({})
