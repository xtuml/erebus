"""Testing __init__.py
"""

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
    assert response.status_code == 400
