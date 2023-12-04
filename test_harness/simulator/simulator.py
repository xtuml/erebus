# pylint: disable=R0903
# pylint: disable=R0913
"""Generic async simulator
"""
from abc import ABC, abstractmethod
from typing import Callable, Awaitable, Any, NamedTuple, Iterator, Generator
import asyncio
from datetime import datetime

from tqdm import tqdm
from test_harness.utils import delayed_async_func


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

    def __init__(self) -> None:
        """Constructor method"""
        self.results: list[Any] = []

    def handle_result(self, result: Any) -> None:
        """Method to append the given result to the results list

        :param result: The result from the simulation iteration
        :type result: `Any`
        """
        self.results.append(result)


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
                await self.run_simulation(pbar)
        else:
            await self.run_simulation(self.pbar)
