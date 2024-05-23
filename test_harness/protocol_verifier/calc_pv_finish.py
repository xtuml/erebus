# pylint: disable=R0914
"""Requests to pv for files"""
import asyncio
from time import time
import os
from typing import Any
import logging

from test_harness.requests_th.request_logs import get_log_files
from test_harness.requests_th.request_pv_io import (
    gather_get_requests_json_response,
)
from test_harness.config.config import TestConfig
from test_harness.protocol_verifier.config.config import ProtocolVerifierConfig

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
    return (greater_required_time_interval, is_same)


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
    interval = (t_diff // interval_time + 1) * interval_time - t_diff
    return interval


async def get_coords(
    urls: dict[str, str], read_timeout: float = 300.0
) -> dict[str, tuple[int, int]]:
    """Asynchronous function to get time, number of files pairs for each url

    :param urls: Dictionary mapping domain to urls to get the pairs
    :type urls: `dict`[`str`, `str`]
    :param read_timeout: The timeout for reading of the request, defaults to
    `300.0`
    :type read_timeout: `float`
    :return: Returns dictionary mapping domain to time, number of files pair
    :rtype: `dict`[`str`, `tuple`[`int`, `int`]]
    """
    num_files = await gather_get_requests_json_response(
        urls.values(), read_timeout=read_timeout
    )
    return {
        url_name: (coord_pair["t"], coord_pair["num_files"])
        for url_name, coord_pair in zip(urls.keys(), num_files)
    }


async def pv_inspector_io(
    coords: dict[str, list[tuple[int, int]]],
    io_calc_interval_time: int,
    urls: dict[str, str],
    read_timeout: float = 300.0,
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
    :param read_timeout: The timeout for reading of the request, defaults to
    `300.0`
    :type read_timeout: `float`
    """
    while True:
        t_1 = time()
        await handle_coords_request(
            coords=coords, urls=urls, read_timeout=read_timeout
        )
        t_2 = time()
        interval = calc_interval(t_1, t_2, io_calc_interval_time)
        await asyncio.sleep(interval)


async def handle_coords_request(
    coords: dict[str, list[tuple[int, int]]],
    urls: dict[str, str],
    read_timeout: float = 300.0,
) -> None:
    """Asynchronous method to handle request to obtain the number of files in
    the pv directories. Looks for timeout excpetions and logs a warning
    indicating the problem.

    :param coords: Dictionary mapping domain to lists of time, number of files
    pair
    :type coords: `dict`[`str`, `list`[`tuple`[`int`, `int`]]]
    :param urls: Dictionary mapping domain to url
    :type urls: `dict`[`str`, `str`]
    :param read_timeout: The timeout for reading of the request, defaults to
    `300.0`
    :type read_timeout: `float`
    """
    try:
        current_coords = await get_coords(urls=urls, read_timeout=read_timeout)
        for domain, coord in current_coords.items():
            coords[domain].append(coord)
    except asyncio.TimeoutError:
        logging.getLogger().warning(
            "Obtaining the number of files in one of the domains has timed"
            " out. Suggest increasing the harnes config parameter"
            " io_read_timeout and io_calc_interval_time if this is smaller"
            " than the time requests are tiaking to timeout %.1f",
            read_timeout,
        )


async def pv_finish_inspector_logs(
    file_names: dict[str, list[str]],
    urls: dict[str, dict[str, str]],
    interval_time: int,
    required_time_interval: int,
    log_file_store_path: str,
    save_log_files: bool = True,
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
    :param save_log_files: Boolean indicating whether to save the log files,
    defaults to `True`
    :type save_log_files: `bool`, optional
    :raises RuntimeError: Raises a :class:`RuntimeError` when the run has
    finished
    """
    prev_file_strings = {domain: "" for domain in file_names.keys()}
    current_file_strings = {domain: "" for domain in file_names.keys()}
    most_current_log_file_names = {domain: "" for domain in file_names.keys()}
    last_time_changes = {domain: time() for domain in file_names.keys()}
    while True:
        t_1 = time()
        finished_params = {}
        for domain, domain_file_names in file_names.items():
            (
                current_log_file_name,
                current_log_file_string,
                unreceived_log_file_names,
            ) = handle_domain_log_file_reception_and_save(
                urls=urls[domain],
                domain_file_names=[
                    domain_file_name
                    for domain_file_name in domain_file_names
                    if ".gz" in domain_file_name
                ],
                log_file_store_path=log_file_store_path,
                save_log_files=save_log_files,
                file_prefix=urls[domain]["prefix"],
                location=urls[domain]["location"],
            )
            # update domain variables
            most_current_log_file_names[domain] = current_log_file_name
            current_file_strings[domain] = current_log_file_string
            if current_log_file_name:
                if current_log_file_name not in domain_file_names:
                    domain_file_names.append(current_log_file_name)
            domain_file_names.extend(unreceived_log_file_names)
            # calculate the domain finished parameters
            finished_params[domain] = calc_pv_finished_params(
                (last_time_changes[domain], prev_file_strings[domain]),
                (t_1, current_log_file_string),
                required_time_interval,
            )
        # check whether the run is deemed to have been finished
        if all(
            param
            for domain_finish_params in finished_params.values()
            for param in domain_finish_params
        ):
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
        interval = calc_interval(t_1, t_2, interval_time)
        await asyncio.sleep(interval)


def handle_domain_log_file_reception_and_save(
    urls: dict[str, str],
    domain_file_names: list[str],
    log_file_store_path: str,
    location: str | None = None,
    file_prefix: str | None = None,
    save_log_files: bool = True,
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
    :param location: The location of the log files, defaults to `None`
    :type location: `str`, optional
    :param file_prefix: The prefix of the log files, defaults to `None`
    :type file_prefix: `str`, optional
    :param save_log_files: Boolean indicating whether to save the log files,
    defaults to `True`
    :type save_log_files: `bool`, optional
    :return: Returns a tuple of:
    * the current log file name
    * the current log file string
    * a list of log files received excluding the current log file
    :rtype: `tuple`[`str`, `str`, `list`[`str`]]
    """
    log_files = get_log_files(
        url_log_file_names=urls["getFileNames"],
        url_get_file=urls["getFile"],
        already_received_file_names=domain_file_names,
        location=location,
        file_prefix=file_prefix,
    )
    return save_log_file_strings(
        log_files, log_file_store_path, save_log_files
    )


def save_log_file_strings(
    log_files: dict[str, str],
    log_file_store_path: str,
    save_log_files: bool = True,
) -> tuple[str, str, list[str]]:
    """Method to save the log file strings to file and returns
    the current log file string, the log files that were received excluding
    the current log file and the current log fiel name

    :param log_files: Dictionary mapping log file name to log file string
    :type log_files: `dict`[`str`, `str`]
    :param log_file_store_path: The path of the log file store
    :type log_file_store_path: `str`
    :param save_log_files: Boolean indicating whether to save the log files,
    defaults to `True`
    :type save_log_files: `bool`, optional
    :return: Returns a tuple of:
    * the current log file name
    * the current log file string
    * a list of log files received excluding the current log file
    :rtype: `tuple`[`str`, `str`, `list`[`str`]]
    """
    current_log_file_string = ""
    log_files_received = []
    current_log_file_name = ""
    for file_name, file_string in log_files.items():
        if save_log_files:
            with open(
                os.path.join(log_file_store_path, file_name),
                "w",
                encoding="utf-8",
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
    :type harness_config: :class:`ProtocolVerifierConfig`
    """

    def __init__(
        self,
        harness_config: ProtocolVerifierConfig,
        test_config: TestConfig,
        save_log_files: bool = True,
    ) -> None:
        """Constructor method"""
        self.harness_config = harness_config
        self.test_config = test_config
        self.coords: dict[str, list[tuple[int, int]]] = {
            domain: [] for domain in ["aer", "ver"]
        }
        self.file_names: dict[str, list[str]] = {
            domain: [] for domain in ["aer", "ver"]
        }
        self.test_boundaries: tuple[int, int, int, int, int] | None = None
        self.save_log_files = save_log_files

    async def run_pv_file_inspector(
        self,
    ) -> None:
        """Method to run the pv file inspector and update attributes"""
        gathered_futures = asyncio.gather(
            pv_finish_inspector_logs(
                file_names=self.file_names,
                urls=self.harness_config.log_urls,
                interval_time=self.test_config.test_finish[
                    "metric_get_interval"
                ],
                required_time_interval=(
                    self.test_config.test_finish["finish_interval"]
                ),
                log_file_store_path=self.harness_config.log_file_store,
                save_log_files=self.save_log_files,
            )
        )
        await gathered_futures

    def calc_test_boundaries(self) -> tuple[int, int, int]:
        """Method to calculate the boundaries of the tes

        :return: Returns a tuple of integere of the:
        * start of the test
        * end of the test
        * test running time
        * aer end time
        * ver end time
        :rtype: `tuple`[`int`, `int`, `int`, `int`, `int`]
        """
        test_start = min(self.coords["aer"][0][0], self.coords["ver"][0][0])
        aer_end_time = self.calc_domain_end(self.coords["aer"]) - test_start
        test_end_time = self.calc_domain_end(self.coords["ver"])
        test_run_time = test_end_time - test_start
        ver_end_time = test_end_time - test_start
        self.test_boundaries = (
            test_start,
            test_end_time,
            test_run_time,
            aer_end_time,
            ver_end_time,
        )

    @staticmethod
    def calc_domain_end(domain_coords: list[tuple[int, int]]) -> int:
        """Method to calculate the end time of a domain

        :param domain_coords: The coordinates of the domain to calculate end
        time for
        :type domain_coords: `list`[`tuple`[`int`, `int`]]
        :return: Returns the end time for the domain
        :rtype: `int`
        """
        end_time = domain_coords[-1][0]
        for coord, coord_prev in zip(
            domain_coords[-1:0:-1], domain_coords[-2::-1]
        ):
            difference = coord[1] - coord_prev[1]
            if difference != 0:
                end_time = coord[0]
                break
        return end_time

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
                "r",
                encoding="utf-8",
            ) as file:
                log_string += file.read() + "\n"
        return log_string

    def normalise_coords(self) -> None:
        """Method to normalise data"""
        if not self.test_boundaries:
            return
        for domain, coords in self.coords.items():
            coords_start = coords[0]
            for index, coord in enumerate(coords):
                coords[index] = (
                    coord[0] - self.test_boundaries[0],
                    (
                        coord[1] - coords_start[1]
                        if domain == "ver"
                        else coord[1]
                    ),
                )
