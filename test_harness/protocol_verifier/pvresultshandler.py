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
import re
import shelve
from datetime import datetime
from multiprocessing import Pipe, Process, current_process
from multiprocessing.connection import Connection
from queue import Empty, Queue
from threading import Thread
from typing import Type

from test_harness.simulator.simulator import ResultsHandler

from .pvresults import PVResults
from .types import PVResultsHandlerItem


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
        events_cache_file: str | None = None,
    ) -> None:
        """Constructor method"""
        self.queue = Queue()
        self.results_holder = results_holder
        self.test_output_directory = test_output_directory
        self.daemon_thread = Thread(target=self.queue_handler, daemon=True)
        self.daemon_not_done = True
        self.save_files = save_files

        self.events_cache_process: Process | None = None
        self.events_cache_parent_conn: Connection[
            PVResultsHandlerItem | None
        ] | None = None
        """Items sent to this connection are written to the events cache file."""

        if events_cache_file is not None and not events_cache_file.endswith(
            ".db"
        ):
            raise ValueError(
                "events_cache_file must end in '.db', got"
                f" '{events_cache_file}'."
            )
        self.events_cache_file = events_cache_file

        if self.events_cache_file is not None and os.path.exists(
            self.events_cache_file
        ):
            shelf_name = re.sub(r".db$", "", self.events_cache_file)
            with shelve.open(shelf_name) as shelf:
                for item in shelf.values():
                    self.handle_result(item)

    def _events_cache_worker_function(self, child_conn: Connection, filename):
        start_time = datetime.utcnow()
        last_updated = datetime.utcnow()

        id_ = 0
        with shelve.open(filename, writeback=False) as shelf:
            # This loop will continue to run until the child_conn recieves a
            # falsey value, e.g. None, False, etc.
            while item := child_conn.recv():
                id_ += 1
                shelf[str(id_)] = item

                if (last_updated - start_time).total_seconds() > 10:
                    shelf.sync()
                    last_updated = datetime.utcnow()
        return

    def __enter__(self):
        """Entry to the context manager"""
        self.daemon_thread.start()
        return self

    def __exit__(
        self,
        exc_type: Type[Exception] | None,
        exc_value: Exception | None,
        *args,
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
        result: PVResultsHandlerItem | None,
    ) -> None:
        """Method to handle the result from a simulation iteration

        :param result: The result from the PV simulation iteration - could be
        `None` or a tuple of:
        * the event dicts in a list
        * a string representing the filename used to send the data
        * a string representing the job id
        * a dict representing the job info
        * a string representing the response from the request
        :type result: `PVResultsHandlerItem` | `None`
        """
        self.queue.put(result)

    def queue_handler(self) -> None:
        """Method to handle the queue as it is added to"""
        # Hi programmer,
        # You may ask why the events_cache_process is created and started in the
        # queue_handler rather than the __enter__ and __exit__ methods. The
        # reason is simple: in creating the thread, Python somehow calls the
        # __enter__ method *again* and this causes another process to start
        # which is inaccessible within the scope of this code. So the process is
        # started only within the thread and then only one process is ever
        # spawned.
        if self.events_cache_file is not None:
            self.events_cache_parent_conn, child_conn = Pipe()
            shelf_name = re.sub(r".db$", "", self.events_cache_file)
            self.events_cache_process = Process(
                target=self._events_cache_worker_function,
                args=(child_conn, shelf_name),
                daemon=True,
            )
            self.events_cache_process.start()

        while self.daemon_not_done:
            try:
                item = self.queue.get(timeout=0.1)
                self.handle_item_from_queue(item)
            except Empty:
                continue

        if self.events_cache_file is not None:
            self.events_cache_parent_conn.send(None)
            self.events_cache_process.join()

    def handle_item_from_queue(
        self,
        item: PVResultsHandlerItem | tuple | None,
    ) -> None:
        """Method to handle saving the data when an item is take from the queue

        :param item: PV iteration data taken from the queue
        """
        if item is None:
            return

        if isinstance(item, tuple):
            item = PVResultsHandlerItem(*item)

        if self.events_cache_file is not None:
            self.events_cache_parent_conn.send(item)

        self.results_holder.update_from_sim(**item._asdict())

        if self.save_files:
            output_file_path = os.path.join(
                self.test_output_directory, item.file_name
            )
            with open(output_file_path, "w", encoding="utf-8") as file:
                json.dump(item.event_list, file)
