import pyarrow
import pyarrow.flight as flight
import argparse
import ast
import threading
import multiprocessing
import platform
import time
import logging

from kazoo.client import KazooClient
from kazoo.retry import KazooRetry
from kazoo.handlers.threading import KazooTimeoutError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# test_data = pyarrow.Table.from_arrays(
#                 [
#                     pyarrow.array(["AAPL", "GOOG", "MSFT"]),
#                     pyarrow.array([1672345600, 1672345600, 1672345600]),  # Timestamps
#                     pyarrow.array([150.0, 110.0, 250.0])
#                 ],
#                 names=["symbol", "timestamp", "price"]
#              )


class FlightServer(flight.FlightServerBase):
    def __init__(self, host="localhost", location=None,
                 tls_certificates=None, verify_client=False,
                 root_certificates=None, auth_handler=None, registry_address=None):
        super(FlightServer, self).__init__(
            location, auth_handler, tls_certificates, verify_client,
            root_certificates)
        # self.flights = {"get_test_data": test_data}
        self.flights = {}
        self.host = host
        self.tls_certificates = tls_certificates
        self.registry_address = registry_address

    def connect_to_zookeeper(self):
        try:
            log.info(f'connecting to zookeeper: {self.registry_address}')
            # kr = KazooRetry(max_tries=3, delay=1, backoff=2)
            kr = KazooRetry(
                max_tries=3,
                delay=0.5,
                backoff=2,
                max_delay=10
            )

            try:
                self.zk = KazooClient(hosts=self.registry_address, connection_retry=kr)
                self.zk.start()
            except KazooTimeoutError:
                log.error(f"Zookeeper connection timeout")
            except Exception as e:
                log.error(f"Failed to connect to Zookeeper: {e}")
        except:
            import traceback
            log.error(traceback.format_exc())

    @classmethod
    def descriptor_to_key(self, descriptor):
        return (descriptor.descriptor_type.value, descriptor.command,
                tuple(descriptor.path or tuple()))

    def _make_flight_info(self, key, descriptor, table):
        if self.tls_certificates:
            location = pyarrow.flight.Location.for_grpc_tls(
                self.host, self.port
            )
        else:
            location = pyarrow.flight.Location.for_grpc_tcp(
                self.host, self.port
            )
        endpoints = [pyarrow.flight.FlightEndpoint(repr(key), [location]), ]

        mock_sink = pyarrow.MockOutputStream()
        stream_writer = pyarrow.RecordBatchStreamWriter(
            mock_sink, table.schema)
        stream_writer.write_table(table)
        stream_writer.close()
        data_size = mock_sink.size()

        return pyarrow.flight.FlightInfo(table.schema,
                                         descriptor, endpoints,
                                         table.num_rows, data_size)

    def list_flights(self, context, criteria):
        for key, table in self.flights.items():
            if key[1] is not None:
                descriptor = pyarrow.flight.FlightDescriptor.for_command(key[1])
            else:
                descriptor = pyarrow.flight.FlightDescriptor.for_path(*key[2])

            yield self._make_flight_info(key, descriptor, table)

    def get_flight_info(self, context, descriptor):
        key = FlightServer.descriptor_to_key(descriptor)
        if key in self.flights:
            table = self.flights[key]
            return self._make_flight_info(key, descriptor, table)
        raise KeyError('Flight not found.')

    def do_put(self, context, descriptor, reader, writer):
        key = FlightServer.descriptor_to_key(descriptor)
        log.info(f'adding key: {key}')
        self.flights[key] = reader.read_all()
        log.info(f'{key} has {self.flights[key].num_rows} rows and {self.flights[key].num_columns} columns')

    def do_get(self, context, ticket):
        key = ast.literal_eval(ticket.ticket.decode())
        if key not in self.flights:
            return None
        return pyarrow.flight.RecordBatchStream(self.flights[key])

    def list_actions(self, context):
        return [
            ("clear", "Clear the stored flights."),
            ("shutdown", "Shut down this server."),
        ]

    def do_action(self, context, action):
        if action.type == "clear":
            raise NotImplementedError(
                "{} is not implemented.".format(action.type))
        elif action.type == "healthcheck":
            pass
        elif action.type == "shutdown":
            yield pyarrow.flight.Result(pyarrow.py_buffer(b'Shutdown!'))
            # Shut down on background thread to avoid blocking current
            # request
            threading.Thread(target=self._shutdown).start()
        else:
            raise KeyError("Unknown action {!r}".format(action.type))

    def _shutdown(self):
        """Shut down after a delay."""
        log.info("Server is shutting down...")
        time.sleep(2)
        self.shutdown()


def start_producer(location, registry_address):
    server = FlightServer(location=location, registry_address=registry_address)
    server.connect_to_zookeeper()

    log.info(f'starting producer: {location}')
    server.serve()


# def start_server(host, location, tls_certificates, verify_client):
#     rpc_server = FlightServer(host, location, tls_certificates=tls_certificates, verify_client=verify_client)
#     log.info(f'starting server: {location}')
#     rpc_server.serve()



def start_producers(**kwargs):
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--host", type=str, default="localhost",
                            help="Address or hostname to listen on")
        parser.add_argument("--port", type=int, default=5005,
                            help="Port number to listen on")
        parser.add_argument("--tls", nargs=2, default=None,
                            metavar=('CERTFILE', 'KEYFILE'),
                            help="Enable transport-level security")
        parser.add_argument("--verify_client", type=bool, default=False,
                            help="enable mutual TLS and verify the client if True")

        args = parser.parse_args()
        args.host = kwargs.get("host", args.host)
        args.port = kwargs.get("port", args.port)

        tls_certificates = []
        scheme = "grpc+tcp"
        if args.tls:
            scheme = "grpc+tls"
            with open(args.tls[0], "rb") as cert_file:
                tls_cert_chain = cert_file.read()
            with open(args.tls[1], "rb") as key_file:
                tls_private_key = key_file.read()
            tls_certificates.append((tls_cert_chain, tls_private_key))

        location = "{}://{}:{}".format(scheme, args.host, args.port)

        # server = FlightServer(args.host, location, tls_certificates=tls_certificates, verify_client=args.verify_client)
        # log.info(f'serving on: {location}')
        # server.serve()

        registry_address = "zoo1:2181,zoo2:2182,zoo3:2183"
        registry_address = "localhost:2181,localhost:2182,localhost:2183"

        if platform.system() == "Windows":
            registry_address = "localhost:2181"
            producer_locations = [
                'grpc+tcp://localhost:50051',
                # 'grpc+tcp://localhost:50052',
                # 'grpc+tcp://localhost:50053',

            ]
        else:
            registry_address = "zoo1:2181"
            producer_locations = [
                # 'grpc+tcp://localhost:50051',
                # # 'grpc+tcp://localhost:50052',
                # # 'grpc+tcp://localhost:50053',

                'grpc+tcp://0.0.0.0:50051',
                # 'grpc+tcp://0.0.0.0:50052',
                # 'grpc+tcp://0.0.0.0:50053',
            ]


        # start producers
        start_producer(producer_locations[0], registry_address)
        #
        # processes = []
        # for pl in producer_locations:
        #     p = multiprocessing.Process(target=start_producer, args=(pl, registry_address))
        #     processes.append(p)
        #     p.start()


        # # start flight server
        # # p = multiprocessing.Process(target=start_server, args=(args.host, location, tls_certificates, args.verify_client))
        # # processes.append(p)
        # # p.start()
        #
        # rpc_server = FlightServer(args.host, location, tls_certificates=tls_certificates, verify_client=args.verify_client)
        # rpc_server.serve()

        return {f"started producers: {producer_locations}"}, 200
    except Exception as e:
        import traceback
        log.error(traceback.format_exc())
        return {"error": str(e)}, 500


def start_server(**kwargs):
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--host", type=str, default="localhost",
                            help="Address or hostname to listen on")
        parser.add_argument("--port", type=int, default=5005,
                            help="Port number to listen on")
        parser.add_argument("--tls", nargs=2, default=None,
                            metavar=('CERTFILE', 'KEYFILE'),
                            help="Enable transport-level security")
        parser.add_argument("--verify_client", type=bool, default=False,
                            help="enable mutual TLS and verify the client if True")

        args = parser.parse_args()
        args.host = kwargs.get("host", args.host)
        args.port = kwargs.get("port", args.port)

        tls_certificates = []
        scheme = "grpc+tcp"
        if args.tls:
            scheme = "grpc+tls"
            with open(args.tls[0], "rb") as cert_file:
                tls_cert_chain = cert_file.read()
            with open(args.tls[1], "rb") as key_file:
                tls_private_key = key_file.read()
            tls_certificates.append((tls_cert_chain, tls_private_key))

        location = "{}://{}:{}".format(scheme, args.host, args.port)

        # start flight server
        rpc_server = FlightServer(args.host, location, tls_certificates=tls_certificates,
                                  verify_client=args.verify_client)
        log.info(f'starting server: {location}')
        rpc_server.serve()

        return {f"started server: {location}"}, 200
    except Exception as e:
        import traceback
        log.error(traceback.format_exc())
        return {"error": str(e)}, 500


if __name__ == "__main__":
    start_producers()
