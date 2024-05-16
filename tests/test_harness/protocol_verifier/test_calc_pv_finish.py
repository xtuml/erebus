"""Tests of functionality to calculate PV has finished processing
"""
import logging

from aiohttp import ClientConnectionError
import pytest
from aioresponses import aioresponses


from test_harness.protocol_verifier.calc_pv_finish import pv_inspector_io


logging.basicConfig(level=logging.INFO)


@pytest.mark.asyncio()
async def test_pv_inspector_io_timeout(
    caplog: pytest.LogCaptureFixture
) -> None:
    """Tests `pv_inspector_io` when there is a `asyncio`.`TimeoutError`
    exception raised

    :param caplog: Fixture that captures logs
    :type caplog: `pytest`.`LogCaptureFixture`
    """
    caplog.set_level(logging.INFO)
    with aioresponses() as mock:
        url_aer = "http://test.server/ioTracking/aer-incoming"
        url_ver = "http://test.server/ioTracking/verifier-processed"
        read_timeout = 1.0
        mock.get(url=url_aer, payload={"num_files": 10, "t": 1})
        mock.get(url=url_ver, exception=TimeoutError)

        coords = {"aer": [], "ver": []}
        urls = {
            "aer": "http://test.server/ioTracking/aer-incoming",
            "ver": "http://test.server/ioTracking/verifier-processed"
        }
        with pytest.raises(ClientConnectionError):
            await pv_inspector_io(
                coords=coords,
                io_calc_interval_time=1,
                urls=urls,
                read_timeout=read_timeout
            )
        assert all(len(domain_list) == 0 for domain_list in coords.values())
        assert (
            "Obtaining the number of files in one of the domains has timed"
            " out. Suggest increasing the harnes config parameter"
            " io_read_timeout and io_calc_interval_time if this is smaller"
            f" than the time requests are tiaking to timeout {read_timeout}"
        ) in caplog.text


@pytest.mark.asyncio()
async def test_pv_inspector_io_no_timeout(
    caplog: pytest.LogCaptureFixture
) -> None:
    """Tests `pv_inspector_io` when there is no timeout
    exception raised

    :param caplog: Fixture that captures logs
    :type caplog: `pytest`.`LogCaptureFixture`
    """
    caplog.set_level(logging.INFO)
    with aioresponses() as mock:
        url_aer = "http://test.server/ioTracking/aer-incoming"
        url_ver = "http://test.server/ioTracking/verifier-processed"
        read_timeout = 1.0
        mock.get(url=url_aer, payload={"num_files": 10, "t": 1})
        mock.get(url=url_ver, payload={"num_files": 10, "t": 1})

        coords = {"aer": [], "ver": []}
        urls = {
            "aer": "http://test.server/ioTracking/aer-incoming",
            "ver": "http://test.server/ioTracking/verifier-processed"
        }
        with pytest.raises(ClientConnectionError):
            await pv_inspector_io(
                coords=coords,
                io_calc_interval_time=1,
                urls=urls,
                read_timeout=read_timeout
            )
        assert all(len(domain_list) == 1 for domain_list in coords.values())
        assert (
            "Obtaining the number of files in one of the domains has timed"
            " out. Suggest increasing the harnes config parameter"
            "io_read_timeout and io_calc_interval_time if this is smaller"
            f"than the time requests are tiaking to timeout {read_timeout}"
        ) not in caplog.text
