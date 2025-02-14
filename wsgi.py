import os
import logging
from dotenv import load_dotenv

import flightsvc.controllers.multi_flight_producer
from flightsvc.app_factory import create_app

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)


if __name__ == '__main__':
    app = create_app()
    # app.run(host='127.0.0.1', port=8080, log_level='debug')

    import threading

    # start flight producers
    log.info(f'about to start flight producers')
    threading.Thread(target=lambda: flightsvc.controllers.multi_flight_producer.start_producers(
        host="0.0.0.0", port=5006
    )).start()


    # start flight server
    log.info(f'about to start flight server')
    threading.Thread(target=lambda: flightsvc.controllers.multi_flight_producer.start_server(
        host="0.0.0.0", port=5006
    )).start()


    import platform

    if platform.system() == "Windows":
        app.run(host='0.0.0.0', port=8082, log_level='debug')
    else:
        app.run(host='0.0.0.0', port=8080, log_level='debug')
