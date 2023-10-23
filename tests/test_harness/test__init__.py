# pylint: disable=R1732
"""Testing __init__.py
"""
import os
from io import BufferedReader
from pathlib import Path
from typing import Optional

from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from test_harness import create_test_output_directory
from test_harness.config.config import HarnessConfig

# get test config
test_config_path = os.path.join(
    Path(__file__).parent,
    "config/test_config.config"
)
# get resources folder in tests folder
input_resources = Path(__file__).parent / "test_files"
# get uml_file_store in tests folder
output_resources = Path(__file__).parent / "uml_file_store"
# test file output resource
test_file_output_resources = Path(__file__).parent / "test_file_store"
# get profile file store
output_profile_resources = Path(__file__).parent / "profile_store"


def get_file_data(
    file_id: str,
    file_name: str,
    alt_file_name: Optional[str] = None
) -> dict:
    """Get file data for a request

    :param file_id: The id of the file in the request
    :type file_id: `str`
    :param file_name: The name of the file in the directory
    :type file_name: `str`
    :param alt_file_name: Alternative name to give the file, defaults to None
    :type alt_file_name: :class:`Optional`[`str`], optional
    :return: Returns a dictionary of {file_id: (file_data, file_name)}
    :rtype: `dict`
    """
    proper_file_path = os.path.join(input_resources, file_name)
    file_data = open(proper_file_path, "rb")
    data: dict[str, tuple[BufferedReader, str]] = {
        file_id: (
            file_data,
            alt_file_name if isinstance(alt_file_name, str) else file_name
        )
    }
    return data


def get_multi_file_data(
    file_name_tuples: list[tuple[str, str, Optional[str]]]
) -> dict[str, tuple[BufferedReader, str]]:
    """Get mutlple file data for a request

    :param file_name_tuples: Tuple with file_id, file_name and
    alt_file_name
    :type file_name_tuples:
    `list`[`tuple`[`str`, `str`, :class:`Optional`[`str`]]]
    :return: Dictionary of file_id mapped to (file_data, file_name)
    :rtype: `dict`
    """
    return {
        key: value
        for file_name_tuple in file_name_tuples
        for key, value in get_file_data(*file_name_tuple).items()
    }


def post_multi_form_data(
    client: FlaskClient,
    data: dict,
    resource: str
) -> TestResponse:
    """POST request of a multipart/form-data using given
    data and resource

    :param client: Flask test client
    :type client: :class:`FlaskClient`
    :param data: Dictionary mapping file_id to (file_data, file_name)
    :type data: `dict`
    :param resource: The endpoint for the request
    :type resource: `str`
    :return: The response from the request
    :rtype: :class:`TestResponse`
    """
    response = client.post(
        resource,
        data=data,
        buffered=True,
        content_type="multipart/form-data"
    )
    # clean up open files
    close_all_files(data)
    return response


def close_all_files(data: dict[str, tuple[BufferedReader, str]]) -> None:
    """Close all open files in a data dictionary

    :param data: Dictionary of data passed to client request
    :type data: `dict`
    """
    for file_data_tuple in data.values():
        file_data_tuple[0].close()


def file_content_compare(file_path_1: str, file_path_2: str) -> bool:
    """Confirm if files are exactly the same in terms of content

    :param file_path_1: Path of first file to compare
    :type file_path_1: `str`
    :param file_path_2: Path of second file to compare
    :type file_path_2: str
    :return: _description_
    :rtype: bool
    """
    with open(file_path_1, "r", encoding="utf-8") as file:
        file_1_data = file.read()
    with open(file_path_2, "r", encoding="utf-8") as file:
        file_2_data = file.read()
    return file_1_data == file_2_data


def test_bad_mime_type(client: FlaskClient) -> None:
    """Test bad mime-type given

    :param client: Flask test client
    :type client: :class:`FlaskClient`
    """
    response = client.post(
        "/uploadUML",
        content_type="application/json",
    )
    assert response.data == b"mime-type must be multipart/form-data\n"
    assert response.status_code == 400


def test_no_file_name(client: FlaskClient) -> None:
    """Test no file name given

    :param client: Flask test client
    :type client: :class:`FlaskClient`
    """
    data = get_file_data("file", "test_uml_1.puml", "")

    response = post_multi_form_data(
        client,
        data,
        "/uploadUML"
    )
    assert response.data == b"One of the uploaded files has no filename\n"
    assert response.status_code == 400


def test_shared_file_name(client: FlaskClient) -> None:
    """Test two given files share the same file name

    :param client: The Flask test client
    :type client: FlaskClient
    """
    data = get_multi_file_data(
        [
            ("file1", "test_uml_1.puml", None),
            ("file2", "test_uml_1.puml", None)
        ]
    )

    response = post_multi_form_data(
        client,
        data,
        "/uploadUML"
    )
    assert response.data == b"At least two of the uploaded"\
        b" files share the same filename\n"
    assert response.status_code == 400


def test_successful_upload(client: FlaskClient) -> None:
    """Test a successful upload of multiple files

    :param client: The flask client
    :type client: :class:`FlaskClient`
    """
    data = get_multi_file_data(
        [
            ("file1", "test_uml_1.puml", None),
            ("file2", "test_uml_2.puml", None)
        ]
    )

    response = post_multi_form_data(
        client,
        data,
        "/uploadUML"
    )
    assert response.data == b"Files uploaded successfully\n"
    assert response.status_code == 200

    assert file_content_compare(
       os.path.join(input_resources, "test_uml_1.puml"),
       os.path.join(output_resources, "test_uml_1.puml"),
    )
    os.remove(os.path.join(output_resources, "test_uml_1.puml"))
    assert file_content_compare(
       os.path.join(input_resources, "test_uml_2.puml"),
       os.path.join(output_resources, "test_uml_2.puml"),
    )
    os.remove(os.path.join(output_resources, "test_uml_2.puml"))


def test_upload_profile_two_profiles(client: FlaskClient) -> None:
    """Test an unsuccessful upload of two profiles

    :param client: The flask client
    :type client: :class:`FlaskClient`
    """
    data = get_multi_file_data(
        [
            ("file1", "test_profile.csv", None),
            ("file2", "test_profile_2.csv", None),
        ]
    )

    response = post_multi_form_data(
        client,
        data,
        "/upload/profile"
    )
    assert response.data == (
        b"More than two files uploaded. A single file is required\n"
    )
    assert response.status_code == 400


def test_upload_profile_successful(client: FlaskClient) -> None:
    """Test a successful upload of a profile

    :param client: The flask client
    :type client: :class:`FlaskClient`
    """
    data = get_multi_file_data(
        [
            ("file1", "test_profile.csv", None)
        ]
    )

    response = post_multi_form_data(
        client,
        data,
        "/upload/profile"
    )
    assert response.data == b"Files uploaded successfully\n"
    assert response.status_code == 200

    assert file_content_compare(
       os.path.join(input_resources, "test_profile.csv"),
       os.path.join(output_profile_resources, "test_profile.csv"),
    )
    os.remove(os.path.join(output_profile_resources, "test_profile.csv"))


def test_create_output_directory_does_not_exist() -> None:
    """Tests `create_test_output_directory` when the output directory does not
    exist
    """
    harness_config = HarnessConfig(
        config_path=test_config_path
    )
    directory_name, directory_path = create_test_output_directory(
        harness_config=harness_config,
        test_name="Test"
    )
    assert directory_name == "Test"
    expected_path = os.path.join(
        harness_config.report_file_store,
        "Test"
    )
    assert directory_path == expected_path
    assert os.path.exists(expected_path)
    os.rmdir(directory_path)


def test_successful_test_files_upload(client: FlaskClient) -> None:
    """Test a successful upload of multiple files for the endpoint
    `/upload/test-files`

    :param client: The flask client
    :type client: :class:`FlaskClient`
    """
    data = get_multi_file_data(
        [
            ("file1", "test_uml_1_events.json", None),
            ("file2", "test_uml_2_events.json", None)
        ]
    )

    response = post_multi_form_data(
        client,
        data,
        "/upload/test-files"
    )
    assert response.data == b"Files uploaded successfully\n"
    assert response.status_code == 200

    assert file_content_compare(
       os.path.join(input_resources, "test_uml_1_events.json"),
       os.path.join(test_file_output_resources, "test_uml_1_events.json"),
    )
    os.remove(os.path.join(
        test_file_output_resources, "test_uml_1_events.json"
    ))
    assert file_content_compare(
       os.path.join(input_resources, "test_uml_2_events.json"),
       os.path.join(test_file_output_resources, "test_uml_2_events.json"),
    )
    os.remove(os.path.join(
        test_file_output_resources, "test_uml_2_events.json"
    ))