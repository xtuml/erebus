"""Configuration for requests tests
"""
from io import BytesIO

import pytest


@pytest.fixture
def file_bytes() -> BytesIO:
    """:class:`BytesIO` instance to send with request

    :return: Returns a string encoded as utf8 bytes for testing
    :rtype: :class:`BytesIO`
    """
    return BytesIO('test'.encode("utf8"))


@pytest.fixture
def file_name() -> str:
    """Test file name

    :return: Returns a filename
    :rtype: `str`
    """
    return "test_file"


@pytest.fixture
def form_parameter() -> str:
    """Form parameter as a string

    :return: Returns the form parameter as a string
    :rtype: `str`
    """
    return 'upload'
