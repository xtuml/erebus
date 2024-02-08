# pylint: disable=R1732
"""Testing send_config.py
"""
from io import BytesIO

import responses

from test_harness.requests.send_config import post_config_form_upload


@responses.activate
def test_post_config_from_upload_200(
    file_bytes: BytesIO,
    file_name: str,
) -> None:
    """Method to test `post_config_from_upload` when the response is 200OK

    :param file_bytes: Fixture providing file bytes
    :type file_bytes: `BytesIO`
    :param file_name: Fixture providing a file name
    :type file_name: `str`
    """
    url = 'http://mockserver.com/upload-config'
    responses.add(
        responses.POST,
        url,
        status=200
    )
    assert post_config_form_upload(
        file_bytes_file_names=[(file_bytes, file_name)],
        url=url
    )[0]


@responses.activate
def test_post_config_from_upload_404(
    file_bytes: BytesIO,
    file_name: str,
) -> None:
    """Method to test `post_config_from_upload` when the response is 404

    :param file_bytes: Fixture providing file bytes
    :type file_bytes: `BytesIO`
    :param file_name: Fixture providing a file name
    :type file_name: `str`
    """
    url = 'http://mockserver.com/upload-config'
    responses.add(
        responses.POST,
        url,
        json={"error": 'not found'},
        status=404
    )
    assert not post_config_form_upload(
        file_bytes_file_names=[(file_bytes, file_name)],
        url=url
    )[0]
