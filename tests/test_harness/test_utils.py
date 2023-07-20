"""Tests for utils.py
"""
import os

from test_harness.utils import (
    create_file_io_file_name_tuple,
    create_file_io_file_name_tuple_with_file_path
)


def test_create_file_io_file_name_tuple() -> None:
    """Test for `create_file_io_file_name_tuple`
    """
    file_string = "test"
    file_name = "test_file"
    file_io_file_name_pair = create_file_io_file_name_tuple(
        file_name=file_name,
        file_string=file_string
    )
    assert file_io_file_name_pair[1] == file_name
    assert file_io_file_name_pair[0].read().decode("utf-8") == file_string


def test_create_file_io_file_name_tuple_with_file_path() -> None:
    """Test for `create_file_io_file_name_tuple_with_file_path`
    """
    file_string = "test"
    file_name = "test_file"
    file_path = os.path.join("some_directory", file_name)
    file_io_file_name_pair = create_file_io_file_name_tuple_with_file_path(
        file_path=file_path,
        file_string=file_string
    )
    assert file_io_file_name_pair[1] == file_name
    assert file_io_file_name_pair[0].read().decode("utf-8") == file_string
