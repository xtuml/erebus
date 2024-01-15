"""Tests for async_management module.
"""
from test_harness.async_management import (
    AsyncMPManager, AsyncKillManager
)
import asyncio
import time

import pytest


class TestAsyncKillManager:
    """Tests for AsyncKillManager class.
    """
    @staticmethod
    async def process_wait_with_exception(
        delay: int = 1,
    ) -> None:
        """Coroutine that waits for a specified amount of time and then raises
        an exception.

        :param delay: The amount of time to wait before raising an exception.
        :type delay: `int`
        """
        await asyncio.sleep(delay)
        raise RuntimeError("Test")

    @staticmethod
    @pytest.mark.asyncio
    async def test_gathered__call__s() -> None:
        """Test that the kill event is set when a coroutine raises an
        exception.
        """
        manager = AsyncKillManager()
        with pytest.raises(RuntimeError) as error:
            t1 = time.time()
            await asyncio.gather(
                manager(TestAsyncKillManager.process_wait_with_exception(1)),
                manager(asyncio.sleep(20))
            )
        t2 = time.time()
        assert error.value.args[0] == "Test"
        assert manager.kill_event.is_set()
        assert t2 - t1 < 2
        assert t2 - t1 >= 1


class TestAsyncMPManager:
    """Tests for AsyncMPManager class.
    """
    @staticmethod
    def process_wait(delay: int = 1) -> None:
        """Process that waits for a specified amount of time.

        :param delay: The delay, defaults to `1`
        :type delay: `int`, optional
        """
        time.sleep(delay)

    @staticmethod
    async def process_wait_and_kill(
        kill_event: asyncio.Event,
        delay: int = 1,
    ) -> None:
        """Coroutine that waits for a specified amount of time and then sets a
        kill event.

        :param kill_event: The kill event to set.
        :type kill_event: :class:`asyncio`.`Event`
        :param delay: The amount of time to wait before setting the kill event,
        defaults to `1`
        :type delay: `int`, optional
        """
        await asyncio.sleep(delay)
        kill_event.set()

    @staticmethod
    @pytest.mark.asyncio
    async def test_run_processes() -> None:
        """Test that processes are run.
        """
        manager = AsyncMPManager()
        manager.add_process(
            target=TestAsyncMPManager.process_wait,
            args=(1, ),
            kwargs={},
            daemon=True
        )
        manager.add_process(
            target=TestAsyncMPManager.process_wait,
            args=(1, ),
            kwargs={},
            daemon=True
        )
        t1 = time.time()
        await manager.run_processes()
        t2 = time.time()
        assert t2 - t1 < 3
