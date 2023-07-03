"""Generate Protocol Verifier config using Plus2Json
"""
import sys
from typing import TextIO, Callable
from io import StringIO
from plus2json.__main__ import main


def collect_std_out() -> tuple[StringIO, TextIO]:
    """Method to start collecting the stdout

    :return: Returns the values of new stdout collector and old stdout
    collector
    :rtype: `tuple`[:class:`StringIO`, :class:`TextIO`]
    """
    old = sys.stdout
    new = StringIO()
    set_std_out(new)
    return new, old


def collect_std_err() -> tuple[StringIO, TextIO]:
    """Method to start collecting the stderr

    :return: Returns the values of new stderr collector and old stderr
    collector
    :rtype: `tuple`[:class:`StringIO`, :class:`TextIO`]
    """
    old = sys.stderr
    new = StringIO()
    set_std_error(new)
    return new, old


def set_std_out(
    to_set: TextIO
) -> None:
    """Method to set the stdout collector

    :param to_set: The collector object to be set
    :type to_set: :class:`TextIO`
    """
    sys.stdout = to_set


def set_std_error(
    to_set: TextIO
) -> None:
    """Method to set the stderr collector

    :param to_set: The collector object to be set
    :type to_set: :class:`TextIO`
    """
    sys.stderr = to_set


def get_job_def_from_uml(
    uml_file_path: str,
) -> str:
    """Method to take a uml file by file path and convert into PV job
    definition json string

    :param uml_file_path: The path of the uml file
    :type uml_file_path: `str`
    :return: Returns the json string
    :rtype: `str`
    """
    args = [
        None,
        uml_file_path,
    ]
    check_string = get_string_io_output_from_main_with_args(
        args,
        collect_func=collect_std_err,
        set_func=set_std_error
    )
    if check_string:
        raise RuntimeError(
            f"Plus2json found the following errors that should be rectified:\n"
            f"{check_string}"
        )
    args += ["--job"]
    job_string = get_string_io_output_from_main_with_args(
        args,
        collect_func=collect_std_out,
        set_func=set_std_out
    )
    return job_string


def get_string_io_output_from_main_with_args(
    args: list,
    collect_func: Callable[[], tuple[StringIO, TextIO]],
    set_func: Callable[[TextIO], None]
) -> str:
    """Method to run `main` and collect text going to the shell

    :param args: The arguments for `main`
    :type args: `list`
    :param collect_func: The function used to collect text from the
    shell
    :type collect_func: :class:`Callable`[[], `tuple`[:class:`StringIO`,
    :class:`TextIO`]]
    :param set_func: The function to reset the collector to the old value
    :type set_func: :class:`Callable`[[:class:`TextIO`], `None`]
    :return: Returns the string representation of the shell output
    :rtype: `str`
    """
    new, old = collect_func()
    main(args)
    std_out_string = new.getvalue()
    set_func(old)
    return std_out_string
