# pylint: disable=R1732
"""Testing __init__.py
"""
from io import BytesIO
from pathlib import Path
import os

import responses

from test_harness.requests import (
    build_upload_file_tuple,
    build_upload_file_tuples,
    post_sync_file_bytes_in_form,
    send_json_post_request,
    send_get_request,
    download_file_to_path
)

# download folder path for tests
download_folder_path = Path(__file__).parent


def check_build_upload(
    result: tuple,
    file_bytes: BytesIO,
    file_name: str,
    form_parameter: str
) -> None:
    """Method to check the correct buil of upload file tuples

    :param result: The result from the test
    :type result: `tuple`
    :param file_bytes: The file bytes input
    :type file_bytes: :class:`BytesIO`
    :param file_name: The file name input
    :type file_name: `str`
    :param form_parameter: The form parameter input
    :type form_parameter: `str`
    """
    assert result[0] == form_parameter
    assert result[1][0] == file_name
    assert result[1][1] == file_bytes
    assert result[1][2] == 'application/octet-stream'


def test_build_upload_file_tuple(
    file_bytes: BytesIO,
    file_name: str,
    form_parameter: str
) -> None:
    """Tests the method `build_upload_file_tuple`

    :param file_bytes: Fixture providing file bytes
    :type file_bytes: `BytesIO`
    :param file_name: Fixture providing a file name
    :type file_name: `str`
    :param form_parameter: Fixture providing a form parameter
    :type form_parameter: `str`
    """
    result = build_upload_file_tuple(
        file_bytes=file_bytes,
        file_name=file_name,
        form_parameter=form_parameter
    )
    check_build_upload(
        result=result,
        file_bytes=file_bytes,
        file_name=file_name,
        form_parameter=form_parameter
    )


def test_build_upload_file_tuples(
    file_bytes: BytesIO,
    file_name: str,
    form_parameter: str
) -> None:
    """Tests the method `build_upload_file_tuples`

    :param file_bytes: Fixture providing file bytes
    :type file_bytes: `BytesIO`
    :param file_name: Fixture providing a file name
    :type file_name: `str`
    :param form_parameter: Fixture providing a form parameter
    :type form_parameter: `str`
    """
    file_bytes_file_names = [(file_bytes, file_name)] * 3
    results = build_upload_file_tuples(
        file_bytes_file_names=file_bytes_file_names,
        form_param=form_parameter
    )
    for result in results:
        check_build_upload(
            result=result,
            file_bytes=file_bytes,
            file_name=file_name,
            form_parameter=form_parameter
        )


@responses.activate
def test_post_sync_file_bytes_in_form_200_ok(
    file_bytes: BytesIO,
    file_name: str,
    form_parameter: str
) -> None:
    """Method to test `post_sync_file_bytes_in_form` when the response is 200OK

    :param file_bytes: Fixture providing file bytes
    :type file_bytes: `BytesIO`
    :param file_name: Fixture providing a file name
    :type file_name: `str`
    :param form_parameter: Fixture providing a form parameter
    :type form_parameter: `str`
    """
    url = 'http://mockserver.com/test'
    responses.add(
        responses.POST,
        url,
        status=200
    )
    upload_file_tuples = build_upload_file_tuples(
        [(file_bytes, file_name)],
        form_parameter
    )
    response = post_sync_file_bytes_in_form(
        upload_file_tuples=upload_file_tuples,
        url=url
    )
    assert response[0]
    assert response[1] == 0
    assert response[2].status_code == 200


@responses.activate
def test_post_sync_file_bytes_in_form_not_404(
    file_bytes: BytesIO,
    file_name: str,
    form_parameter: str
) -> None:
    """Method to test `post_sync_file_bytes_in_form` when the response is 404

    :param file_bytes: Fixture providing file bytes
    :type file_bytes: `BytesIO`
    :param file_name: Fixture providing a file name
    :type file_name: `str`
    :param form_parameter: Fixture providing a form parameter
    :type form_parameter: `str`
    """
    url = 'http://mockserver.com/test'
    responses.add(
        responses.POST,
        url,
        json={"error": 'upload error'},
        status=404
    )
    upload_file_tuples = build_upload_file_tuples(
        [(file_bytes, file_name)],
        form_parameter
    )
    response = post_sync_file_bytes_in_form(
        upload_file_tuples=upload_file_tuples,
        url=url,
        max_retries=3
    )
    assert not response[0]
    assert response[1] == 3
    assert response[2].status_code == 404


@responses.activate
def test_send_json_post_request_200_ok(
    json_request_body_file_name: dict[str, str]
) -> None:
    """Test `send_json_post_request` for 200 ok response

    :param json_request_body_file_name: Fixture providing a mapping "fileName"
    to a file name
    :type json_request_body_file_name: `dict`[`str`, `str`]
    """
    url = 'http://mockserver.com/test/post'
    responses.add(
        responses.POST,
        url,
        status=200
    )
    response = send_json_post_request(
        json_dict=json_request_body_file_name,
        url=url
    )

    assert response[0]
    assert response[1] == 0
    assert response[2].status_code == 200


@responses.activate
def test_send_json_post_request_404(
    json_request_body_file_name: dict[str, str]
) -> None:
    """Test `send_json_post_request` for 404 response

    :param json_request_body_file_name: Fixture providing a mapping "fileName"
    to a file name
    :type json_request_body_file_name: `dict`[`str`, `str`]
    """
    url = 'http://mockserver.com/test/post'
    responses.add(
        responses.POST,
        url,
        status=404
    )
    response = send_json_post_request(
        json_dict=json_request_body_file_name,
        url=url,
        max_retries=3
    )

    assert not response[0]
    assert response[1] == 3
    assert response[2].status_code == 404


@responses.activate
def test_send_get_request_200_ok() -> None:
    """Test for `send_get_request` with 200 ok response
    """
    url = 'http://mockserver.com/test/post'
    responses.add(
        responses.GET,
        url,
        status=200
    )
    response = send_get_request(
        url=url
    )

    assert response[0]
    assert response[1] == 0
    assert response[2].status_code == 200


@responses.activate
def test_send_get_request_404() -> None:
    """Test for `send_get_request` with 200 ok response
    """
    url = 'http://mockserver.com/test/post'
    responses.add(
        responses.GET,
        url,
        status=404
    )
    response = send_get_request(
        url=url,
        max_retries=3
    )

    assert not response[0]
    assert response[1] == 3
    assert response[2].status_code == 404


@responses.activate
def test_download_file_to_path() -> None:
    """Test for `download_file_to_path` with 200 ok response
    """
    test_string = "test"
    url = 'http://mockserver.com/getgrok'
    responses.add(
        responses.GET,
        url,
        body=test_string.encode("utf-8"),
        status=200,
        headers={
            "Content-Type": "text/plain; version=0.0.4; charset=utf-8"
        }
    )
    download_file_path = download_folder_path / "test_file"
    download_file_to_path(
        url,
        str(download_file_path)
    )
    assert os.path.exists(download_file_path)
    os.remove(download_file_path)
