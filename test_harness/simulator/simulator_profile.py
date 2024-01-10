# pylint: disable=W0707
"""Methods for handling simulation profiles
"""
import csv
from typing import Callable, Literal, Any, Generator
import logging
from io import StringIO, TextIOWrapper
from copy import deepcopy, copy

from pandas import DataFrame, read_csv
import numpy as np


class Profile:
    """Class to hold and handle input profiles for simulations

    :param raw_profile: A raw profile dataframe that has two columns:
    * first column is the time of the reading (must be an integer)
    * second column is the number of events per second (must be an integer)
    , defaults to `None`
    :type raw_profile: :class:`DataFrame` | `None`, optional
    """

    profile_builders = {"uniform": "_uniform_profile_builder"}

    def __init__(self, raw_profile: DataFrame | None = None) -> None:
        """Constructor method"""
        self.raw_profile: DataFrame | None = raw_profile
        self.delay_times: "InterpolatedProfile" | None

    @property
    def raw_profile(self) -> DataFrame | None:
        """Property getter for the raw_profile

        :return: Returns the raw_profile dataframe
        :rtype: :class:`DataFrame` | `None`
        """
        return self._raw_profile

    @raw_profile.setter
    def raw_profile(self, profile: DataFrame | None) -> None:
        """Property setter for the raw profile. Asserts that there are two
        columns and changes the columns to "Time" and "Number"

        :param profile: The input raw_profile
        :type profile: :class:`DataFrame` | `None`
        """
        if isinstance(profile, DataFrame):
            assert len(profile.columns) == 2
            profile.columns = ["Time", "Number"]
            for column in profile.columns:
                profile[column] = profile[column].astype(int)
        self._raw_profile = profile

    def load_raw_profile_from_string(self, csv_string: str) -> None:
        """Method to load a raw profile from a csv string

        :param csv_string: The string representation of the csv
        :type csv_string: `str`
        """
        self.load_raw_profile_from_csv_buffer(StringIO(csv_string))

    def load_raw_profile_from_file_path(self, file_path: str) -> None:
        """Method to load a raw profile from a csv file

        :param file_path: The relative or full path of the csv file
        :type file_path: `str`
        """
        with open(file_path, "r", encoding="utf-8") as file_buffer:
            self.load_raw_profile_from_csv_buffer(StringIO(file_buffer.read()))

    def load_raw_profile_from_csv_buffer(self, file_buffer: StringIO) -> None:
        """Method to set the raw_profile from an input csv file buffer

        :param file_path: The full or relative path to the csv file
        :type file_path: `str`
        :raises RuntimeError: Raises a :class:`RuntimeError` when the
        simulation profile file is empty
        """
        sample = self.get_sample(deepcopy(file_buffer))
        header = self.check_headings(sample)
        self.raw_profile = read_csv(file_buffer, header=header)

    @staticmethod
    def check_headings(sample: str) -> Literal["infer"] | None:
        """Method to check whether or not a sample string representation of a
        csv file has a header

        :return: Returns the header option for :class:`pd`.`DataFrame`
        :rtype: :class:`Literal`[`'infer'`] | `None`
        """
        has_headings = csv.Sniffer().has_header(sample)
        if not has_headings:
            logging.getLogger().warning(
                "The simulation profile csv file provided has no headers"
            )
        header = "infer" if has_headings else None
        return header

    @staticmethod
    def get_sample(file_buffer: TextIOWrapper | StringIO) -> str:
        """Method to get a sample of lines from a file buffer

        :param file_buffer: The file buffer
        :type file_buffer: :class:`TextIOWrapper` | :class:`StringIO`
        :raises RuntimeError: Raises a :class:`RuntimError` if the buffer is
        empty
        :return: Returns the sample as a string of lines
        :rtype: `str`
        """
        lines = []
        lines_iterable = iter(file_buffer)
        for counter in range(10):
            try:
                lines.append(next(lines_iterable))
            except StopIteration:
                if counter == 0:
                    raise RuntimeError(
                        "The given simulation profile csv is empty"
                    )
        sample = "".join(lines)
        return sample

    def transform_raw_profile(self, method: str = "uniform") -> None:
        """Method to transform a raw profile to a list of delay times for the
        to be used for performing asynchronous tasks in a simulation. Has an
        input `method` keyword that describes how the delay times are
        distributed in between seconds

        :param method: An optional method keyword that is used to realte to a
        function attribute of the class that is mapped to by `profile_builders`
        , defaults to "uniform"
        :type method:` str`, optional
        :raises RuntimeError: Raises a :class:`RuntimeError` when a
        raw_profile has not been set
        """
        if not isinstance(self.raw_profile, DataFrame):
            raise RuntimeError("No raw profile has been set")
        interp_num_per_sec = self.get_interp_num_per_sec_from_raw_profile(
            self.raw_profile
        )
        self.delay_times = self.get_delays_from_interp_num_per_sec(
            interp_num_per_sec=interp_num_per_sec, method=method
        )

    @staticmethod
    def get_interp_num_per_sec_from_raw_profile(
        raw_profile: DataFrame, col_map: dict[int, str] | None = None
    ) -> DataFrame:
        """Method to interpolate the field "Number" at second time intervals

        :param raw_profile: A dataframe containing the raw profile for number
        per second
        :type raw_profile: :class:`DataFrame`
        :param col_map: A dictionary to map column number to the actual name,
        defaults to `None`
        :type col_map: dict[int, str] | None, optional
        :return: Returns an dataframe with interpolated values for every
        second between the start and end times of the input dataframe
        :rtype: :class:`DataFrame`
        """
        if not col_map:
            col_map = {0: "Time", 1: "Number"}
        col_time = col_map[0]
        col_number = col_map[1]
        start_value = raw_profile.iloc[0, 0]
        end_time = raw_profile.iloc[-1, 0]
        num_per_sec = DataFrame(
            np.nan, index=range(end_time + 1), columns=[col_number]
        )
        num_per_sec.iloc[0, 0] = start_value
        for _, row in raw_profile.iterrows():
            num_per_sec.loc[row[col_time]] = row[col_number]
        num_per_sec = num_per_sec.interpolate(
            method="linear", limit_direction="forward", axis=0
        )
        num_per_sec[col_number] = num_per_sec[col_number].round().astype(int)
        return num_per_sec.iloc[:-1]

    @classmethod
    def get_delays_from_interp_num_per_sec(
        cls, interp_num_per_sec: DataFrame, method: str = "uniform"
    ) -> list[float]:
        """Class method to get a list of times for performing tasks from a
        dataframe of number of tasks per second for each time interval in the
        simulation. Can choose the method of obtaining the list of time.

        :param interp_num_per_sec: Dataframe with values for every
        second between the start and end times of the simulation
        :type interp_num_per_sec: :class:`DataFrame`
        :param method: Keyword to choose the method for getting the list of
        times:
        * "uniform" - Takes the value for each time step and splits the
        interval equally by that value
        , defaults to "uniform"
        :type method: `str`, optional
        :return: Returns the list of task starting times
        :rtype: `list`[`float`]
        """
        builder_func: Callable[[DataFrame], list[float]] = getattr(
            cls, (cls.profile_builders[method])
        )
        return builder_func(interp_num_per_sec)

    @staticmethod
    def _uniform_profile_builder(
        interp_num_per_sec: DataFrame,
    ) -> "InterpolatedProfile":
        """Method to get a list of times for performing tasks from a
        dataframe of number of tasks per second for each time interval in the
        simulation. Takes the value for each time step and splits the
        interval equally by that value.

        :param interp_num_per_sec: Dataframe with values for every
        second between the start and end times of the simulation
        :type interp_num_per_sec: :class:`DataFrame`
        :return: Returns the list of task starting times
        :rtype: `list`[`float`]
        """
        return InterpolatedProfile(interp_num_per_sec)


class InterpolatedProfile:
    """Class to hold and handle interpolated profiles for simulations

    :param interp_num_per_sec: A dataframe with interpolated values for every
    second between the start and end times of the input dataframe
    :type interp_num_per_sec: :class:`DataFrame`
    """
    def __init__(self, interp_num_per_sec: DataFrame) -> None:
        self._interp_num_per_sec = interp_num_per_sec.copy()
        self._add_cumulative_interp_num_per_sec()
        self._start_index = 0
        self._end_index = self._calc_length_from_interp_num_per_sec() - 1
        self._step = 1
        self._iter_index = self._start_index
        self._iter_generator = None

    def set_slice(self, start_index: int, end_index: int, step: int) -> None:
        """Method to set the slice of the interpolated profile

        :param start_index: The start index of the slice
        :type start_index: `int`
        :param end_index: The end index of the slice
        :type end_index: `int`
        :param step: The step of the slice
        :type step: `int`
        """
        start_index = self._get_start_index(start_index)
        end_index = self._get_end_index(end_index)
        self._check_slice(start_index, end_index)
        self._start_index = start_index
        self._end_index = end_index
        self._step = step

    def _get_start_index(self, start_index: int) -> None:
        """Method to get the start index of the slice

        :param start_index: The start index of the slice
        :type start_index: `int`
        :raises IndexError: Raises an :class:`IndexError` when the start index
        is out of range
        :return: Returns the start index of the slice
        """
        if start_index < 0:
            start_index = self._end_index + start_index + 1
        if start_index > self._end_index:
            raise IndexError("Start index out of range")
        return start_index

    def _get_end_index(self, end_index: int) -> None:
        """Method to get the end index of the slice

        :param end_index: The end index of the slice
        :type end_index: `int`
        """
        if end_index < 0:
            end_index = self._end_index + end_index + 1
        if end_index > self._end_index:
            end_index = self._end_index + 1
        return end_index - 1

    def _check_slice(self, start_index: int, end_index: int) -> None:
        """Method to check that the slice is valid

        :param start_index: The start index of the slice
        :type start_index: `int`
        :param end_index: The end index of the slice
        :type end_index: `int`
        :raises ValueError: Raises a :class:`ValueError` when the start index
        is greater than the end index
        """
        if start_index > end_index:
            raise ValueError(
                "Start index must be less than or equal to end index"
            )

    def _add_cumulative_interp_num_per_sec(self) -> None:
        """Method to add a cumulative number column to the dataframe
        """
        self._interp_num_per_sec["CumulativeNumber"] = (
            self._interp_num_per_sec["Number"].cumsum()
        )

    def _calc_length_from_interp_num_per_sec(self) -> int:
        """Method to calculate the length of the interpolated profile from the
        dataframe

        :return: Returns the length of the interpolated profile
        :rtype: `int`
        """
        return self._interp_num_per_sec["CumulativeNumber"].iloc[-1]

    def __len__(self) -> int:
        """Method to get the length of the interpolated profile

        :return: Returns the length of the interpolated profile
        :rtype: `int`
        """
        return (self._end_index + 1 - self._start_index) // self._step

    def create_sliced_interp_profile(
        self, start_index: int | None = None, end_index: int | None = None,
        step: int | None = None
    ) -> "InterpolatedProfile":
        """Method to create a sliced interpolated profile

        :param start_index: The start index of the slice, defaults to `None`
        :type start_index: `int` | `None`, optional
        :param end_index: The end index of the slice, defaults to `None`
        :type end_index: `int` | `None`, optional
        :param step: The step of the slice, defaults to `None`
        :type step: `int` | `None`, optional
        :return: Returns the sliced interpolated profile
        :rtype: :class:`InterpolatedProfile`
        """
        if start_index is None:
            start_index = self._start_index
        if end_index is None:
            end_index = self._end_index + 1
        if step is None:
            step = self._step
        slice_profile = copy(self)
        slice_profile.set_slice(start_index, end_index, step)
        return slice_profile

    def __getitem__(self, index: int | slice) -> int | list[int]:
        """Method to get the value at an index or a slice of values

        :param index: The index or slice of indices to get the values at
        :type index: `int` | `slice`
        :raises TypeError: Raises a :class:`TypeError` when the index is not
        an int or a slice
        :raises ValueError: Raises a :class:`ValueError` when the slice step
        is not `None`
        :raises IndexError: Raises an :class:`IndexError` when the index is
        out of range
        :return: Returns the value at the index or a list of values at the
        slice of indices
        :rtype: `int` | `list`[`int`]
        """
        if isinstance(index, int):
            return self._get_value_at_index(index)
        elif isinstance(index, slice):
            if index.step is not None:
                if index.step < 0:
                    raise ValueError("Slice step must be positive")
            return self.create_sliced_interp_profile(
                index.start, index.stop, index.step
            )
        else:
            raise TypeError("Index must be an int or a slice")

    def _get_value_at_index(self, index: int) -> int:
        """Method to get the value at an index

        :param index: The index to get the value at
        :type index: `int`
        :raises IndexError: Raises an :class:`IndexError` when the index is
        out of range
        :return: Returns the value at the index
        :rtype: `int`
        """
        if index < 0:
            index = self._end_index + index + 1
        if index < self._start_index or index > self._end_index:
            raise IndexError("Index out of range")
        return self._get_value_at_index_from_interp_num_per_sec(index)

    def _get_value_at_index_from_interp_num_per_sec(self, index: int) -> int:
        """Method to get the value at an index from the dataframe

        :param index: The index to get the value at
        :type index: `int`
        :return: Returns the value at the index
        :rtype: `int`
        """
        to_calculate_time_val_index = (
            self._interp_num_per_sec["CumulativeNumber"] - index - 1
        )
        idx = to_calculate_time_val_index[
            to_calculate_time_val_index >= 0
        ].idxmin()
        idx, position_in_window = self._calc_interp_idx_from_index(index)
        return (
            idx
            + (position_in_window)
            / self._interp_num_per_sec.loc[idx, "Number"]
        )

    def _calc_interp_idx_from_index(self, index: int) -> int:
        """Method to calculate the interpolated index from the dataframe

        :param index: The index to get the value at
        :type index: `int`
        :return: Returns the interpolated index and the position in the window
        :rtype: `tuple`[`int`, `int`]
        """
        to_calculate_time_val_index = (
            self._interp_num_per_sec["CumulativeNumber"] - index - 1
        )
        idx = to_calculate_time_val_index[
            to_calculate_time_val_index >= 0
        ].idxmin()
        position_in_window = (
            self._interp_num_per_sec.loc[idx, "Number"]
            - to_calculate_time_val_index.loc[idx]
            - 1
        )
        return idx, position_in_window

    def __iter__(self) -> "InterpolatedProfile":
        """Method to set up the iterator

        :return: Returns the iterator
        :rtype: :class:`InterpolatedProfile`
        """
        return self._iter_generator_func()

    def _set_iter_generator(self) -> None:
        """Method to set up the iterator generator
        """
        self._iter_generator = self._iter_generator_func()

    def _iter_generator_func(self) -> Generator[float, Any, None]:
        """Method to set up the iterator generator function

        :return: Returns the iterator generator function
        :rtype: :class:`Generator`[`float`, `Any`, `None`]
        """
        start_idx, start_position_in_window = self._calc_interp_idx_from_index(
            self._start_index
        )
        end_idx, end_position_in_window = self._calc_interp_idx_from_index(
            self._end_index
        )
        full_counter = 0

        for index, row in self._interp_num_per_sec.iloc[
            start_idx: end_idx + 1
        ].iterrows():
            num_start = index
            num_end = index + 1
            step = (num_end - num_start) / row["Number"]
            counter = 0
            if index == start_idx:
                num_start = (
                    num_start + start_position_in_window / row["Number"]
                )
                counter = start_position_in_window
            if index == end_idx:
                end_count = end_position_in_window + 1
            else:
                end_count = row["Number"]
            while counter < end_count:
                if full_counter % self._step == 0:
                    yield num_start
                num_start += step
                counter += 1
                full_counter += 1

    def get_max_num_per_sec(self) -> int:
        """Method to get the maximum number of tasks per second in the

        :return: Returns the maximum number of tasks per second in the
        interpolated profile
        :rtype: `int`
        """
        start_idx, _ = self._calc_interp_idx_from_index(
            self._start_index
        )
        end_idx, _ = self._calc_interp_idx_from_index(self._end_index)
        return max(self._interp_num_per_sec["Number"].loc[
            start_idx: end_idx + 1
        ])
