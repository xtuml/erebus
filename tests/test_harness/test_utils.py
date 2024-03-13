"""Tests for utils.py
"""
import os

import pytest

from test_harness.utils import (
    create_file_io_file_name_tuple,
    create_file_io_file_name_tuple_with_file_path,
    RollOverChoice
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


class TestRollOverChoice:
    """Test for `RollOverChoice`
    """
    def test_roll_over_choice(self) -> None:
        """Test for `RollOverChoice`
        """
        list_to_choose_from = ["a", "b", "c"]
        roll_over_choice = RollOverChoice(len(list_to_choose_from))
        assert roll_over_choice(list_to_choose_from)[0] == "a"
        assert roll_over_choice(list_to_choose_from)[0] == "b"
        assert roll_over_choice(list_to_choose_from)[0] == "c"
        choices = roll_over_choice(list_to_choose_from, k=2)
        assert len(choices) == 2
        assert all([choice in choices for choice in list_to_choose_from[:2]])
        assert roll_over_choice(list_to_choose_from)[0] == "c"
        choices = roll_over_choice(list_to_choose_from, k=6)
        assert len(choices) == 6
        assert all(
            choice == member
            for choice, member in zip(choices, list_to_choose_from * 2)
        )

    def test_roll_over_choice_zero_roll_over(self) -> None:
        """Test for `RollOverChoice` with an empty list
        """
        with pytest.raises(ValueError):
            RollOverChoice(0)

    def test_roll_over_choice_empty_list(self) -> None:
        """Test for `RollOverChoice` with an empty list
        """
        with pytest.raises(IndexError):
            RollOverChoice(1)([])

    def test_roll_over_larger_than_list(self) -> None:
        """Test for `RollOverChoice` with a larger rollover than the list
        length
        """
        list_to_choose_from = ["a", "b", "c"]
        roll_over_choice = RollOverChoice(len(list_to_choose_from) + 1)
        with pytest.raises(IndexError):
            roll_over_choice(list_to_choose_from, k=4)
