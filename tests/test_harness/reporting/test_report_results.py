"""Tests for reporting results
"""
import re
from pandas import DataFrame
from test_harness.reporting.report_results import (
    generate_junit_xml,
    generate_html_report_string
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
        fields=["JobName", "Validity", "Category"]
    )
    assert xml_string == expected_junit_string


def test_generate_html_report_string(
    expected_results: DataFrame,
    expected_html_string: str
) -> None:
    """Tests the method `generate_html_report_string` for the correct output
    from input results

    :param expected_results: Fixture providing expected results dataframe
    :type expected_results: :class:`DataFrame`
    :param expected_html_string: Fixture providing the expected html output
    string
    :type expected_html_string: `str`
    """
    html_string = generate_html_report_string(
        results_df=expected_results,
        fields=["JobName", "Validity", "Category"],
        field_depth=2
    )
    sub_html_string = re.sub('id=".*"', 'id=""', html_string)
    sub_html_string = re.sub('href=".*"', 'href=""', sub_html_string)
    sub_expected_html_string = re.sub('id=".*"', 'id=""', expected_html_string)
    sub_expected_html_string = re.sub(
        'href=".*"', 'href=""', sub_expected_html_string
    )
    assert sub_html_string == sub_expected_html_string
