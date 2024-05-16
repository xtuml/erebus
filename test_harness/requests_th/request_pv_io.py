"""Methods to request the number of files processed by pv
"""
import asyncio

import aiohttp
from aiohttp import ClientTimeout


async def get_request_json_response(
    url: str,
    read_timeout: float = 300.0
) -> dict:
    """Asynchronous get request from given url with json response

    :param url: The url to send the request to
    :type url: `str`
    :param read_timeout: The timeout for reading of the request, defaults to
    `300.0`
    :type read_timeout: `float`
    :return: Returns a json response as a dictionary
    :rtype: `dict`
    """
    timeout = ClientTimeout(total=read_timeout)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            return await response.json()


async def gather_get_requests_json_response(
    urls: list[str],
    read_timeout: float = 300.0
) -> list:
    """Method to gather async get request with json response

    :param urls: List of urls to send the requests to
    :type urls: `list`[`str`]
    :param read_timeout: The timeout for reading of the request, defaults to
    `300.0`
    :type read_timeout: `float`
    :return: Returns a list of the dictionary representations of the json
    responses
    :rtype: `list`[`dict`]
    """
    tasks = [
        get_request_json_response(
            url,
            read_timeout=read_timeout
        ) for url in urls
    ]
    responses = await asyncio.gather(*tasks)
    return responses
