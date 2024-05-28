# pylint: disable=R0913
"""Tests for request_logs.py"""
import logging
from typing import Callable, Literal

import pytest
import responses
from responses import matchers

from test_harness.protocol_verifier.requests.request_logs import (
    get_verifier_log_file_names,
    get_verifier_log_file_data,
    get_log_files_raw_bytes,
    get_log_files_strings_from_log_files_bytes,
    get_log_file_string_from_log_file_bytes,
    get_log_files,
)


def test_get_log_file_string_from_log_file_bytes_not_zipped(
    file_string: str, file_raw_bytes: bytes
) -> None:
    """Tests for `get_log_file_string_from_log_file_bytes` when the file is
    not zipped

    :param file_string: Fixture providing a file string
    :type file_string: `str`
    :param file_raw_bytes: Fixture providing raw bytes of file string utf-8
    :type file_raw_bytes: `bytes`
    """
    output_file_string = get_log_file_string_from_log_file_bytes(
        raw_bytes=file_raw_bytes
    )
    assert output_file_string == file_string


def test_get_log_file_string_from_log_file_bytes_zipped(
    file_string: str, file_raw_bytes_gzipped: bytes
) -> None:
    """Tests for `get_log_file_string_from_log_file_bytes` when the file is
    zipped

    :param file_string: Fixture providing a file string
    :type file_string: `str`
    :param file_raw_bytes_gzipped: Fixture providing zipped raw bytes of file
    string utf-8
    :type file_raw_bytes_gzipped: `bytes`
    """
    output_file_string = get_log_file_string_from_log_file_bytes(
        raw_bytes=file_raw_bytes_gzipped, is_gzip=True
    )
    assert output_file_string == file_string


def test_get_log_files_string_from_log_files_bytes(
    file_string: str, file_raw_bytes_dict: dict[str, bytes]
) -> None:
    """Test for `get_log_files_strings_from_log_files_bytes`

    :param file_string: Fixture providing a file string
    :type file_string: `str`
    :param file_raw_bytes_dict: Dictionary mapping file name to raw bytes file
    :type file_raw_bytes_dict: `dict`[`str`, `bytes`]
    """
    files = get_log_files_strings_from_log_files_bytes(file_raw_bytes_dict)
    for file_name in file_raw_bytes_dict.keys():
        assert file_name in files
        assert files[file_name] == file_string


@responses.activate
def test_get_verifier_log_file_data_200_ok(
    file_name: str, file_raw_bytes: bytes
) -> None:
    """Test for `get_verifier_log_file_data` with 200 ok response

    :param file_name: Fixture providing a file name
    :type file_name: `str`
    :param file_raw_bytes: Fixture providing the raw bytes of the file
    :type file_raw_bytes: `bytes`
    """
    url = "http://mockserver.com/get-log-data"
    responses.add(
        responses.POST,
        url,
        body=file_raw_bytes,
        status=200,
        match=[matchers.json_params_matcher({"fileName": file_name})],
    )
    response_content = get_verifier_log_file_data(file_name=file_name, url=url)
    assert file_raw_bytes == response_content


@responses.activate
def test_get_verifier_log_file_data_404(
    file_name: str, file_raw_bytes: bytes
) -> None:
    """Test for `get_verifier_log_file_data` with 404 response

    :param file_name: Fixture providing a file name
    :type file_name: `str`
    :param file_raw_bytes: Fixture providing the raw bytes of the file
    :type file_raw_bytes: `bytes`
    """
    url = "http://mockserver.com/get-log-data"
    responses.add(
        responses.POST,
        url,
        body=file_raw_bytes,
        status=404,
        match=[matchers.json_params_matcher({"fileName": file_name})],
    )
    with pytest.raises(RuntimeError) as e_info:
        get_verifier_log_file_data(file_name=file_name, url=url)
    assert (
        e_info.value.args[0]
        == f"Endpoint {url} is not providing a correct response or is "
        f"unreachable.\nResponse code is {404} "
        "and response text is:\n'Not Found'"
    )


@responses.activate
def test_get_verifier_log_file_names_200_ok(file_names: list[str]) -> None:
    """Test for `get_verifier_log_file_names` with 200 ok response

    :param file_names: Fixture providing a list of file names
    :type file_names: `list`[`str`]
    """
    url = "http://mockserver.com/get-log-file-names"
    responses.add(
        responses.GET, url, status=200, json={"fileNames": file_names}
    )
    response_file_names = get_verifier_log_file_names(url=url)

    for file_name in response_file_names:
        assert file_name in file_names


@responses.activate
def test_get_verifier_log_file_names_location_200_ok(
    get_log_file_names_call_back: Callable[
        ...,
        tuple[Literal[400], dict, Literal["Error response"]]
        | tuple[Literal[400], dict, str]
        | tuple[Literal[200], dict, str],
    ],
) -> None:
    """Test for `get_verifier_log_file_names` with 200 ok response
    using location and file prefix inputs

    :param get_log_file_names_call_back: Fixture to provide a call back
    request function
    :type get_log_file_names_call_back: :class:`Callable`[
        `...`,
        `tuple`[:class:`Literal`[`400`], `dict`, :class:`Literal`[
            `"Error response"`
        ]]
        | `tuple`[:class:`Literal`[`400`], `dict`, `str`]
        | `tuple`[:class:`Literal`[`200`], `dict`, `str`],
    ]
    """
    url = "http://mockserver.com/get-log-file-names"
    responses.add_callback(
        responses.POST,
        url=url,
        callback=get_log_file_names_call_back,
        content_type="application/json",
    )
    actual_file_names = []
    for location, file_prefix in zip(
        ["RECEPTION"] + ["VERIFIER"] * 3,
        ["AEReception", "AEOrdering", "AESequenceDC", "IStore"],
    ):
        response_file_names = get_verifier_log_file_names(
            url=url, location=location, file_prefix=file_prefix
        )
        actual_file_names.extend(response_file_names)
    expected_file_names = [
        "AEReception.log",
        "AEOrdering.log",
        "AESequenceDC.log",
        "IStore.log",
    ]
    for file_name in actual_file_names:
        assert file_name in expected_file_names


@responses.activate
def test_get_verifier_log_file_names_404() -> None:
    """Test for `get_verifier_log_file_names` with 404 response"""
    url = "http://mockserver.com/get-log-file-names"
    responses.add(
        responses.GET,
        url,
        status=404,
    )
    with pytest.raises(RuntimeError) as e_info:
        get_verifier_log_file_names(url=url)
    assert (
        e_info.value.args[0]
        == f"Endpoint {url} is not providing a correct response or is "
        f"unreachable.\nResponse code is {404} "
        "and response text is:\n'Not Found'"
    )


@responses.activate
def test_get_verifier_log_file_names_not_json() -> None:
    """Test for `get_verifier_log_file_names` when the returned body is not
    json
    """
    url = "http://mockserver.com/get-log-file-names"
    responses.add(responses.GET, url, status=200, body="not json")

    with pytest.raises(RuntimeError) as e_info:
        get_verifier_log_file_names(url=url)
    assert (
        e_info.value.args[0]
        == f"Endpoint {url} for obtaining log file names is not returning"
        " a decodeable JSON. This must be corrected before the Test "
        "Harness can be functional"
    )


@responses.activate
def test_get_verifier_log_file_names_not_file_names(
    file_names: list[str],
) -> None:
    """Test for `get_verifier_log_file_names` when the returned json field is
    not "fileNames"

    :param file_names: Fixture providing a list of file names
    :type file_names: `list`[`str`]
    """
    url = "http://mockserver.com/get-log-file-names"
    responses.add(
        responses.GET, url, status=200, json={"fileNeemes": file_names}
    )

    with pytest.raises(RuntimeError) as e_info:
        get_verifier_log_file_names(url=url)
    assert (
        e_info.value.args[0]
        == f"Endpoint {url} json response has is not of the correct schema. "
        "This must be corrected before the Test Harness can be functional."
        " Json must have key 'fileName'"
    )


@responses.activate
def test_get_verifier_log_file_names_reponse_not_list(
    file_names: list[str],
) -> None:
    """Test for `get_verifier_log_file_names` when the returned json value
    under the field "fileNames" is not a list

    :param file_names: Fixture providing a list of file names
    :type file_names: `list`[`str`]
    """
    url = "http://mockserver.com/get-log-file-names"
    responses.add(
        responses.GET,
        url,
        status=200,
        json={"fileNames": ",".join(file_names)},
    )

    with pytest.raises(RuntimeError) as e_info:
        get_verifier_log_file_names(url=url)
    assert (
        e_info.value.args[0]
        == f"Endpoint {url} json response has is not of the correct schema. "
        "This must be corrected before the Test Harness can be functional."
        " Json must have a list of string file names under key 'fileNames'"
    )


@responses.activate
def test_get_verifier_log_file_names_list_not_all_string() -> None:
    """Test for `get_verifier_log_file_names` when the returned json value
    under the field "fileNames" is a list but not all of the elements are
    strings
    """
    url = "http://mockserver.com/get-log-file-names"
    responses.add(
        responses.GET, url, status=200, json={"fileNames": ["file", 2]}
    )

    with pytest.raises(RuntimeError) as e_info:
        get_verifier_log_file_names(url=url)
    assert (
        e_info.value.args[0]
        == f"Endpoint {url} json response has is not of the correct schema. "
        "This must be corrected before the Test Harness can be functional."
        " Json must have a list of string file names under key 'fileNames'"
    )


@responses.activate
def test_get_log_file_raw_bytes_all_to_get(
    file_names: list[str],
    file_name: str,
    file_name_gzipped: str,
    file_raw_bytes: bytes,
    file_raw_bytes_gzipped: bytes,
) -> None:
    """Tests for `get_log_files_raw_bytes` when retrieving all files

    :param file_names: Fixture providing a list of file names
    :type file_names: `list`[`str`]
    :param file_name: Fixture providing a file name
    :type file_name: `str`
    :param file_name_gzipped: Fixture providing a file name of a zipped file
    :type file_name_gzipped: `str`
    :param file_raw_bytes: Fixture providing the raw bytes of a file
    :type file_raw_bytes: `bytes`
    :param file_raw_bytes_gzipped: Fixture providing the zipped bytes of a file
    :type file_raw_bytes_gzipped: `bytes`
    """
    url_log_file_names = "http://mockserver.com/get-log-file-names"
    url_get_file = "http://mockserver.com/get-log-data"
    responses.add(
        responses.GET,
        url_log_file_names,
        status=200,
        json={"fileNames": file_names},
    )

    responses.add(
        responses.POST,
        url_get_file,
        body=file_raw_bytes,
        status=200,
        match=[matchers.json_params_matcher({"fileName": file_name})],
    )
    responses.add(
        responses.POST,
        url_get_file,
        body=file_raw_bytes_gzipped,
        status=200,
        match=[matchers.json_params_matcher({"fileName": file_name_gzipped})],
    )
    log_file_raw_bytes = get_log_files_raw_bytes(
        url_log_file_names=url_log_file_names, url_get_file=url_get_file
    )
    assert log_file_raw_bytes[file_name] == file_raw_bytes
    assert log_file_raw_bytes[file_name_gzipped] == file_raw_bytes_gzipped


@responses.activate
def test_get_log_file_raw_bytes_already_received(
    file_names: list[str],
    file_name: str,
    file_name_gzipped: str,
    file_raw_bytes: bytes,
    file_raw_bytes_gzipped: bytes,
) -> None:
    """Tests for `get_log_files_raw_bytes` when not retrieving all files

    :param file_names: Fixture providing a list of file names
    :type file_names: `list`[`str`]
    :param file_name: Fixture providing a file name
    :type file_name: `str`
    :param file_name_gzipped: Fixture providing a file name of a zipped file
    :type file_name_gzipped: `str`
    :param file_raw_bytes: Fixture providing the raw bytes of a file
    :type file_raw_bytes: `bytes`
    :param file_raw_bytes_gzipped: Fixture providing the zipped bytes of a file
    :type file_raw_bytes_gzipped: `bytes`
    """
    url_log_file_names = "http://mockserver.com/get-log-file-names"
    url_get_file = "http://mockserver.com/get-log-data"
    responses.add(
        responses.GET,
        url_log_file_names,
        status=200,
        json={"fileNames": file_names},
    )

    responses.add(
        responses.POST,
        url_get_file,
        body=file_raw_bytes,
        status=200,
        match=[matchers.json_params_matcher({"fileName": file_name})],
    )
    responses.add(
        responses.POST,
        url_get_file,
        body=file_raw_bytes_gzipped,
        status=200,
        match=[matchers.json_params_matcher({"fileName": file_name_gzipped})],
    )
    log_file_raw_bytes = get_log_files_raw_bytes(
        url_log_file_names=url_log_file_names,
        url_get_file=url_get_file,
        already_received_file_names=[file_name_gzipped],
    )
    assert log_file_raw_bytes[file_name] == file_raw_bytes
    assert file_name_gzipped not in log_file_raw_bytes
    assert len(log_file_raw_bytes) == 1


@responses.activate
def test_get_log_files_location_file_prefix(
    file_names: list[str],
    file_name: str,
    file_name_gzipped: str,
    file_raw_bytes: bytes,
    file_raw_bytes_gzipped: bytes,
    file_string: str,
) -> None:
    """Tests for `get_log_files` with a location and file prefix

    :param file_names: Fixture providing a list of file names
    :type file_names: `list`[`str`]
    :param file_name: Fixture providing a file name
    :type file_name: `str`
    :param file_name_gzipped: Fixture providing a file name of a zipped file
    :type file_name_gzipped: `str`
    :param file_raw_bytes: Fixture providing the raw bytes of a file
    :type file_raw_bytes: `bytes`
    :param file_raw_bytes_gzipped: Fixture providing the zipped bytes of a file
    :type file_raw_bytes_gzipped: `bytes`
    :param file_string: Fixture providing a the string representation of a file
    :type file_string: `str`
    """
    url_log_file_names = "http://mockserver.com/get-log-file-names"
    url_get_file = "http://mockserver.com/get-log-data"
    responses.add(
        responses.POST,
        url_log_file_names,
        status=200,
        json={"fileNames": file_names},
        match=[
            matchers.json_params_matcher(
                {"location": "RECEPTION", "file_prefix": "AEReception"}
            )
        ],
    )

    responses.add(
        responses.POST,
        url_get_file,
        body=file_raw_bytes,
        status=200,
        match=[
            matchers.json_params_matcher(
                {"fileName": file_name, "location": "RECEPTION"}
            )
        ],
    )
    responses.add(
        responses.POST,
        url_get_file,
        body=file_raw_bytes_gzipped,
        status=200,
        match=[
            matchers.json_params_matcher(
                {"fileName": file_name_gzipped, "location": "RECEPTION"}
            )
        ],
    )
    log_files = get_log_files(
        url_log_file_names=url_log_file_names,
        url_get_file=url_get_file,
        location="RECEPTION",
        file_prefix="AEReception",
    )
    assert log_files[file_name] == file_string
    assert log_files[file_name_gzipped] == file_string


@responses.activate
def test_get_log_files(
    file_names: list[str],
    file_name: str,
    file_name_gzipped: str,
    file_raw_bytes: bytes,
    file_raw_bytes_gzipped: bytes,
    file_string: str,
) -> None:
    """Tests for `get_log_files`

    :param file_names: Fixture providing a list of file names
    :type file_names: `list`[`str`]
    :param file_name: Fixture providing a file name
    :type file_name: `str`
    :param file_name_gzipped: Fixture providing a file name of a zipped file
    :type file_name_gzipped: `str`
    :param file_raw_bytes: Fixture providing the raw bytes of a file
    :type file_raw_bytes: `bytes`
    :param file_raw_bytes_gzipped: Fixture providing the zipped bytes of a file
    :type file_raw_bytes_gzipped: `bytes`
    :param file_string: Fixture providing a the string representation of a file
    :type file_string: `str`
    """
    url_log_file_names = "http://mockserver.com/get-log-file-names"
    url_get_file = "http://mockserver.com/get-log-data"
    responses.add(
        responses.GET,
        url_log_file_names,
        status=200,
        json={"fileNames": file_names},
    )

    responses.add(
        responses.POST,
        url_get_file,
        body=file_raw_bytes,
        status=200,
        match=[matchers.json_params_matcher({"fileName": file_name})],
    )
    responses.add(
        responses.POST,
        url_get_file,
        body=file_raw_bytes_gzipped,
        status=200,
        match=[matchers.json_params_matcher({"fileName": file_name_gzipped})],
    )
    log_files = get_log_files(
        url_log_file_names=url_log_file_names, url_get_file=url_get_file
    )
    assert log_files[file_name] == file_string
    assert log_files[file_name_gzipped] == file_string


def test_get_log_files_strings_from_log_files_bytes(
    file_raw_bytes_gzipped: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    """Tests `get_log_files_strings_from_log_files_bytes` when there is no end
    of file

    :param file_raw_bytes_gzipped: Fixture providing bytes for a gzipped file
    :type file_raw_bytes_gzipped: `bytes`
    :param caplog: Fixture to capture logs
    :type caplog: :class:`pytest`.`LogCaptureFixture`
    """
    corrupted_file = file_raw_bytes_gzipped[:-2]
    caplog.set_level(logging.WARNING)
    get_log_files_strings_from_log_files_bytes(
        {"corrupted_file.gz": corrupted_file}
    )
    assert (
        "gzip log file 'corrupted_file.gz' was found to be invalid"
        in caplog.text
    )
