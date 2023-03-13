"""Testing __init__.py
"""
import os
from pathlib import Path

from flask.testing import FlaskClient

# get resources folder in tests folder
resources = Path(__file__).parent / "test_files"


def test_bad_mime_type(client: FlaskClient) -> None:
    """Test bad mime-type given

    :param client: Flask test client
    :type client: :class:`FlaskClient`
    """
    response = client.post(
        "/uploadUML",
        content_type="application/json",
    )
    assert response.data == b"mime-type must be multipart/form-data\n"
    assert response.status_code == 400


def test_no_file_name(client: FlaskClient) -> None:
    """Test no file name given

    :param client: Flask test client
    :type client: :class:`FlaskClient`
    """
    proper_file_path = os.path.join(resources, "test_uml_1.puml")
    file_data = open(proper_file_path, "rb")
    data = {
        "file": (file_data, "")
    }

    response = client.post(
        "/uploadUML",
        data=data,
        buffered=True,
        content_type="multipart/form-data"
    )
    assert response.data == b"One of the uploaded files has no filename\n"
    assert response.status_code == 400
