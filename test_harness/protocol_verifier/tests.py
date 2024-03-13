# pylint: disable=R0902
# pylint: disable=R0913
# pylint: disable=W0221
# pylint: disable=W0246
# pylint: disable=W0613
# pylint: disable=C0302
"""Methods and classes relating to tests
"""
from typing import Generator, Any, Callable, Iterable, Iterator, Awaitable
from abc import ABC, abstractmethod
from random import choice, choices
import os
import shutil
import asyncio
import logging
import math
from datetime import datetime
import glob
from multiprocessing import Queue, Event
import queue
from contextlib import AsyncExitStack

import matplotlib.pyplot as plt
import flatdict
import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure
import requests
from tqdm import tqdm

from test_harness.config.config import HarnessConfig, TestConfig
from test_harness.utils import (
    clean_directories, ProcessGeneratorManager, RollOverChoice,
    choose_from_front_of_list
)
from test_harness.protocol_verifier.calc_pv_finish import (
    PVFileInspector,
    handle_domain_log_file_reception_and_save,
)
from test_harness.protocol_verifier.simulator_data import (
    Job,
    generate_events_from_template_jobs,
    generate_job_batch_events,
    generate_single_events,
    job_sequencer,
)
from test_harness.simulator.simulator import (
    SimDatum,
    Simulator,
    MultiProcessDateSync
)
from test_harness.simulator.simulator_profile import (
    Profile,
    InterpolatedProfile
)
from test_harness.message_buses.message_buses import (
    get_producer_context
)
from test_harness.reporting.report_delivery import deliver_test_report_files
from test_harness.reporting import create_report_files
from test_harness.reporting.report_results import (
    generate_performance_test_reports,
)
from test_harness.requests import send_get_request
from test_harness.async_management import (
    AsyncMPManager, AsyncKillManager, AsyncKillException
)
from .pvresults import PVResults
from .pvresultshandler import (
    PVResultsHandler, PVResultsAdder, PVKafkaMetricsHandler
)
from .pvperformanceresults import PVPerformanceResults
from .kafka_metrics import PVKafkaMetricsRetriever
from .pvresultsdataframe import PVResultsDataFrame
from .pvfunctionalresults import PVFunctionalResults
from .types import (
    TemplateOptions,
    MetricsRetriverKwargsPairAndHandlerKwargsPair,
    MetricsRetrieverKwargsPair,
    ResultsHandlerKwargsPair
)
from .send_events import (
    get_message_bus_kwargs, get_producer_kwargs, PVMessageSender
)


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
    :param pbar: A progress bar to track the progress of the test, defaults to
    `None`
    :type pbar: :class:`tqdm` | `None`, optional
    :param save_log_files: Boolean indicating whether to save log files -
    will only save if a test output directory has been given, defaults to
    `True`
    :type save_log_files: `bool`, optional
    :param async_metrics_retrievers_and_handlers: A list of
    :class:`MetricsRetriverKwargsPairAndHandlerKwargsPair` objects to
    asynchronously retrieve metrics, defaults to `None`
    :type async_metrics_retrievers_and_handlers: `list`[
    :class:`MetricsRetriverKwargsPairAndHandlerKwargsPair`] | `None`, optional
    :param test_graceful_kill_functions: A list of functions to run to
    gracefully kill the test, defaults to `None`
    :type test_graceful_kill_functions: `list`[ `Callable`[ `...`,
    `Awaitable`[ `None`]]] | `None`, optional
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
        *,
        harness_config: HarnessConfig | None = None,
        test_config: TestConfig | None = None,
        test_output_directory: str | None = None,
        test_profile: Profile | None = None,
        save_files: bool = True,
        pbar: tqdm | None = None,
        save_log_files: bool = True,
        async_metrics_retrievers_and_handlers: list[
            MetricsRetriverKwargsPairAndHandlerKwargsPair
        ] | None = None,
        test_graceful_kill_functions: list[
            Callable[..., Awaitable[None]]
        ] | None = None

    ) -> None:
        """Constructor method"""
        self.test_files = test_file_generators
        self.test_output_directory = test_output_directory
        self.harness_config = (
            harness_config if harness_config else HarnessConfig()
        )
        self.test_config = test_config if test_config else TestConfig()
        self._check_config_test_finish_values()
        self.test_profile = test_profile
        self.simulator: Simulator | None = None
        self.sim_data_generator: Generator[SimDatum, Any, None] | None = None
        if save_files and not test_output_directory:
            logging.getLogger().warning(
                "Save files has been set but there is not output directory"
                " for tests"
            )
        self.save_files = (
            save_files if save_files and test_output_directory else False
        )
        # set up requires attributes
        self.job_templates: list[Job] = []
        self.results = self.set_results_holder()
        self.pv_file_inspector = PVFileInspector(
            harness_config,
            test_config=self.test_config,
            save_log_files=save_log_files,
        )
        self.total_number_of_events: int
        self.delay_times: InterpolatedProfile
        self.jobs_to_send: list[Job]
        self.set_test_rate()
        # prepare the test given inputs
        self.prepare_test()
        self.time_start: datetime | None = None
        self.time_end: datetime | None = None
        self.pbar = pbar
        self.async_metrics_retrievers_and_handlers = (
            async_metrics_retrievers_and_handlers
            if async_metrics_retrievers_and_handlers else []
        )
        self.graceful_kill_functions = [self.timeout_test] + (
            test_graceful_kill_functions
            if test_graceful_kill_functions else []
        )
        if self.test_config.num_workers >= 1:
            kill_event = Event()
        else:
            kill_event = asyncio.Event()
        self.kill_manager = AsyncKillManager(kill_event)

    def _check_config_test_finish_values(self):
        """Method to check the configs for the test"""
        for harness_config_attr, test_config_finish_val_field in zip(
            [
                "pv_test_timeout",
                "pv_finish_interval",
                "log_calc_interval_time"
            ],
            ["timeout", "finish_interval", "metric_get_interval"],
        ):
            if test_config_finish_val_field not in (
                self.test_config.test_finish
            ):
                self.test_config.test_finish[test_config_finish_val_field] = (
                    getattr(self.harness_config, harness_config_attr)
                )

    @abstractmethod
    def set_results_holder(self) -> (
        PVResults | PVFunctionalResults | PVPerformanceResults
    ):
        """Abstract metho to return the results holder

        :return: Returns a :class:`PVResults` object
        :rtype: :class:`PVResults` | :class:`PVPerformanceResults`
        """
        return PVFunctionalResults()

    def _make_job_templates(self) -> None:
        """Method to make the template jobs from the generated tests files"""
        flattened_test_files = flatdict.FlatDict(self.test_files)
        flattened_keys: list[str] = flattened_test_files.keys()
        counter = 0
        # loop until the max number of different sequences have been templated
        # or until all test sequences have been used up
        if self.test_config.performance_options["round_robin"]:
            chooser = choose_from_front_of_list
        else:
            chooser = choice
        while (
            counter < (self.test_config.max_different_sequences)
            and flattened_keys
        ):
            counter += 1
            try:
                flattened_key = chooser(flattened_keys)
                try:
                    job_sequence = next(
                        flattened_test_files[flattened_key][0]
                    )[0]
                    job_name_sol_type = flattened_key.split(":")
                    job_info = {
                        "SequenceName": job_name_sol_type[0],
                        "Category": job_name_sol_type[1],
                        "Validity": flattened_test_files[flattened_key][1],
                    }
                    job_options = {}
                    if len(flattened_test_files[flattened_key]) == 3:
                        job_options = flattened_test_files[
                            flattened_key
                        ][2]
                    job = Job(
                        job_info=job_info,
                        job_options=TemplateOptions(**job_options)
                    )

                    job.parse_input_jobfile(job_sequence)
                    self.job_templates.append(job)
                except StopIteration:
                    flattened_keys.remove(flattened_key)
            except IndexError:
                break

    def prepare_test(self) -> None:
        """Method to prepare the test data"""
        self._make_job_templates()
        if self.test_profile is not None:
            self.test_profile.transform_raw_profile()
        self._set_jobs_to_send()
        self._set_total_number_of_events()
        self._set_delay_profile()
        self.sim_data_generator = self._get_sim_data(self.jobs_to_send)

    def _set_total_number_of_events(self) -> None:
        """Method to calculate and set the total number of events of the
        simulation
        """
        self.total_number_of_events = sum(
            len(job.events) for job in self.jobs_to_send
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
                pd.DataFrame(
                    [
                        [sim_time, num_per_sec]
                        for sim_time in range(
                            math.ceil(
                                (self.total_number_of_events + 1) / num_per_sec
                            )
                            + 1
                        )
                    ]
                )
            )
            self.test_profile.transform_raw_profile()
        self.delay_times = self.test_profile.delay_times[
            : self.total_number_of_events
        ]

    def _get_min_interval(self) -> float | int:
        """Method to get the minimum interval between events
        """
        return 1 / self.delay_times.get_max_num_per_sec()

    @abstractmethod
    def _get_sim_data(
        self, jobs_to_send: list[Job]
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
            },
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
        """Method to set the test interval and shard attribute"""
        self.interval = 0.1
        self.shard = False

    async def send_test_files(
        self,
        results_handler: PVResultsHandler,
    ) -> None:
        """Asynchronous method to send test files to the PV

        :param results_handler: A list of the template jobs to send
        :type results_handler: `list`[:class:`Job`]
        """
        if isinstance(self.pbar, tqdm):
            self.pbar.total = self.total_number_of_events
        if self.test_config.num_workers == 0:
            self.time_start = datetime.now()
            self.results.time_start = self.time_start
            await self.kill_manager(self.send_test_files_with_simulator(
                results_handler=results_handler,
                sim_data_iterator=self.sim_data_generator,
                delay_times=self.delay_times,
                harness_config=self.harness_config,
                pbar=self.pbar,
                kill_manager=self.kill_manager,
            ))
            return
        await self._async_multi_process_send_test_files(results_handler)

    async def _async_multi_process_send_test_files(
        self,
        results_handler: PVResultsAdder,
    ) -> None:
        """Method to send test files to the PV using multiple processes

        :param results_handler: The results handler to add results to
        :type results_handler: :class:`PVResultsAdder`
        """
        with ProcessGeneratorManager(
            generator=self.sim_data_generator
        ) as process_generator_manager:
            time_sync = MultiProcessDateSync(
                num_processes=self.test_config.num_workers
            )
            async_mp_manager = AsyncMPManager()
            for i in range(self.test_config.num_workers):
                async_mp_manager.add_process(
                    target=self._sync_send_test_files,
                    args=(
                        results_handler,
                        process_generator_manager.create_iterator(),
                        self.delay_times[i::self.test_config.num_workers],
                        self.harness_config,
                        self.pbar,
                        time_sync,
                        self.kill_manager,
                    ),
                    daemon=True,
                )
            self.time_start = datetime.now()
            self.results.time_start = self.time_start
            await async_mp_manager.run_processes()
            logging.getLogger().info(
                "All processes have finished"
            )
        self.pbar.update(0)

    @staticmethod
    def _sync_send_test_files(
        results_handler: PVResultsHandler,
        sim_data_iterator: Iterator[SimDatum],
        delay_times: Iterable[float],
        harness_config: HarnessConfig,
        pbar: tqdm,
        time_sync: MultiProcessDateSync | None = None,
        kill_manager: AsyncKillManager | None = None,
    ) -> None:
        asyncio.run(Test.send_test_files_with_simulator(
            results_handler=results_handler,
            sim_data_iterator=sim_data_iterator,
            delay_times=delay_times,
            harness_config=harness_config,
            pbar=pbar,
            time_sync=time_sync,
            kill_manager=kill_manager,
        ))

    @staticmethod
    async def send_test_files_with_simulator(
        results_handler: PVResultsAdder,
        sim_data_iterator: Iterator[SimDatum],
        delay_times: Iterable[float],
        harness_config: HarnessConfig,
        pbar: tqdm,
        time_sync: MultiProcessDateSync | None = None,
        kill_manager: AsyncKillManager | None = None,
    ) -> None:
        """Asynchronous method to send test data

        :param results_handler: The results handler to add results to
        :type results_handler: :class:`PVResultsAdder`
        :param sim_data_iterator: Iterator of simulation data
        :type sim_data_iterator: :class:`Iterator`[:class:`SimDatum`]
        :param delay_times: Iterable of delay times
        :type delay_times: :class:`Iterable`[:class:`float`]
        :param harness_config: The harness config
        :type harness_config: :class:`HarnessConfig`
        :param pbar: A progress bar to track the progress of the test
        :type pbar: :class:`tqdm`
        :param time_sync: A time sync object for multiple processes,
        defaults to `None`
        :type time_sync: :class:`MultiProcessDateSync` | `None`, optional
        """
        message_bus_kwargs = get_message_bus_kwargs(
            harness_config=harness_config,
        )
        producer_kwargs = get_producer_kwargs(
            harness_config=harness_config,
        )
        async with get_producer_context(
            message_bus=harness_config.message_bus_protocol,
            message_bus_kwargs=message_bus_kwargs,
            producer_kwargs=producer_kwargs
        ) as producer:
            message_sender = PVMessageSender(
                message_producer=producer,
                message_bus=harness_config.message_bus_protocol
            )
            simulator = Simulator(
                delays=delay_times,
                simulation_data=sim_data_iterator,
                action_func=message_sender.send,
                results_handler=results_handler,
                pbar=pbar,
                time_sync=time_sync,
                kill_manager=kill_manager,
            )
            await simulator.simulate()

    async def timeout_test(self) -> None:
        """Method to timeout the test after a certain amount of time if all the
        events have been sent

        :raises RuntimeError: Raises a :class:`RuntimeError` when the test has
        timed out
        """
        await asyncio.sleep(
            self.test_config.test_finish["timeout"] + self.delay_times[-1]
        )
        logging.getLogger().info(
            "Protocol Verifier failed to finish within the test timeout of "
            f"{self.harness_config.pv_test_timeout} seconds.\nResults will "
            "be calculated at this point"
        )

        raise AsyncKillException(
            "Protocol Verifier failed to finish within the test timeout of "
            f"{self.test_config.test_finish['timeout']} seconds.\nResults will"
            " be calculated at this point"
        )

    async def stop_test(self) -> None:
        """Method to stop the test after a :class: `RuntimeError` has been
        raised in one of the graceful kill Coroutines

        :raises RuntimeError: Raises a :class:`RuntimeError` when the test has
        been cancelled
        """
        await asyncio.gather(
            *[func() for func in self.graceful_kill_functions]

        )

    async def run_test(self) -> None:
        """Asynchronous method to run the test"""
        with PVResultsHandler(
            results_holder=self.results,
            test_output_directory=self.test_output_directory,
            save_files=self.save_files,
            queue_type=queue.Queue if self.test_config.num_workers <= 1 else (
                Queue
            ),
        ) as pv_results_handler:
            async with AsyncExitStack() as metrics_stack:
                metrics_retrievers_awaitables = []
                for (
                    async_metrics_retriever_kwargs_pair,
                    async_metrics_handler,
                ) in self.async_metrics_retrievers_and_handlers:
                    metrics_handler = metrics_stack.enter_context(
                        async_metrics_handler.handler_class(
                            results_holder=self.results
                        )
                    )
                    metrics_retrievers = (
                        await metrics_stack.enter_async_context(
                            async_metrics_retriever_kwargs_pair.
                            metric_retriever_class(
                                **async_metrics_retriever_kwargs_pair.kwargs
                            )
                        )
                    )
                    metrics_retrievers_awaitables.append(
                        metrics_retrievers.async_continuous_retrieve_metrics(
                            metrics_handler,
                            **async_metrics_handler.kwargs

                        )
                    )
                try:
                    await asyncio.gather(
                        self.send_test_files(
                            pv_results_handler
                        ),
                        self.kill_manager(
                            self.pv_file_inspector.run_pv_file_inspector()
                        ),
                        self.kill_manager(self.stop_test()),
                        *[
                            self.kill_manager(metrics_retrievers_awaitable)
                            for metrics_retrievers_awaitable
                            in metrics_retrievers_awaitables
                        ],
                    )
                except RuntimeError as error:
                    logging.getLogger().info(msg=str(error))
                self.time_end = datetime.now()
                logging.getLogger().info(
                    "Sending test files has completed"
                )

    @abstractmethod
    def calc_results(self) -> None:
        """Method to cal the results and save reports for the test"""

    def get_all_remaining_log_files(self) -> None:
        """Method to get all remaining log files from the PV"""
        # get all other log files
        try:
            for location, prefix in zip(
                ["RECEPTION"] + ["VERIFIER"] * 3,
                ["AEReception", "AEOrdering", "AESequenceDC", "IStore"],
            ):
                _, _, _ = handle_domain_log_file_reception_and_save(
                    urls=self.harness_config.log_urls["location"],
                    domain_file_names=[],
                    log_file_store_path=self.harness_config.log_file_store,
                    location=location,
                    file_prefix=prefix,
                )
        except (RuntimeError, requests.ConnectionError) as error:
            logging.getLogger().warning(
                (
                    "Obtaining all the other relevant log files failed with"
                    " the following error:\n%s"
                ),
                str(error),
            )

    def save_log_files_to_test_output_directory(self) -> None:
        """Method to copy all log files to the test output directory"""
        files = glob.glob("*.*", root_dir=self.harness_config.log_file_store)
        for file in files:
            shutil.copy(
                os.path.join(self.harness_config.log_file_store, file),
                self.test_output_directory,
            )

    def clean_directories(self) -> None:
        """Method to clean up log and uml file store directories"""
        results_db_path = os.path.join(
            self.test_output_directory, "results.db"
        )
        if os.path.exists(results_db_path):
            os.remove(results_db_path)
        clean_directories(
            [
                self.harness_config.uml_file_store,
                self.harness_config.log_file_store,
                self.harness_config.profile_store,
                self.harness_config.test_file_store,
            ]
        )
        try:
            try:
                response_tuple = send_get_request(
                    url=self.harness_config.pv_clean_folders_url,
                    max_retries=self.harness_config.requests_max_retries,
                    timeout=(
                        self.harness_config.requests_timeout,
                        self.harness_config.pv_clean_folders_read_timeout,
                    ),
                )
                if not response_tuple[0]:
                    logging.getLogger().warning(
                        (
                            "There was an error with the request to clean up "
                            "PV folders"
                            " for next test with request response: %s"
                        ),
                        response_tuple[2].text,
                    )
            except (requests.ConnectionError, requests.ConnectTimeout):
                logging.getLogger().warning(
                    "There was an error with the request to clean up PV"
                    "folders"
                    " for next test"
                )
        except (requests.ReadTimeout, requests.ConnectionError):
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
    :param test_profile: The profile for the test, defaults to `None`
    :type test_profile: :class:`Profile` | `None`, optional
    :param pbar: A progress bar to track the progress of the test, defaults to
    `None`
    :type pbar: :class:`tqdm` | `None`, optional
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
        *,
        harness_config: HarnessConfig | None = None,
        test_config: TestConfig | None = None,
        test_output_directory: str | None = None,
        test_profile: None = None,
        pbar: tqdm | None = None,
        test_graceful_kill_functions: list[
            Callable[..., Awaitable[None]]
        ] | None = None
    ) -> None:
        super().__init__(
            test_file_generators=test_file_generators,
            harness_config=harness_config,
            test_config=test_config,
            test_output_directory=test_output_directory,
            save_files=True,
            test_profile=test_profile,
            pbar=pbar,
            test_graceful_kill_functions=test_graceful_kill_functions,
        )

    def set_results_holder(self) -> PVResults:
        return super().set_results_holder()

    def _get_sim_data(
        self, jobs_to_send: list[Job]
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
        """Method to set the test interval at the default value of 0.1
        seconds
        """
        self.interval = 0.1
        self.shard = False

    def calc_results(self) -> None:
        """Method to calc the results after the test and save reports"""
        # load verifier logs and concatenate string
        log_string = self.pv_file_inspector.load_log_files_and_concat_strings(
            self.test_config.functional_options["log_domain"]
        )
        # get the validity dataframe
        validity_df = self.results.create_validity_dataframe()
        # analyse the logs and get report files
        report_files_mapping = create_report_files(
            log_string=log_string, validity_df=validity_df,
            test_name="Results",
            event_id_job_id_map=self.results.event_id_job_id_map
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
        aggregated_df = (
            results_df[["Category", "TestResult", "JobId"]]
            .groupby(["Category", "TestResult"])
            .agg("count")
            .reset_index()
        )
        aggregated_df.columns = ["Category", "TestResult", "Count"]
        fig = px.bar(
            aggregated_df, x="TestResult", y="Count", color="Category"
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
    :type test_output_directory: `str` | `None`, optional,
    :param test_profile: The profile for the test, defaults to `None`
    :type test_profile: :class:`Profile` | `None`, optional
    :param pbar: A progress bar to track the progress of the test, defaults to
    `None`
    :type pbar: :class:`tqdm` | `None`, optional
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
        *,
        harness_config: HarnessConfig | None = None,
        test_config: TestConfig | None = None,
        test_output_directory: str | None = None,
        test_profile: Profile | None = None,
        pbar: tqdm | None = None,
        test_graceful_kill_functions: list[
            Callable[..., Awaitable[None]]
        ] | None = None
    ) -> None:
        """Constructor method"""
        metrics_retriever_and_handlers = [
            MetricsRetriverKwargsPairAndHandlerKwargsPair(
                metric_retriever_kwargs_pair=MetricsRetrieverKwargsPair(
                    metric_retriever_class=PVKafkaMetricsRetriever,
                    kwargs={
                        "msgbroker": (
                            harness_config.kafka_metrics_host
                        ),
                        "topic": (
                            harness_config.kafka_metrics_topic
                        ),
                    },
                ),
                handler_kwargs_pair=ResultsHandlerKwargsPair(
                    handler_class=PVKafkaMetricsHandler,
                    kwargs={
                        "interval": (
                            harness_config.kafka_metrics_collection_interval
                        ),
                    },
                )
            )
        ] if harness_config.metrics_from_kafka else []
        super().__init__(
            test_file_generators=test_file_generators,
            harness_config=harness_config,
            test_config=test_config,
            test_output_directory=test_output_directory,
            save_files=False,
            test_profile=test_profile,
            pbar=pbar,
            save_log_files=test_config.performance_options["save_logs"],
            async_metrics_retrievers_and_handlers=(
                metrics_retriever_and_handlers
            ),
            test_graceful_kill_functions=test_graceful_kill_functions,
        )

    def set_results_holder(self) -> PVResultsDataFrame:
        return PVResultsDataFrame(
            test_output_directory=self.test_output_directory,
            sample_rate=self.test_config.sample_rate,
            agg_during_test=self.test_config.aggregate_during,
            low_memory=self.test_config.low_memory,
        )

    def _get_sim_data(
        self, jobs_to_send: list[Job]
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
                "min_interval_between_job_events": self._get_min_interval(),
                "desired_job_event_gap": self.test_config.performance_options[
                    "job_event_gap"
                ],
            },
        )

    def _get_jobs_to_send(self) -> list[Job]:
        """Method to create the jobs to send

        :return: Returns the jobs to send
        :rtype: `list`[`tuple`[:class:`Job`, `dict`[`str`, `str` | `bool`]]]
        """
        if self.test_config.performance_options["round_robin"]:
            chooser = RollOverChoice(
                len(self.job_templates)
            )
        else:
            chooser = choices
        if self.test_profile:
            jobs_to_send = []
            num_events = 0
            max_number_of_events = len(self.test_profile.delay_times)
            while True:
                job = chooser(self.job_templates, k=1)[0]
                num_events += len(job.events)
                if num_events > max_number_of_events:
                    break
                jobs_to_send.append(job)
        else:
            jobs_to_send = chooser(
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

    def get_all_simulation_data(self) -> None:
        """Method to read and calculate al simulation data"""
        self.get_pv_sim_data()
        self.results.calc_all_results()

    def get_pv_sim_data(self) -> None:
        """Method to get the PV sim data from the grok endpoint and read into
        results
        """
        if self.harness_config.metrics_from_kafka:
            return
        self.results.add_reception_results_from_log_files(
            file_paths=[
                os.path.join(self.harness_config.log_file_store, file_name)
                for file_name in self.pv_file_inspector.file_names["aer"]
                + ["Reception.log"]
            ]
        )
        self.results.add_verifier_results_from_log_files(
            file_paths=[
                os.path.join(self.harness_config.log_file_store, file_name)
                for file_name in self.pv_file_inspector.file_names["ver"]
                + ["Verifier.log"]
            ]
        )

    def get_report_files_from_results(self) -> tuple[str, str]:
        """Method to get the reports from the results

        :return: Returns a tuple of:
        * html report string
        * xml report string
        :rtype: `tuple`[`str`, `str`]
        """
        html_report, xml_report = generate_performance_test_reports(
            results=self.results.failures,
            properties={
                **self.results.end_times,
                **self.results.full_averages,
                **self.results.reception_event_counts,
                **self.results.process_errors_counts,
                **{
                    "test_start_time": self.time_start.strftime(
                        "%Y/%m/%d, %H:%M:%S"
                    ),
                    "test_end_time": self.time_end.strftime(
                        "%Y/%m/%d, %H:%M:%S"
                    ),
                },
            },
        )
        return html_report, xml_report

    def calc_results(self) -> None:
        """Method to calc results and generate reports from the results"""
        self.get_all_simulation_data()
        html_report, xml_report = self.get_report_files_from_results()
        # get events sent vs events processed figure
        sent_vs_processed = self.make_fig_melt(
            self.results.agg_results[
                [
                    "Time (s)",
                    "Events Sent (/s)",
                    "Events Processed (/s)",
                    "AER Events Processed (/s)",
                ]
            ],
            x_col="Time (s)",
            y_axis_name="Events/s",
            color_group_name="Metric",
            markers=True,
        )
        # get aggregated event response and queue times figure
        reponse_vs_queue = self.make_fig_melt(
            self.results.agg_results[
                [
                    "Time (s)",
                    "Queue Time (s)",
                    "Response Time (s)",
                ]
            ],
            x_col="Time (s)",
            y_axis_name="Time period (s)",
            color_group_name="Metric",
            markers=True,
        )
        # get the processing error figure
        processing_errors = self.make_fig_melt(
            self.results.process_errors_agg_results,
            x_col="Time (s)",
            y_axis_name="Number",
            color_group_name="Processing Error",
            plotly_func=px.bar,
        )
        # get cumulative sent, processed, aer processed events figure
        cumulative_sent_vs_processed = self.make_fig_melt(
            self.results.agg_results[
                [
                    "Time (s)",
                    "Cumulative Events Sent",
                    "Cumulative Events Processed",
                    "Cumulative AER Events Processed",
                ]
            ],
            x_col="Time (s)",
            y_axis_name="Count",
            color_group_name="Metric",
        )
        # deliver the report files
        deliver_test_report_files(
            {
                "Report.xml": xml_report,
                "Report.html": html_report,
                "EventsSentVSProcessed.html": sent_vs_processed,
                "CumulativeEventsSentVSProcessed.html": (
                    cumulative_sent_vs_processed
                ),
                "ResponseAndQueueTime.html": reponse_vs_queue,
                "AggregatedResults.csv": self.results.agg_results,
                "ProcessingErrors.html": processing_errors,
                "AggregatedErrors.csv": (
                    self.results.process_errors_agg_results
                ),
            },
            output_directory=self.test_output_directory,
        )

    @staticmethod
    def make_fig_melt(
        df_un_melted: pd.DataFrame,
        x_col: str,
        y_axis_name: str,
        color_group_name: str,
        plotly_func: Callable[..., Figure] = px.line,
        **func_kwargs,
    ) -> Figure:
        """Melt a dataframe identifying an x axis column to melt against. Plot
        a line graph using an identifier y axis and color group columns.
        The remaining column names (those no x_col) of the un-melted dataframe
        will be used a color group names and the column cell values will be
        used as y-axis values.

        :param df_un_melted: The unmelted dataframe
        :type df_un_melted: :class:`pd`.`DataFrame`
        :param x_col: The column from the given dataframe to use as the x-axis
        values
        :type x_col: `str`
        :param y_axis_name: The name given to the y axis
        :type y_axis_name: `str`
        :param color_group_name: The title for the key of the color groups
        :type color_group_name: `str`
        :param plotly_func: The title for the key of the color groups,
        defaults to :class:`px`.`line`
        :type plotly_func: :class:`Callable`[..., :class:`Figure`], optional
        :return: Returns a plotly line figure
        :rtype: :class:`Figure`
        """
        melted_df = df_un_melted.melt(
            id_vars=[x_col], var_name=color_group_name, value_name=y_axis_name
        )
        fig = plotly_func(
            melted_df,
            x=x_col,
            y=y_axis_name,
            color=color_group_name,
            **func_kwargs,
        )
        return fig
