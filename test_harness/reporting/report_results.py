"""
Contains base class for printing test cases
"""
from __future__ import annotations
from abc import ABC, abstractmethod


class TestPrint(ABC):
    """Class to handle printing of tests

    :param name: The identifying name of the Test or group of tests
    :type name: `str`
    """
    def __init__(
        self,
        name: str
    ) -> None:
        """Constructor method
        """
        super().__init__()
        self.name = name
        self.parent = None

    @property
    def parent(self) -> TestPrint | None:
        """Property identifying parent of the instance

        :return: Returns the parent
        :rtype: :class:`TestPrint` | `None`
        """
        return self._parent

    @parent.setter
    def parent(self, test_print: TestPrint | None) -> None:
        """Sette for the parent of the instance

        :param test_print: The parent to be set
        :type test_print: :class:`TestPrint` | `None`
        """
        self._parent = test_print

    @staticmethod
    def create_indent_string(indent: int) -> str:
        """Method to create an indent of whitespaces

        :param indent: The number characters of indent
        :type indent: `int`
        :return: Returns the indent
        :rtype: `str`
        """
        return "".join(" " for _ in range(indent))

    @abstractmethod
    def print_case(self) -> str:
        """Abstract method to print the instance

        :return: Returns the string representation of the case
        :rtype: `str`
        """
        return ""

    @abstractmethod
    def count_tests(self) -> tuple[int, int, int]:
        """Abstract method to count the tests

        :return: Returns a tuple of integers representing:
        * number of tests
        * number of failures
        * number of errors
        :rtype: `tuple`[`int`, `int`, `int`]
        """
        return (0, 0, 0)
