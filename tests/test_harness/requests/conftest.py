# pylint: disable=W0621
"""Configuration for requests tests
"""
from io import BytesIO
import gzip

import pytest


@pytest.fixture
def file_name() -> str:
    """Test file name

    :return: Returns a filename
    :rtype: `str`
    """
    return "test_file"


@pytest.fixture
def file_name_gzipped(
    file_name: str
) -> str:
    """Fixture providing the file name of a zipped file

    :param file_name: Fixture providing a file name
    :type file_name: `str`
    :return: Returns the zipped name of the file
    :rtype: `str`
    """
    return f"{file_name}.gz"


@pytest.fixture
def file_names(
    file_name: str,
    file_name_gzipped: str
) -> list[str]:
    """Fixture providing a list of file names

    :param file_name: Fixture providing a file name
    :type file_name: `str`
    :param file_name_gzipped: Fixture providing the file name of a zipped file
    :type file_name_gzipped: `str`
    :return: Returns a list of file names
    :rtype: `list`[`str`]
    """
    return [file_name, file_name_gzipped]


@pytest.fixture
def form_parameter() -> str:
    """Form parameter as a string

    :return: Returns the form parameter as a string
    :rtype: `str`
    """
    return 'upload'


@pytest.fixture
def json_request_body_file_name() -> dict[str, str]:
    """Fixture providing a json request body file name mapping

    :return: Returns the dictionary of the mapping
    :rtype: `dict`[`str`, `str`]
    """
    return {
        "fileName": "test_file.log"
    }


@pytest.fixture
def json_request_body_file_name_gz() -> dict[str, str]:
    """Fixture providing a json request body file name mapping of a gzipped
    file

    :return: Returns the dictionary of the mapping
    :rtype: `dict`[`str`, `str`]
    """
    return {
        "fileName": "test_file.log.gz"
    }


@pytest.fixture
def json_reponse_body_file_names() -> dict[str, list[str]]:
    """Fixture providing a mapping from "fileNames" to a list of file names

    :return: Returns the mapping dictionary to the list
    :rtype: `dict`[`str`, `list`[`str`]]
    """
    return {
        "fileNames": ["test_file.log", "test_file.log.gz"]
    }


@pytest.fixture
def file_string() -> str:
    """Fixture providing a file string

    :return: the file string
    :rtype: `str`
    """
    return "test"


@pytest.fixture
def file_raw_bytes(
    file_string: str
) -> bytes:
    """Fixture providing the raw bytes utf-8 encoded version of the file string

    :param file_string: Fixture providing a file string
    :type file_string: str
    :return: Returns the raw bytes
    :rtype: `bytes`
    """
    return file_string.encode("utf-8")


@pytest.fixture
def file_bytes(
    file_raw_bytes: bytes
) -> BytesIO:
    """:class:`BytesIO` instance to send with request

    :return: Returns a string encoded as utf8 bytes for testing
    :rtype: :class:`BytesIO`
    """
    return BytesIO(file_raw_bytes)


@pytest.fixture
def file_raw_bytes_gzipped(
    file_raw_bytes: bytes
) -> bytes:
    """Fixture providing the zipped raw bytes of a file string

    :param file_raw_bytes: Fixture providing the raw bytes of a file string
    :type file_raw_bytes: `bytes`
    :return: the zipped bytes
    :rtype: bytes
    """
    return gzip.compress(file_raw_bytes)


@pytest.fixture
def file_raw_bytes_dict(
    file_name: str,
    file_name_gzipped: str,
    file_raw_bytes: bytes,
    file_raw_bytes_gzipped: bytes
) -> dict[str, bytes]:
    """Fixture providing a mapping of file name to bytes

    :param file_name: Fixture providing a file name
    :type file_name: `str`
    :param file_name_gzipped: Fixture providing a zippe file name
    :type file_name_gzipped: `str`
    :param file_raw_bytes: Fixture providing the raw bytes of a file string
    :type file_raw_bytes: `bytes`
    :param file_raw_bytes_gzipped: Fixture providing the zipped raw bytes of a
    file string
    :type file_raw_bytes_gzipped: `bytes`
    :return: Returns the dictionary mapping file name to bytes
    :rtype: `dict`[`str`, `bytes`]
    """
    return {
        file_name: file_raw_bytes,
        file_name_gzipped: file_raw_bytes_gzipped
    }
