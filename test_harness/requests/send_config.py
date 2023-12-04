# pylint: disable=C0103
"""Methods for sending post requests for
"""
from io import BytesIO

import requests

from test_harness.requests import (
    post_sync_file_bytes_in_form,
    build_upload_file_tuples
)


def post_config_form_upload(
    file_bytes_file_names: list[tuple[BytesIO, str]],
    url: str,
    max_retries: int = 5,
    timeout: int = 10
) -> tuple[bool, int, "requests.Response"]:
    """Method to post config files to an endpoint given a list of file bytes
    and file name pairs

    :param file_bytes_file_names: List of file bytes and file name pairs
    :type file_bytes_file_names: `list`[`tuple`[:class:`BytesIO`, `str`]]
    :param url: The url to send the request to
    :type url: `str`
    :param max_retries: The number of times to retry the request if it fails,
    defaults to `5`
    :type max_retries: `int`, optional
    :param timeout: The number of seconds to wait for a response, defaults to
    `10`
    :type timeout: `int`, optional
    :return: Returns a tuple with:
    * Boolean indicating if the request was succesful or not
    * An integer indicating the nuber of retries
    * The :class:`Response` object received
    :rtype: `tuple`[`bool`, `int`, :class:`Response`]
    """
    upload_file_tuples = build_upload_file_tuples(
        file_bytes_file_names=file_bytes_file_names,
        form_param="upload"
    )
    response = post_sync_file_bytes_in_form(
        upload_file_tuples=upload_file_tuples,
        url=url,
        max_retries=max_retries,
        timeout=timeout
    )
    return response


if __name__ == "__main__":
    import sys
    import os
    args = sys.argv
    if len(args) == 1:
        raise RuntimeError("No file path supplied")
    upload_url = args[2]
    with open(args[1], 'rb') as file:
        file_bytes = BytesIO(file.read())
    file_name = os.path.basename(args[1])
    post_response = post_config_form_upload(
        file_bytes_file_names=[(file_bytes, file_name)],
        url=upload_url
    )
    if post_response[0]:
        print('Succeeded')
    else:
        print("Failed")
