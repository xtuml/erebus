"""Package to manage multprocessing for the test harness.
"""
import asyncio
from typing import Callable, Iterable, Any, Coroutine
from multiprocessing import Process
import threading
import logging


class AsyncMPManager:
    """Class to manage multiprocessing processes in an async context.
    """
    def __init__(
        self,
    ) -> None:
        """Constructor method
        """
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
        """Add a process to the manager.

        :param group: Unused by the test harness. Defaults to None.
        :type group: `None`
        :param target: The callable object to be invoked by the run() method.
        Defaults to `None`, meaning nothing is called.
        :type target: :class:`Callable`[`...`, `Any`] | `None`
        :param name: A string specifying the process name. By default, this is
        the name of the function or method passed to the constructor.
        :type name: `str` | `None`
        :param args: The argument tuple for the target invocation.
        Defaults to `()`.
        :type args: :class:`Iterable`[`Any`]
        :param kwargs: A dictionary of keyword arguments for the target
        invocation. Defaults to `{}`.
        :type kwargs: `dict`[`str`, `Any`]
        :param daemon: A boolean value indicating whether this process is a
        daemon process. Defaults to `None`.
        :type daemon: `bool` | `None`
        """
        self.processes.append(Process(
            group=group,
            target=target,
            name=name,
            args=args,
            kwargs=kwargs,
            daemon=daemon
        ))

    async def run_processes(self) -> None:
        """Run all processes in the manager and wait for completion
        """
        for process in self.processes:
            process.start()
        await self._check_processes()

    async def _check_processes(self) -> bool:
        """Check if all processes have completed.

        :return: True if all processes have completed, False otherwise.
        :rtype: `bool`
        """
        while True:
            await asyncio.sleep(1)
            if all(process.exitcode is not None for process in self.processes):
                logging.getLogger().info("All processes completed")
                break


class AsyncFinishException(Exception):
    """Exception raised when a coroutine finishes before the kill event is set.
    """


class AsyncKillException(Exception):
    """Exception raised when a coroutine is killed.
    """


class AsyncKilledException(Exception):
    """Exception raised when the kill event is set.
    """


class AsyncKillManager:
    """Class to manage killing coroutines in an async context.

    :param kill_event: An event to set when the coroutine is killed.
    :type kill_event: :class:`asyncio`.`Event` | :class:`threading`.`Event` |
    `None`
    """
    def __init__(
        self,
        kill_event: asyncio.Event | threading.Event | None = None,
    ) -> None:
        """Constructor method
        """
        self._kill_event = (
            asyncio.Event() if kill_event is None else kill_event
        )
        self._kill_event.clear()

    @property
    def kill_event(self) -> asyncio.Event | threading.Event:
        """The kill event.

        :return: The kill event.
        :rtype: :class:`asyncio`.`Event` | :class:`threading`.`Event`
        """
        return self._kill_event

    async def __call__(
        self,
        coroutine: Coroutine[Any, Any, Any]
    ) -> None:
        """Run a coroutine and wait for either the coroutine to finish or the
        kill event to be set.

        :param coroutine: The coroutine to run.
        :type coroutine: :class:`Coroutine`[`Any`, `Any`, `Any`]
        """
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
        """Wait for a coroutine to finish.

        :param coroutine: The coroutine to wait for.
        :type coroutine: :class:`Coroutine`[`Any`, `Any`, `Any`]
        :raises AsyncFinishException: Raised when the coroutine finishes before
        the kill event is set.
        """
        await coroutine
        raise AsyncFinishException("Coroutine finished before kill event")

    async def _wait_kill(self) -> None:
        """Wait for the kill event to be set.

        :raises AsyncKillException: Raised when the kill event is set before
        the coroutine finishes.
        """
        while True:
            await asyncio.sleep(1)
            if self._kill_event.is_set():
                raise AsyncKilledException("Kill event set")
