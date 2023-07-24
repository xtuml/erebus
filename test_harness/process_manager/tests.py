# pylint: disable=R0902
# pylint: disable=R0913
"""Methods and classes relating to tests
"""
from typing import Generator, Any
from abc import ABC, abstractmethod
from random import choice, choices
import os
import asyncio
import logging

import matplotlib.pyplot as plt
import flatdict
from tqdm import tqdm
import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure

from test_harness.config.config import HarnessConfig, TestConfig
from test_harness.jobs.job_factory import parse_input_jobfile, Job
from test_harness.utils import divide_chunks, clean_directories
from test_harness.jobs.job_delivery import send_job_templates_async
from test_harness.process_manager.calc_pv_finish import PVFileInspector
from test_harness.reporting.report_delivery import deliver_test_report_files
from test_harness.reporting import create_report_files
from test_harness.requests import send_get_request


class Results:
    """Class to hold results of test
    """
    def __init__(self) -> None:
        self.job_ids = []
        self.jobs_info = []
        self.file_names = []
        self.responses = []

    def update_test_files_info(
        self,
        job_ids: list[str],
        jobs_info: list[dict[str, str]],
        file_names: list[str]
    ) -> None:
        """Method to update the test files info for the results.
        The lists should be of the same legnth and every index of each list
        should refer to the same file

        :param job_ids: List of job ids
        :type job_ids: `list`[`str`]
        :param jobs_info: List of dictionary mapping name of info to info
        :type jobs_info: `list`[`dict`[`str`, `str`]]
        :param file_names: List of file names of the tests
        :type file_names: `list`[`str`]
        :raises RuntimeError: Raises a :class:`RuntimeError` if the lists are
        not all of the same length
        """
        if len(set(
            len(obj_list)
            for obj_list in [job_ids, jobs_info, file_names]
        )) != 1:
            raise RuntimeError("all lists should be the same length")
        self.job_ids.extend(job_ids)
        self.jobs_info.extend(jobs_info)
        self.file_names.extend(file_names)

    def update_responses(self, responses: list[str]) -> None:
        """Method to update the responses

        :param response: List of responses
        :type response: `str`
        """
        self.responses.extend(responses)

    def create_validity_dataframe(self) -> pd.DataFrame:
        """Create a validity dataframe for the instance

        :return: Returns the validity dataframe
        :rtype: :class:`pd`.`DataFrame`
        """
        validity_df_lines = [
            {
                **{
                    "JobId": job_id,
                    "FileName": file_name
                },
                **job_info
            }
            for job_id, job_info, file_name in zip(
                self.job_ids,
                self.jobs_info,
                self.file_names
            )
        ]
        validity_df = pd.DataFrame.from_records(
            validity_df_lines
        )
        validity_df.set_index("JobId", inplace=True)
        return validity_df


class Test(ABC):
    """Base class to hold and run a test.

    :param test_file_generators: Dictionary containing generated tests for
    each job definition
    :type test_file_generators: `dict`[ `str`, `dict`[ `str`, `tuple`[
    :class:`Generator`[ `tuple`[`list`[`dict`], `list`[`str`],
    :class:`plt`.`Figure`  |  `None`, `str`], `Any`, `None`, ], `bool`, ], ], ]
    :param harness_config: Main config for the test harness, defaults to `None`
    :type harness_config: :class:`HarnessConfig` | `None`, optional
    :param test_config: Config for the specific test, defaults to `None`
    :type test_config: :class:`TestConfig` | `None`, optional
    :param test_output_directory: The path of the test output directory where
    files relating to the test results are stored, defaults to `None`
    :type test_output_directory: `str` | `None`, optional
    :param save_files: Boolean indicating whether to save test results - will
    only save if a test output directory has been given, defaults to `True`
    :type save_files: `bool`, optional
    """

    def __init__(
        self,
        test_file_generators: dict[
            str,
            dict[
                str,
                tuple[
                    Generator[
                        tuple[list[dict], list[str], plt.Figure | None, str],
                        Any,
                        None,
                    ],
                    bool,
                ],
            ],
        ],
        harness_config: HarnessConfig | None = None,
        test_config: TestConfig | None = None,
        test_output_directory: str | None = None,
        save_files: bool = True,
    ) -> None:
        """Constructor method"""
        self.test_files = test_file_generators
        self.test_output_directory = test_output_directory
        self.harness_config = (
            harness_config if harness_config else HarnessConfig()
        )
        self.test_config = test_config if test_config else TestConfig()
        if save_files and not test_output_directory:
            logging.getLogger().warning(
                (
                    "Save files has been set but there is not output directory"
                    " for tests"
                )
            )
        self.save_files = (
            save_files if save_files and test_output_directory else False
        )
        # set up requires attributes
        self.job_templates: list[tuple[Job, dict[str, str | bool]]] = []
        self.chunked_jobs_to_send: list[
            list[tuple[Job, dict[str, str | bool]]]
        ] = []
        self.results = Results()
        self.pv_file_inspector = PVFileInspector(harness_config)
        self.set_test_rate()
        # prepare the test given inputs
        self.prepare_test()

    def make_job_templates(self) -> None:
        """Method to make the template jobs from the generated tests files
        """
        flattened_test_files = flatdict.FlatDict(self.test_files)
        flattened_keys: list[str] = flattened_test_files.keys()
        counter = 0
        # loop until the max number of different sequences have been templated
        # or until all test sequences have been used up
        while (
            counter < (self.test_config.max_different_sequences)
            and flattened_keys
        ):
            try:
                flattened_key: str = choice(flattened_keys)
                try:
                    job_sequence = next(
                        flattened_test_files[flattened_key][0]
                    )[0]
                    job_name_sol_type = flattened_key.split(":")
                    self.job_templates.append(
                        (
                            parse_input_jobfile(job_sequence),
                            {
                                "SequenceName": job_name_sol_type[0],
                                "Category": job_name_sol_type[1],
                                "Validity": flattened_test_files[
                                    flattened_key
                                ][1],
                            },
                        )
                    )
                except StopIteration:
                    flattened_keys.remove(flattened_key)
            except IndexError:
                break

    def prepare_test(self) -> None:
        """Method to prepare the test data
        """
        self.make_job_templates()
        jobs_to_send = self.get_jobs_to_send()
        self.chunked_jobs_to_send = list(
            divide_chunks(
                jobs_to_send,
                chunk_size=self.harness_config.max_files_in_memory,
            )
        )

    @abstractmethod
    def get_jobs_to_send(self) -> list[tuple[Job, dict[str, str | bool]]]:
        """Method to get all the jobs to send

        :return: Returns a list of jobs sequences and their info
        :rtype: `list`[`tuple`[:class:`Job`, `dict`[`str`, `str` | `bool`]]]
        """
        return self.job_templates

    @abstractmethod
    def set_test_rate(self) -> None:
        """Method to set the test interval and shard attribute
        """
        self.interval = 0.1
        self.shard = False

    async def send_test_files(self) -> None:
        """Asynchronous method to send test files to the PV
        """
        # send the chunked jobs
        for test_files_info_chunk in tqdm(
            self.chunked_jobs_to_send,
            total=len(self.chunked_jobs_to_send),
            desc="Sending Chunks",
        ):
            # split the jobs and their info into separate lists
            jobs_and_info = list(map(list, zip(*test_files_info_chunk)))
            jobs_to_send: list[Job] = jobs_and_info[0]
            job_info: list[dict[str, str | bool]] = jobs_and_info[1]

            # send all the jobs
            results, files = await send_job_templates_async(
                jobs_to_send,
                self.interval,
                url=self.harness_config.pv_send_url,
                shard_events=self.shard,
            )
            # update the responses
            self.results.update_responses(results)

            # update test info
            job_ids = []
            file_names = []
            for file_tuple in files:
                job_ids.append(file_tuple[3])
                file_names.append(file_tuple[1])
            self.results.update_test_files_info(
                job_ids=job_ids,
                jobs_info=job_info,
                file_names=file_names
            )
            # save test files if option enabled
            if self.save_files:
                for file_tuple in files:
                    file_string = file_tuple[0].decode("utf-8")
                    with open(
                        os.path.join(
                            self.test_output_directory, file_tuple[1]
                        ),
                        "w",
                        encoding="utf-8",
                    ) as file_to_save:
                        file_to_save.write(
                            file_string
                        )

    async def run_test(self) -> None:
        """Asynchronous method to run the tes
        """
        try:
            await asyncio.gather(
                self.send_test_files(),
                self.pv_file_inspector.run_pv_file_inspector(),
            )
        except RuntimeError as error:
            logging.getLogger().info(msg=str(error))

    @abstractmethod
    def calc_results(self) -> None:
        """Method to cal the results and save reports for the test
        """

    def clean_directories(self) -> None:
        """Method to clean up log and uml file store directories
        """
        clean_directories(
            [
                self.harness_config.uml_file_store,
                self.harness_config.log_file_store
            ]
        )
        response_tuple = send_get_request(
            url=self.harness_config.pv_clean_folders_url,
            max_retries=self.harness_config.requests_max_retries,
            timeout=self.harness_config.requests_timeout
        )
        if not response_tuple[0]:
            logging.getLogger().warning(
                "There was an error with the request to clean up PV folders"
                " for next test with request response: %s",
                response_tuple[2].text
            )


class FunctionalTest(Test):
    """Child class of :class:`Test` for functional tests.

    :param test_file_generators: Dictionary containing generated tests for
    each job definition
    :type test_file_generators: `dict`[ `str`, `dict`[ `str`, `tuple`[
    :class:`Generator`[ `tuple`[`list`[`dict`], `list`[`str`],
    :class:`plt`.`Figure`  |  `None`, `str`], `Any`, `None`, ], `bool`, ], ], ]
    :param harness_config: Main config for the test harness, defaults to `None`
    :type harness_config: :class:`HarnessConfig` | `None`, optional
    :param test_config: Config for the specific test, defaults to `None`
    :type test_config: :class:`TestConfig` | `None`, optional
    :param test_output_directory: The path of the test output directory where
    files relating to the test results are stored, defaults to `None`
    :type test_output_directory: `str` | `None`, optional
    """

    def __init__(
        self,
        test_file_generators: dict[
            str,
            dict[
                str,
                tuple[
                    Generator[
                        tuple[list[dict], list[str], plt.Figure | None, str],
                        Any,
                        None,
                    ],
                    bool,
                ],
            ],
        ],
        harness_config: HarnessConfig | None = None,
        test_config: TestConfig | None = None,
        test_output_directory: str | None = None,
    ) -> None:
        super().__init__(
            test_file_generators,
            harness_config,
            test_config,
            test_output_directory=test_output_directory,
            save_files=True
        )

    def get_jobs_to_send(self) -> list[tuple[Job, dict[str, str | bool]]]:
        """Method to get all the jobs to send

        :return: Returns a list of jobs sequences and their info
        :rtype: `list`[`tuple`[:class:`Job`, `dict`[`str`, `str` | `bool`]]]
        """
        return self.job_templates

    def set_test_rate(self) -> None:
        """Method to set the test interval at the default value of 0.1 seconds
        """
        self.interval = 0.1
        self.shard = False

    def calc_results(self) -> None:
        """Method to calc the results after the test and save reports
        """
        # load verifier logs and concatenate string
        log_string = self.pv_file_inspector.load_log_files_and_concat_strings()
        # get the validity dataframe
        validity_df = self.results.create_validity_dataframe()
        # analyse the logs and get report files
        report_files_mapping = create_report_files(
            log_string=log_string,
            validity_df=validity_df,
            test_name="Results"
        )
        report_files_mapping["Results_Aggregated.html"] = self.make_figs(
            report_files_mapping["Results.csv"]
        )
        deliver_test_report_files(
            report_files_mapping=report_files_mapping,
            output_directory=self.test_output_directory,
        )

    @staticmethod
    def make_figs(results_df: pd.DataFrame) -> Figure:
        """Method to generate a grouped bar chart from the test output
        dataframe

        :param results_df: Dataframe with columns:
        * "Category" - The category of sequence
        * "TestResult" - The result of the test
        * "JobId" - the identifier of the job
        :type results_df: :class:`pd`.`DataFrame`
        :return: Returns the plotly :class:`Figure` object
        :rtype: :class:`Figure`
        """
        results_df = results_df.reset_index()
        aggregated_df = results_df[
            ["Category", "TestResult", "JobId"]
        ].groupby(
            [
                "Category", "TestResult"
            ]
        ).agg("count").reset_index()
        aggregated_df.columns = ["Category", "TestResult", "Count"]
        fig = px.bar(
            aggregated_df,
            x="TestResult",
            y="Count",
            color="Category"
        )
        fig.add_hline(len(results_df))
        return fig


class PerformanceTest(Test):
    """Class to hold and run a performance test. Sub class of :class:`Test`

    :param test_file_generators: Dictionary containing generated tests for
    each job definition
    :type test_file_generators: `dict`[ `str`, `dict`[ `str`, `tuple`[
    :class:`Generator`[ `tuple`[`list`[`dict`], `list`[`str`],
    :class:`plt`.`Figure`  |  `None`, `str`], `Any`, `None`, ], `bool`, ], ], ]
    :param harness_config: Main config for the test harness, defaults to `None`
    :type harness_config: :class:`HarnessConfig` | `None`, optional
    :param test_config: Config for the specific test, defaults to `None`
    :type test_config: :class:`TestConfig` | `None`, optional
    :param test_output_directory: The path of the test output directory where
    files relating to the test results are stored, defaults to `None`
    :type test_output_directory: `str` | `None`, optional
    """
    def __init__(
        self,
        test_file_generators: dict[
            str,
            dict[
                str,
                tuple[
                    Generator[
                        tuple[list[dict], list[str], Any | None, str],
                        Any,
                        None,
                    ],
                    bool,
                ],
            ],
        ],
        harness_config: HarnessConfig | None = None,
        test_config: TestConfig | None = None,
        test_output_directory: str | None = None,
    ) -> None:
        """Constructor method
        """
        super().__init__(
            test_file_generators,
            harness_config,
            test_config,
            test_output_directory=test_output_directory,
            save_files=False,
        )

    def get_jobs_to_send(self) -> list[tuple[Job, dict[str, str | bool]]]:
        """Method to create the jobs to send

        :return: Returns the jobs to send
        :rtype: `list`[`tuple`[:class:`Job`, `dict`[`str`, `str` | `bool`]]]
        """
        jobs_to_send = choices(
            self.job_templates,
            k=self.test_config.performance_options["total_jobs"],
        )
        return jobs_to_send

    def set_test_rate(self) -> None:
        """Method to set the test interval at the default value of 0.1 seconds
        and shard attribute
        """
        self.interval = (
            1 / self.test_config.performance_options["num_files_per_sec"]
        )
        self.shard = self.test_config.performance_options["shard"]

    def calc_results(self) -> None:
        """Method to calc the results after the test and save reports
        """
        self.pv_file_inspector.calc_test_boundaries()
        self.pv_file_inspector.normalise_coords()
        num_jobs = 0
        num_events = 0
        for chunk in self.chunked_jobs_to_send:
            for job_data in chunk:
                num_jobs += 1
                num_events += len(job_data[0].events)
        average_num_jobs_per_sec = (
            num_jobs / self.pv_file_inspector.test_boundaries[2]
        )
        average_num_events_per_sec = (
            num_events / self.pv_file_inspector.test_boundaries[2]
        )
        df_basic_results = pd.DataFrame.from_dict(
            {
                "num_jobs": num_jobs,
                "num_events": num_events,
                "average_jobs_per_sec": average_num_jobs_per_sec,
                "average_events_per_sec": average_num_events_per_sec,
                "reception_end_time": (
                    self.pv_file_inspector.test_boundaries[3]
                ),
                "verifier_end_time": self.pv_file_inspector.test_boundaries[4],
            },
            orient="index",
        )
        df_basic_results.index.name = "Data Field"
        df_pv_file_results = pd.DataFrame(
            [
                (
                    time,
                    self.test_config.performance_options["num_files_per_sec"],
                    "Files Sent/s",
                )
                for time in range(
                    len(self.results.responses)
                    // self.test_config.performance_options[
                        "num_files_per_sec"
                    ]
                )
            ]
            + [
                coord + ("AER Incoming\nFiles",)
                for coord in self.pv_file_inspector.coords["aer"]
            ]
            + [
                (time, 0, "Files Sent/s")
                for time in range(
                    len(self.results.responses)
                    // self.test_config.performance_options[
                        "num_files_per_sec"
                    ],
                    self.pv_file_inspector.test_boundaries[2],
                )
            ]
            + [
                coord + ("Verifier Files",)
                for coord in self.pv_file_inspector.coords["ver"]
            ],
            columns=["Time (s)", "Number", "Metric"],
        )
        df_pv_file_results = df_pv_file_results.groupby(
            ["Time (s)", "Metric"]
        ).mean().reset_index()
        # add verifier files pers second
        verifier_files_per_second = (
            df_pv_file_results.loc[
                df_pv_file_results["Metric"] == "Verifier Files"
            ].sort_values("Time (s)").reset_index(
                drop=True
            )
        )
        verifier_files_per_second["Number"] = verifier_files_per_second[
            "Number"
        ].diff()
        verifier_files_per_second.loc[0, "Number"] = 0
        verifier_files_per_second["Metric"] = "Verifier Files/s"
        df_pv_file_results = pd.concat(
            [df_pv_file_results, verifier_files_per_second],
            ignore_index=True
        )
        # filter out results that are greater than the calculated test end time
        df_pv_file_results = df_pv_file_results[
            (
                df_pv_file_results["Time (s)"]
            ) <= self.pv_file_inspector.test_boundaries[2]
        ]
        df_pv_file_results.index.name = "Index"
        # make figures
        figure = self.make_figs(df_pv_file_results)
        deliver_test_report_files(
            {
                "Basic_Stats.csv": df_basic_results,
                "PV_File_IO.csv": df_pv_file_results,
                "PV_File_IO.html": figure,
            },
            output_directory=self.test_output_directory,
        )

    @staticmethod
    def make_figs(df_pv_file_results: pd.DataFrame) -> Figure:
        """Method to generate a grouped bar chart from the test output
        dataframe

        :param df_pv_file_results: Dataframe with columns:
        * "Time (s)" - the simulation time of the entry - integer
        * "Number" - the value of the given metric - float
        * "Metric" - the identifier of the metric
        :type df_pv_file_results: :class:`pd`.`DataFrame`
        :return: Returns the plotly :class:`Figure` object
        :rtype: :class:`Figure`
        """
        # first figure
        fig = px.bar(
            df_pv_file_results,
            x="Time (s)",
            y="Number",
            color="Metric",
            barmode="group",
        )
        fig.update_xaxes(dtick=1)
        return fig
