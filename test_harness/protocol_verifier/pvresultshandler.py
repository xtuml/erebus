# pylint: disable=R0902
# pylint: disable=R0913
# pylint: disable=W0221
# pylint: disable=W0246
# pylint: disable=W0613
# pylint: disable=C0302
# pylint: disable=C0114
import json
import logging
import os
from datetime import datetime
from queue import Empty, Queue
from threading import Thread
from typing import Type, Any

from test_harness.simulator.simulator import ResultsHandler

from .pvresults import PVResults


class PVResultsHandler(ResultsHandler):
    """Subclass of :class:`ResultsHandler` to handle saving of files and data
    from a PV test run. Uses a context manager and daemon thread to save
    results in the background whilst a test is running.


    :param results_holder: Instance used to hold the data relating to the sent
    jobs/events
    :type results_holder: :class:`Results`
    :param test_output_directory: The path of the output directory of the test
    :type test_output_directory: `str`
    :param save_files: Boolean indicating whether the files should be saved or
    not, defaults to `False`
    :type save_files: `bool`, optional
    """

    def __init__(
        self,
        results_holder: PVResults,
        test_output_directory: str,
        save_files: bool = False,
    ) -> None:
        """Constructor method"""
        self.queue = Queue()
        self.results_holder = results_holder
        self.test_output_directory = test_output_directory
        self.daemon_thread = Thread(target=self.queue_handler, daemon=True)
        self.daemon_not_done = True
        self.save_files = save_files

    def __enter__(self) -> None:
        """Entry to the context manager"""
        self.daemon_thread.start()
        return self

    def __exit__(
        self,
        exc_type: Type[Exception] | None,
        exc_value: Exception | None,
        *args
    ) -> None:
        """Exit from context manager

        :param exc_type: The type of the exception
        :type exc_type: :class:`Type` | `None`
        :param exc_value: The value of the excpetion
        :type exc_value: `str` | `None`
        :param traceback: The traceback fo the error
        :type traceback: `str` | `None`
        :raises RuntimeError: Raises a :class:`RuntimeError`
        if an error occurred in the main thread
        """
        if exc_type is not None:
            logging.getLogger().error(
                "The folowing type of error occurred %s with value %s",
                exc_type,
                exc_value,
            )
            raise exc_value
        while self.queue.qsize() != 0:
            continue
        self.daemon_not_done = False
        self.daemon_thread.join()

    def handle_result(
        self,
        result: tuple[
            list[dict[str, Any]],
            str,
            str,
            dict[str, str | None],
            str,
            datetime,
        ]
        | None,
    ) -> None:
        """Method to handle the result from a simulation iteration

        :param result: The result from the PV simulation iteration - could be
        `None` or a tuple of:
        * the event dicts in a list
        * a string representing the filename used to send the data
        * a string representing the job id
        * a dict representing the job info
        * a string representing the response from the request
        :type result: `tuple`[ `list`[`dict`[`str`, `Any`]], `str`, `str`,
        :class:`datetime`
        `dict`[`str`, `str`  |  `None`], `str` ] | `None`
        """
        self.queue.put(result)

    def queue_handler(self) -> None:
        """Method to handle the queue as it is added to"""
        while self.daemon_not_done:
            try:
                item = self.queue.get(timeout=0.1)
                self.handle_item_from_queue(item)
            except Empty:
                continue

    def handle_item_from_queue(
        self,
        item: tuple[
            list[dict[str, Any]],
            str,
            str,
            dict[str, str | None],
            str,
            datetime,
        ]
        | None,
    ) -> None:
        """Method to handle saving the data when an item is take from the queue

        :param item: PV iteration data taken from the queue
        :type item: `tuple`[ `list`[`dict`[`str`, `Any`]], `str`, `str`,
        :class:`datetime`
        `dict`[`str`, `str`  |  `None`], `str` ] | `None`
        """
        if item is None:
            return
        self.results_holder.update_from_sim(
            event_list=item[0],
            job_id=item[2],
            file_name=item[1],
            job_info=item[3],
            response=item[4],
            time_completed=item[5],
        )
        if self.save_files:
            output_file_path = os.path.join(
                self.test_output_directory, item[1]
            )
            with open(output_file_path, "w", encoding="utf-8") as file:
                json.dump(item[0], file)
