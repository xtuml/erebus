"""Tests for reporting results
"""
import re
from pandas import DataFrame
from test_harness.reporting.report_results import (
    generate_junit_xml,
    generate_html_report_string,
    get_report_files_mapping_from_dataframe_report
)


def test_generate_junit_xml(
    expected_results: DataFrame,
    expected_junit_string: str
) -> None:
    """Tests the method `generate_junit_xml` for the correct output from input
    results

    :param expected_results: Fixture providing expected results dataframe
    :type expected_results: :class:`DataFrame`
    :param expected_junit_string: Fixture providing the expected junit xml out
    put string
    :type expected_junit_string: `str`
    """
    xml_string = generate_junit_xml(
        results_df=expected_results,
        fields=["JobName", "Validity", "Category"],
        field_depth=2
    )
    assert xml_string == expected_junit_string


def test_generate_html_report_string(
    expected_results: DataFrame,
    expected_html_string: str,
    expected_junit_string: str
) -> None:
    """Tests the method `generate_html_report_string` for the correct output
    from input results

    :param expected_results: Fixture providing expected results dataframe
    :type expected_results: :class:`DataFrame`
    :param expected_html_string: Fixture providing the expected html output
    string
    :type expected_html_string: `str`
    """
    html_string, xml_string = generate_html_report_string(
        results_df=expected_results,
        fields=["JobName", "Validity", "Category"],
        field_depth=2
    )
    assert expected_junit_string == xml_string
    check_html_generated_strings(
        expected_html_string,
        html_string
    )


def check_html_generated_strings(
    html_string_1: str,
    html_string_2: str
) -> None:
    """Method to check two generated htmls strings are equivalent

    :param html_string_1: First html string
    :type html_string_1: `str`
    :param html_string_2: Second html string
    :type html_string_2: `str`
    """
    sub_html_string_1 = sub_id_href(html_string_1)
    sub_html_string_2 = sub_id_href(html_string_2)
    assert sub_html_string_1 == sub_html_string_2


def sub_id_href(
    html_string: str
) -> str:
    """Method to sustitute id and href values for empty strings

    :param html_string: The html string
    :type html_string: `str`
    :return: Returns the same string but with href and id values as empty
    strings
    :rtype: `str`
    """
    sub_html_string = re.sub('id=".*"', 'id=""', html_string)
    sub_html_string = re.sub('href=".*"', 'href=""', sub_html_string)
    return sub_html_string


def test_get_report_files_mapping_from_dataframe_report(
    expected_results: DataFrame,
    expected_junit_string: str,
    expected_html_string: str
) -> None:
    """Tests `get_report_files_mapping_from_dataframe_report`

    :param expected_results: Fixture providing expected results dataframe
    :type expected_results: :class:`DataFrame`
    :param expected_junit_string: Fixtgure providing expected junit string
    :type expected_junit_string: `str`
    :param expected_html_string: Fixture providing expected html string
    :type expected_html_string: `str`
    """
    report_files_mapping = get_report_files_mapping_from_dataframe_report(
        expected_results,
        "test"
    )
    file_names = ["test." + suffix for suffix in ["csv", "html", "xml"]]
    assert all(
        file_name in report_files_mapping
        for file_name in file_names
    )
    assert report_files_mapping["test.xml"] == expected_junit_string
    check_html_generated_strings(
        expected_html_string,
        report_files_mapping["test.html"]
    )
    assert expected_results.equals(report_files_mapping["test.csv"])
