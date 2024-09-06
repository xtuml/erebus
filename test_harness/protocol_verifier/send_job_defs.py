"""Methods to send job defs to PV using uml file paths"""

from io import BytesIO
from typing import Literal

from test_harness.protocol_verifier.config.config import ProtocolVerifierConfig
from test_harness.utils import create_file_io_file_name_tuple_with_file_path
from test_harness.protocol_verifier.pv_config.pv_config_generation import (
    get_job_defs_from_uml_files,
)
from test_harness.requests_th.send_config import post_config_form_upload


def handle_send_job_defs(
    file_paths: list[str],
    harness_config: ProtocolVerifierConfig,
    file_type: Literal["json", "uml"],
) -> None:
    """Method to handle sending job defs to an url with
    :class:`ProtocolVerifierConfig`

    :param url: The url to send the request for uploading job definitions
    :type url: `str`
    :param file_paths: A list of file paths to job definitions
    :type file_paths: `list`[`str`]
    :param harness_config: Config for the test harness
    :type harness_config: :class:`ProtocolVerifierConfig`
    :param file_type: The type of file to send job defs from
    :type file_type: `Literal`["json", "uml"]
    """
    match file_type:
        case "json":
            send_job_defs_from_json(
                harness_config.pv_send_job_defs_url, file_paths, harness_config
            )
        case "uml":
            send_job_defs_from_uml(
                harness_config.pv_send_job_defs_url, file_paths, harness_config
            )
        case _:
            raise ValueError(f"Invalid file type: {file_type}")


def send_job_defs(
    url: str, job_defs: list[str],
    file_paths: list[str],
    harness_config: ProtocolVerifierConfig
) -> None:
    """Method to send job defs from a list of job defs and file paths to an url
    with :class:`ProtocolVerifierConfig`

    :param url: The url to send the request for uploading job definitions
    :type url: `str`
    :param job_defs: A list of job definitions as strings
    :type job_defs: `list`[`str`]
    :param file_paths: A list of file paths to job definitions
    :type file_paths: `list`[`str`]
    :param harness_config: Config for the test harness
    :type harness_config: :class:`ProtocolVerifierConfig`
    """
    file_io_file_name_tuples = [
        create_file_io_file_name_tuple_with_file_path(
            file_path, job_def
        )
        for job_def, file_path in zip(job_defs, file_paths)
    ]
    send_job_defs_from_file_io_file_name_tuples(
        file_io_file_name_tuples=file_io_file_name_tuples,
        url=url,
        max_retries=harness_config.requests_max_retries,
        timeout=harness_config.requests_timeout,
    )


def get_job_defs_from_jsons(json_file_paths: list[str]) -> list[str]:
    """Method to get job defs from a list of json file paths

    :param json_file_paths: A list of file paths to json file job definitions
    :type json_file_paths: `list`[`str`]
    :return: A list of job definitions as strings
    :rtype: `list`[`str`]
    """
    job_defs: list[str] = []
    for json_file_path in json_file_paths:
        with open(json_file_path, "r") as json_file:
            job_defs.append(json_file.read())
    return job_defs


def send_job_defs_from_json(
    url: str, json_file_paths: list[str],
    harness_config: ProtocolVerifierConfig
) -> None:
    """Method to send job defs from a list of json file paths to an url with
    :class:`ProtocolVerifierConfig`

    :param url: The url to send the request for uploading job definitions
    :type url: `str`
    :param json_file_paths: A list of file paths to json file job definitions
    :type json_file_paths: `list`[`str`]
    :param harness_config: Config for the test harness
    :type harness_config: :class:`ProtocolVerifierConfig`
    """
    job_defs = get_job_defs_from_jsons(json_file_paths)
    send_job_defs(url, job_defs, json_file_paths, harness_config)


def send_job_defs_from_uml(
    url: str, uml_file_paths: list[str], harness_config: ProtocolVerifierConfig
) -> None:
    """Method to send job defs from a list of uml file paths to an url with
    :class:`ProtocolVerifierConfig`

    :param url: The url to send the request for uploading job definitions
    :type url: `str`
    :param uml_file_paths: A list of filepaths to uml file job definitions
    :type uml_file_paths: `list`[`str`]
    :param harness_config: Config for the test harness
    :type harness_config: :class:`ProtocolVerifierConfig`
    """
    job_defs = get_job_defs_from_uml_files(uml_file_paths)
    converted_file_paths = [
        file_path.replace(".puml", ".json") for file_path in uml_file_paths
    ]
    send_job_defs(url, job_defs, converted_file_paths, harness_config)


def send_job_defs_from_file_io_file_name_tuples(
    file_io_file_name_tuples: list[tuple[BytesIO, str]],
    url: str,
    max_retries: int,
    timeout: int,
) -> None:
    """Method to send job defs as file io Bytes and file name tuples to an url
    with :class:`ProtocolVerifierConfig`

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
        timeout=timeout,
    )
    if not response_tuple[0]:
        raise RuntimeError(
            f"Error sending job defs to PV after {response_tuple[1]} retries"
            f" with code {response_tuple[2].status_code} and reason"
            f" '{response_tuple[2].reason}'. Determine the issue before"
            " retrying."
        )
