"""Package to manage multprocessing for the test harness.
"""
import asyncio
from typing import Callable, Iterable, Any, Coroutine
from multiprocessing import Process


class AsyncMPManager:
    def __init__(
        self,
    ):
        self.processes: list[Process] = []

    def add_process(
        self,
        group: None = None,
        target: Callable[..., Any] | None = None,
        name: str | None = None,
        args: Iterable[Any] = (),
        kwargs: dict[str, Any] = {},
        *,
        daemon: bool | None = None
    ) -> None:
        self.processes.append(Process(
            group=group,
            target=target,
            name=name,
            args=args,
            kwargs=kwargs,
            daemon=daemon
        ))

    async def run_processes(self) -> None:
        for process in self.processes:
            process.start()
        await self._check_processes()

    async def _check_processes(self) -> bool:
        while True:
            await asyncio.sleep(1)
            if all(process.exitcode is not None for process in self.processes):
                break


class AsyncFinishException(Exception):
    pass


class AsyncKillException(Exception):
    pass


class AsyncKilledException(Exception):
    pass


class AsyncKillManager:
    def __init__(
        self,
        kill_event: asyncio.Event | None = None,
    ):
        self._kill_event = (
            asyncio.Event() if kill_event is None else kill_event
        )
        self._kill_event.clear()

    @property
    def kill_event(self) -> asyncio.Event:
        return self._kill_event

    async def __call__(
        self,
        coroutine: Coroutine[Any, Any, Any]
    ) -> None:
        try:
            await asyncio.gather(
                self._wait_coroutine(coroutine),
                self._wait_kill()
            )
        except Exception as error:
            if isinstance(error, AsyncFinishException):
                return
            elif isinstance(error, AsyncKilledException):
                return
            elif isinstance(error, AsyncKillException):
                self._kill_event.set()
                return
            self._kill_event.set()
            raise error

    async def _wait_coroutine(
        self,
        coroutine: Coroutine[Any, Any, Any]
    ) -> None:
        await coroutine
        raise AsyncFinishException("Coroutine finished before kill event")

    async def _wait_kill(self) -> None:
        while True:
            await asyncio.sleep(1)
            if self._kill_event.is_set():
                raise AsyncKilledException("Kill event set")
