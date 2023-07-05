"""Tests for report delivery
"""
from pathlib import Path
import os

from pandas import DataFrame
import pandas as pd
import pytest

from test_harness.reporting.report_delivery import (
    deliver_test_report_file,
    deliver_test_report_files
)

# get report_output folder in tests folder
output_resources = Path(__file__).parent.parent / "report_output"


def test_deliver_test_report_file_string(
    expected_junit_string: str
) -> None:
    """Tests `deliver_test_report_file` when the input file is a string

    :param expected_junit_string: Fixture providing expected junit string
    :type expected_junit_string: `str`
    """
    file_name = "test_junit.xml"
    output_path = os.path.join(output_resources, file_name)
    deliver_test_report_file(
        file_name,
        expected_junit_string,
        output_resources
    )
    assert os.path.exists(output_path)
    with open(output_path, 'r', encoding="utf-8") as file:
        junit_string = file.read()
    assert junit_string == expected_junit_string
    os.remove(output_path)


def test_deliver_test_report_file_dataframe(
    expected_results: DataFrame
) -> None:
    """Tests `deliver_test_report_file` when the input file is a dataframe

    :param expected_results: Expected results dataframe
    :type expected_results: :class:`DataFrame`
    """
    file_name = "test_junit.csv"
    output_path = os.path.join(output_resources, file_name)
    deliver_test_report_file(
        file_name,
        expected_results,
        output_resources
    )
    assert os.path.exists(output_path)
    saved_df = pd.read_csv(
        output_path,
        index_col=["JobId"]
    )
    assert str(expected_results) == str(saved_df)
    os.remove(output_path)


def test_deliver_test_report_file_folder_not_exist(
    expected_junit_string: str
) -> None:
    """Tests `deliver_test_report_file` when the output directory does not
    exist

    :param expected_junit_string: Fixture providing expected junit string
    :type expected_junit_string: `str`
    """
    file_name = "test_file.xml"
    output_dir = os.path.join(output_resources, "not_exists")
    with pytest.raises(RuntimeError) as e_info:
        deliver_test_report_file(
            file_name,
            expected_junit_string,
            output_dir
        )
    assert e_info.value.args[0] == (
        f"The directory {output_dir} does not exist"
    )


def test_deliver_test_report_files_out_dir_exists(
    report_files_mapping: dict[str, str | DataFrame]
) -> None:
    """Tests `deliver_test_report_files` when output directory exists

    :param report_files_mapping: Fixture providing mapping dictionary for file
    names and files
    :type report_files_mapping: `dict`[`str`, `str`  |  :class:`DataFrame`]
    """
    output_directory = str(output_resources)
    deliver_test_report_files(
        report_files_mapping=report_files_mapping,
        output_directory=output_directory
    )
    for file_name, file in report_files_mapping.items():
        file_path = os.path.join(output_directory, file_name)
        assert os.path.exists(file_path)
        if isinstance(file, DataFrame):
            saved_file = str(
                pd.read_csv(file_path, index_col="JobId")
            )
        else:
            with open(file_path, 'r', encoding="utf-8") as loaded_file:
                saved_file = loaded_file.read()
        assert saved_file == str(file)
        os.remove(file_path)


def test_deliver_test_report_files_out_dir_not_exists(
    report_files_mapping: dict[str, str | DataFrame]
) -> None:
    """Tests `deliver_test_report_files` when output directory does not exist

    :param report_files_mapping: Fixture providing mapping dictionary for file
    names and files
    :type report_files_mapping: `dict`[`str`, `str`  |  :class:`DataFrame`]
    """
    output_directory = os.path.join(output_resources, "new")
    deliver_test_report_files(
        report_files_mapping=report_files_mapping,
        output_directory=output_directory
    )
    assert os.path.exists(output_directory)
    for file_name, file in report_files_mapping.items():
        file_path = os.path.join(output_directory, file_name)
        assert os.path.exists(file_path)
        if isinstance(file, DataFrame):
            saved_file = str(
                pd.read_csv(file_path, index_col="JobId")
            )
        else:
            with open(file_path, 'r', encoding="utf-8") as loaded_file:
                saved_file = loaded_file.read()
        assert saved_file == str(file)
        os.remove(file_path)
    os.rmdir(output_directory)
