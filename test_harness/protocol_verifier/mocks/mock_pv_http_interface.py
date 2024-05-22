"""mock pv http interface abstraction
"""

from contextlib import contextmanager
from typing import Callable, Generator, Any

import responses

from test_harness.protocol_verifier.config.config import ProtocolVerifierConfig
from aioresponses import aioresponses, CallbackResult
from test_harness.protocol_verifier.utils import PVLogFileNameCallback


@contextmanager
def mock_pv_http_interface(
    harness_config: ProtocolVerifierConfig,
    send_pv_callback: Callable[..., CallbackResult] | None = None,
    log_return_callback: Callable[..., tuple[int, dict, str]] | None = None,
    log_file_name_call_back: Callable[..., tuple[int, dict, str]] | None = None,
) -> Generator[aioresponses, Any, None]:
    """Context manager to mock the pv http interface

    :param harness_config: The harness config
    :type harness_config: :class:`ProtocolVerifierConfig`
    :param send_pv_callback: The callback for the send pv function, defaults to
    `None`
    :type send_pv_callback: :class:`Callable`[..., :class:`CallbackResult`],
    optional
    :param log_return_callback: The callback for the log return function,
    defaults to `None`
    :type log_return_callback: :class:`Callable`[..., `tuple`[`int`, `dict`,
    `str`]], optional
    :param log_file_name_call_back: The callback for the log file name
    function, defaults to `None`
    :type log_file_name_call_back: :class:`Callable`[..., `tuple`[`int`, `dict`
    , `str`]], optional
    :return: Yields the mock
    :rtype: :class:`Generator`[:class:`aioresponses`, `Any`, `None`]
    """
    if log_file_name_call_back is None:
        log_file_name_call_back = PVLogFileNameCallback(harness_config).call_back
    responses.add_callback(
        responses.POST,
        harness_config.log_urls["location"]["getFileNames"],
        callback=log_file_name_call_back,
    )
    if log_return_callback is None:
        responses.post(
            url=harness_config.log_urls["location"]["getFile"],
            body=b"test log",
        )
    else:
        responses.add_callback(
            responses.POST,
            harness_config.log_urls["location"]["getFile"],
            callback=log_return_callback,
        )
    responses.get(url=harness_config.pv_clean_folders_url)
    responses.post(url=harness_config.pv_send_job_defs_url)
    with aioresponses() as mock:
        mock.post(
            url=harness_config.pv_send_url, repeat=True, callback=send_pv_callback
        )
        yield mock
