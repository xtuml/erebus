"""Module holding aggregation classes and functions.
"""
from abc import ABC, abstractmethod
from typing import Any, Callable, Type
import math

import numpy as np


class BinValue(ABC):
    """Abstract base class for a bin value"""

    @abstractmethod
    def update(self, value: float) -> None:
        """Method to update the bin value

        :param value: The value to update the bin value with
        :type value: `float`
        """

    @abstractmethod
    def get_value(self) -> float:
        """Method to get the bin value

        :return: Returns the bin value
        :rtype: `float`
        """


class BinValueCount(BinValue):
    """Class to hold a bin value that is a count"""

    def __init__(self) -> None:
        """Constructor method"""
        self.count = 0

    def update(self, value: float) -> None:
        """Method to update the bin value

        :param value: The value to update the bin value with
        :type value: `float`
        """

        self.count += 1

    def get_value(self) -> float:
        """Method to get the bin value

        :return: Returns the bin value
        :rtype: `float`
        """
        return self.count


class BinValueSum(BinValue):
    """Class to hold a bin value that is a sum"""

    def __init__(self) -> None:
        """Constructor method"""
        self.sum = 0

    def update(self, value: float) -> None:
        """Method to update the bin value

        :param value: The value to update the bin value with
        :type value: `float`
        """

        self.sum += value

    def get_value(self) -> float:
        """Method to get the bin value

        :return: Returns the bin value
        :rtype: `float`
        """
        return self.sum


class BinValueAverage(BinValue):
    """Class to hold a bin value that is an average"""

    def __init__(self) -> None:
        """Constructor method"""
        self.count = 0
        self.sum = 0

    def update(self, value: float) -> None:
        """Method to update the bin value

        :param value: The value to update the bin value with
        :type value: `float`
        """

        self.sum += value
        self.count += 1

    def get_value(self) -> float:
        """Method to get the bin value

        :return: Returns the bin value or None if the count is 0
        :rtype: `float` | `None`
        """
        return self.sum / self.count if self.count > 0 else np.nan


class BinValueMax(BinValue):
    """Class to hold a bin value that is a max"""

    def __init__(self) -> None:
        """Constructor method"""
        self.max = np.nan

    def update(self, value: float) -> None:
        """Method to update the bin value

        :param value: The value to update the bin value with
        :type value: `float`
        """

        self.max = np.nanmax([self.max, value])

    def get_value(self) -> float:
        """Method to get the bin value

        :return: Returns the bin value
        :rtype: `float`
        """
        return self.max


class AggregationHolder(ABC):
    """Abstract base class for an aggregation holder
    """
    @abstractmethod
    def __init__(self) -> None:
        """Constructor method
        """
        ...

    @property
    @abstractmethod
    def value(self) -> Any:
        """Method to get the value of the aggregation

        :return: Returns the value of the aggregation
        :rtype: `Any`
        """
        ...

    @abstractmethod
    def update(self, input_val: float) -> None:
        """Method to update the aggregation

        :param input_val: The value to update the aggregation with
        :type input_val: `float`
        """
        ...


class AggregationScalar(AggregationHolder):
    """Class to hold a scalar aggregation
    """
    @abstractmethod
    def __init__(self) -> None:
        """Constructor method
        """
        self._value: BinValue

    @property
    @abstractmethod
    def value(self) -> BinValue:
        """Method to get the value of the aggregation

        :return: Returns the value of the aggregation
        :rtype: :class:`BinValue`
        """
        ...

    def update(self, input_val: float) -> None:
        """Method to update the aggregation with a float value

        :param input_val: The value to update the aggregation with
        :type input_val: `float`
        """
        self._value.update(input_val)


class AggregationCount(AggregationScalar):
    """Class to hold a count aggregation
    """
    def __init__(self) -> None:
        """Constructor method
        """
        self._value = BinValueCount()

    @property
    def value(self) -> BinValue:
        """Method to get the value of the aggregation

        :return: Returns the value of the aggregation
        :rtype: :class:`BinValue`
        """
        return self._value.get_value()


class AggregationSum(AggregationScalar):
    """Class to hold a sum aggregation
    """
    def __init__(self) -> None:
        """Constructor method
        """
        self._value = BinValueSum()

    @property
    def value(self) -> BinValue:
        """Method to get the value of the aggregation

        :return: Returns the value of the aggregation
        :rtype: :class:`BinValue`
        """
        return self._value.get_value()


class AggregationAverage(AggregationScalar):
    """Class to hold an average aggregation
    """
    def __init__(self) -> None:
        """Constructor method
        """
        self._value = BinValueAverage()

    @property
    def value(self) -> BinValue:
        """Method to get the value of the aggregation

        :return: Returns the value of the aggregation
        :rtype: :class:`BinValue`
        """
        return self._value.get_value()


class AggregationMax(AggregationScalar):
    """Class to hold a max aggregation
    """
    def __init__(self) -> None:
        """Constructor method
        """
        self._value = BinValueMax()

    @property
    def value(self) -> BinValue:
        """Method to get the value of the aggregation

        :return: Returns the value of the aggregation
        :rtype: :class:`BinValue`
        """
        return self._value.get_value()


class AggregationBin(AggregationHolder):
    """Class to hold a binned aggregation
    """
    def __init__(self, binning_window: int, bin_type: Type[BinValue]) -> None:
        """Constructor method

        :param binning_window: The binning window
        :type binning_window: `int`
        :param bin_type: The type of bin to use
        :type bin_type: :class:`BinValue`
        """
        self._value: dict[int, BinValue] = {}
        self._binning_window = binning_window
        self.bin_type = bin_type

    @property
    def value(self) -> dict[int, float]:
        """Method to get the value of the aggregation as dictionary of floats

        :return: Returns the value of the aggregation
        :rtype: `dict`[`int`, `float`]
        """
        return {
            bin_number: bin_value.get_value()
            for bin_number, bin_value in self._value.items()
        }

    def update(self, input_val: float) -> None:
        """Method to update the aggregation with a float value

        :param input_val: The value to update the aggregation with
        :type input_val: `float`
        """
        bin_number = math.floor(input_val / self._binning_window)
        if bin_number not in self._value:
            self._value[bin_number] = self.bin_type()
        self._value[bin_number].update(input_val)


class AggregationTask:
    """Class to hold an aggregation task

    :param agg_holder: The aggregation holder to use
    :type agg_holder: :class:`AggregationHolder`
    :param pre_agg_func: The function to apply to the input value before
    aggregating
    :type pre_agg_func: `callable`, optional
    """
    def __init__(
        self,
        agg_holder: AggregationHolder,
        pre_agg_func: Callable[[Any], float] | None = None,
    ) -> None:
        """Constructor method
        """
        self.pre_agg_func = pre_agg_func
        self.agg_holder = agg_holder

    def __call__(self, value: Any) -> Any:
        """Method to call the aggregation task

        :param value: The value to aggregate
        :type value: `Any`
        :return: Returns the aggregated value
        :rtype: `Any`
        """
        self.update(value)

    def update(self, value: Any) -> None:
        """Method to update the aggregation task

        :param value: The value to aggregate
        :type value: `Any`
        """
        if (
            not isinstance(value, (int, float))
        ) and self.pre_agg_func is None:
            raise ValueError(
                "input_value must be int or float if pre_agg_func is None"
            )
        if self.pre_agg_func is not None:
            update_value = self.pre_agg_func(value)
        else:
            update_value: int | float = value
        if update_value is None:
            return
        self.agg_holder.update(update_value)
