# pylint: disable=C0103
"""Group of methods to request logs from Protocol Verifier
"""
from typing import Iterable
import gzip
import logging

import requests

from test_harness.requests import (
    send_json_post_request,
    send_get_request,
    check_response_tuple_ok
)


def get_verifier_log_file_names(
    url: str
) -> list[str]:
    """Method to get verifier log file names

    :param url: url endpoint to send request to
    :type url: `str`
    :raises RuntimeError: Raises a :class:`RuntimeError` if the response was
    not a 200OK after 5 retries
    :raises RuntimeError: Raises a :class:`RuntimeError` if the reponse was
    not decodeable as a json
    :raises RuntimeError: Raises a :class:`RuntimeError` if the response json
    does not contain the key "fileNames"
    :raises RuntimeError: Raises a :class:`RuntimeError` if the value under
    "fileNames" is not a list
    :raises RuntimeError: Raises a :class:`RuntimeError` if the list of values
    under "fileNames" is not a list of strings
    :return: Returns a list of the file names of logs
    :rtype: `list`[`str`]
    """
    response_tuple = send_get_request(
        url=url,
        max_retries=5
    )
    check_response_tuple_ok(response_tuple=response_tuple, url=url)
    try:
        json_response = response_tuple[2].json()
    except requests.exceptions.JSONDecodeError as exception:
        raise RuntimeError(
            f"Endpoint {url} for obtaining log file names is not returning"
            " a decodeable JSON. This must be corrected before the Test "
            "Harness can be functional"
        ) from exception
    if "fileNames" not in json_response:
        raise RuntimeError(
            f"Endpoint {url} json response has is not of the correct schema. "
            "This must be corrected before the Test Harness can be functional."
            " Json must have key 'fileName'"
        )
    file_names = json_response["fileNames"]
    if not isinstance(file_names, list):
        raise RuntimeError(
            f"Endpoint {url} json response has is not of the correct schema. "
            "This must be corrected before the Test Harness can be functional."
            " Json must have a list of string file names under key 'fileNames'"
        )
    if file_names and not all(
        isinstance(file_name, str) for file_name in file_names
    ):
        raise RuntimeError(
            f"Endpoint {url} json response has is not of the correct schema. "
            "This must be corrected before the Test Harness can be functional."
            " Json must have a list of string file names under key 'fileNames'"
        )
    return file_names


def get_verifier_log_file_data(
    file_name: str,
    url: str
) -> bytes:
    """Method to get the bytes response content of a file from the endpoint

    :param file_name: The file name of the file to receive
    :type file_name: `str`
    :param url: The url endpoint from which to request the file
    :type url: `str`
    :return: Returns the bytes of the file
    :rtype: `bytes`
    """
    json_dict = {
        "fileName": file_name
    }
    response_tuple = send_json_post_request(
        json_dict=json_dict,
        url=url,
        max_retries=5
    )
    check_response_tuple_ok(
        response_tuple=response_tuple,
        url=url
    )
    return response_tuple[2].content


def get_verifier_log_files_data(
    file_names: Iterable[str],
    url: str
) -> dict[str, bytes]:
    """Method to get raw file bytes from an iterable of file names

    :param file_names: An iterable of file names to get
    :type file_names: :class:`Iterable`[`str`]
    :param url: The url endpoint to send requests to
    :type url: `str`
    :return: A dictionary of file names mapped to file bytes
    :rtype: `dict`[`str`, `bytes`]
    """
    return {
        file_name: get_verifier_log_file_data(
            file_name,
            url
        )
        for file_name in file_names
    }


def get_log_files_raw_bytes(
    url_log_file_names: str,
    url_get_file: str,
    already_received_file_names: list[str] | None = None
) -> dict[str, bytes]:
    """Method to get log files raw bytes from server

    :param url_log_file_names: The url endpoint to get the log file names
    :type url_log_file_names: `str`
    :param url_get_file: The url endpoint to get file data
    :type url_get_file: `str`
    :param already_received_files: A `list` of already received
    files, defaults to `None`
    :type already_received_files: :class:`list`[`str`] | `None`, optional
    :return: Returns a dictionary mapping file name to the raw bytes of the
    file
    :rtype: `dict`[`str`, `bytes`]
    """
    if not already_received_file_names:
        already_received_file_names = []
    file_names = get_verifier_log_file_names(
        url_log_file_names
    )
    files_to_request = set(file_names).difference(
        set(already_received_file_names)
    )
    # request files
    files = get_verifier_log_files_data(
        files_to_request,
        url_get_file
    )
    return files


def get_log_files_strings_from_log_files_bytes(
    raw_bytes_files: dict[str, bytes]
) -> dict[str, str]:
    """Method to convert files as bytes to utf-8 strings representing the file

    :param raw_bytes_files: Dictionary of raw bytes files
    :type raw_bytes_files: `dict`[`str`, `bytes`]
    :return: Returns a dictionary of file names mapped to their string
    representation
    :rtype: `dict`[`str`, `str`]
    """
    files = {}
    for file_name, raw_bytes in raw_bytes_files.items():
        try:
            files[file_name] = get_log_file_string_from_log_file_bytes(
                raw_bytes=raw_bytes,
                is_gzip=".gz" in file_name
            )
        except gzip.BadGzipFile:
            logging.getLogger().warning(
                "gzip log file '%s' was found to be invalid", file_name
            )
    return files


def get_log_file_string_from_log_file_bytes(
    raw_bytes: bytes,
    is_gzip: bool = False
) -> str:
    """Method to get a log file string from raw bytes. If gzipped will gzip
    decompress first

    :param raw_bytes: Raw bytes of the log file
    :type raw_bytes: `bytes`
    :param is_gzip: Boolean indicating if the file has been gzipped, defaults
    to `False`
    :type is_gzip: `bool`, optional
    :return: Returns the string representation of the log file
    :rtype: `str`
    """
    if is_gzip:
        raw_bytes = gzip.decompress(raw_bytes)
    file_string = raw_bytes.decode("utf-8")
    return file_string


def get_log_files(
    url_log_file_names: str,
    url_get_file: str,
    already_received_file_names: list[str] | None = None
) -> dict[str, str]:
    """Method to get log files strings from server

    :param url_log_file_names: The url endpoint to get the log file names
    :type url_log_file_names: `str`
    :param url_get_file: The url endpoint to get file data
    :type url_get_file: `str`
    :param already_received_files: A `list` of already received
    files, defaults to `None`
    :type already_received_files: :class:`list`[`str`] | `None`, optional
    :return: Returns a dictionary mapping file name to the raw bytes of the
    file
    :rtype: `dict`[`str`, `str`]
    """
    raw_bytes_files = get_log_files_raw_bytes(
        url_log_file_names=url_log_file_names,
        url_get_file=url_get_file,
        already_received_file_names=already_received_file_names
    )
    files = get_log_files_strings_from_log_files_bytes(raw_bytes_files)
    return files


if __name__ == "__main__":
    import sys
    args = sys.argv
    url_file_names = (
        "http://host.docker.internal:9000/download/verifier-log-file-names"
    )
    url_file = (
        "http://host.docker.internal:9000/download/verifierlog"
    )
    already_received_files = []
    if "--url-names" in args:
        url_file_names = args[args.index("--url-names") + 1]
    if "--url-file" in args:
        url_file = args[args.index("--url-file") + 1]
    for index, arg in enumerate(args):
        if "--omit" == arg:
            already_received_files.append(
                args[index + 1]
            )
    log_files = get_log_files(
        url_log_file_names=url_file_names,
        url_get_file=url_file,
        already_received_file_names=already_received_files
    )
    concat_string = "\n".join(log_files.values())
    if "--save-path" in args:
        save_path = args[args.index("--save-path") + 1]
        with open(save_path, 'w', encoding="utf-8") as file:
            file.write(concat_string)
    else:
        print(concat_string)
