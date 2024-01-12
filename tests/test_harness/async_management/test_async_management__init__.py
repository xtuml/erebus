"""Tests for async_management module.
"""
from test_harness.async_management import (
    AsyncMPManager, AsyncKillManager
)
import asyncio
import time

import pytest


class TestAsyncKillManager:
    @staticmethod
    async def process_wait_with_exception(
        delay: int = 1,
    ):
        await asyncio.sleep(delay)
        raise RuntimeError("Test")

    @staticmethod
    @pytest.mark.asyncio
    async def test_gathered__call__s():
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
    @staticmethod
    def process_wait(delay: int = 1):
        time.sleep(delay)

    @staticmethod
    async def process_wait_and_kill(
        kill_event: asyncio.Event,
        delay: int = 1,
    ):
        await asyncio.sleep(delay)
        kill_event.set()

    @staticmethod
    @pytest.mark.asyncio
    async def test_run_processes():
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
