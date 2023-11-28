"""
Module containing base classes and methods for retrieving metrics from a
test
"""
import logging
from typing import Self
from abc import ABC, abstractmethod

from test_harness.simulator.simulator import ResultsHandler


class MetricsRetriever(ABC):
    def __init__(
        self,
    ) -> None:
        """Constructor method"""

    @abstractmethod
    def __enter__(self) -> Self:
        return self

    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if exc_type is not None:
            logging.getLogger().error(
                "The folowing type of error occurred %s with value %s",
                exc_type,
                exc_value,
            )
            raise exc_value

    @abstractmethod
    async def async_retrieve_metrics(
        self,
        handler: ResultsHandler
    ) -> None:
        """Method to retrieve the metrics from the source and send them to the
        handler

        :param handler: _description_
        :type handler: ResultsHandler
        """
