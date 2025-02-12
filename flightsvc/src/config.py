import logging
import os
env_var_summary = {}

required_env_values = [
    "DB_HOST",
    "DB_USER",
    "DB_PORT",
    "JWT_SECRET_KEY"
    ]


DEFAULT_ENV_VALUES = {
    "FLASK_TYPE": "openapi",
    "OPEN_ACCESS": "true",
    "API_ENDPOINT": "/api/v1",
    "FLASK_APP": "flightsvc",
    "NUM_RETRIES": "6",
    "BACKOFF_FACTOR": "0.5",
    "TOKEN_AUTH_TIME": "1440",
}


def check_env_vars():

    for val in required_env_values:
        if os.environ.get(val):
            env_var_summary[val] = os.environ.get(val)
            pass
        else:
            logging.error(f'{val} not set')
            raise ValueError(f'{val} not set')
    for key, value in DEFAULT_ENV_VALUES.items():
        if os.environ.get(key):
            env_var_summary[key] = os.environ.get(key)
        else:
            os.environ.setdefault(key, value)
            env_var_summary[key] = value
    return True