# pylint: disable=W0622
# pylint: disable=R0903
"""Utility functions"""
from typing import Generator, Any, Literal, Callable, Awaitable, Self, TypeVar
from io import BytesIO
import os
import glob
import logging
import asyncio
import shutil
from threading import Thread
from multiprocessing import Queue
from contextlib import contextmanager
from threading import Lock

import flatdict
from tqdm import tqdm
import numpy as np
from kafka3.producer.future import FutureRecordMetadata
from test_harness.async_management import AsyncKillException

T = TypeVar("T")


def create_file_io_file_name_tuple(
    file_name: str, file_string: str
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
    return (BytesIO(file_string.encode("utf-8")), file_name)


def create_file_io_file_name_tuple_with_file_path(
    file_path: str, file_string: str
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
        os.path.basename(file_path), file_string
    )
    return file_io_file_name


def divide_chunks(
    list_to_chunk: list, chunk_size: int
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


def clean_directories(directory_paths: list[str]) -> None:
    """Method to clear directories of non-hidden files

    :param directory_paths: Paths of directories to clear
    :type directory_paths: `list`[`str`]
    """
    for directory_path in directory_paths:
        clean_directory(directory_path)


def clean_directory(directory_path: str) -> None:
    """Method to clear a directory of non-hidden files

    :param directory_path: The path of the directory to clear
    :type directory_path: `str`
    """
    files = glob.glob("*", root_dir=directory_path)
    for file in files:
        path = os.path.join(directory_path, file)
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


def check_dict_equivalency(dict_1: dict, dict_2: dict) -> None:
    """Method to check the equivalency of two dictionaries

    :param dict_1: Dictionary to compare
    :type dict_1: `dict`
    :param dict_2: Dictionary to compare
    :type dict_2: `dict`
    """
    flat_dict_1 = flatdict.FlatterDict(dict_1)
    flat_dict_2 = flatdict.FlatterDict(dict_2)
    for sub_1_item, sub_2_item in zip(
        sorted(flat_dict_1.items(), key=lambda item: item[0]),
        sorted(flat_dict_2.items(), key=lambda item: item[0]),
    ):
        # check sorted values are the same
        # for floats check if nan first
        if isinstance(sub_1_item[1], float) and isinstance(
            sub_2_item[1], float
        ):
            if np.isnan(sub_1_item[1]) and np.isnan(sub_2_item[1]):
                assert True
            else:
                assert sub_1_item[1] == sub_2_item[1]
        else:
            assert sub_1_item[1] == sub_2_item[1]
        # check the value lies at the correct depth
        assert (len(sub_1_item[0].split(":"))) == (
            len(sub_2_item[0].split(":"))
        )


class FilterException(Exception):
    """:class:`Exception` subslass to differentiate exceptions when logs
    filtered by :class:`ErrorFilter:
    """

    def __init__(self, *args: object) -> None:
        """Constructor method"""
        super().__init__(*args)


class ErrorFilter(logging.Filter):
    """Subclass of :class:`logging`.`Filter` used to filter anything but
    errors from the logger and raise a :class:`FilterException` error when an
    error is logged

    :param name: Name of the filter, defaults to `""`
    :type name: `str`, optional
    """

    def __init__(self, name: str = "") -> None:
        """Constructor method"""
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
            raise FilterException("There was a logging error from the logger")
        return False


def collect_error_logs_from_func(
    logger: logging.Logger,
    filter: ErrorFilter,
    func: Callable,
    *args,
    **kwargs,
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
    kwargs: dict | None = None,
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
    if pbar is not None:
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
    if interval_time <= 0:
        return 0
    t_diff = t_2 - t_1
    interval = (t_diff // interval_time + 1) * interval_time - t_diff
    return interval


class ProcessSafeSharedIterator:
    """Class to create an iterator that can be shared between processes

    :param queue: The queue to use
    :type queue: :class:`multiprocessing`.`Queue`
    :param request_queue: The request queue to use
    :type request_queue: :class:`multiprocessing`.`Queue`
    """

    def __init__(self, queue: Queue, request_queue: Queue) -> None:
        """Constructor method"""
        self.queue = queue
        self.request_queue = request_queue

    def __iter__(self) -> Self:
        """Method to return self as the iterator"""
        return self

    def __next__(self) -> Any:
        """Method to get the next item from the queue as an iterator

        :raises StopIteration: Raises a :class:`StopIteration` if the stop
        event is set
        :return: Returns the next item from the queue
        :rtype: `Any`
        """
        self.request_queue.put(True)
        value = self.queue.get()
        if value is False:
            raise StopIteration
        return value


class ProcessGeneratorManager:
    """Class to manage a generator in a separate process

    :param generator: The generator to manage
    :type generator: :class:`Generator`[`Any`, `Any`, `Any`]
    """

    def __init__(
        self,
        generator: Generator[Any, Any, Any],
    ) -> None:
        """Constructor method"""
        self.generator = generator
        self.receive_request_daemon = Thread(target=self.serve, daemon=True)
        self.output_queue = Queue()
        self.receive_queue = Queue()
        self.num_children = 0

    def _update_num_children(self) -> None:
        """Method to update the number of children"""
        self.num_children += 1

    def serve(self) -> None:
        """Method to serve the generator"""
        while True:
            try:
                request = self.receive_queue.get()
                if request is False:
                    break
                self.output_queue.put(next(self.generator))
            except StopIteration:
                break
        # clear up for children
        for _ in range(max(self.num_children, 1)):
            self.output_queue.put(False)

    def __enter__(self) -> Self:
        """Method to enter the context manager

        :return: Returns a :class:`ProcessGeneratorManager` instance
        :rtype: :class:`ProcessGeneratorManager`
        """
        self.receive_request_daemon.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        traceback: Any,
    ) -> None:
        """Method to exit the context manager

        :param exc_type: The type of exception raised if any
        :type exc_type: `type`[:class:`BaseException`]
        :param exc_value: The exception raised if any
        :type exc_value: :class:`BaseException`
        :param traceback: The traceback of the exception raised if any
        :type traceback: `Any`
        :raises exc_value: Raises the exception if any
        """
        # exhaust generator
        logging.getLogger().debug("Exhausting generator")
        self.generator = iter(())
        logging.getLogger().debug("Generator exhausted")
        self.receive_queue.put(False)
        self.receive_request_daemon.join()
        if exc_type is not None:
            raise exc_value

    def create_iterator(self) -> ProcessSafeSharedIterator:
        """Method to create an iterator

        :return: Returns a :class:`ProcessSafeSharedIterator` instance
        :rtype: :class:`ProcessSafeSharedIterator`
        """
        self._update_num_children()
        return ProcessSafeSharedIterator(self.output_queue, self.receive_queue)


def wrap_kafka_future(future: FutureRecordMetadata) -> asyncio.Future[Any]:
    """Method to wrap a kafka future in an asyncio future

    :param future: The kafka future
    :type future: :class:`FutureRecordMetadata`
    :return: Returns an asyncio future
    :rtype: :class:`asyncio`.`Future`[`Any`]
    """
    loop = asyncio.get_event_loop()
    aio_future = loop.create_future()

    def on_err(*_):
        loop.call_soon_threadsafe(aio_future.set_exception, future.exception)

    def on_success(*_):
        loop.call_soon_threadsafe(aio_future.set_result, future.value)

    future.add_callback(on_success)
    future.add_errback(on_err)
    return aio_future


def create_zip_file_from_folder(folder_path: str, zip_file_path: str) -> None:
    """Method to create a zip file from a folder

    :param folder_path: The path of the folder to zip
    :type folder_path: `str`
    :param zip_file_path: The path of the zip file to create
    :type zip_file_path: `str`
    """
    shutil.make_archive(zip_file_path[:-4], "zip", folder_path)


class RollOverChoice:
    """Class to create a roll over choice object

    :param roll_over_value: The roll over value
    :type roll_over_value: `int`
    """

    def __init__(self, roll_over_value: int) -> None:
        """Constructor method"""
        self.roll_over_value = roll_over_value
        if roll_over_value < 1:
            raise ValueError(
                "The roll over value must be an integer greater than or equal"
                "to 1"
            )
        self._counter = 0

    def __call__(self, list_to_choose_from: list[T], k: int = 1) -> list[T]:
        """Method to choose from a list with a roll over value

        :param list_to_choose_from: The list to choose from
        :type list_to_choose_from: `list`[`T`]
        :param k: The number of items to choose, defaults to 1
        :type k: `int`, optional
        :return: Returns a list of items chosen from the input list
        :rtype: `list`[`T`]
        :raises IndexError: Raises an :class:`IndexError` if the roll over
        value is larger than the length of the list
        """
        try:
            return_value = []
            for _ in range(k):
                return_value.append(
                    list_to_choose_from[self._counter % self.roll_over_value]
                )
                self._counter += 1
            return return_value
        except IndexError:
            raise IndexError(
                f"The rollover value ({self.roll_over_value}) is larger than"
                f" the length of the list ({len(list_to_choose_from)}) you are"
                " trying to choose from"
            )


def choose_from_front_of_list(list_to_choose_from: list[T]) -> T:
    """Method to choose from the front of a list

    :param list_to_choose_from: The list to choose from
    :type list_to_choose_from: `list`[`T`]
    :return: Returns the item at the front of the list
    :rtype: `T`
    """
    return list_to_choose_from[0]


class AsyncTestStopper:
    """Class to stop a test"""

    def __init__(self) -> None:
        """Constructor method"""
        self.stop_test = False
        self.lock = Lock()
        self.is_stopped = False

    @contextmanager
    def run_test(
        self,
    ) -> Generator["AsyncTestStopper", Any, None]:
        """Method to run the test as a context manager

        :raises exception: Raises an exception if an exception is raised
        :yield: Yields the instance of the class
        :rtype: `Generator`[:class:`AsyncTestStopper`, `Any`, `None`]
        """
        try:
            self.reset()
            yield self
        except Exception as exception:
            logging.getLogger().error(
                "The folowing type of error occurred %s with value %s",
                type(exception),
                exception,
            )
            raise exception

        finally:
            self.reset()

    async def stop(self) -> None:
        """Method to stop the test"""
        while True:
            await asyncio.sleep(1)
            with self.lock:
                if self.stop_test:
                    self.is_stopped = True
                    logging.getLogger().info("Test stopped")
                    raise AsyncKillException("Test stopped")

    def reset(self) -> None:
        """Method to reset the test"""
        with self.lock:
            self.stop_test = False
            self.is_stopped = False

    def set(self) -> None:
        """Method to set the test"""
        with self.lock:
            self.stop_test = True
