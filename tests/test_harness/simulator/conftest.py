# pylint: disable=W0621
"""Test config file
"""
from io import StringIO, TextIOWrapper, BytesIO

import pandas as pd
import pytest


@pytest.fixture
def raw_profile() -> pd.DataFrame:
    """Fixture to provide a raw profile

    :return: Returns the raw profile dataframe with columns of:
    * Time - the time
    * Number - the number at that time
    :rtype: pd.DataFrame
    """
    profile = pd.DataFrame(
        [
            [0, 10],
            [2, 20],
            [4, 10],
            [6, 2]
        ],
        columns=["Time", "Number"]
    )
    return profile


@pytest.fixture
def expected_interp_profile() -> pd.DataFrame:
    """Fixture for the expected interpolated profile from `raw_profile`

    :return: Returns the expected interpolated profile
    :rtype: :class:`pd`.`DataFrame`
    """
    return pd.DataFrame([10, 15, 20, 15, 10, 6, 2], columns=["Number"])


@pytest.fixture
def expected_delay_times(
    expected_interp_profile: pd.DataFrame
) -> list[float]:
    """Fixture for the expected task delay times given the expected
    interpolated profile.

    :param expected_interp_profile: Fixture providing the expected
    interpolated profile
    :type expected_interp_profile: :class:`pd`.`DataFrame`
    :return: Returns a list of the expected task delay times
    :rtype: `list`[`float`]
    """
    return [
        index + i / row["Number"]
        for index, row in expected_interp_profile.iloc[: -1].iterrows()
        for i in range(row["Number"])
    ]


@pytest.fixture
def csv_string() -> str:
    """Fixture to provide a csv string

    :return: Returns the csv string
    :rtype: `str`
    """
    return (
        "Time,Number\n"
        "0,10\n"
        "2, 20\n"
        "4, 10\n"
        "6, 2"
    )


@pytest.fixture
def stringio_sample(csv_string: str) -> StringIO:
    """Fixture to provide a :class:`StringIO` representation of the csv string

    :param csv_string: Fixture providing a csv string
    :type csv_string: `str`
    :return: Returns the string buffer
    :rtype: :class:`StringIO`
    """
    return StringIO(csv_string)


@pytest.fixture
def bytesio_sample(csv_string: str) -> BytesIO:
    """Fixture to provide a :class:`BytesIO` representation of the csv string

    :param csv_string: Fixture providing a csv string
    :type csv_string: `str`
    :return: Returns the bytes buffer
    :rtype: :class:`BytesIO`
    """
    return BytesIO(csv_string.encode("utf-8"))


@pytest.fixture
def textio_wrapper_sample(
    bytesio_sample: BytesIO
) -> TextIOWrapper:
    """Fixture to provide a :class:`TextIOWrapper` representation of the csv
    string

    :param bytesio_sample: Bytes buffer
    :type bytesio_sample: :class:`BytesIO`
    :return: Returns the text buffer
    :rtype: :class:`TextIOWrapper`
    """
    return TextIOWrapper(bytesio_sample, encoding="utf-8")
