"""Tests for requiest for protocol verifier input and output end points
"""
import asyncio
from typing import Callable, Coroutine, Any
from unittest.mock import patch

import pytest

from test_harness.requests_th.request_pv_io import (
    get_request_json_response,
)


def timeout(
    delay: float
) -> Callable[..., Coroutine[Any, Any, None]]:
    """Wrapped function so a timeout can be set in a mock connection

    :param delay: The delay of the timeout
    :type delay: `float`
    :return: Returns a coroutine that will be called as a side effect in a mock
    :rtype: :class:`Callable`[`...`, :class:`Coroutine`[`Any`, `Any`, `None`]]
    """
    async def async_timeout(*args, **kwargs) -> None:  # pylint: disable=W0613
        await asyncio.sleep(delay)
        raise RuntimeError("Total timeout passed")
    return async_timeout


@pytest.mark.asyncio
async def test_get_request_json_response_timeout_error() -> None:
    """Tests `get_request_json_response` when the reuqest takes longer than
    the specified timeout
    """
    url = "http://test-server.com/test"

    with patch(
        "aiohttp.connector.BaseConnector.connect",
        side_effect=timeout(1)
    ):
        with pytest.raises(TimeoutError):
            await get_request_json_response(
                url=url,
                read_timeout=0.1
            )


@pytest.mark.asyncio
async def test_get_request_json_response_timeout_no_error() -> None:
    """Tests `get_request_json_response` when the reuqest takes less time than
    the specified timeout
    """
    url = "http://test-server.com/test"

    with patch(
        "aiohttp.connector.BaseConnector.connect",
        side_effect=timeout(1)
    ):
        with pytest.raises(RuntimeError) as error:
            await get_request_json_response(
                url=url,
                read_timeout=2
            )
        assert error.value.args[0] == "Total timeout passed"
