# pylint: disable=W0621
# pylint: disable=C0301
"""Fixtures for reporting tests
"""
import pytest
import pandas as pd
import numpy as np


@pytest.fixture
def expected_results() -> pd.DataFrame:
    """Fixture providing dataframe of expected results

    :return: Returns dataframe of expected results
    :rtype: :class:`pd`.`DataFrame`
    """
    data = [
        [
            "job_1",
            "job_name",
            True,
            "ValidSols",
            "file_1",
            [np.nan],
            [True],
            "Pass",
        ],
        [
            "job_2",
            "job_name",
            True,
            "ValidSols",
            "file_2",
            ["It Failed"],
            [False],
            "Fail",
        ],
        [
            "job_3",
            "job_name",
            False,
            "StackedSols",
            "file_3",
            ["It Failed"] * 2,
            [False, False],
            "Pass",
        ],
        [
            "job_4",
            "job_name",
            False,
            "ANDConstraintBreak",
            "file_4",
            ["It Failed", np.nan],
            [False, True],
            "Inconclusive|SVDC Success|Notified Failure",
        ],
        [
            "job_5",
            "job_name",
            False,
            "MissingEdges",
            "file_5",
            np.nan,
            np.nan,
            "Inconclusive|No SVDC Success|No Notification Failure",
        ],
    ]
    results_df = pd.DataFrame(
        data,
        columns=[
            "JobId",
            "SequenceName",
            "Validity",
            "Category",
            "FileName",
            "FailureReason",
            "PVResult",
            "TestResult",
        ],
    )
    results_df.set_index("JobId", inplace=True)
    return results_df


@pytest.fixture
def expected_junit_string() -> str:
    """Fixture providing an expected J-Unit xml string from expected results

    :return: Returns a string representation of the xml file
    :rtype: `str`
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<testsuites name="Tests Run"'
        ' tests="5" failures="1" errors="2">\n    <testsuite'
        ' name="job_name.False.ANDConstraintBreak" tests="1" failures="0"'
        ' errors="1">\n        <testcase name="JobId=job_4, FileName=file_4"'
        ' classname="job_name.False.ANDConstraintBreak">\n            <error'
        ' message="SVDC Success and PV failure" type="PVMisMatch">\n          '
        "      Protocol Verifier showed success and failure messages. PV"
        " Failure reasons below:\n                    It Failed;\n           "
        " </error>\n        </testcase>\n    </testsuite>\n    <testsuite"
        ' name="job_name.False.MissingEdges" tests="1" failures="0"'
        ' errors="1">\n        <testcase name="JobId=job_5, FileName=file_5"'
        ' classname="job_name.False.MissingEdges">\n            <error'
        ' message="No PV SVDC Success and no PV failure" type="PVMisMatch">\n '
        "               Time out was allowed but Protocol Verifier showed no"
        " success or failure messages\n            </error>\n       "
        " </testcase>\n    </testsuite>\n    <testsuite"
        ' name="job_name.False.StackedSols" tests="1" failures="0"'
        ' errors="0">\n        <testcase name="JobId=job_3, FileName=file_3"'
        ' classname="job_name.False.StackedSols" />\n    </testsuite>\n   '
        ' <testsuite name="job_name.True.ValidSols" tests="2" failures="1"'
        ' errors="0">\n        <testcase name="JobId=job_1, FileName=file_1"'
        ' classname="job_name.True.ValidSols" />\n        <testcase'
        ' name="JobId=job_2, FileName=file_2"'
        ' classname="job_name.True.ValidSols">\n            <failure'
        ' message="PV Result does not match validity" type="AssertionError">\n'
        "                PV Result was a fail when sequence is valid. PV"
        " failure reasons below:\n                    It Failed;\n           "
        " </failure>\n        </testcase>\n    </testsuite>\n</testsuites>"
    )


@pytest.fixture
def report_files_mapping(
    expected_results: pd.DataFrame,
    expected_junit_string: str,
    expected_html_string: str,
) -> dict[str, str | pd.DataFrame]:
    """Fixture providing a dictionary mapping file name to file

    :param expected_results: Fixture providing expected results dataframe
    :type expected_results: :class:`pd`.`DataFrame`
    :param expected_junit_string: Fixture providing expected junit string
    :type expected_junit_string: `str`
    :param expected_html_string: Fixture providing expected html string
    :type expected_html_string: `str`
    :return: Dictionary mapping filename to file
    :rtype: `dict`[`str`, `str` | :class:`pd`.`DataFrame`]
    """
    return {
        "test.csv": expected_results,
        "test.xml": expected_junit_string,
        "test.html": expected_html_string,
    }


@pytest.fixture
def expected_html_string() -> str:
    """Fixture providing an html string of expected results

    :return: Returns a string representation of the html file
    :rtype: `str`
    """
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n    <meta'
        ' charset="UTF-8">\n    <title>Test Results</title>\n    <style'
        ' type="text/css">\n        body {\n    background-color: white;\n   '
        " padding-bottom: 20em;\n    margin: 0;\n    min-height:"
        " 15cm;\n}\n\nh1, h2, h3, h4, h5, h6, h7 {\n    font-family:"
        " sans-serif;\n}\n\nh1 {\n    background-color: #007acc;\n    color:"
        " white;\n    padding: 3mm;\n    margin-top: 0;\n    margin-bottom:"
        " 1mm;\n}\n\n.footer {\n    font-style: italic;\n    font-size:"
        " small;\n    text-align: right;\n    padding: 1em;\n}\n\n.testsuite"
        " {\n    padding-bottom: 2em;\n    margin-left: 1em;\n}\n\n.proplist"
        " {\n    width: 100%;\n    margin-bottom: 2em;\n    border-collapse:"
        " collapse;\n    border: 1px solid grey;\n}\n\n.proplist th {\n   "
        " background-color: silver;\n    width: 5em;\n    padding: 2px;\n   "
        " padding-right: 1em;\n    text-align: left;\n}\n\n.proplist td {\n   "
        " padding: 2px;\n}\n\n.index-table {\n    width: 90%;\n   "
        " margin-left: 1em;\n}\n\n.index-table td {\n    vertical-align:"
        " top;\n    width: 50%;\n}\n\n.failure-index {\n\n}\n\n.toc {\n   "
        " margin-bottom: 2em;\n    font-family: monospace;\n}\n\n.stdio, pre"
        " {\n    min-height: 1em;\n    background-color: #1e1e1e;\n    color:"
        " silver;\n    padding: 0.5em;\n}\n.tdpre {\n    background-color:"
        " #1e1e1e;\n}\n\n.test {\n    margin-left: 0.5cm;\n}\n\n.outcome {\n  "
        "  border-left: 1em;\n    padding: 2px;\n}\n\n.outcome-failed {\n   "
        " border-left: 1em solid lightcoral;\n}\n\n.outcome-passed {\n   "
        " border-left: 1em solid lightgreen;\n}\n\n.outcome-skipped {\n   "
        " border-left: 1em solid lightyellow;\n}\n\n.stats-table"
        " {\n}\n\n.stats-table td {\n    min-width: 4em;\n    text-align:"
        " right;\n}\n\n.stats-table .failed {\n    background-color:"
        " lightcoral;\n}\n\n.stats-table .passed {\n    background-color:"
        " lightgreen;\n}\n\n.matrix-table {\n    table-layout: fixed;\n   "
        " border-spacing: 0;\n    width: available;\n    margin-left:"
        " 1em;\n}\n\n.matrix-table td {\n    vertical-align:"
        " center;\n}\n\n.matrix-table td:last-child {\n    width:"
        " 0;\n}\n\n.matrix-table tr:hover {\n    background-color:"
        " yellow;\n}\n\n.matrix-axis-name {\n    white-space: nowrap;\n   "
        " padding-right: 0.5em;\n    border-left: 1px solid black;\n   "
        " border-top: 1px solid black;\n    text-align:"
        " right;\n}\n\n.matrix-axis-line {\n    border-left: 1px solid"
        " black;\n    width: 0.5em;\n}\n\n.matrix-classname {\n    text-align:"
        " left;\n    width: 100%;\n    border-top: 2px solid grey;\n   "
        " border-bottom: 1px solid silver;\n}\n\n.matrix-casename {\n   "
        " text-align: left;\n    font-weight: normal;\n    font-style:"
        " italic;\n    padding-left: 1em;\n    border-bottom: 1px solid"
        " silver;\n}\n\n.matrix-result {\n    display: block;\n    width:"
        " 1em;\n    text-align: center;\n    padding: 1mm;\n    margin:"
        " 0;\n}\n\n.matrix-result-combined {\n    white-space: nowrap;\n   "
        " padding-right: 0.2em;\n    text-align:"
        " right;\n}\n\n.matrix-result-failed {\n    background-color:"
        " lightcoral;\n}\n\n.matrix-result-passed {\n    background-color:"
        " lightgreen;\n}\n\n.matrix-result-skipped {\n    background-color:"
        " lightyellow;\n}\n\n.matrix-even {\n    background-color:"
        " lightgray;\n}\n    </style>\n</head>\n<body>\n    \n<h1>\n    Test"
        ' Report : Test Results\n</h1>\n<a id="toc"></a>\n<table'
        ' class="index-table">\n    <tr>\n        <td>\n            <ul'
        ' class="toc">\n            \n                \n               '
        " <li>job_name.False.ANDConstraintBreak\n                <ul>\n       "
        "             \n                    <li><a"
        ' href="#7962f23a-eb97-4ada-8877-819e3ba5c04f">JobId=job_4,'
        " FileName=file_4</a></li>\n                    \n               "
        " </ul>\n                </li>\n                \n            \n      "
        "          \n                <li>job_name.False.MissingEdges\n        "
        "        <ul>\n                    \n                    <li><a"
        ' href="#f83f740e-7df3-47c4-a794-f7a40f7b943d">JobId=job_5,'
        " FileName=file_5</a></li>\n                    \n               "
        " </ul>\n                </li>\n                \n            \n      "
        "          \n                <li>job_name.False.StackedSols\n         "
        "       <ul>\n                    \n                    <li><a"
        ' href="#647f58a9-3bef-4ac2-b273-2a096d1af1ad">JobId=job_3,'
        " FileName=file_3</a></li>\n                    \n               "
        " </ul>\n                </li>\n                \n            \n      "
        "          \n                <li>job_name.True.ValidSols\n            "
        "    <ul>\n                    \n                    <li><a"
        ' href="#f1d2bba9-df08-42a6-aedb-902e12b7237c">JobId=job_1,'
        " FileName=file_1</a></li>\n                    \n                   "
        ' <li><a href="#bb4fa17f-9934-4cc2-85ef-dacd5a527cfd">JobId=job_2,'
        " FileName=file_2</a></li>\n                    \n               "
        " </ul>\n                </li>\n                \n            \n      "
        '      </ul>\n        </td>\n        <td class="failure-index">\n     '
        '       <ul class="toc">\n            \n                \n            '
        "        \n                    \n                    <li><a"
        ' href="#7962f23a-eb97-4ada-8877-819e3ba5c04f">[F]'
        " job_name.False.ANDConstraintBreak : JobId=job_4,"
        " FileName=file_4</a></li>\n                    \n                   "
        " \n                \n            \n                \n                "
        "    \n                    \n                    <li><a"
        ' href="#f83f740e-7df3-47c4-a794-f7a40f7b943d">[F]'
        " job_name.False.MissingEdges : JobId=job_5,"
        " FileName=file_5</a></li>\n                    \n                   "
        " \n                \n            \n                \n                "
        "    \n                    \n                    \n                \n "
        "           \n                \n                    \n                "
        "    \n                    \n                    \n                   "
        ' <li><a href="#bb4fa17f-9934-4cc2-85ef-dacd5a527cfd">[F]'
        " job_name.True.ValidSols : JobId=job_2, FileName=file_2</a></li>\n   "
        "                 \n                    \n                \n          "
        "  \n            </ul>\n        </td>\n    </tr>\n</table>\n\n\n   "
        ' <div class="testsuite">\n        <h2>Test Suite:'
        " job_name.False.ANDConstraintBreak</h2>\n        <a"
        ' id="c4586ed8-e888-40eb-aaa5-915c9d6ce8d4"></a>\n        \n        \n'
        '        <h3>Results</h3>\n        <table class="proplist">\n         '
        "   <tr>\n                <th>Duration</th><td>0.0 sec</td>\n         "
        "   </tr>\n            <tr>\n               "
        " <th>Tests</th><td>1</td>\n            </tr>\n            <tr>\n     "
        "           <th>Failures</th><td>1</td>\n            </tr>\n       "
        ' </table>\n\n        <div class="testclasses">\n           '
        ' <h3>Tests</h3>\n            \n            <div class="testclass">\n '
        "               <h4>job_name.False.ANDConstraintBreak</h4>\n          "
        '      <div class="testcases">\n                \n                   '
        ' <div class="test outcome outcome-failed">\n                       '
        ' <a id="7962f23a-eb97-4ada-8877-819e3ba5c04f"></a>\n                 '
        '       <table class="proplist">\n                           '
        " <tr><th>Test case:</th><td><b>JobId=job_4,"
        " FileName=file_4</b></td></tr>\n                           "
        " <tr><th>Outcome:</th><td>Failed</td></tr>\n                         "
        "   <tr><th>Duration:</th><td>0.0 sec</td></tr>\n                     "
        "   \n                            <tr><th>Failed</th><td>SVDC Success"
        " and PV failure</td></tr>\n                        \n                "
        "        \n                        </table>\n\n                       "
        " \n                        <pre>\n                Protocol Verifier"
        " showed success and failure messages. PV Failure reasons below:\n    "
        "                It Failed;\n            </pre>\n                     "
        "   \n                        \n\n                        \n          "
        "              \n                        \n                   "
        " </div>\n                \n                </div>\n           "
        " </div>\n            \n        </div>\n    </div>\n    \n\n    <div"
        ' class="testsuite">\n        <h2>Test Suite:'
        " job_name.False.MissingEdges</h2>\n        <a"
        ' id="57293b90-debb-47a8-8057-1798f596ac63"></a>\n        \n        \n'
        '        <h3>Results</h3>\n        <table class="proplist">\n         '
        "   <tr>\n                <th>Duration</th><td>0.0 sec</td>\n         "
        "   </tr>\n            <tr>\n               "
        " <th>Tests</th><td>1</td>\n            </tr>\n            <tr>\n     "
        "           <th>Failures</th><td>1</td>\n            </tr>\n       "
        ' </table>\n\n        <div class="testclasses">\n           '
        ' <h3>Tests</h3>\n            \n            <div class="testclass">\n '
        "               <h4>job_name.False.MissingEdges</h4>\n               "
        ' <div class="testcases">\n                \n                    <div'
        ' class="test outcome outcome-failed">\n                        <a'
        ' id="f83f740e-7df3-47c4-a794-f7a40f7b943d"></a>\n                    '
        '    <table class="proplist">\n                           '
        " <tr><th>Test case:</th><td><b>JobId=job_5,"
        " FileName=file_5</b></td></tr>\n                           "
        " <tr><th>Outcome:</th><td>Failed</td></tr>\n                         "
        "   <tr><th>Duration:</th><td>0.0 sec</td></tr>\n                     "
        "   \n                            <tr><th>Failed</th><td>No PV SVDC"
        " Success and no PV failure</td></tr>\n                        \n     "
        "                   \n                        </table>\n\n            "
        "            \n                        <pre>\n                Time out"
        " was allowed but Protocol Verifier showed no success or failure"
        " messages\n            </pre>\n                        \n            "
        "            \n\n                        \n                        \n "
        "                       \n                    </div>\n               "
        " \n                </div>\n            </div>\n            \n       "
        ' </div>\n    </div>\n    \n\n    <div class="testsuite">\n       '
        " <h2>Test Suite: job_name.False.StackedSols</h2>\n        <a"
        ' id="076d72a9-c088-4561-916d-a9da5c96372a"></a>\n        \n        \n'
        '        <h3>Results</h3>\n        <table class="proplist">\n         '
        "   <tr>\n                <th>Duration</th><td>0.0 sec</td>\n         "
        "   </tr>\n            <tr>\n               "
        " <th>Tests</th><td>1</td>\n            </tr>\n            <tr>\n     "
        "           <th>Failures</th><td>0</td>\n            </tr>\n       "
        ' </table>\n\n        <div class="testclasses">\n           '
        ' <h3>Tests</h3>\n            \n            <div class="testclass">\n '
        "               <h4>job_name.False.StackedSols</h4>\n               "
        ' <div class="testcases">\n                \n                    <div'
        ' class="test outcome outcome-passed">\n                        <a'
        ' id="647f58a9-3bef-4ac2-b273-2a096d1af1ad"></a>\n                    '
        '    <table class="proplist">\n                           '
        " <tr><th>Test case:</th><td><b>JobId=job_3,"
        " FileName=file_3</b></td></tr>\n                           "
        " <tr><th>Outcome:</th><td>Passed</td></tr>\n                         "
        "   <tr><th>Duration:</th><td>0.0 sec</td></tr>\n                     "
        "   \n                           "
        " <tr><th>Failed</th><td>None</td></tr>\n                        \n   "
        "                     \n                        </table>\n\n          "
        "              \n                        <pre>None</pre>\n            "
        "            \n                        \n\n                        \n "
        "                       \n                        \n                  "
        "  </div>\n                \n                </div>\n           "
        " </div>\n            \n        </div>\n    </div>\n    \n\n    <div"
        ' class="testsuite">\n        <h2>Test Suite:'
        " job_name.True.ValidSols</h2>\n        <a"
        ' id="f58935c3-7446-49a8-8dd7-771950ed613e"></a>\n        \n        \n'
        '        <h3>Results</h3>\n        <table class="proplist">\n         '
        "   <tr>\n                <th>Duration</th><td>0.0 sec</td>\n         "
        "   </tr>\n            <tr>\n               "
        " <th>Tests</th><td>2</td>\n            </tr>\n            <tr>\n     "
        "           <th>Failures</th><td>1</td>\n            </tr>\n       "
        ' </table>\n\n        <div class="testclasses">\n           '
        ' <h3>Tests</h3>\n            \n            <div class="testclass">\n '
        "               <h4>job_name.True.ValidSols</h4>\n                <div"
        ' class="testcases">\n                \n                    <div'
        ' class="test outcome outcome-passed">\n                        <a'
        ' id="f1d2bba9-df08-42a6-aedb-902e12b7237c"></a>\n                    '
        '    <table class="proplist">\n                           '
        " <tr><th>Test case:</th><td><b>JobId=job_1,"
        " FileName=file_1</b></td></tr>\n                           "
        " <tr><th>Outcome:</th><td>Passed</td></tr>\n                         "
        "   <tr><th>Duration:</th><td>0.0 sec</td></tr>\n                     "
        "   \n                           "
        " <tr><th>Failed</th><td>None</td></tr>\n                        \n   "
        "                     \n                        </table>\n\n          "
        "              \n                        <pre>None</pre>\n            "
        "            \n                        \n\n                        \n "
        "                       \n                        \n                  "
        '  </div>\n                \n                    <div class="test'
        ' outcome outcome-failed">\n                        <a'
        ' id="bb4fa17f-9934-4cc2-85ef-dacd5a527cfd"></a>\n                    '
        '    <table class="proplist">\n                           '
        " <tr><th>Test case:</th><td><b>JobId=job_2,"
        " FileName=file_2</b></td></tr>\n                           "
        " <tr><th>Outcome:</th><td>Failed</td></tr>\n                         "
        "   <tr><th>Duration:</th><td>0.0 sec</td></tr>\n                     "
        "   \n                            <tr><th>Failed</th><td>PV Result"
        " does not match validity</td></tr>\n                        \n       "
        "                 \n                        </table>\n\n              "
        "          \n                        <pre>\n                PV Result"
        " was a fail when sequence is valid. PV failure reasons below:\n      "
        "              It Failed;\n            </pre>\n                       "
        " \n                        \n\n                        \n            "
        "            \n                        \n                    </div>\n "
        "               \n                </div>\n            </div>\n        "
        '    \n        </div>\n    </div>\n    \n\n\n\n<p class="footer">\n   '
        " Generated by junit2html\n</p>\n</body>\n</html>"
    )
