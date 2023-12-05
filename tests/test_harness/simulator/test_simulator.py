# pylint: disable=W0212
# pylint: disable=W0143
# pylint: disable=R0903
# pylint: disable=R0913
# pylint: disable=R1735
"""Tests for simulator.py
"""
import asyncio
import math
from time import time
from typing import Any
from multiprocessing import Process, Manager

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from tqdm import tqdm

from test_harness.simulator.simulator import (
    Batch,
    SimDatum,
    SimpleResultsHandler,
    SimpleSimDatumTranformer,
    Simulator,
    async_do_nothing,
    MultiProcessDateSync
)


class TestSimDatum:
    """Group of tests for :class:`SimDatum`"""

    @staticmethod
    def test_sim_datum_no_kwargs() -> None:
        """Tests :class:`SimDatum` with no kwargs given"""
        sim_datum = SimDatum()
        assert isinstance(sim_datum.args, list)
        assert isinstance(sim_datum.kwargs, dict)
        assert not sim_datum.args and not sim_datum.kwargs
        assert sim_datum.action_func is None

    @staticmethod
    def test_sim_datum() -> None:
        """Tests :class:`SimDatum` with kwargs given"""
        args = [1]
        kwargs = {"kwarg": 1}

        async def action_func() -> None:
            await asyncio.sleep(1)

        sim_datum_kwargs = {
            "args": args,
            "kwargs": kwargs,
            "action_func": action_func,
        }
        sim_datum = SimDatum(**sim_datum_kwargs)
        for kwarg_name, kwarg in sim_datum_kwargs.items():
            assert kwarg == getattr(sim_datum, kwarg_name)


class TestSimulator:
    """Group of tests for :class:`Simulator`"""

    @staticmethod
    @pytest.mark.asyncio
    async def test__execute_simulation_data_single_action_func_iterator():
        """Tests :class:`Simulator`.`_execute_simulation_data` with a single
        action function input to the instance as an attribute and using an
        input iterator
        """
        delays = [1]
        simulation_data = [SimDatum(args=[{}], kwargs={"kwarg": {}})]
        simulation_data_iter = iter(simulation_data)

        async def action_func(arg, kwarg) -> None:
            return (arg, kwarg)

        simulator = Simulator(
            delays=delays,
            simulation_data=simulation_data_iter,
            action_func=action_func,
        )
        return_data = await simulator._execute_simulation_data()

        assert return_data[0] == simulation_data[0].args[0]
        assert return_data[1] == simulation_data[0].kwargs["kwarg"]

    @staticmethod
    @pytest.mark.asyncio
    async def test__execute_simulation_data_single_action_func_generator():
        """Tests :class:`Simulator`.`_execute_simulation_data` with a single
        action function input to the instance as an attribute and using an
        input generator
        """
        delays = [1]
        simulation_data = SimDatum(args=[{}], kwargs={"kwarg": {}})

        def gen_data():
            """Create generator"""
            yield simulation_data

        simulation_data_gen = gen_data()

        async def action_func(arg, kwarg) -> None:
            return (arg, kwarg)

        simulator = Simulator(
            delays=delays,
            simulation_data=simulation_data_gen,
            action_func=action_func,
        )
        return_data = await simulator._execute_simulation_data()

        assert return_data[0] == simulation_data.args[0]
        assert return_data[1] == simulation_data.kwargs["kwarg"]

    @staticmethod
    @pytest.mark.asyncio
    async def test__execute_simulation_data_action_func_in_iterator() -> None:
        """Tests :class:`Simulator`.`_execute_simulation_data` with an
        action function input into the :class:`SimDatum`
        """

        async def action_func(arg, kwarg) -> None:
            return (arg, kwarg)

        delays = [1]
        simulation_data = [
            SimDatum(args=[{}], kwargs={"kwarg": {}}, action_func=action_func)
        ]
        simulation_data_iter = iter(simulation_data)
        simulator = Simulator(
            delays=delays,
            simulation_data=simulation_data_iter,
        )
        return_data = await simulator._execute_simulation_data()

        assert return_data[0] == simulation_data[0].args[0]
        assert return_data[1] == simulation_data[0].kwargs["kwarg"]

    @staticmethod
    @pytest.mark.asyncio
    async def test__execute_simulation_data_no_action_func() -> None:
        """Tests :class:`Simulator`.`_execute_simulation_data` with no action
        function provided to the instance or in the :class:`SimDatum`
        """
        delays = [1]
        simulation_data = [
            SimDatum(
                args=[{}],
                kwargs={"kwarg": {}},
            )
        ]
        simulation_data_iter = iter(simulation_data)
        simulator = Simulator(
            delays=delays,
            simulation_data=simulation_data_iter,
        )
        with pytest.raises(RuntimeError) as e_info:
            await simulator._execute_simulation_data()
        assert e_info.value.args[0] == (
            "There is no action function prescribed for current sim datum"
        )

    @staticmethod
    @pytest.mark.asyncio
    async def test__pass_data_to_delay_func() -> None:
        """Tests :class:`Simulator`.`_pass_data_to_delay_func`"""
        delays = [2.0]
        simulation_data = [SimDatum(args=[{}], kwargs={"kwarg": {}})]
        simulation_data_iter = iter(simulation_data)

        async def action_func(arg, kwarg) -> None:
            return (arg, kwarg)

        simulator = Simulator(
            delays=delays,
            simulation_data=simulation_data_iter,
            action_func=action_func,
        )
        with tqdm(total=len(delays)) as pbar:
            t_1 = time()
            await simulator._pass_data_to_delay_function(
                delay=delays[0], pbar=pbar
            )
            t_2 = time()
        assert round(t_2 - t_1) == delays[0]

        assert simulator.results_handler.results[0][0] == (
            simulation_data[0].args[0]
        )
        assert simulator.results_handler.results[0][1] == (
            simulation_data[0].kwargs["kwarg"]
        )

    @staticmethod
    @given(
        st.floats(min_value=0.1),
        st.floats(min_value=0.1, max_value=5.0),
        st.integers(min_value=10, max_value=1000),
    )
    @settings(max_examples=10, deadline=None)
    @pytest.mark.asyncio
    async def test_simulate(
        schedule_ahead_time: float, total_time: float, events_per_second: int
    ) -> None:
        """Tests :class:`Simulator`.`simulate`"""
        # delays = [2.0]
        delays = [
            i / events_per_second
            for i in range(int(events_per_second * total_time))
        ]
        # assert False, delays
        simulation_data = [SimDatum(args=[{}], kwargs={"kwarg": {}})] * len(
            delays
        )
        simulation_data_iter = iter(simulation_data)

        async def action_func(arg, kwarg) -> Any:
            return (arg, kwarg)

        if schedule_ahead_time < 0.2:
            with pytest.raises(ValueError):
                simulator = Simulator(
                    delays=delays,
                    simulation_data=simulation_data_iter,
                    action_func=action_func,
                    schedule_ahead_time=schedule_ahead_time,
                )
            return

        simulator = Simulator(
            delays=delays,
            simulation_data=simulation_data_iter,
            action_func=action_func,
            schedule_ahead_time=schedule_ahead_time,
        )
        t_1 = time()
        await simulator.simulate()
        t_2 = time()
        # The relative tolerance is quite high here as the way range() works
        # can bin things in odd ways that means the total time can be off
        # by up to a second due to rounding errors
        assert math.isclose(
            t_2 - t_1, total_time, rel_tol=1
        ), (
            f"{t_2 - t_1} != {total_time}, time was not close enough to"
            f" total time, args: "
            f"""{dict(
                        schedule_ahead_time=schedule_ahead_time,
                        total_time=total_time,
                        events_per_second=events_per_second
                        )}"""
        )

        assert simulator.results_handler.results[0][0] == (
            simulation_data[0].args[0]
        )
        assert simulator.results_handler.results[0][1] == (
            simulation_data[0].kwargs["kwarg"]
        )


class TestSimpleSimDatumTransformer:
    """Groups of tests for :class:`SimpleSimDatumTransformer`"""

    @staticmethod
    def test_get_sim_datum() -> None:
        """Test for :class:`SimpleSimDatumTransformer`.`get_sim_datum`"""
        simple_transformer = SimpleSimDatumTranformer()
        args = [{}]
        kwargs = {"a_field": "test"}
        generator = simple_transformer.get_sim_datum(*args, **kwargs)
        sim_datums = list(generator)
        assert len(sim_datums) == 1
        assert sim_datums[0].args[0] == args[0]
        assert "a_field" in sim_datums[0].kwargs
        assert sim_datums[0].kwargs["a_field"] == "test"
        assert sim_datums[0].action_func is None


class TestBatch:
    """Class to group tests for :class:`Batch`"""

    @staticmethod
    def test_update_batcher_batch_size_not_reached() -> None:
        """Test for :class:`Batch`.`update_batcher` when the batch size isn't
        reached
        """
        batcher = Batch(length=2, batch_concat=list)
        batch_member = {}
        batcher.update_batcher(batch_member)
        assert batcher._counter == 1
        assert len(batcher.batch_list) == 1
        assert batcher.batch_output is None
        assert batcher.batch_list[0] == batch_member

    @staticmethod
    def test_update_batcher_batch_size_reached() -> None:
        """Test for :class:`Batch`.`update_batcher` when the batch size is
        reached
        """
        batcher = Batch(length=2, batch_concat=list)
        batch_members = [{} for _ in range(2)]
        for batch_member in batch_members:
            batcher.update_batcher(batch_member)
        assert batcher._counter == 2
        assert len(batcher.batch_list) == 2
        assert batcher.batch_output
        for (
            expected_batch_member,
            batch_list_member,
            batch_output_member,
        ) in zip(batch_members, batcher.batch_list, batcher.batch_output):
            assert expected_batch_member == batch_list_member
            assert expected_batch_member == batch_output_member


class TestSimpleResultsHandler:
    """Group of tests for :class:`SimpleResultsHandler`"""

    @staticmethod
    def test_handle_result() -> None:
        """Tests :class:`SimpleResultsHandler`.`handle_result`"""
        result_1 = {}
        result_2 = {}
        result_handler = SimpleResultsHandler()
        result_handler.handle_result(result_1)
        result_handler.handle_result(result_2)


@pytest.mark.asyncio
async def test_async_do_nothing() -> None:
    """Test for `async_do_nothing`"""
    await async_do_nothing()


def test_multiprocess_date_sync() -> None:
    """Test for :class:`MultiProcessDateSync` and it `sync` method"""
    num_processes = 4
    date_sync = MultiProcessDateSync(num_processes=num_processes)
    manager = Manager()
    sync_dict = manager.dict()

    def process_sync_test(
        date_sync: MultiProcessDateSync,
        value_dict,
        process_num
    ) -> None:
        value_dict[process_num] = date_sync.sync().timestamp()

    processes = [
        Process(
            target=process_sync_test,
            args=(date_sync, sync_dict, process_num)
        )
        for process_num in range(num_processes)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join()
    for process in processes:
        process.close()
    assert len(sync_dict) == num_processes
    values = list(sync_dict.values())
    for val, next in zip(
        values[:-1],
        values[1:]
    ):
        assert val == next
