# pylint: disable=W0622
# pylint: disable=R0903
"""Utility functions
"""
from typing import Generator, Any, Literal, Callable, Awaitable
from io import BytesIO
import os
import glob
import logging
import asyncio
import shutil

import flatdict
from tqdm import tqdm
import numpy as np


def create_file_io_file_name_tuple(
    file_name: str,
    file_string: str
) -> tuple[BytesIO, str]:
    """Function to create file io file name tuple from a file name and file
    string

    :param file_name: The name of the file
    :type file_name: `str`
    :param file_string: The string representing the file
    :type file_string: `str`
    :return: Returns a tuple of the file io and file name pair
    :rtype: `tuple`[:class:`BytesIO`, `str`]
    """
    return (
        BytesIO(file_string.encode("utf-8")),
        file_name
    )


def create_file_io_file_name_tuple_with_file_path(
    file_path: str,
    file_string: str
) -> tuple[BytesIO, str]:
    """Function to create file io file name tuple from a file path and file
    string

    :param file_path: The path of the file
    :type file_path: `str`
    :param file_string: The string representing the file
    :type file_string: `str`
    :return: Returns a tuple of the file io and file name pair
    :rtype: `tuple`[:class:`BytesIO`, `str`]
    """
    file_io_file_name = create_file_io_file_name_tuple(
        os.path.basename(file_path),
        file_string
    )
    return file_io_file_name


def divide_chunks(
    list_to_chunk: list,
    chunk_size: int
) -> Generator[list, Any, None]:
    """Method to split list into chunks

    :param list_to_chunk: The list ot chunk
    :type list_to_chunk: `list`
    :param chunk_size: The size of the chunks
    :type chunk_size: `int`
    :yield: Generates lists
    :rtype: :class:`Generator`[`list`, `Any`, `None`]
    """
    for index in range(0, len(list_to_chunk), chunk_size):
        yield list_to_chunk[index: index + chunk_size]


def clean_directories(
    directory_paths: list[str]
) -> None:
    """Method to clear directories of non-hidden files

    :param directory_paths: Paths of directories to clear
    :type directory_paths: `list`[`str`]
    """
    for directory_path in directory_paths:
        clean_directory(directory_path)


def clean_directory(
    directory_path: str
) -> None:
    """Method to clear a directory of non-hidden files

    :param directory_path: The path of the directory to clear
    :type directory_path: `str`
    """
    files = glob.glob("*", root_dir=directory_path)
    for file in files:
        path = os.path.join(
            directory_path,
            file
        )
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


def check_dict_equivalency(
    dict_1: dict,
    dict_2: dict
) -> None:
    """Method to check the equivalency of two dictionaries

    :param dict_1: Dictionary to compare
    :type dict_1: `dict`
    :param dict_2: Dictionary to compare
    :type dict_2: `dict`
    """
    flat_dict_1 = flatdict.FlatterDict(
        dict_1
    )
    flat_dict_2 = flatdict.FlatterDict(
        dict_2
    )
    for sub_1_item, sub_2_item in zip(
        sorted(flat_dict_1.items(), key=lambda item: item[0]),
        sorted(flat_dict_2.items(), key=lambda item: item[0])
    ):
        # check sorted values are the same
        # for floats check if nan first
        if (
            isinstance(sub_1_item[1], float) and
            isinstance(sub_2_item[1], float)
        ):
            if np.isnan(sub_1_item[1]) and np.isnan(sub_2_item[1]):
                assert True
            else:
                assert sub_1_item[1] == sub_2_item[1]
        else:
            assert sub_1_item[1] == sub_2_item[1]
        # check the value lies at the correct depth
        assert (
            len(sub_1_item[0].split(":"))
        ) == (
            len(sub_2_item[0].split(":"))
        )


class FilterException(Exception):
    """:class:`Exception` subslass to differentiate exceptions when logs
    filtered by :class:`ErrorFilter:
    """
    def __init__(self, *args: object) -> None:
        """Constructor method
        """
        super().__init__(*args)


class ErrorFilter(logging.Filter):
    """Subclass of :class:`logging`.`Filter` used to filter anything but
    errors from the logger and raise a :class:`FilterException` error when an
    error is logged

    :param name: Name of the filter, defaults to `""`
    :type name: `str`, optional
    """
    def __init__(self, name: str = "") -> None:
        """Constructor method
        """
        super().__init__(name)
        self.output_error_message: str

    def filter(self, record: logging.LogRecord) -> Literal[False]:
        """Method to perform the described filtering

        :param rec: The logging record
        :type rec: :class:`logging`.`LogRecord`
        :raises FilterException: Raises a :class:`FilterException` when an
        error is logged
        :return: Returns `False` if an error is not raised
        :rtype: :class:`Literal`[`False`]
        """
        if record.levelno == logging.ERROR:
            self.output_error_message = record.msg
            raise FilterException(
                "There was a logging error from the logger"
            )
        return False


def collect_error_logs_from_func(
    logger: logging.Logger,
    filter: ErrorFilter,
    func: Callable,
    *args,
    **kwargs
) -> None:
    """Collects errors logs and raises exception when found. Filters any other
    logs

    :param logger: The logger
    :type logger: :class:`logging`.`Logger`
    :param filter: The filter
    :type filter: :class:`ErrorFilter`
    :param func: Function whose logs will be collected and filtered
    :type func: :class:`Callable`
    :raises FilterException: Raises a :class:`FilterException` when the filter
    raises the same excpetion
    """
    logger.addFilter(filter)
    try:
        func(*args, **kwargs)
    except FilterException as error:
        logger.removeFilter(filter)
        raise error
    logger.removeFilter(filter)


async def delayed_async_func(
    delay: float,
    func: Callable[..., Awaitable[Any]],
    *,
    pbar: tqdm | None = None,
    args: list[Any] | None = None,
    kwargs: dict | None = None
) -> Any:
    """Method to delay an async func by an amount of time in seconds

    :param delay: The delay before th async function starts
    :type delay: `float`
    :param func: The async function to delay
    :type func: :class:`Callable`[`...`, :class:`Awaitable`[`Any`]]
    :param pbar: Progress bar
    :type pbar: :class:`tqdm`
    :return: Returns any value that the input function would
    :rtype: `Any`
    """
    await asyncio.sleep(delay)
    if pbar:
        pbar.update(1)
    if not args:
        args = []
    if not kwargs:
        kwargs = {}
#   This has been placed before the await
#   as running it after the await could cause the
#   updates to happen out of order
    awaited_data = await func(*args, **kwargs)
    return awaited_data
