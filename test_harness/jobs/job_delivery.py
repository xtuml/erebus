"""Methods to deliver jobs to an endpoint
"""
from typing import Callable, Awaitable, Any, Generator
import os
import io
import asyncio
from glob import glob
from time import sleep
from datetime import datetime, timedelta
import json
from copy import copy

from test_harness.utils import delayed_async_func
import requests
import aiohttp
from tqdm import tqdm
import numpy as np

from test_harness.jobs.job_factory import (
    Job,
    parse_input_jobfile,
    make_job_from_template
)


def send_payload(
    target: str,
    url: str = "http://host.docker.internal:9000/upload/events"
) -> None:
    """Method to send a single file as a POST request to an url

    :param target: The target file path
    :type target: `str`
    :param url: The url to send the POST request to,
    defaults to "http://host.docker.internal:9000/upload/events"
    :type url: `str`, optional
    """
    payload = {}
    files = build_files(target)
    headers = {}
    response = requests.request(
        "POST",
        url,
        headers=headers,
        data=payload,
        files=files,
        timeout=100
    )
    print(response.text)


async def delayed_send_payload(
    file: io.BytesIO,
    file_name: str,
    pbar: tqdm,
    url: str = "http://host.docker.internal:9000/upload/events",
    delay: float = 0
) -> str:
    """Method to asynchronously send payload data to end point

    :param file: Binary :class:`io`.`BytesIO` instance representing file
    :type file: :class:`io`.`BytesIO`
    :param file_name: Name of file to be uploaded
    :type file_name: `str`
    :param pbar: The progress bar
    :type pbar: :class:`tqdm`
    :param url: The endpoint to request, defaults to
    "http://host.docker.internal:9000/upload/events"
    :type url: `str`, optional
    :param delay: The amount of time to delay in seconds, defaults to 0
    :type delay: `float`, optional
    :return: Returns a string representation of the response
    :rtype: `str`
    """
    try:
        response = await asyncio.wait_for(delayed_async_func(
            delay,
            send_payload_async,
            pbar,
            file=file,
            file_name=file_name,
            url=url,
        ), timeout=None)
    except Exception as error:
        response = handle_error_response(error)
    return response


async def send_payload_async(
    file: bytes,
    file_name: str,
    url: str = "http://host.docker.internal:9000/upload/events",
    session: aiohttp.ClientSession | None = None
) -> str:
    """Method to asynchronously send a payload

    :param file: Binary :class:`io`.`BytesIO` instance representing file
    :type file: :class:`io`.`BytesIO`
    :param file_name: Name of file to be uploaded
    :type file_name: `str`
    :param url: Url endpoint to post to, defaults to
    "http://host.docker.internal:9000/upload/events"
    :type url: `str`, optional
    :return: The response from the post request
    :rtype: `str`
    :param session: The session for HTTP requests, defaults to `None`
    :type session: `aiohttp`.`ClientSession` | `None`, optional
    """
    form_data = aiohttp.FormData()
    form_data.add_field(
        'upload',
        io.BytesIO(file),
        filename=file_name,
        content_type='application/octet-stream'
    )
    if session is not None:
        async with session.post(
            url,
            data=form_data(),
        ) as response:
            try:
                awaited_response = await asyncio.wait_for(
                    response.text(),
                    timeout=200
                )
                awaited_response = ""
            except Exception as error:
                awaited_response = handle_error_response(error)
            return awaited_response
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            data=form_data(),
        ) as response:
            try:
                awaited_response = await asyncio.wait_for(
                    response.text(),
                    timeout=200
                )
                awaited_response = ""
            except Exception as error:
                awaited_response = handle_error_response(error)
            return awaited_response


def handle_error_response(error: Exception) -> str:
    """Handler for an exception occuring

    :param error: The error
    :type error: :class:`Exception`
    :return: Returns a message realting to the error
    :rtype: `str`
    """
    if isinstance(error, asyncio.TimeoutError):
        return "timed out"
    if isinstance(error, aiohttp.ClientConnectionError):
        return "Connection Error"
    return str(error)


# async def delayed_async_func(
#     delay: float,
#     func: Callable[..., Awaitable[Any]],
#     pbar: tqdm,
#     *args,
#     **kwargs
# ) -> Any:
#     """Method to delay an async func by an amount of time in seconds

#     :param delay: The delay before th async function starts
#     :type delay: `float`
#     :param func: The async function to delay
#     :type func: :class:`Callable`[`...`, :class:`Awaitable`[`Any`]]
#     :param pbar: Progress bar
#     :type pbar: :class:`tqdm`
#     :return: Returns any value that the input function would
#     :rtype: `Any`
#     """
#     await asyncio.sleep(delay)
#     pbar.update(1)
#     awaited_data = await func(*args, **kwargs)
#     return awaited_data


async def send_output_dir_async(
    dir_name: str,
    interval_time: float,
    url: str = "http://host.docker.internal:9000/upload/events"
) -> list[Any]:
    """Asynchronous function to send files to an endpoint from a directory

    :param dir_name: The path of the directory
    :type dir_name: `str`
    :param interval_time: The interval time between requests
    :type interval_time: `float`
    :param url: The endpoint to send the request to, defaults to
    "http://host.docker.internal:9000/upload/events"
    :type url: `str`, optional
    :return: Returns a list of the return values from the sent payload
    :rtype: `list`[`Any`]
    """
    output_files = glob(dir_name + "/*")
    file_file_name_delay_tuples = create_binary_file_file_name_delay_tuples(
        file_paths=output_files,
        interval=interval_time
    )
    results = await send_delayed_binary_files(
        binary_files=file_file_name_delay_tuples,
        url=url
    )
    return results


async def send_delayed_binary_files(
    binary_files: list[tuple[io.BytesIO, str, float]],
    url: str = "http://host.docker.internal:9000/upload/events",
) -> list[Any]:
    """Method send (arbitrarily) staggered binary files to an endpoint

    :param binary_files: List of tuples of io bytes, file name and a delay
    :type binary_files: `list`[`tuple`[:class:`io`.`BytesIO`,
    `str`, `float`]]
    :param url: The endpoint to send files to, defaults to
    "http://host.docker.internal:9000/upload/events"
    :type url: `str`, optional
    :return: Returns a list of the results
    :rtype: `list`[`Any`]
    """
    tasks: list[asyncio.Task] = []
    with tqdm(total=len(binary_files)) as pbar:
        async with asyncio.TaskGroup() as task_group:
            for file, file_name, start_time, _ in binary_files:
                task = task_group.create_task(
                    delayed_send_payload(
                        file=file,
                        file_name=file_name,
                        delay=start_time,
                        pbar=pbar,
                        url=url
                    )
                )
                tasks.append(task)
    results = [
        task.result()
        for task in tasks
    ]
    return results


def create_binary_file_file_name_delay_tuples(
    file_paths: list[str],
    interval: float
) -> list[tuple[io.BytesIO, str, float]]:
    """Method to create an iterable of binary file, file name, delay tuples

    :param file_paths: List of file paths to load
    :type file_paths: `list`[`str`]
    :param interval: The interval in seconds with which to send a file
    :type interval: `float`
    :return: Returns a list of tuples of binary file, file name, delay
    :rtype: `list`[`tuple`[:class:`io`.`BytesIO`, `str`, `float`]]
    """
    delays = calc_start_times(
        len(file_paths),
        interval
    )
    file_file_name_delay_tuples = [
        create_binary_file_file_name_delay_tuple(
            file_path=file_path,
            delay=delay
        )
        for file_path, delay in zip(
            file_paths,
            delays
        )
    ]
    return file_file_name_delay_tuples


def create_binary_file_file_name_delay_tuple(
    file_path: str,
    delay: float
) -> tuple[io.BytesIO, str, float]:
    """Method to create a binary file, file name, delay tuple. Reads in file
    into bytes and gets basename for file.

    :param file_path: Path to the file
    :type file_path: `str`
    :param delay: The delay before starting to send file
    :type delay: `float`
    :return: Returns a tuple of binary file, file name, delay
    :rtype: `tuple`[:class:`io`.`BytesIO`, `str`, `float`]
    """
    with open(file_path, 'rb') as opened_file:
        file = io.BytesIO(opened_file.read())
    file_name = os.path.basename(file_path)
    return (
        file,
        file_name,
        delay
    )


def calc_start_times(
    num_files: int,
    interval_time: float
) -> list[float]:
    """Method to calculate the start times, as a list, given an interval and
    number of files

    :param num_files: The number of files to be sent
    :type num_files: `int`
    :param interval_time: The time required between requests
    :type interval_time: `float`
    :return: Returns a list of the start times in seconds for each file
    :rtype: `list`[`float`]
    """
    start_times = np.arange(
        start=0,
        stop=num_files * interval_time,
        step=interval_time
    ).tolist()
    return start_times


def calc_event_start_times(
    jobs: list[Job],
    interval_time: float
) -> list[list[float]]:
    """Method to calculate the start times, as a list of list of floats,
    given a list of jobs

    :param jobs: The list of jobs to calculate event start times
    :type jobs: `list`[:class:`Job`]
    :param interval_time: The time required between requests
    :type interval_time: `float`
    :return: Returns a list of the start times in seconds for each file
    :rtype: `list`[`float`]
    """
    job_delays = [[] for _ in jobs]
    indexes = list(range(len(jobs)))
    delay = 0
    rate = round(1/interval_time)
    events = [
        copy(job.events) for job in jobs[: rate]
    ]
    events_job_index = indexes[: rate]
    while any(events):
        for index, job_events in enumerate(events):
            if job_events:
                job_delays[events_job_index[index]].append(delay)
                delay += interval_time
                job_events.pop(0)
                if not job_events and rate < len(jobs):
                    events[index] = copy(jobs[rate].events)
                    events_job_index[index] = rate
                    rate += 1
    return job_delays


async def send_job_templates_async(
    template_jobs: list[Job],
    interval_time: float,
    url: str = "http://host.docker.internal:9000/upload/events",
    test_start_time: datetime | None = None,
    shard_events: bool = False
) -> tuple[list[Any], list[tuple[bytes, str, float, str]]]:
    """Asynchronous function to send files to an endpoint from a directory

    :param template_jobs: A list of template jobs
    :type template_jobs: `list`[:class:`Job`]
    :param interval_time: The interval time between requests
    :type interval_time: `float`
    :param url: The endpoint to send the request to, defaults to
    "http://host.docker.internal:9000/upload/events"
    :type url: `str`, optional
    :param test_start_time: A `datatime` object indicating the start time of
    the test, defaults to `None`
    :type test_start_time: `datetime` | `None`, optional
    :param shard_events: Boolean indicatin whether to shard jobs into events
    or not, defaults to `False`
    :type shard_events: `bool`
    :return: Returns tuple of
    * a list of the return values from the sent payload
    * a list of tuples of binary file, file name, delay, job id
    :rtype: `tuple`[`list`[`Any`], `list`[`tuple`[`bytes`, `str`, `float`,
    `str`]]]
    """
    if not test_start_time:
        test_start_time = datetime.utcnow()
    file_file_name_delay_tuples = (
        create_binary_files_file_name_delay_tuples_from_job_templates(
            template_jobs=template_jobs,
            interval=interval_time,
            test_start_time=test_start_time,
            shard_events=shard_events
        )
    )
    saved_file_file_name_tuples = [
        (data_tuple[0].getvalue(),) + data_tuple[1:]
        for data_tuple in file_file_name_delay_tuples
    ]
    results = await send_delayed_binary_files(
        binary_files=file_file_name_delay_tuples,
        url=url
    )
    return results, saved_file_file_name_tuples


def create_binary_files_file_name_delay_tuples_from_job_templates(
    template_jobs: list[Job],
    interval: float,
    test_start_time: datetime,
    shard_events: bool = False
) -> list[tuple[io.BytesIO, str, float, str]]:
    """Method to create an iterable of binary file, file name, delay tuples

    :param template_jobs: A list of template jobs
    :type template_jobs: `list`[:class:`Job`]
    :param interval: The interval in seconds with which to send a file
    :type interval: `float`
    :param test_start_time: A `datatime` object indicating the start time of
    the test
    :type test_start_time: `datetime`
    :param shard_events: Boolean indicatin whether to shard jobs into events
    or not, defaults to `False`
    :type shard_events: `bool`
    :return: Returns a list of tuples of binary file, file name, delay, job id
    :rtype: `list`[`tuple`[:class:`io`.`BytesIO`, `str`, `float`, `str`]]
    """
    if shard_events:
        delays = calc_event_start_times(
            jobs=template_jobs,
            interval_time=interval
        )
    else:
        num_files = len(template_jobs)
        delays = calc_start_times(
            num_files,
            interval
        )
    file_file_name_delay_tuples = []
    for index, template_job in enumerate(template_jobs):
        if shard_events:
            delays_slice = delays[index]
        else:
            delays_slice = delays[index: index + 1]
        file_file_name_delay_tuples.extend(
            generate_binary_file_file_name_delay_tuples_from_job_template(
                template_job=template_job,
                delays_slice=delays_slice,
                test_start_time=test_start_time,
                shard_events=shard_events
            )
        )
    return file_file_name_delay_tuples


def generate_binary_file_file_name_delay_tuples_from_job_template(
    template_job: Job,
    delays_slice: list[float],
    test_start_time: datetime,
    shard_events: bool = False
) -> Generator[tuple[io.BytesIO, str, float, str], Any, None]:
    """Method to create a binary file, file name, delay tuple

    :param template_job: A template :class:`Job`
    :type template_job: :class:`Job`
    :param delay: The delay in seconds of both the start time of the job and
    delay of asynchronous request
    :type delay: `float`
    :param test_start_time: A `datatime` object indicating the start time of
    the test
    :type test_start_time: `datetime`
    :param shard_events: Boolean indicatin whether to shard jobs into events
    or not, defaults to `False`
    :type shard_events: `bool`
    :return: Returns a tuple of binary file, file name, delay, job_id
    :rtype: `tuple`[:class:`io`.`BytesIO`, `str`, `float`, `str`]
    """
    job_start_time = test_start_time + timedelta(seconds=delays_slice[0])
    if len(delays_slice) > 1:
        gap = delays_slice[1] - delays_slice[0]
    else:
        gap = 1
    job_to_send = make_job_from_template(
        template=template_job,
        gap_seconds=gap,
        start_time=job_start_time
    )
    if shard_events:
        yield from generate_binary_file_file_name_delay_tuples_events_from_job(
            job_to_send=job_to_send,
            delays_slice=delays_slice,
        )
    else:
        yield from generate_binary_file_file_name_delay_tuple_from_job(
            job_to_send=job_to_send,
            delay=delays_slice[0]
        )


def generate_binary_file_file_name_delay_tuple_from_job(
    job_to_send: Job,
    delay: float
) -> Generator[tuple[io.BytesIO, str, float, str], Any, None]:
    """Method to generate a json string (as bytes), file name, delay tuple

    :param job_to_send: The job that is being sent
    :type job_to_send: :class:`Job`
    :param delay: The delay the job will have
    :type delay: `float`
    :yield: Yields the json string (as bytes), file name, delay tuple, job id
    :rtype: :class:`Generator`[`tuple`[:class:`io`.`BytesIO`, `str`, `float`,
    `str`], `Any`, `None`]
    """
    job_io_bytes = io.BytesIO(job_to_send.export_job_to_json().encode("utf8"))

    file_name = job_to_send.job_id + ".json"

    yield (
        job_io_bytes,
        file_name,
        delay,
        job_to_send.job_id
    )


def generate_binary_file_file_name_delay_tuples_events_from_job(
    job_to_send: Job,
    delays_slice: list[float]
) -> Generator[tuple[io.BytesIO, str, float, str], Any, None]:
    """_summary_

    :param job_to_send: The job that is being sent
    :type job_to_send: :class:`Job`
    :param delays_slice: A slice of delays to be given to each event in the job
    :type delays_slice: `list`[`float`]
    :yield: Yields the json string (as bytes), file name, delay tuple, job id
    :rtype: :class:`Generator`[`tuple`[:class:`io`.`BytesIO`, `str`, `float`,
    `str`], `Any`, `None`]
    """
    for event, delay in zip(job_to_send.events, delays_slice):
        event_io_bytes = io.BytesIO(
            event.export_event_to_json_list().encode("utf8")
        )
        file_name = f"{event.event_id}_{job_to_send.job_id}.json"
        yield (
            event_io_bytes,
            file_name,
            delay,
            job_to_send.job_id
        )


def build_files(target: str) -> list[tuple]:
    """Method to build from a target file path a tuple payload that can be
    sent as part of a multipart form request

    :param target: Filepath of target file
    :type target: `str`
    :return: Returns a list of a single tuple
    :rtype: list[tuple]
    """
    files = [
        ('upload', (target, open(target, 'rb'), 'application/octet-stream'))
    ]
    return files


def send_output_dir(dir_name: str, wait_time_seconds: float) -> None:
    """Method to send all files (that are jobs) from a directory path waiting
    a specified time after each request

    :param dir_name: The path of the directory containing job sequences
    :type dir_name: `str`
    :param wait_time_seconds: The wait time between requests
    :type wait_time_seconds: `float`
    """
    output_files = glob(dir_name + "/*")
    for file in tqdm(output_files, total=len(output_files)):
        send_payload(file)
        sleep(wait_time_seconds)


def send_job_templates(
    template_jobs: list[Job],
    interval_time: float,
    url: str = "http://host.docker.internal:9000/upload/events",
    test_start_time: datetime | None = None,
    shard_events: bool = False
) -> list[Any]:
    """Function to send files to an endpoint from a directory using an
    asynchronous implementation.

    :param template_jobs: A list of template jobs
    :type template_jobs: `list`[:class:`Job`]
    :param interval_time: The interval time between requests
    :type interval_time: `float`
    :param url: The endpoint to send the request to, defaults to
    "http://host.docker.internal:9000/upload/events"
    :type url: `str`, optional
    :param test_start_time: A `datatime` object indicating the start time of
    the test, defaults to `None`
    :type test_start_time: `datetime` | `None`, optional
    :param shard_events: Boolean indicatin whether to shard jobs into events
    or not, defaults to `False`
    :type shard_events: `bool`
    :return: Returns a list of the return values from the sent payload
    :rtype: `list`[`Any`]
    """
    task_results, _ = asyncio.run(
        send_job_templates_async(
            template_jobs=template_jobs,
            interval_time=interval_time,
            url=url,
            test_start_time=test_start_time,
            shard_events=shard_events
        )
    )
    return task_results


if __name__ == "__main__":
    import sys
    args = sys.argv
    num_jobs = 10000
    num_iterations = 1
    rate = 100
    url = "http://host.docker.internal:9000/upload/events"
    shard_events = False
    if "--numjobs" in args:
        num_jobs = int(args[args.index("--numjobs") + 1])
    if "--numiters" in args:
        num_iters = int(args[args.index("--numiters") + 1])
    if "--rate" in args:
        rate = float(args[args.index("--rate") + 1])
    if "--url" in args:
        url = int(args[args.index("--url") + 1])
    if "--shard" in args:
        shard_events = True

    interval = 1 / rate
    with open("test_sequence.json", 'r', encoding="utf8") as file:
        job_file = json.load(file)
    job = parse_input_jobfile(job_file)
    template_jobs = [job] * num_jobs
    for i in range(1):
        task_results = send_job_templates(
            template_jobs=template_jobs,
            interval_time=interval,
            url=url,
            shard_events=shard_events
        )
        print(f"Iteration {i} complete")
