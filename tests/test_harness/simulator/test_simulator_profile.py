# pylint: disable=W0212
# pylint: disable=R0801
"""Tests for simulator_profile.py
"""
from io import StringIO, TextIOWrapper, BytesIO
from pathlib import Path

from pandas import DataFrame
import pytest

from test_harness.simulator.simulator_profile import Profile

# get resources folder in tests folder
input_resources = Path(__file__).parent.parent / "test_files"


class TestProfile:
    """Class to hold groups of tests for :class:`Profile`
    """
    @staticmethod
    def test_get_interp_num_per_sec_from_raw_profile(
        raw_profile: DataFrame,
        expected_interp_profile: DataFrame
    ) -> None:
        """Tests :class:`Profile`.`get_interp_num_per_sec_from_raw_profile`

        :param raw_profile: The raw profile dataframe
        :type raw_profile: :class:`DataFrame`
        :param expected_interp_profile: Fixture providing the expected
        interpolated dataframe
        :type expected_interp_profile: :class:`DataFrame`
        """
        interp_num_per_sec = Profile.get_interp_num_per_sec_from_raw_profile(
            raw_profile
        )
        for index, row in interp_num_per_sec.iterrows():
            assert expected_interp_profile.loc[index, "Number"] == row[
                "Number"
            ]

    @staticmethod
    def test__uniform_profile_builder(
        expected_interp_profile: DataFrame,
        expected_delay_times: list[float]
    ) -> None:
        """Tests :class:`Profile`.`_uniform_profile_builder`

        :param expected_interp_profile: Fixture providing the expected
        interpolated dataframe
        :type expected_interp_profile: :class:`DataFrame`
        :param expected_delay_times: Fixture providing the expected task delay
        times
        :type expected_delay_times: `list`[`float`]
        """
        delay_times = Profile._uniform_profile_builder(
            expected_interp_profile
        )
        for expected, actual in zip(
            expected_delay_times, delay_times
        ):
            assert pytest.approx(expected, 1e-6) == actual

    @staticmethod
    def test_get_delays_from_interp_num_per_sec_method_uniform(
        expected_interp_profile: DataFrame,
        expected_delay_times: list[float]
    ) -> None:
        """Tests :class:`Profile`.`get_delays_from_interp_num_per_sec`

        :param expected_interp_profile: Fixture providing the expected
        interpolated dataframe
        :type expected_interp_profile: :class:`DataFrame`
        :param expected_delay_times: Fixture providing the expected task delay
        times
        :type expected_delay_times: `list`[`float`]
        """
        delay_times = Profile.get_delays_from_interp_num_per_sec(
            expected_interp_profile,
            method="uniform"
        )
        for expected, actual in zip(
            expected_delay_times, delay_times
        ):
            assert pytest.approx(expected, 1e-6) == actual

    @staticmethod
    def test_get_sample_stringio(
        stringio_sample: StringIO,
        csv_string: str
    ) -> None:
        """Test for :class:`Profile`.`get_sample` with :class:`StringIO` input

        :param stringio_sample: The input csv as :class:`StringIO`
        :type stringio_sample: :class:`StringIO`
        :param csv_string: The expected file string
        :type csv_string: `str`
        """
        output = Profile.get_sample(stringio_sample)
        assert output == csv_string

    @staticmethod
    def test_get_sample_textio_wrapper(
        textio_wrapper_sample: TextIOWrapper,
        csv_string: str
    ) -> None:
        """Test for :class:`Profile`.`get_sample` with :class:`TextIOWrapper`
        input

        :param textio_wrapper_sample: The input csv as :class:`TextIOWrapper`
        :type textio_wrapper_sample: :class:`TextIOWrapper`
        :param csv_string: The expected file string
        :type csv_string: `str`
        """
        output = Profile.get_sample(textio_wrapper_sample)
        assert output == csv_string

    @staticmethod
    def test_get_sample_empty_file() -> None:
        """Test for :class:`Profile`.`get_sample` with an empty file
        """
        with pytest.raises(RuntimeError) as e_info:
            Profile.get_sample(TextIOWrapper(BytesIO(b"")))
        assert e_info.value.args[0] == (
            "The given simulation profile csv is empty"
        )

    @staticmethod
    def test_check_headings_heading(csv_string: str) -> None:
        """Tests :class:`Profile`.`check_headings` with a heading

        :param csv_string: fixture prpviding csv string
        :type csv_string: `str`
        """
        assert Profile.check_headings(csv_string)

    @staticmethod
    def test_check_headings_no_heading(csv_string: str) -> None:
        """Tests :class:`Profile`.`check_headings` with no heading

        :param csv_string: fixture prpviding csv string
        :type csv_string: `str`
        """
        assert not Profile.check_headings(
            "\n".join(csv_string.split("\n")[1:])
        )

    @staticmethod
    def test_load_raw_profile_from_csv_buffer_stringio(
        stringio_sample: StringIO,
        raw_profile: DataFrame
    ) -> None:
        """Tests :class:`Profile`.`load_raw_profile_from_csv_buffer`

        :param stringio_sample: Fixture providing a :class:`StringIO` buffer
        :type stringio_sample: :class:`StringIO`
        :param raw_profile: Fixture providing the expected raw profile
        dataframe
        :type raw_profile: :class:`DataFrame`
        """
        profile = Profile()
        profile.load_raw_profile_from_csv_buffer(
            stringio_sample
        )
        for index, row in profile.raw_profile.iterrows():
            assert raw_profile.loc[index, "Time"] == row["Time"]
            assert raw_profile.loc[index, "Number"] == row["Number"]

    @staticmethod
    def test_load_raw_profile_from_string(
        csv_string: str,
        raw_profile: DataFrame
    ) -> None:
        """Tests :class:`Profile`.`load_raw_profile_from_string`

        :param csv_string: The expected file string
        :type csv_string: `str`
        :param raw_profile: Fixture providing the expected raw profile
        dataframe
        :type raw_profile: :class:`DataFrame`
        """
        profile = Profile()
        profile.load_raw_profile_from_string(
            csv_string
        )
        for index, row in profile.raw_profile.iterrows():
            assert raw_profile.loc[index, "Time"] == row["Time"]
            assert raw_profile.loc[index, "Number"] == row["Number"]

    @staticmethod
    def test_load_raw_profile_from_file_path(
        raw_profile: DataFrame
    ) -> None:
        """Tests :class:`Profile`.`load_raw_profile_from_file_path`

        :param raw_profile: Fixture providing the expected raw profile
        dataframe
        :type raw_profile: :class:`DataFrame`
        """
        profile = Profile()
        profile.load_raw_profile_from_file_path(
            input_resources / "test_profile.csv"
        )
        for index, row in profile.raw_profile.iterrows():
            assert raw_profile.loc[index, "Time"] == row["Time"]
            assert raw_profile.loc[index, "Number"] == row["Number"]

    @staticmethod
    def test_transform_raw_profile_uniform(
        raw_profile: DataFrame,
        expected_delay_times: list[float]
    ) -> None:
        """Tests :class:`Profile`.`transform_raw_profile`

        :param raw_profile: The raw profile dataframe
        :type raw_profile: :class:`DataFrame`
        :param expected_delay_times: Fixture providing the expected task delay
        times
        :type expected_delay_times: `list`[`float`]
        """
        profile = Profile(raw_profile)
        profile.transform_raw_profile()
        for expected, actual in zip(
            expected_delay_times, profile.delay_times
        ):
            assert pytest.approx(expected, 1e-6) == actual
