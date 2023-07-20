"""Module init file
"""
from typing import Literal, Iterable, Callable
from io import BytesIO
import requests


def post_sync_file_bytes_in_form(
    upload_file_tuples: list[tuple[str, tuple[str, BytesIO, str]]],
    url: str,
    max_retries: int = 0,
    timeout: int = 10
) -> tuple[bool, int, requests.Response]:
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
    :param timeout: The number of seconds to wait for a response, defaults to
    `10`
    :type timeout: `int`, optional
    :return: Returns a tuple with:
    * Boolean indicating if the request was succesful or not
    * An integer indicating the nuber of retries
    * The :class:`requests`.`Response` object received or None if it was 200 OK
    :rtype: `tuple`[`bool`, `int`, :class:`requests`.`Response`]
    """
    response_tuple = request_retry(
        request_method=requests.post,
        max_retries=max_retries,
        url=url,
        files=upload_file_tuples,
        timeout=timeout
    )
    return response_tuple


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


def send_json_post_request(
    json_dict: dict,
    url: str,
    max_retries: int = 0,
    timeout: int = 10
) -> tuple[bool, int, requests.Response]:
    """Method to send arbitrary json data that is from a serializable
    dictionary.

    :param json_dict: Dictionary representing a json
    :type json_dict: `dict`
    :param url: The url endpoint to send the post request to
    :type url: `str`
    :param max_retries: Number of times to retry the request, defaults to `0`
    :type max_retries: `int`, optional
    :param timeout: The number of seconds to wait for a response, defaults to
    `0`
    :type timeout: `int`, optional
    :return: Returns a tuple with:
    * Boolean indicating if the request was succesful or not
    * An integer indicating the nuber of retries
    * The :class:`requests`.`Response` object received or None if it was 200 OK
    :rtype: `tuple`[`bool`, `int`, :class:`requests`.`Response`]
    """
    response_tuple = request_retry(
        request_method=requests.post,
        max_retries=max_retries,
        url=url,
        json=json_dict,
        timeout=timeout
    )
    return response_tuple


def request_retry(
    request_method: Callable[..., requests.Response],
    *request_args,
    max_retries: int = 0,
    acceptable_status_codes: list[int] | None = None,
    **request_kwargs
) -> tuple[bool, int, requests.Response]:
    """Method to retry a :class:`requests` post a maximum number of times if
    there is a failure

    :param request_method: The method of the request from `requests`
    :type request_method: :class:`Callable`[..., :class:`requests`.`Response`]
    :param max_retries: Number of times to retry the request, defaults to `0`
    :type max_retries: `int`, optional
    :param acceptable_status_codes: A list of acceptable status codes,
    defaults to `none
    :type acceptable_status_codes: `list` | `None`, optional
    :return: Returns a tuple with:
    * Boolean indicating if the request was succesful or not
    * An integer indicating the nuber of retries
    * The :class:`requests`.`Response` object received or None if it was 200 OK
    :rtype: `tuple`[`bool`, `int`, :class:`requests`.`Response`]
    """
    if not acceptable_status_codes:
        acceptable_status_codes = [200]
    num_retries = 0
    while num_retries <= max_retries:
        response = request_method(*request_args, **request_kwargs)
        if response.status_code in acceptable_status_codes:
            return (True, num_retries, response)
        num_retries += 1
    return (False, max_retries, response)


def send_get_request(
    url: str,
    max_retries: int = 0,
    timeout: int = 10
) -> tuple[bool, int, requests.Response]:
    """Method to send a get request to an url endpoint

    :param url: The url endpoint to send the post request to
    :type url: `str`
    :param max_retries: Number of times to retry the request, defaults to `0`
    :type max_retries: `int`, optional
    :param timeout: The number of seconds to wait for a response, defaults to
    `0`
    :type timeout: `int`, optional
    :return: Returns a tuple with:
    * Boolean indicating if the request was succesful or not
    * An integer indicating the nuber of retries
    * The :class:`requests`.`Response` object received
    :rtype: `tuple`[`bool`, `int`, :class:`requests`.`Response`]
    """
    response_tuple = request_retry(
        request_method=requests.get,
        max_retries=max_retries,
        url=url,
        timeout=timeout
    )
    return response_tuple


def check_response_tuple_ok(
    response_tuple: tuple[bool, int, requests.Response],
    url: str
) -> None:
    """Method to check the response tuple is ok

    :param response_tuple: Response tuple
    :type response_tuple: `tuple`[`bool`, `int`, :class:`requests`.Response`]
    :param url: the url endpoint for the request
    :type url: `str`
    :raises RuntimeError: Raises a :class:`RuntimeError` if the response was
    not a correct response
    """
    if not response_tuple[0]:
        raise RuntimeError(
            f"Endpoint {url} is not providing a correct response or is "
            f"unreachable.\nResponse code is {response_tuple[2].status_code} "
            f"and response text is:\n'{response_tuple[2].reason}'"
        )
