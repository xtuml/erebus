# pylint: disable=R0902
# pylint: disable=R0913
"""Methods and classes relating to tests
"""
from typing import Generator, Any, Type
from abc import ABC, abstractmethod
from random import choice, choices
import os
import asyncio
import logging
import math
from queue import Queue, Empty
import json
from threading import Thread

import matplotlib.pyplot as plt
import flatdict
import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure
from requests import ReadTimeout
import numpy as np

from test_harness.config.config import HarnessConfig, TestConfig
from test_harness.utils import clean_directories
from test_harness.protocol_verifier.calc_pv_finish import PVFileInspector
from test_harness.protocol_verifier.simulator_data import (
    Job,
    generate_events_from_template_jobs,
    generate_job_batch_events,
    generate_single_events,
    job_sequencer,
    send_list_dict_as_json_wrap_url
)
from test_harness.simulator.simulator import (
    SimDatum, Simulator, ResultsHandler
)
from test_harness.simulator.simulator_profile import Profile
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


class PVResultsHandler(ResultsHandler):
    """Subclass of :class:`ResultsHandler` to handle saving of files and data
    from a PV test run. Uses a context manager and daemon thread to save
    results in the background whilst a test is running.


    :param results_holder: Instance used to hold the data relating to the sent
    jobs/events
    :type results_holder: :class:`Results`
    :param test_output_directory: The path of the output directory of the test
    :type test_output_directory: `str`
    :param save_files: Boolean indicating whether the files should be saved or
    not, defaults to `False`
    :type save_files: `bool`, optional
    """
    def __init__(
        self,
        results_holder: Results,
        test_output_directory: str,
        save_files: bool = False
    ) -> None:
        """Constructor method
        """
        self.queue = Queue()
        self.results_holder = results_holder
        self.test_output_directory = test_output_directory
        self.daemon_thread = Thread(target=self.queue_handler, daemon=True)
        self.daemon_not_done = True
        self.save_files = save_files

    def __enter__(self) -> None:
        """Entry to the context manager
        """
        self.daemon_thread.start()
        return self

    def __exit__(
        self,
        exc_type: Type[Exception] | None,
        exc_value: Exception | None,
        *args
    ) -> None:
        """Exit from context manager

        :param exc_type: The type of the exception
        :type exc_type: :class:`Type` | `None`
        :param exc_value: The value of the excpetion
        :type exc_value: `str` | `None`
        :param traceback: The traceback fo the error
        :type traceback: `str` | `None`
        :raises RuntimeError: Raises a :class:`RuntimeError`
        if an error occurred in the main thread
        """
        if exc_type is not None:
            logging.getLogger().error(
                "The folowing type of error occurred %s with value %s",
                exc_type,
                exc_value
            )
            raise exc_value
        while self.queue.qsize() != 0:
            continue
        self.daemon_not_done = False
        self.daemon_thread.join()

    def handle_result(
        self,
        result: tuple[
            list[dict[str, Any]], str, str, dict[str, str | None], str
        ] | None
    ) -> None:
        """Method to handle the result from a simulation iteration

        :param result: The result from the PV simulation iteration - could be
        `None` or a tuple of:
        * the event dicts in a list
        * a string representing the filename used to send the data
        * a string representing the job id
        * a dict representing the job info
        * a string representing the response from the request
        :type result: `tuple`[ `list`[`dict`[`str`, `Any`]], `str`, `str`,
        `dict`[`str`, `str`  |  `None`], `str` ] | `None`
        """
        self.queue.put(result)

    def queue_handler(self) -> None:
        """Method to handle the queue as it is added to
        """
        while self.daemon_not_done:
            try:
                item = self.queue.get(timeout=1)
                self.handle_item_from_queue(item)
            except Empty:
                continue

    def handle_item_from_queue(
        self,
        item: tuple[
            list[dict[str, Any]], str, str, dict[str, str | None], str
        ] | None
    ) -> None:
        """Method to handle saving the data when an item is take from the queue

        :param item: PV iteration data taken from the queue
        :type item: `tuple`[ `list`[`dict`[`str`, `Any`]], `str`, `str`,
        `dict`[`str`, `str`  |  `None`], `str` ] | `None`
        """
        if item is None:
            return
        self.results_holder.update_test_files_info(
            job_ids=[item[2]],
            jobs_info=[item[3]],
            file_names=[item[1]]
        )
        self.results_holder.update_responses([item[4]])
        if self.save_files:
            output_file_path = os.path.join(
                self.test_output_directory,
                item[1]
            )
            with open(output_file_path, 'w', encoding="utf-8") as file:
                json.dump(item[0], file)


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
        test_profile: Profile | None = None,
        save_files: bool = True,
    ) -> None:
        """Constructor method"""
        self.test_files = test_file_generators
        self.test_output_directory = test_output_directory
        self.harness_config = (
            harness_config if harness_config else HarnessConfig()
        )
        self.test_config = test_config if test_config else TestConfig()
        self.test_profile = test_profile
        self.simulator: Simulator | None = None
        self.sim_data_generator: Generator[SimDatum, Any, None] | None = None
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
        self.job_templates: list[Job] = []
        self.results = Results()
        self.pv_file_inspector = PVFileInspector(harness_config)
        self.total_number_of_events: int
        self.delay_times: list[float]
        self.jobs_to_send: list[Job]
        self.set_test_rate()
        # prepare the test given inputs
        self.prepare_test()

    def _make_job_templates(self) -> None:
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
                    job_info = {
                        "SequenceName": job_name_sol_type[0],
                        "Category": job_name_sol_type[1],
                        "Validity": flattened_test_files[
                            flattened_key
                        ][1],
                    }
                    job = Job(job_info=job_info)
                    job.parse_input_jobfile(job_sequence)
                    self.job_templates.append(job)
                except StopIteration:
                    flattened_keys.remove(flattened_key)
            except IndexError:
                break

    def prepare_test(self) -> None:
        """Method to prepare the test data
        """
        self._make_job_templates()
        if self.test_profile is not None:
            self.test_profile.transform_raw_profile()
        self._set_jobs_to_send()
        self._set_total_number_of_events()
        self._set_delay_profile()
        self.sim_data_generator = self._get_sim_data(
            self.jobs_to_send
        )

    def _set_total_number_of_events(self) -> None:
        """Method to calculate and set the total number of events of the
        simulation
        """
        self.total_number_of_events = sum(
            len(job.events)
            for job in self.jobs_to_send
        )

    def _set_delay_profile(self) -> None:
        """Method to set the delay profile for the test. If no test profile
        has been input a uniform profile is created using a rate of one
        divided by the `interval` attribute
        """
        if self.test_profile is None:
            num_per_sec = min(
                self.total_number_of_events, round(1 / self.interval)
            )
            self.test_profile = Profile(
                pd.DataFrame([
                    [sim_time, num_per_sec] for sim_time in range(
                        math.ceil(
                            (self.total_number_of_events + 1) / num_per_sec
                        ) + 1
                    )
                ])
            )
            self.test_profile.transform_raw_profile()
        self.delay_times = self.test_profile.delay_times[
            : self.total_number_of_events
        ]

    def _get_min_interval(self) -> float | int:
        return np.min(np.diff(self.delay_times))

    @abstractmethod
    def _get_sim_data(
        self,
        jobs_to_send: list[Job]
    ) -> Generator[SimDatum, Any, None]:
        """Abstract method to get the sim data for the test

        :param jobs_to_send: A list of the template jobs to send
        :type jobs_to_send: `list`[:class:`Job`]
        :yield: Yields :class:`SimDatum` containing the relevant simulation
        information for each event, respectively
        :rtype: :class:`Generator`[:class:`SimDatum`, `Any`, `None`]
        """
        yield from generate_events_from_template_jobs(
            template_jobs=jobs_to_send,
            sequence_generator=job_sequencer,
            generator_function=generate_job_batch_events,
            sequencer_kwargs={
                "min_interval_between_job_events": self._get_min_interval()
            }
        )

    def _set_jobs_to_send(self):
        self.jobs_to_send = self._get_jobs_to_send()

    @abstractmethod
    def _get_jobs_to_send(self) -> list[Job]:
        """Method to get all the jobs to send

        :return: Returns a list of jobs sequences and their info
        :rtype: `list`[:class:`Job`]
        """

    @abstractmethod
    def set_test_rate(self) -> None:
        """Method to set the test interval and shard attribute
        """
        self.interval = 0.1
        self.shard = False

    async def send_test_files(
        self,
        results_handler: PVResultsHandler
    ) -> None:
        """Asynchronous method to send test files to the PV

        :param results_handler: A list of the template jobs to send
        :type results_handler: `list`[:class:`Job`]
        """
        self.simulator = Simulator(
            delays=self.delay_times,
            simulation_data=self.sim_data_generator,
            action_func=send_list_dict_as_json_wrap_url(
                url=self.harness_config.pv_send_url
            ),
            results_handler=results_handler
        )
        await self.simulator.simulate()

    async def run_test(self) -> None:
        """Asynchronous method to run the test
        """
        with PVResultsHandler(
            results_holder=self.results,
            test_output_directory=self.test_output_directory,
            save_files=self.save_files
        ) as pv_results_handler:
            try:
                await asyncio.gather(
                    self.send_test_files(results_handler=pv_results_handler),
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
                self.harness_config.log_file_store,
                self.harness_config.profile_store
            ]
        )
        try:
            response_tuple = send_get_request(
                url=self.harness_config.pv_clean_folders_url,
                max_retries=self.harness_config.requests_max_retries,
                timeout=(
                    self.harness_config.requests_timeout,
                    self.harness_config.pv_clean_folders_read_timeout
                )
            )
            if not response_tuple[0]:
                logging.getLogger().warning(
                    "There was an error with the request to clean up PV"
                    "folders"
                    " for next test with request response: %s",
                    response_tuple[2].text
                )
        except ReadTimeout:
            logging.getLogger().warning(
                "The read time out limit of %s was reached. Not all PV folders"
                "will be empty. It is suggested the harness config "
                "'pv_clean_folder_read_timeout' is increased."
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
        test_profile: None = None
    ) -> None:
        super().__init__(
            test_file_generators,
            harness_config,
            test_config,
            test_output_directory=test_output_directory,
            save_files=True,
            test_profile=test_profile
        )

    def _get_sim_data(
        self,
        jobs_to_send: list[Job]
    ) -> Generator[SimDatum, Any, None]:
        """Method to get the sim data for the test

        :param jobs_to_send: A list of the template jobs to send
        :type jobs_to_send: `list`[:class:`Job`]
        :yield: Yields :class:`SimDatum` containing the relevant simulation
        information for each event, respectively
        :rtype: :class:`Generator`[:class:`SimDatum`, `Any`, `None`]
        """
        yield from super()._get_sim_data(jobs_to_send)

    def _get_jobs_to_send(self) -> list[Job]:
        """Method to get all the jobs to send

        :return: Returns a list of jobs sequences and their info
        :rtype: `list`[:class:`Job`]
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
        test_profile: Profile | None = None
    ) -> None:
        """Constructor method
        """
        super().__init__(
            test_file_generators,
            harness_config,
            test_config,
            test_output_directory=test_output_directory,
            save_files=False,
            test_profile=test_profile
        )

    def _get_sim_data(
        self,
        jobs_to_send: list[Job]
    ) -> Generator[SimDatum, Any, None]:
        """Method to get the sim data for the test

        :param jobs_to_send: A list of the template jobs to send
        :type jobs_to_send: `list`[:class:`Job`]
        :yield: Yields :class:`SimDatum` containing the relevant simulation
        information for each event, respectively
        :rtype: :class:`Generator`[:class:`SimDatum`, `Any`, `None`]
        """
        if self.shard:
            event_generator = generate_single_events
        else:
            event_generator = generate_job_batch_events
        yield from generate_events_from_template_jobs(
            template_jobs=jobs_to_send,
            sequence_generator=job_sequencer,
            generator_function=event_generator,
            sequencer_kwargs={
                "min_interval_between_job_events": self._get_min_interval()
            }
        )

    def _get_jobs_to_send(self) -> list[Job]:
        """Method to create the jobs to send

        :return: Returns the jobs to send
        :rtype: `list`[`tuple`[:class:`Job`, `dict`[`str`, `str` | `bool`]]]
        """
        if self.test_profile:
            jobs_to_send = []
            num_events = 0
            max_number_of_events = len(self.test_profile.delay_times)
            while True:
                job = choice(self.job_templates)
                num_events += len(job.events)
                if num_events > max_number_of_events:
                    break
                jobs_to_send.append(job)
        else:
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
        if any(
            len(domain_coords) < 2
            for domain_coords in self.pv_file_inspector.coords.values()
        ):
            logging.getLogger().warning(
                "Cannot calculate results as not enough data points were "
                "taken. The read timeout of io folder calculations may need "
                "to be increased"
            )
            return
        self.pv_file_inspector.calc_test_boundaries()
        self.pv_file_inspector.normalise_coords()
        num_jobs = len(self.jobs_to_send)
        num_events = self.total_number_of_events
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
