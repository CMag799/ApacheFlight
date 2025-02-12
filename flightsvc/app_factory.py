#!/usr/bin/env python3
"""
basic example of a resource server
"""

import datetime
import logging
import os

import connexion
from flask_jwt_extended import JWTManager

import flightsvc.src.config as config
from flightsvc.configs import DevConfig

from json import JSONEncoder
from connexion.options import SwaggerUIOptions

conf_path = os.path.abspath(__file__)
conf_path = os.path.dirname(conf_path)
swaggerdoc_path = os.path.join(conf_path, "openapi")

import logging

log = logging.getLogger(__name__)

def create_app(config_object=DevConfig):
    res = config.check_env_vars()
    log.info(f'checked required env vars: {res}')

    swagger_ui_options = SwaggerUIOptions(swagger_ui=True)
    app = connexion.FlaskApp(__name__, specification_dir="./openapi/", swagger_ui_options=swagger_ui_options)
    app.app.json_encoder = JSONEncoder
    app.app.config.from_object(config_object)
    app.app.config['JWT_SECRET_KEY'] = os.environ.get("JWT_SECRET_KEY")
    token_valid_period = int(os.environ.get("TOKEN_AUTH_TIME", None))
    app.app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(minutes=token_valid_period)
    app.add_api("openapi.yaml", resolver_error=501)#, validate_responses=True)

    jwt = JWTManager(app.app)
    log.debug(f'using openapi flask')
    return app


