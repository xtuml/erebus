"""Methods to send job defs to PV using uml file paths
"""
from io import BytesIO

from test_harness.config.config import HarnessConfig
from test_harness.utils import create_file_io_file_name_tuple_with_file_path
from test_harness.pv_config.pv_config_generation import (
    get_job_defs_from_uml_files
)
from test_harness.requests.send_config import post_config_form_upload


def send_job_defs_from_uml(
    url: str,
    uml_file_paths: list[str],
    harness_config: HarnessConfig
) -> None:
    """Method to send job defs from a list of uml file paths to an url with
    :class:`HarnessConfig`

    :param url: The url to send the request for uploading job definitions
    :type url: `str`
    :param uml_file_paths: A list of filepaths to uml file job definitions
    :type uml_file_paths: `list`[`str`]
    :param harness_config: Config for the test harness
    :type harness_config: :class:`HarnessConfig`
    """
    job_defs = get_job_defs_from_uml_files(uml_file_paths)
    file_io_file_name_tuples = [
        create_file_io_file_name_tuple_with_file_path(
            file_path.replace(".puml", ".json"),
            file_string
        )
        for file_path, file_string in zip(uml_file_paths, job_defs)
    ]
    send_job_defs_from_file_io_file_name_tuples(
        file_io_file_name_tuples=file_io_file_name_tuples,
        url=url,
        max_retries=harness_config.requests_max_retries,
        timeout=harness_config.requests_timeout
    )


def send_job_defs_from_file_io_file_name_tuples(
    file_io_file_name_tuples: list[tuple[BytesIO, str]],
    url: str,
    max_retries: int,
    timeout: int
) -> None:
    """Method to send job defs as file io Bytes and file name tuples to an url
    with :class:`HarnessConfig`

    :param file_io_file_name_tuples: A list of file io and file name tuple
    pairs
    :type file_io_file_name_tuples: `list`[`tuple`[:class:`BytesIO`, `str`]]
    :param url: The url to send the request for uploading job definitions
    :type url: `str`
    :param max_retries: Number of times to retry the request
    :type max_retries: `int`
    :param timeout: The number of seconds to wait for a response
    :type timeout: `int`
    :raises RuntimeError: Raises a :class:`RuntimeError` if the reponse is not
    ok
    """
    response_tuple = post_config_form_upload(
        file_bytes_file_names=file_io_file_name_tuples,
        url=url,
        max_retries=max_retries,
        timeout=timeout
    )
    if not response_tuple[0]:
        raise RuntimeError(
            f"Error sending job defs to PV after {response_tuple[1]} retries"
            f" with code {response_tuple[2].status_code} and reason"
            f" '{response_tuple[2].reason}'. Determine the issue before"
            " retrying."
        )
