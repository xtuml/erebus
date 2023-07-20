"""Utility functions
"""
from typing import Generator, Any
from io import BytesIO
import os
import glob


def create_file_io_file_name_tuple(
    file_name: str,
    file_string: str
) -> tuple[BytesIO, str]:
    """Function to create file io file name tuple from a file name and file
    string

    :param file_name: The name of the file
    :type file_name: `str`
    :param file_string: The string representing the file
    :type file_string: `str`
    :return: Returns a tuple of the file io and file name pair
    :rtype: `tuple`[:class:`BytesIO`, `str`]
    """
    return (
        BytesIO(file_string.encode("utf-8")),
        file_name
    )


def create_file_io_file_name_tuple_with_file_path(
    file_path: str,
    file_string: str
) -> tuple[BytesIO, str]:
    """Function to create file io file name tuple from a file path and file
    string

    :param file_path: The path of the file
    :type file_path: `str`
    :param file_string: The string representing the file
    :type file_string: `str`
    :return: Returns a tuple of the file io and file name pair
    :rtype: `tuple`[:class:`BytesIO`, `str`]
    """
    file_io_file_name = create_file_io_file_name_tuple(
        os.path.basename(file_path),
        file_string
    )
    return file_io_file_name


def divide_chunks(
    list_to_chunk: list,
    chunk_size: int
) -> Generator[list, Any, None]:
    """Method to split list into chunks

    :param list_to_chunk: The list ot chunk
    :type list_to_chunk: `list`
    :param chunk_size: The size of the chunks
    :type chunk_size: `int`
    :yield: Generates lists
    :rtype: :class:`Generator`[`list`, `Any`, `None`]
    """
    for index in range(0, len(list_to_chunk), chunk_size):
        yield list_to_chunk[index: index + chunk_size]


def clean_directories(
    directory_paths: list[str]
) -> None:
    """Method to clear directories of non-hidden files

    :param directory_paths: Paths of directories to clear
    :type directory_paths: `list`[`str`]
    """
    for directory_path in directory_paths:
        clean_directory(directory_path)


def clean_directory(
    directory_path: str
) -> None:
    """Method to clear a directory of non-hidden files

    :param directory_path: The path of the directory to clear
    :type directory_path: `str`
    """
    files = glob.glob("*.*", root_dir=directory_path)
    for file in files:
        os.remove(
            os.path.join(
                directory_path,
                file
            )
        )
