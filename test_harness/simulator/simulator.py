# pylint: disable=R0903
# pylint: disable=R0913
"""Generic async simulator
"""
from abc import ABC, abstractmethod
from typing import (
    Callable, Awaitable, Any, NamedTuple, Iterator, Generator, Type, Self,
    Coroutine
)
import asyncio
from datetime import datetime
from multiprocessing import Barrier, Manager
import multiprocessing
import logging
from queue import Empty, Queue
from threading import Thread

from tqdm import tqdm
from test_harness.utils import delayed_async_func
from test_harness.async_management import AsyncKillManager


class SimDatum(NamedTuple):
    """Sub-class of named tuple to carry arguments and keyword arguments and
    an asynchronous action func

    """

    args: list[Any] = []
    kwargs: dict = {}
    action_func: Callable[[Any, Any], Awaitable[Any]] | None = None


class SimDatumTransformer(ABC):
    """Base class to be used for transforming data to :class:`SimDatum`'s"""

    def __init__(self) -> None:
        """Constructor method"""

    @abstractmethod
    def get_sim_datum(
        self,
        *args,
        **kwargs,
    ) -> None:
        """Abstract method to generate :class:`SimDatum`"""


class SimpleSimDatumTranformer(SimDatumTransformer):
    """Sub class that provides the basis for a simple transform to
    :class:`SimDatum`
    """

    def __init__(self) -> None:
        """Constructor method"""

    def get_sim_datum(self, *args, **kwargs) -> Generator[SimDatum, Any, None]:
        """Generates a :class:`SimDatum`

        :yield: _description_
        :rtype: :class:`Generator`[:class:`SimDatum`, `Any`, `None`]
        """
        yield SimDatum(args=args, kwargs=kwargs)


class Batch:
    """Batch class that provides a basis for batching things in a simulation

    :param length: The expected length of the batch
    :type length: `int`
    :param batch_concat: The function to concat all data in the `batch_list`,
    defaults to `None`
    :type batch_concat: :class:`Callable`[[`list`[`Any`]], `Any`] | `None`,
    optional
    """

    def __init__(
        self,
        length: int,
        batch_concat: Callable[[list[Any]], Any] | None = None,
    ) -> None:
        """Constructor method"""
        self._counter = 0
        self._length = length
        self.batch_list = []
        self.batch_concat = batch_concat
        self.batch_output = None

    def update_batcher(self, batch_member: Any) -> bool:
        """Method to update the batch with a new member. Returns True if the
        batch is of the correct size

        :param batch_member: The batch memeber to update
        :type batch_member: `Any`
        :return: Returns a boolean indicating if the batch is now full
        :rtype: `bool`
        """
        self._counter += 1
        self.batch_list.append(batch_member)
        if self._counter == self._length:
            if self.batch_concat:
                self.batch_output = self.batch_concat(self.batch_list)
            else:
                self.batch_output = self.batch_list
            return True
        return False


async def async_do_nothing() -> None:
    """async method to do nothing"""


class ResultsHandler(ABC):
    """Base class for results handling"""
    def __init__(self, results_holder: Any | None = None) -> None:
        """Constructor method"""
        if results_holder is None:
            results_holder: list[Any] = []
        self.results_holder = results_holder

    @abstractmethod
    def handle_result(self, result: Any) -> None:
        """Abstract method that will be called in the simulation class to
        handle the results provided

        :param result: The result from the simulation iteration
        :type result: `Any`
        """


class SimpleResultsHandler(ResultsHandler):
    """Sub class of :class:`ResultsHandler` to provide a simple means of
    saving results to the class.
    """

    def __init__(self, results_holder: Any | None = None) -> None:
        """Constructor method"""
        super().__init__(results_holder)

    def handle_result(self, result: Any) -> None:
        """Method to append the given result to the results list

        :param result: The result from the simulation iteration
        :type result: `Any`
        """
        self.results_holder.append(result)


class QueueHandler(ResultsHandler):
    """Abstract Subclass of :class:`ResultsHandler` to handle queueing
    of queuing of items added to the queue through queue_handler method.

    :param results_holder: The results holder to add the results to, defaults
    to `None`
    :type results_holder: `Any` | `None`, optional
    :param queue_type: The type of queue to use, defaults to :class:`Queue`
    :type queue_type: :class:`Type`[:class:`Queue`] | :class:`Type`[
    :class:`multiprocessing.Queue`], optional
    """
    def __init__(
        self,
        results_holder: Any | None = None,
        queue_type: Type[Queue] | Type[multiprocessing.Queue] = Queue,
    ) -> None:
        """Constructor method"""
        super().__init__(results_holder)
        self.queue = queue_type()
        self.daemon_thread = Thread(target=self.queue_handler, daemon=True)
        self.daemon_not_done = True

    def __enter__(self) -> Self:
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
        result: Any,
    ) -> None:
        """Method to handle the result from a simulation iteration

        :param result: The result from to add to the queue
        :type result: `Any`
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

    @abstractmethod
    def handle_item_from_queue(
        self,
        item: Any,
    ) -> None:
        """Method to handle saving the data when an item is take from the queue

        :param item: An item to handle
        :type item: `Any`
        """


class MultiProcessDateSync:
    """Class to sync the start time of multiple processes

    :param num_processes: The number of processes to sync
    :type num_processes: `int`
    """
    def __init__(
        self,
        num_processes: int,
    ) -> None:
        """Constructor method"""
        self.barrier = Barrier(
            num_processes,
            self.update_queue_with_synced_date
        )
        self.manager = Manager()
        self.sync_list = self.manager.list()

    def update_queue_with_synced_date(self) -> None:
        """Method to update the sync list with the current time"""
        self.sync_list.append(datetime.utcnow())

    def sync(self) -> datetime:
        """Method to sync the processes and return the synced time

        :return: Returns the synced time
        :rtype: :class:`datetime`
        """
        self.barrier.wait()
        return self.sync_list[0]


class Simulator:
    """Generic Simulator class for simulating asynchronous scheduled workloads.

    :param delays: A list of the scheduled starting times for each entry in
    the `simulation_data` iterator. Required size to be less than or equal to
    the size of `simulation_data` iterator.
    :type delays: `list`[`float`]
    :param simulation_data: An iterator of :class:`SimDatum` that contains all
    the data neededfor the simulation
    :type simulation_data: :class:`Iterator`[:class:`SimDatum`]
    :param action_func: Asynchronous function that will act on the
    :class:`SimDatum`, defaults to `None`
    :type action_func: :class:`Callable`[[`Any`, `Any`],
    :class:`Awaitable`[`Any`]] | `None`, optional
    :param return_data: A list that return data from the action_func's is
    added to, defaults to `None`
    :type return_data: `list` | `None`, optional
    :param schedule_ahead_time: The amount of time events in the future are
    scheduled for, e.g. a value of 10 will schedule events approximately 10
    seconds before they are due to happen
    :type schedule_ahead_time: `int`, optional
    :param pbar: A progress bar instance, defaults to `None`
    :type pbar: :class:`tqdm` | `None`, optional
    """

    def __init__(
        self,
        delays: list[float],
        *,
        simulation_data: Iterator[SimDatum],
        action_func: Callable[[Any, Any], Awaitable[Any]] | None = None,
        results_handler: ResultsHandler | None = None,
        schedule_ahead_time=10,
        pbar: tqdm | None = None,
        time_sync: MultiProcessDateSync | None = None,
        kill_manager: AsyncKillManager | None = None,
    ) -> None:
        """Constructor method"""
        self.delays = delays
        self.simulation_data = simulation_data
        self.action_func = action_func
        if not results_handler:
            results_handler = SimpleResultsHandler()
        self.results_handler = results_handler
        self.schedule_ahead_time = schedule_ahead_time
        if schedule_ahead_time < 0.2:
            raise ValueError(
                "Values of less than 0.2 can lead to unpredictable "
                "behaviour, consider increasing the value"
            )
        self.pbar = pbar
        self.time_sync = time_sync
        self.kill_manager = (
            kill_manager if kill_manager is not None else SimMockKillManager()
        )

    async def _execute_simulation_data(self) -> Any:
        """Asynchronous method to execute the next :class:`SimDatum` in the
        instances attribute `simulation_data` iterator

        :raises RuntimeError: Raises a :class:`RuntimeError` when there is no
        action function given - either in the :class:`SimDatum` or directly
        given to the simulator
        :return: Returns the output from the action function used given the
        arguments and keywords arguments in the :class:`SimDatum` taken from
        the iterator
        :rtype: `Any`
        """
        datum = next(self.simulation_data)
        action = self.action_func
        if datum.action_func:
            action = datum.action_func
        if not action:
            raise RuntimeError(
                "There is no action function prescribed for current sim datum"
            )
        return_data = await action(*datum.args, **datum.kwargs)
        return return_data

    async def _pass_data_to_delay_function(
        self, delay: float, pbar: tqdm
    ) -> None:
        """Method to put a delay on (or schedule) the executed simulation data
        for the next item in the `simulation_data` attribute sequence

        :param delay: The delay (or scheduled time) of the execution of the
        simulation data
        :type delay: `float`
        :param pbar: The progress bar instance
        :type pbar: :class:`tqdm`
        """
        return_data = await delayed_async_func(
            delay=delay,
            func=self._execute_simulation_data,
            pbar=pbar,
        )
        self.results_handler.handle_result(return_data)

    async def run_simulation(self, pbar: tqdm) -> None:
        """Method to run the simulation with the given progress bar"""
        async with asyncio.TaskGroup() as task_group:
            if isinstance(self.time_sync, MultiProcessDateSync):
                start_time = self.time_sync.sync()
            else:
                start_time = datetime.utcnow()
            for delay in self.delays:
                time_from_start = (
                    datetime.utcnow() - start_time
                ).total_seconds()
                new_delay = delay - time_from_start
                while new_delay > self.schedule_ahead_time:
                    await asyncio.sleep(0.1)
                    time_from_start = (
                        datetime.utcnow() - start_time
                    ).total_seconds()
                    new_delay = delay - time_from_start
                task_group.create_task(
                    self._pass_data_to_delay_function(
                        delay=new_delay, pbar=pbar
                    )
                )

    async def simulate(self) -> None:
        """Method to simulate the instances simulation data"""
        if self.pbar is None:
            with tqdm(total=len(self.delays)) as pbar:
                await self.kill_manager(self.run_simulation(pbar))
        else:
            await self.kill_manager(self.run_simulation(self.pbar))


class SimMockKillManager:
    """Mock class to replace the :class:`AsyncKillManager` class in the
    simulator
    """
    async def __call__(
        self,
        coro: Coroutine[Any, Any, Any],
    ) -> Any:
        """Method to run the coroutine

        :param coro: The coroutine to run
        :type coro: :class:`Coroutine`[`Any`, `Any`, `Any`]
        """
        await coro
