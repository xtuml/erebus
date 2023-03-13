"""Testing __init__.py
"""
import os
from pathlib import Path
from typing import Optional

from flask.testing import FlaskClient
from werkzeug.test import TestResponse

# get resources folder in tests folder
resources = Path(__file__).parent / "test_files"


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
    proper_file_path = os.path.join(resources, file_name)
    file_data = open(proper_file_path, "rb")
    data = {
        file_id: (
            file_data,
            alt_file_name if isinstance(alt_file_name, str) else file_name
        )
    }
    return data


def get_multi_file_data(
    file_name_tuples: list[tuple[str, str, Optional[str]]]
) -> dict:
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
    return response


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
