import pyarrow
from sys import getsizeof
import pyarrow.flight as flight
import timeit
import logging

host = "localhost"  # Replace with the actual host
port = "5005"  # Replace with the actual port

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

def duplicate_columns(table, x):
    new_cols = []
    for _ in range(x):
        for col in table.columns:
            new_col_name = f'{col._name}_{_}'
            new_cols.append(pyarrow.field(new_col_name, col.type))
    all_cols = list(table.schema) + new_cols
    new_schema = pyarrow.schema(all_cols)
    new_arrays = [*table, *[table[col.name[:col.name.rfind('_')]] for col in new_cols]]

    return pyarrow.Table.from_arrays(new_arrays, schema=new_schema)


def generate_rows(table, x):
    for _ in range(x):
        table = pyarrow.concat_tables([table] * 2)
    return table


if __name__ == '__main__':

    client = flight.FlightClient(f"grpc://{host}:{port}")

    descriptor = flight.FlightDescriptor.for_command(b"get_test_data")

    table = pyarrow.Table.from_arrays(
        [
            pyarrow.array(["AAPL", "GOOG", "MSFT"]),
            pyarrow.array([1672345600, 1672345600, 1672345600]),  # Timestamps
            pyarrow.array([150.0, 110.0, 250.0])
        ],
        names=["symbol", "timestamp", "price"]
    )

    table = duplicate_columns(table, 10)

    table = generate_rows(table, 20)

    table_size_mb = round(getsizeof(table) / 1024 / 1024, 5)

    # transmit the table
    tic_write = timeit.default_timer()
    writer, reader = client.do_put(descriptor, table.schema)
    writer.write_table(table)
    writer.close()

    toc_write = timeit.default_timer()
    log.info(
        f'table of: {table.num_rows} rows, {table.num_columns} cols, '
        f'{table_size_mb} MB sent in {(toc_write - tic_write):.2f} seconds')

    table = None

    flights = list(client.list_flights())

    for f in flights:
        log.info(f'flights currently available: {f.descriptor.command}, columns: {f.schema.names}')

    descriptor = flight.FlightDescriptor.for_command(b"get_test_data")
    flight_info = client.get_flight_info(descriptor)

    # retrieve the table
    tic_read = timeit.default_timer()
    for endpoint in flight_info.endpoints:
        reader = client.do_get(endpoint.ticket)
        table = reader.read_all()
        # print(table.to_pandas().head())

    toc_read = timeit.default_timer()
    log.info(
        f'table of: {table.num_rows} rows, {table.num_columns} cols, '
        # f'{table_size_mb} MB retrieved in {round(toc_read - tic_read, 4)} seconds')
        f'{table_size_mb} MB retrieved in {(toc_read - tic_read):.2f} seconds')

    client.close()
