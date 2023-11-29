"""
Module containing base classes and methods for retrieving metrics from a
test
"""
import logging
from typing import Self
from abc import ABC, abstractmethod
import asyncio
import time

from test_harness.simulator.simulator import ResultsHandler
from test_harness.utils import calc_interval


class MetricsRetriever(ABC):
    def __init__(
        self,
    ) -> None:
        """Constructor method"""

    @abstractmethod
    async def __aenter__(self) -> Self:
        return self

    @abstractmethod
    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        if exc_type is not None:
            logging.getLogger().error(
                "The folowing type of error occurred %s with value %s",
                exc_type,
                exc_value,
            )
            raise exc_value

    async def async_continuous_retrieve_metrics(
        self,
        handler: ResultsHandler,
        interval: float,
    ) -> None:
        """Method to continuously retrieve the metrics from the source and
        send them to the handler. Uses an interval to wait between retrievals

        :param handler: The handler to send the results to
        :type handler: :class:`ResultsHandler`
        :param interval: The interval to wait between retrieving metrics
        :type interval: `float`
        """
        while True:
            t1 = time.time()
            await self.async_retrieve_metrics(handler)
            t2 = time.time()
            time_to_wait = calc_interval(t1, t2, interval)
            await asyncio.sleep(time_to_wait)

    @abstractmethod
    async def async_retrieve_metrics(
        self,
        handler: ResultsHandler
    ) -> None:
        """Method to retrieve the metrics from the source and send them to the
        handler

        :param handler: The handler to send the results to
        :type handler: :class:`ResultsHandler`
        """
        pass
