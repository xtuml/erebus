"""Module init file
"""
from typing import Literal, Iterable
from io import BytesIO
import requests


def post_sync_file_bytes_in_form(
    upload_file_tuples: list[tuple[str, tuple[str, BytesIO, str]]],
    url: str,
    max_retries: int = 0
) -> tuple[bool, int, None | requests.Response]:
    """Method to synchronously post to an url a list of files
    (:class:`BytesIO`) as a form under a a parameter with filename bytes and
    mimetype

    :param upload_file_tuples: List of tuple with form parameter and a tuple
    containing file name, file bytes and mime type
    :type upload_file_tuples: list[tuple[str, tuple[str, BytesIO, str]]]
    :param url: The url endpoint to send the post request to
    :type url: `str`
    :param max_retries: Number of times to retry the request, defaults to `0`
    :type max_retries: `int`, optional
    :return: Returns a tuple with:
    * Boolean indicating if the request was succesful or not
    * An integer indicating the nuber of retries
    * The :class:`requests`.`Response` object received or None if it was 200 OK
    :rtype: `tuple`[`bool`, `int`, `None` | :class:`requests`.`Response`]
    """
    num_retries = 0
    while num_retries <= max_retries:
        response = requests.post(
            url=url,
            files=upload_file_tuples,
            timeout=10
        )
        if response.status_code == 200:
            return (True, num_retries, None)
        num_retries += 1
    return (False, max_retries, response)


def build_upload_file_tuples(
    file_bytes_file_names: Iterable[tuple[BytesIO, str]],
    form_param: str
) -> list[
    tuple[str, tuple[str, BytesIO, Literal['application/octet-stream']]]
]:
    """Method to build a list of form parameters for file upload from a list
    of file bytes and file name tuples

    :return: Returns a list of tuples that can be used to upload multiple
    files in a multipart form request
    :rtype: `list`[`tuple`[`str`, `tuple`[`str`, :class:`BytesIO`,
    :class:`Literal`['application/octet-stream']]]]
    """
    return [
        build_upload_file_tuple(
            file_bytes,
            file_name,
            form_param
        )
        for file_bytes, file_name
        in file_bytes_file_names
    ]


def build_upload_file_tuple(
    file_bytes: BytesIO,
    file_name: str,
    form_parameter: str
) -> tuple[str, tuple[str, BytesIO, Literal['application/octet-stream']]]:
    """Method to build form parameters for file upload from a single file from
    file bytes and file names and a form parameter

    :return: Returns a tuple that can be used to upload a file as part of a
    multipart form request
    :rtype: [`tuple`[`str`, `tuple`[`str`, :class:`BytesIO`,
    :class:`Literal`['application/octet-stream']]]]
    """
    return (
        form_parameter,
        (file_name, file_bytes, 'application/octet-stream')
    )
