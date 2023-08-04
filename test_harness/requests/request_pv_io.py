"""Methods to request the number of files processed by pv
"""
import asyncio

import aiohttp


async def get_request_json_response(url: str) -> dict:
    """Asynchronous get request from given url with json response

    :param url: The url to send the request to
    :type url: `str`
    :return: Returns a json response as a dictionary
    :rtype: `dict`
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()


async def gather_get_requests_json_response(urls: list[str]) -> list:
    """Method to gather async get request with json response

    :param urls: List of urls to send the requests to
    :type urls: `list`[`str`]
    :return: Returns a list of the dictionary representations of the json
    responses
    :rtype: `list`[`dict`]
    """
    tasks = [
        get_request_json_response(url) for url in urls
    ]
    responses = await asyncio.gather(*tasks)
    return responses
