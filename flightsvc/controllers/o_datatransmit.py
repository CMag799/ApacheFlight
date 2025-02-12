import os
import pyarrow
from dotenv import load_dotenv
from sys import getsizeof
import pyarrow.flight as flight
import timeit
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)
load_dotenv()


class DataTransmitter:
    """
    Class for transmitting data using various methods.
    """

    def __init__(self):
        self.valid_transmit_methods = ['REST', 'FLIGHT']

    def transmit(self, transmit_method, payload, head=None):
        """
        Transmits data using the specified method.

        Args:
            transmit_method (str): The transmission method ('REST' or 'FLIGHT').
            payload (dict): The data to be transmitted.
            head (dict, optional): Additional headers for the transmission. Defaults to None.

        Raises:
            ValueError: If the transmit method is invalid.

        Returns:
            The result of the transmission.
        """
        if transmit_method not in self.valid_transmit_methods:
            raise ValueError(f"Invalid transmit method: {transmit_method}")

        if transmit_method == 'REST':
            return self.transmit_rest(payload, head)
        elif transmit_method == 'FLIGHT':
            return self.transmit_flight(payload, head)

    def transmit_rest(self, payload, head):
        """
        Transmits data using the REST method.

        Args:
            payload (dict): The data to be transmitted.
            head (dict, optional): Additional headers for the transmission. Defaults to None.

        Returns:
            The result of the transmission.
        """
        return payload

    def transmit_flight(self, payload, head):
        """
        Transmits data using the Flight method.

        Args:
            payload (dict): The data to be transmitted.
            head (dict, optional): Additional headers for the transmission. Defaults to None.

        Raises:
            ValueError: If the destination is invalid or the environment variable for FLIGHT_URL is not defined.

        Returns:
            None
        """
        destination = payload.get('destination', None)
        table_name = payload.get('table_name', None)
        table_metadata = payload.get('table_metadata', None)
        table = payload.get('table', None)

        destination_url = os.environ.get(f'FLIGHT_URL_{destination.upper()}', None)

        if not destination_url:
            raise ValueError(f"Invalid destination, please define environment variable for FLIGHT_URL_{destination.upper()}")

        client = flight.FlightClient(destination_url)
        descriptor = flight.FlightDescriptor.for_command(table_name)
        table_size_mb = round(getsizeof(table) / 1024 / 1024, 5)

        # transmit the table
        tic_write = timeit.default_timer()
        writer, reader = client.do_put(descriptor, table.schema)
        writer.write_table(table)
        writer.close()

        toc_write = timeit.default_timer()
        log.info(
            f'table of: {table.num_rows} rows, {table.num_columns} cols, '
            f'{table_size_mb} MB transmitted in {(toc_write - tic_write):.2f} seconds')

        table = None


class DataProcessor:
    """
    Class for processing data.
    """

    def duplicate_columns(self, table, x):
        """
        Duplicates columns in the table.

        Args:
            table (pyarrow.Table): The input table.
            x (int): The number of times to duplicate each column.

        Returns:
            pyarrow.Table: The table with duplicated columns.
        """
        new_cols = []
        for _ in range(x):
            for col in table.columns:
                new_col_name = f'{col._name}_{_}'
                new_cols.append(pyarrow.field(new_col_name, col.type))
        all_cols = list(table.schema) + new_cols
        new_schema = pyarrow.schema(all_cols)
        new_arrays = [*table, *[table[col.name[:col.name.rfind('_')]] for col in new_cols]]

        return pyarrow.Table.from_arrays(new_arrays, schema=new_schema)

    def generate_rows(self, table, x):
        """
        Generates new rows by concatenating the table with itself.

        Args:
            table (pyarrow.Table): The input table.
            x (int): The number of times to concatenate the table.

        Returns:
            pyarrow.Table: The table with generated rows.
        """
        for _ in range(x):
            table = pyarrow.concat_tables([table] * 2)
        return table


if __name__ == '__main__':
    data_processor = DataProcessor()
    data_transmitter = DataTransmitter()

    table = pyarrow.Table.from_arrays(
        [
            pyarrow.array(["AAPL", "GOOG", "MSFT"]),
            pyarrow.array([1672345600, 1672345600, 1672345600]),  # Timestamps
            pyarrow.array([150.0, 110.0, 250.0])
        ],
        names=["symbol", "timestamp", "price"]
    )

    table = data_processor.duplicate_columns(table, 10)
    table = data_processor.generate_rows(table, 15)

    payload = {
        'destination': 'overlay',
        'table_name': 'stock_prices',
        'table_metadata': {
            'select_fields': [],
            'filters': {},
        },
        'table': table
    }
    res = data_transmitter.transmit('FLIGHT', payload, None)