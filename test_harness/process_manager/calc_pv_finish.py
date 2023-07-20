# pylint: disable=R0914
"""Requests to pv for files
"""
import asyncio
from time import time
import os
from typing import Any
import logging

import numpy as np

from test_harness.requests.request_logs import get_log_files
from test_harness.requests.request_pv_io import (
    gather_get_requests_json_response
)
from test_harness.config.config import HarnessConfig

logging.basicConfig(level=logging.INFO)


def calc_pv_finished_params(
    coord_prev: tuple[int, Any],
    coord_current: tuple[int, Any],
    required_time_interval: int,
) -> tuple[bool]:
    """Method to calculate if protocol verifier has finished

    :param coord_prev: The previous tuple pair of time and object to check
    :type coord_prev: `tuple`[`int`, `Any`]
    :param coord_current: The current tuple pair of time and object to check
    :type coord_current: `tuple`[`int`,`Any`]
    :param required_time_interval: The time interval between which to check if
    there is no changes
    :type required_time_interval: `int`
    :return: Returns a tuple bool pair:
    * The first entry is True if the time interval is correct
    * The second entry is True if the y coords are the same
    :rtype: `bool`
    """
    greater_required_time_interval = (
        coord_current[0] - coord_prev[0] > required_time_interval
    )
    is_same = coord_current[1] == coord_prev[1]
    return (
        greater_required_time_interval,
        is_same
    )


def calc_interval(
    t_1: float,
    t_2: float,
    interval_time: int,
) -> float:
    """Method to calc the remining interval time after some of the interval
    has been used up. If more than the interval has been used up the new
    interval is calculated so the remaining interval makes up a whole number
    of interval times

    :param t_1: Time when process started
    :type t_1: `float`
    :param t_2: Time when process finished
    :type t_2: `float`
    :param interval_time: The required interval time
    :type interval_time: `int`
    :return: Returns a remainder + integer multiples of the interval time
    :rtype: `float`
    """
    t_diff = t_2 - t_1
    interval = (
        (t_diff // interval_time + 1) * interval_time
        - t_diff
    )
    return interval


async def get_coords(
    urls: dict[str, str]
) -> dict[str, tuple[int, int]]:
    """Asynchronous function to get time, number of files pairs for each url

    :param urls: Dictionary mapping domain to urls to get the pairs
    :type urls: `dict`[`str`, `str`]
    :return: Returns dictionary mapping domain to time, number of files pair
    :rtype: `dict`[`str`, `tuple`[`int`, `int`]]
    """
    num_files = await gather_get_requests_json_response(
        urls.values()
    )
    return {
        url_name: (coord_pair["t"], coord_pair["num_files"])
        for url_name, coord_pair in zip(
            urls.keys(),
            num_files
        )
    }


async def pv_inspector_io(
    coords: dict[str, list[tuple[int, int]]],
    io_calc_interval_time: int,
    urls: dict[str, str]
) -> None:
    """Asynchronous method to inspect the io of folders in the protocol
    verifier

    :param coords: Dictionary mapping domain to lists of time, number of files
    pair
    :type coords: `dict`[`str`, `list`[`tuple`[`int`, `int`]]]
    :param io_calc_interval_time: The interval time before requesting the next
    timestep of number of files
    :type io_calc_interval_time: `int`
    :param urls: Dictionary mapping domain to url
    :type urls: `dict`[`str`, `str`]
    """
    while True:
        t_1 = time()
        current_coords = await get_coords(
            urls=urls
        )
        for domain, coord in current_coords.items():
            coords[domain].append(coord)
        t_2 = time()
        interval = calc_interval(
            t_1,
            t_2,
            io_calc_interval_time
        )
        await asyncio.sleep(interval)


async def pv_finish_inspector_logs(
    file_names: dict[str, list[str]],
    urls: dict[str, dict[str, str]],
    interval_time: int,
    required_time_interval: int,
    log_file_store_path: str
) -> None:
    """Asynchronous method to get pv logs and calculate
    the finish of the test

    :param file_names: Dictionary mapping domain to a list of file names
    retrieved
    :type file_names: `dict`[`str`, `list`[`str`]]
    :param urls: Dictionary mapping domain to dictionarys of urls
    :type urls: `dict`[`str`, `dict`[`str`, `str`]]
    :param interval_time: The amount of time between each process
    :type interval_time: `int`
    :param required_time_interval: The required time interval for no change to
    have occured
    :type required_time_interval: `int`
    :param log_file_store_path: The path of the log file store
    :type log_file_store_path: `str`
    :raises RuntimeError: Raises a :class:`RuntimeError` when the run has
    finished
    """
    prev_file_strings = {
        domain: '' for domain in file_names.keys()
    }
    current_file_strings = {
        domain: '' for domain in file_names.keys()
    }
    most_current_log_file_names = {
       domain: '' for domain in file_names.keys()
    }
    last_time_changes = {
        domain: time() for domain in file_names.keys()
    }
    while True:
        t_1 = time()
        finished_params = {}
        for domain, domain_file_names in file_names.items():
            (
                current_log_file_name,
                current_log_file_string,
                unreceived_log_file_names
            ) = handle_domain_log_file_reception_and_save(
                urls=urls[domain],
                domain_file_names=domain_file_names,
                log_file_store_path=log_file_store_path
            )
            # update domain variables
            most_current_log_file_names[domain] = current_log_file_name
            current_file_strings[domain] = current_log_file_string
            domain_file_names.extend(unreceived_log_file_names)
            # calculate the domain finished parameters
            finished_params[domain] = calc_pv_finished_params(
                (last_time_changes[domain], prev_file_strings[domain]),
                (t_1, current_log_file_string),
                required_time_interval
            )
        # check whether the run is deemed to have been finished
        if all(
            param
            for domain_finish_params in finished_params.values()
            for param in domain_finish_params
        ):
            for domain, domain_most_current_file_name in (
                most_current_log_file_names.items()
            ):
                file_names[domain].append(domain_most_current_file_name)
            raise RuntimeError("Test has finished by given parameters")
        # update the last time changes if there has been a change this
        # iteration
        for domain, domain_finish_params in finished_params.items():
            if not domain_finish_params[1]:
                last_time_changes[domain] = t_1
        # update the previous fle strings to this current iterations file
        # strings
        prev_file_strings = {**current_file_strings}
        t_2 = time()
        interval = calc_interval(
            t_1,
            t_2,
            interval_time
        )
        await asyncio.sleep(interval)


def handle_domain_log_file_reception_and_save(
    urls: dict[str, str],
    domain_file_names: list[str],
    log_file_store_path: str
) -> tuple[str, str]:
    """Method to handle the recption of log files and saving for a specific PV
    domain

    :param urls: Dictionary mapping url type to url string
    :type urls: `dict`[`str`, `str`]
    :param domain_file_names: List of file names already received for the
    particular domain
    :type domain_file_names: `list`[`str`]
    :param log_file_store_path: The path where log files received will be
    stored
    :type log_file_store_path: `str`
    :return: Returns a tuple of:
    * the current log file name
    * the current log file string
    * a list of log files received excluding the current log file
    :rtype: `tuple`[`str`, `str`, `list`[`str`]]
    """
    log_files = get_log_files(
        url_log_file_names=urls["getFileNames"],
        url_get_file=urls["getFile"],
        already_received_file_names=domain_file_names
    )
    return save_log_file_strings(log_files, log_file_store_path)


def save_log_file_strings(
    log_files: dict[str, str],
    log_file_store_path: str,
) -> tuple[str, str, list[str]]:
    """Method to save the log file strings to file and returns
    the current log file string, the log files that were received excluding
    the current log file and the current log fiel name

    :param log_files: Dictionary mapping log file name to log file string
    :type log_files: `dict`[`str`, `str`]
    :param log_file_store_path: The path of the log file store
    :type log_file_store_path: `str`
    :return: Returns a tuple of:
    * the current log file name
    * the current log file string
    * a list of log files received excluding the current log file
    :rtype: `tuple`[`str`, `str`, `list`[`str`]]
    """
    current_log_file_string = ''
    log_files_received = []
    current_log_file_name = ''
    for file_name, file_string in log_files.items():
        with open(
            os.path.join(log_file_store_path, file_name),
            'w',
            encoding="utf-8"
        ) as file:
            file.write(file_string)
        if ".gz" in file_name:
            log_files_received.append(file_name)
        else:
            current_log_file_string = file_string
            current_log_file_name = file_name

    return (
        current_log_file_name,
        current_log_file_string,
        log_files_received,
    )


class PVFileInspector:
    """Class to run methods for the pv file inspector

    :param harness_config: Harness config
    :type harness_config: :class:`HarnessConfig`
    """
    def __init__(
        self,
        harness_config: HarnessConfig
    ) -> None:
        """Constructor method
        """
        self.harness_config = harness_config
        self.coords: dict[str, list[tuple[int, int]]] = {
            domain: []
            for domain in self.harness_config.io_urls.keys()
        }
        self.file_names: dict[str, list[str]] = {
            domain: []
            for domain in self.harness_config.io_urls.keys()
        }

    async def run_pv_file_inspector(
        self,
    ) -> None:
        """Method to run the pv file inspector and update attributes
        """
        io_data = await get_coords(
                urls=self.harness_config.io_urls
            )
        for domain, datum in io_data.items():
            self.coords[domain].append(datum)
        gathered_futures = asyncio.gather(
            pv_finish_inspector_logs(
                file_names=self.file_names,
                urls=self.harness_config.log_urls,
                interval_time=self.harness_config.log_calc_interval_time,
                required_time_interval=self.harness_config.pv_finish_interval,
                log_file_store_path=self.harness_config.log_file_store
            ),
            pv_inspector_io(
                coords=self.coords,
                urls=self.harness_config.io_urls,
                io_calc_interval_time=self.harness_config.io_calc_interval_time
            )
        )
        await gathered_futures

    def calc_test_boundaries(self) -> tuple[int, int, int]:
        """Method to calculate the boundaries of the tes

        :return: Returns a tuple of integere of the:
        * start of the test
        * end of the test
        * test running time
        :rtype: `tuple`[`int`, `int`, `int`]
        """
        test_start = min(
            self.coords["aer"][0][0],
            self.coords["ver"][0][0]
        )
        test_end = self.calc_test_end()
        test_run_time = test_end - test_start
        return (test_start, test_end, test_run_time)

    def calc_test_end(self) -> int:
        """Method to calculate the end of the test

        :return: Returns the end of the test
        :rtype: `int`
        """
        index_end = np.argmax([coord[1] for coord in self.coords["ver"]])
        test_end = self.coords["ver"][index_end][0]
        return test_end

    def load_log_files_and_concat_strings(self, domain: str = "ver") -> str:
        """Method to get a log string from a list of log files from a
        specified domain

        :param domain: The PV domain, defaults to "ver"
        :type domain: `str`, optional
        :return: Returns the concatenated string
        :rtype: `str`
        """
        log_string = ""
        for file_name in self.file_names[domain]:
            with open(
                os.path.join(self.harness_config.log_file_store, file_name),
                'r',
                encoding="utf-8"
            ) as file:
                log_string += file.read() + "\n"
        return log_string


async def run_pv_file_inspector(
    harness_config: HarnessConfig,
) -> tuple[dict[str, list[tuple[int, int]]], list[str]]:
    """Method to run the pv file inspector

    :param harness_config: Test harness config
    :type harness_config: :class:`HarnessConfig`
    :return: Returns a tuple of a dictionary mapping domain to file io and a
    list of filenames generated
    :rtype: `tuple`[`dict`[`str`, `list`[`tuple`[`int`, `int`]]],
    `list`[`str`]]
    """
    urls_io_tracking = harness_config.io_urls
    io_calc_interval_time = harness_config.io_calc_interval_time
    pv_finish_interval = harness_config.pv_finish_interval
    log_calc_interval_time = harness_config.log_calc_interval_time
    log_urls = harness_config.log_urls
    log_store_path = harness_config.log_file_store
    io_data = await get_coords(
            urls=urls_io_tracking
        )
    coords = {
        domain: [datum]
        for domain, datum in io_data.items()
    }
    file_names = {
        domain: []
        for domain in io_data.keys()
    }
    gathered_futures = asyncio.gather(
        pv_finish_inspector_logs(
            file_names=file_names,
            urls=log_urls,
            interval_time=log_calc_interval_time,
            required_time_interval=pv_finish_interval,
            log_file_store_path=log_store_path
        ),
        pv_inspector_io(
            coords=coords,
            urls=urls_io_tracking,
            io_calc_interval_time=io_calc_interval_time
        )
    )
    try:
        await gathered_futures
    except RuntimeError as error:
        logging.getLogger().info(msg=str(error))
    return coords, file_names
