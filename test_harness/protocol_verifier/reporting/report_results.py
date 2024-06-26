"""Methods to create junit report into html"""

from __future__ import annotations
import pandas as pd
from typing import Any, Literal
from junit2htmlreport.parser import Junit

from test_harness.reporting.report_results import TestPrint


class PerformanceTestCase(TestPrint):
    """Sub class of :class:`TestPrint` to create xml
    Test cases for a peformance test

    :param name: The name of the test
    :type name: `str`
    :param results: The given results:
    * 'num_tests'
    * 'num_failures'
    * 'num_errors'
    :type results: `dict`[`str`, `int`]
    """

    def __init__(self, name: str, results: dict[str, int]) -> None:
        """Constructor method"""
        super().__init__(name=name)
        self.results = results
        self.result = self.calc_result()

    def count_tests(self) -> tuple[int, int, int]:
        """Method to count the number of tests failures and errors

        :return: Returns the tests failures and errors
        :rtype: tuple[`int`, `int`, `int`]
        """
        return (
            self.results["num_tests"],
            self.results["num_failures"],
            self.results["num_errors"],
        )

    def print_case(self, indent: int = 4, level: int = 0) -> str:
        """Method to print the test case

        :param indent: Indent used in the output, defaults to `4`
        :type indent: `int`, optional
        :param level: The level of indent the test case is on, defaults to `0`
        :type level: `int`, optional
        :return: Returns the string representation of the test case
        :rtype: `str`
        """
        print_string = ""
        indent_string = self.create_indent_string(indent * level)
        print_string += indent_string
        print_string += self.create_tag_start()
        if self.result == "Pass":
            print_string += " />"
            return print_string
        # anything other than pass
        next_level = level + 1
        next_level_indent = self.create_indent_string(indent * next_level)
        print_string += ">\n" + next_level_indent
        failure_indent = self.create_indent_string(indent * (next_level + 1))
        if self.result == "Fail":
            print_string += (
                '<failure message="The protocol verifier failed to process'
                " some "
                'events" '
                'type="PVError">\n'
            )
            print_string += failure_indent + (
                f"{self.results['num_failures']}"
                f" of {self.results['num_tests']} events failed to be"
                " processed "
                "correctly by the PV\n"
            )
            print_string += next_level_indent + ("</failure>\n")
        else:
            print_string += (
                '<error message="The Test Harness failed to successfully send '
                'some events" '
                'type="THError">\n'
            )
            print_string += failure_indent + (
                f"{self.results['num_errors']}"
                f" of {self.results['num_tests']} events failed to be sent "
                "correctly by the Test Harness\n"
            )
            print_string += next_level_indent + "</error>\n"
        print_string += indent_string + "</testcase>"
        return print_string

    def calc_result(self) -> Literal["Pass", "Error", "Fail"]:
        """Method to calculate the result of the test given the results

        :return: Returns:
        * "Pass"
        * "Error"
        * "Fail"
        :rtype: :class:`Literal`[`'Pass'`, `'Error'`, `'Fail'`]
        """
        if self.results["num_failures"] + self.results["num_errors"] == 0:
            return "Pass"
        if self.results["num_errors"] > 0:
            return "Error"
        return "Fail"

    def create_tag_start(self) -> str:
        """Method to create the starting tag for the string representation of
        the test case

        :raises RuntimeError: Raises a :class:`RuntimeError` is there is no
        parent
        :return: Returns the test case starting tag
        :rtype: `str`
        """
        if not self.parent:
            raise RuntimeError("Cannot create tag without parent")
        return f'<testcase name="{self.name}" classname="{self.parent.name}"'


class TestCase(TestPrint):
    """Class to hold information on a Protocol Verifier Test Case

    :param name: The name of the test
    :type name: `str`
    :param result: The result of the test
    * Pass
    * Failure
    * Inconclusive
    :type result: `str`
    :param file_name: The name of the file used for the test, defaults to
    `None`
    :type file_name: `str` | `None`, optional
    """

    def __init__(
        self, name: str, result: str, file_name: str | None = None
    ) -> None:
        """Constructor method"""
        super().__init__(name)
        self.result = result
        self.pv_failure_reason = None
        self.file_name = file_name

    @property
    def pv_failure_reason(self) -> list | None:
        """Property for protocol verifier failure reasons

        :return: Returns the list of failure reasons or `None` if there aren't
        any
        :rtype: `list` | `None`
        """
        return self._pv_failure_reason

    @pv_failure_reason.setter
    def pv_failure_reason(self, reasons: list[Any] | None) -> None:
        """Setter for the property `pv_failure_reason`

        :param reasons: The list of reasons. Filters out non string values
        :type reasons: `list`[`Any`] | `None`
        """
        if not reasons:
            self._pv_failure_reason = None
        else:
            self._pv_failure_reason = list(
                set(
                    reason + ";\n"
                    for reason in reasons
                    if isinstance(reason, str)
                )
            )

    def print_case(self, indent: int = 4, level: int = 0) -> str:
        """Method to print the test case

        :param indent: Indent used in the output, defaults to `4`
        :type indent: `int`, optional
        :param level: The level of indent the test case is on, defaults to `0`
        :type level: `int`, optional
        :return: Returns the string representation of the test case
        :rtype: `str`
        """
        print_string = ""
        indent_string = self.create_indent_string(indent * level)
        print_string += indent_string
        print_string += self.create_tag_start()
        if self.result == "Pass":
            print_string += " />"
            return print_string
        # anything other than pass
        next_level = level + 1
        next_level_indent = self.create_indent_string(indent * next_level)
        print_string += ">\n" + next_level_indent
        failure_indent = self.create_indent_string(indent * (next_level + 1))
        if self.result == "Fail":
            print_string += (
                '<failure message="PV Result does not match validity" '
                'type="AssertionError">\n'
            )
            if self.pv_failure_reason:
                print_string += failure_indent + (
                    "PV Result was a fail when sequence is valid. PV failure "
                    "reasons below:\n"
                )
                print_string += "".join(
                    self.create_indent_string(indent * (next_level + 2))
                    + reason
                    for reason in self.pv_failure_reason
                )
            else:
                print_string += failure_indent + (
                    "PV Result was a success when sequence is invalid\n"
                )
            print_string += next_level_indent + ("</failure>\n")
        elif self.result == (
            "Inconclusive|No SVDC Success|No Notification Failure"
        ):
            print_string += (
                '<error message="No PV SVDC Success and no PV failure" '
                'type="PVMisMatch">\n'
            )
            print_string += failure_indent + (
                "Time out was allowed but "
                "Protocol Verifier showed no success or failure messages\n"
            )
            print_string += next_level_indent + "</error>\n"
        else:
            print_string += (
                '<error message="SVDC Success and PV failure" '
                'type="PVMisMatch">\n'
            )
            print_string += failure_indent + (
                "Protocol Verifier showed success and failure messages. PV "
                "Failure reasons below:\n"
            )
            if self.pv_failure_reason:
                print_string += "".join(
                    self.create_indent_string(indent * (next_level + 2))
                    + reason
                    for reason in self.pv_failure_reason
                )
            print_string += next_level_indent + "</error>\n"
        print_string += indent_string + "</testcase>"
        return print_string

    def create_tag_start(self) -> str:
        """Method to create the starting tag for the string representation of
        the test case

        :raises RuntimeError: Raises a :class:`RuntimeError` is there is no
        parent
        :return: Returns the test case starting tag
        :rtype: `str`
        """
        if not self.parent:
            raise RuntimeError("Cannot create tag without parent")
        return f'<testcase name="{self.name}" classname="{self.parent.name}"'

    def count_tests(self) -> tuple[int, int, int]:
        """Method to count the number of tests failures and errors

        :return: Returns the tests failures and errors
        :rtype: tuple[`int`, `int`, `int`]
        """
        tests, failures, errors = 1, 0, 0
        if self.result == "Fail":
            failures = 1
        elif "Inconclusive" in self.result:
            errors = 1
        return tests, failures, errors


class TestSuite(TestPrint):
    """Class to hold information and children of a xml test suite
    Subclass of :class:`TestPrint`
    """

    def __init__(
        self,
        name: str,
        is_suites: bool = False,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Constructor method"""
        super().__init__(name)
        self.children: list[TestCase | TestSuite] = []
        self.is_suites = is_suites
        self.properties = properties

    def add_child(self, child: TestCase | TestSuite) -> None:
        """Method to adda child to the instancees children

        :param child: A child test suite or test case
        :type child: :class:`TestCase` | :class:`TestSuite`
        """
        self.children.append(child)
        child.parent = self

    def add_children(self, children: list[TestCase | TestSuite]) -> None:
        """Method to add multiple children to the test case

        :param children: A list of children
        :type children: `list`[:class:`TestCase`  |  :class:`TestSuite`]
        """
        for child in children:
            self.add_child(child)

    def print_case(self, indent: int = 4, level: int = 0) -> str:
        """Method to provide a string representation of the instance

        :param indent: Indent used in the output, defaults to `4`
        :type indent: `int`, optional
        :param level: The level of indent the test case is on, defaults to `0`
        :type level: `int`, optional
        :return: Returns the string representation of the test suite
        :rtype: `str`
        """
        print_string = ""
        indent_string = self.create_indent_string(indent * level)
        print_string += indent_string
        print_string += self.create_tag()
        if self.properties:
            print_string += self.create_properties_string(
                indent=indent, level=level + 1
            )
        print_string += "\n".join(
            child.print_case(indent=indent, level=level + 1)
            for child in self.children
        )
        print_string += (
            f"\n{indent_string}" f'</testsuite{"s" if self.is_suites else ""}>'
        )
        return print_string

    def create_tag(self) -> str:
        """MEthod to create the starting tag for the test suite

        :return: Returns the xml testsuite starting tag
        :rtype: `str`
        """
        tests, failures, errors = self.count_tests()
        tag = (
            f'<testsuite{"s" if self.is_suites else ""} name="{self.name}" '
            f'tests="{tests}" failures="{failures}" errors="{errors}">\n'
        )
        return tag

    def count_tests(self) -> tuple[int, int, int]:
        """Method to count test, failure and error numbers

        :return: Returns a tuple of counts for test, failure and error numbers
        :rtype: `tuple`[`int`, `int`, `int`]
        """
        tests = 0
        failures = 0
        errors = 0
        for child in self.children:
            child_tests, child_failures, child_errors = child.count_tests()
            tests += child_tests
            failures += child_failures
            errors += child_errors
        return tests, failures, errors

    def create_properties_string(self, indent: int = 4, level: int = 0) -> str:
        """Method to provide a string representation of the properties

        :param indent: Indent used in the output, defaults to `4`
        :type indent: `int`, optional
        :param level: The level of indent the test case is on, defaults to `0`
        :type level: `int`, optional
        :return: Returns the string representation of the test suite
        :rtype: `str`
        """
        indent_string = self.create_indent_string(indent * level)
        sub_indent_string = self.create_indent_string(indent * (level + 1))
        properties_string = indent_string + "<properties>\n"
        properties_string += "".join(
            sub_indent_string + f'<property name="{name}" value="{value}"/>\n'
            for name, value in self.properties.items()
        )
        properties_string += indent_string + "</properties>\n"
        return properties_string


def generate_performance_test_reports(
    results: dict[str, int], properties: dict[str, Any] | None = None
) -> tuple[str, str]:
    """Method to generate perfromance test:
    * xml junit report
    * html report based off the xml

    :param results: The results of the test
    :type results: `dict`[`str`, `int`]
    :param properties: Extra properties to be written as results, defaults to
    `None`
    :type properties: `dict`[`str`, `Any`] | `None`, optional
    :return: Returns a tuple of:
    * html report string
    * xml report string
    :rtype: `tuple`[`str`, `str`]
    """
    suites = TestSuite(
        name="Performance tests run",
        is_suites=True,
    )
    if properties is None:
        properties = {}
    suite = TestSuite(
        name="Performance test run", properties={**results, **properties}
    )
    suite.add_child(PerformanceTestCase("Run Result", results=results))
    suites.add_child(suite)
    xml_string = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_string += suites.print_case()
    report = Junit(xmlstring=xml_string)
    html_string = report.html()
    return html_string, xml_string


def generate_html_report_string(
    results_df: pd.DataFrame, fields: list[str], field_depth: int = 0
) -> tuple[str, str]:
    """Method to generate an html report string from a results dataframe and
    its junit xml it was generated from

    :param results_df: Dataframe containing test results
    :type results_df: :class:`pd`.`DataFrame`
    :param fields: The list of fields with which to group tests into
    :type fields: `list`[`str`]
    :param field_depth: The depth of the fields list with which to create
    nested test suite, defaults to `0`
    :type field_depth: `int`, optional
    :return: Returns a generated html report and the junit xml it was
    generated from
    :rtype: `tuple`[`str`, `str`]
    """
    xml_string = generate_junit_xml(
        results_df=results_df, fields=fields, field_depth=field_depth
    )
    report = Junit(xmlstring=xml_string)
    html_string = report.html()
    return html_string, xml_string


def generate_junit_xml(
    results_df: pd.DataFrame, fields: list[str], field_depth: int = 0
) -> str:
    """Method to generate a a junit xml string from a results dataframe

    :param results_df: DataFrame of results
    :type results_df: :class:`pd`.`DataFrame`
    :param fields: The list of fields with which to group tests into
    :type fields: `list`[`str`]
    :param field_depth: The depth of the fields list with which to create
    nested test suites. `field_depth = 0` represents creating nested suits for
    all fields and `field_depth = len(fields)` would be no nesting of test
    cases, defaults to `0`
    :type field_depth: `int`, optional
    :return: Returns a xml string representation of the results
    :rtype: `str`
    """
    suites = TestSuite(name="Tests Run", is_suites=True)
    children = get_test_suites_from_results_dataframe(
        results_df=results_df, fields=fields, nth_field=field_depth
    )
    suites.add_children(children)
    junit_string = '<?xml version="1.0" encoding="UTF-8"?>\n'
    junit_string += suites.print_case()
    return junit_string


def get_test_suites_from_results_dataframe(
    results_df: pd.DataFrame, fields: list[str], nth_field: int = 0
) -> list[TestSuite | TestCase]:
    """Method to obtain test suites and test cases from results dataframe

    :param results_df: Dataframe of results
    :type results_df: :class:`pd`.`DataFrame`
    :param fields: The fields with which to categorise the results
    :type fields: `list`[`str`]
    :param nth_field: Integer to indicate at what index of fields list to
    begin, defaults to `0`
    :type nthe_field: `int`, optional
    :return: Returns a list of :class:`TestSuite`'s or :class:`TestCase`'s
    :rtype: `list`[:class:`TestSuite` | :class:`TestCase`]
    """
    nth_field += 1
    children: list[TestSuite | TestCase] = []
    if nth_field <= len(fields):
        for key, idx in results_df.groupby(fields[:nth_field]).groups.items():
            if isinstance(key, tuple):
                name = ".".join(str(col_val) for col_val in key)
            else:
                name = str(key)
            child = TestSuite(name=name)
            child_children = get_test_suites_from_results_dataframe(
                results_df=results_df.loc[idx],
                fields=fields,
                nth_field=nth_field,
            )
            child.add_children(child_children)
            children.append(child)
    else:
        for idx, row in results_df.iterrows():
            child = TestCase(
                name=(
                    f"JobId={str(idx)}"
                    + (
                        f", FileName={row['FileName']}"
                        if "FileName" in row
                        else ""
                    )
                ),
                result=row["TestResult"],
                file_name=row["FileName"] if "FileName" in row else None,
            )
            if (
                (row["TestResult"] == "Fail" and row["Validity"])
                or (
                    (row["TestResult"])
                    == ("Inconclusive|SVDC Success|Notified Failure")
                )
                or (row["TestResult"] == "Pass" and not row["Validity"])
            ):
                if "FailureReason" in row:
                    child.pv_failure_reason = row["FailureReason"]
            children.append(child)
    return children


def generate_html_from_csv_report(
    test_report_csv_path: str, html_report_file_path: str
) -> None:
    """Method to generate and html file from csv report

    :param test_report_csv_path: The path to the csv report
    :type test_report_csv_path: `str`
    :param html_report_file_path: The output path of the html report
    :type html_report_file_path: str
    """
    results_df = pd.read_csv(test_report_csv_path, index_col="JobId")
    html_string, _ = generate_html_report_string(
        results_df=results_df,
        fields=["SequenceName", "Validity", "Category"],
        field_depth=2,
    )
    with open(html_report_file_path, "w", encoding="utf-8") as file:
        file.write(html_string)


def get_report_files_mapping_from_dataframe_report(
    results_df: pd.DataFrame, results_prefix: str
) -> dict[str, str | pd.DataFrame]:
    """Method to get report files mapping from a results dataframe and a
    prefix for the tests

    :param results_df: :class:`pd`.`DataFrame` of results
    :type results_df: :class:`pd`.`DataFrame`
    :param results_prefix: The prefix for the results file names
    :type results_prefix: `str`
    :return: Returns a dictionary mapping file name to file
    :rtype: `dict`[`str`, `str` | :class:`pd`.`DataFrame`]
    """
    html_string, xml_string = generate_html_report_string(
        results_df=results_df,
        fields=["SequenceName", "Validity", "Category"],
        field_depth=2,
    )
    return {
        f"{results_prefix}.html": html_string,
        f"{results_prefix}.xml": xml_string,
        f"{results_prefix}.csv": results_df,
    }


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    generate_html_from_csv_report(args[0], args[1])
