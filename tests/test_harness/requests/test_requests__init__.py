# pylint: disable=R1732
"""Testing __init__.py
"""
from io import BytesIO

import responses
from test_harness.requests import (
    build_upload_file_tuple,
    build_upload_file_tuples,
    post_sync_file_bytes_in_form
)


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
    assert response[2] is None


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
