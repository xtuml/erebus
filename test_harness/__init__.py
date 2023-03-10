"""
Creates the test harness app
"""
import os
from typing import Mapping, Optional

from flask import Flask


def create_app(test_config: Optional[Mapping] = None) -> Flask:
    """Create flask app

    :param test_config: Configuration test config, defaults to None
    :type test_config: :class:`Mapping`, optional
    :return: Returns a Flask instance
    :rtype: :class:`Flask`
    """
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping()

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    return app


if __name__ == "__main__":
    # run the app
    create_app().run()
