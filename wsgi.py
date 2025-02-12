import os

from dotenv import load_dotenv

from flightsvc.app_factory import create_app

load_dotenv()

if __name__ == '__main__':
    app = create_app()
    # app.run(host='127.0.0.1', port=8080, log_level='debug')
    app.run(host='0.0.0.0', port=8080, log_level='debug')
