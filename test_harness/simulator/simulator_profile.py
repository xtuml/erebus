# pylint: disable=W0707
"""Methods for handling simulation profiles
"""
import csv
from typing import Callable, Literal
import logging
from io import StringIO, TextIOWrapper
from copy import deepcopy

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
    profile_builders = {
        "uniform": "_uniform_profile_builder"
    }

    def __init__(
        self,
        raw_profile: DataFrame | None = None
    ) -> None:
        """Constructor method
        """
        self.raw_profile: DataFrame | None = raw_profile
        self.delay_times: list | None

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

    def load_raw_profile_from_string(
        self,
        csv_string: str
    ) -> None:
        """Method to load a raw profile from a csv string

        :param csv_string: The string representation of the csv
        :type csv_string: `str`
        """
        self.load_raw_profile_from_csv_buffer(
            StringIO(csv_string)
        )

    def load_raw_profile_from_file_path(
        self,
        file_path: str
    ) -> None:
        """Method to load a raw profile from a csv file

        :param file_path: The relative or full path of the csv file
        :type file_path: `str`
        """
        with open(file_path, 'r', encoding="utf-8") as file_buffer:
            self.load_raw_profile_from_csv_buffer(StringIO(file_buffer.read()))

    def load_raw_profile_from_csv_buffer(
        self,
        file_buffer: StringIO
    ) -> None:
        """Method to set the raw_profile from an input csv file buffer

        :param file_path: The full or relative path to the csv file
        :type file_path: `str`
        :raises RuntimeError: Raises a :class:`RuntimeError` when the
        simulation profile file is empty
        """
        sample = self.get_sample(
            deepcopy(file_buffer)
        )
        header = self.check_headings(sample)
        self.raw_profile = read_csv(file_buffer, header=header)

    @staticmethod
    def check_headings(sample: str) -> Literal['infer'] | None:
        """Method to check whether or not a sample string representation of a
        csv file has a header

        :return: Returns the header option for :class:`pd`.`DataFrame`
        :rtype: :class:`Literal`[`'infer'`] | `None`
        """
        has_headings = csv.Sniffer().has_header(
            sample
        )
        if not has_headings:
            logging.getLogger().warning(
                "The simulation profile csv file provided has no headers"
            )
        header = 'infer' if has_headings else None
        return header

    @staticmethod
    def get_sample(
        file_buffer: TextIOWrapper | StringIO
    ) -> str:
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
        self.delay_times = (
            self.get_delays_from_interp_num_per_sec(
                interp_num_per_sec=interp_num_per_sec,
                method=method
            )
        )

    @staticmethod
    def get_interp_num_per_sec_from_raw_profile(
        raw_profile: DataFrame,
        col_map: dict[int, str] | None = None
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
            col_map = {
                0: "Time",
                1: "Number"
            }
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
            method='linear', limit_direction='forward', axis=0
        )
        num_per_sec[col_number] = num_per_sec[col_number].round().astype(int)
        return num_per_sec

    @classmethod
    def get_delays_from_interp_num_per_sec(
        cls,
        interp_num_per_sec: DataFrame,
        method: str = "uniform"
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
            cls, (
                cls.profile_builders[method]
            )
        )
        return builder_func(interp_num_per_sec)

    @staticmethod
    def _uniform_profile_builder(
        interp_num_per_sec: DataFrame
    ) -> list[float]:
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
        delay_profile = np.array([], dtype=float)
        for index, row in interp_num_per_sec.iloc[: -1].iterrows():
            delay_profile = np.append(
                delay_profile,
                np.linspace(index, index + 1, row["Number"] + 1)[: -1]
            )
        return delay_profile.tolist()
