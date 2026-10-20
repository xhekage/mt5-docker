import csv
import io
import json
import re
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'config'))
from candle_history import encode, range_rows
from start_fastapi_bridge import CandleRequest, app
from pydantic import ValidationError


class HistoryTests(unittest.TestCase):
    def test_chunking_and_serialization(self):
        class MT:
            TIMEFRAME_M1 = 1

            def symbol_select(self, *args):
                return True

        class Connection:
            def eval(self, query):
                start, end = map(int, re.search(r', (\d+), (\d+)\)', query).groups())
                return json.dumps([[t, 1, 2, 1, 2, 3, 0, 0]
                                   for t in range(100000, 1000000, 60) if start <= t <= end])

        @contextmanager
        def terminal():
            yield MT(), Connection()

        payload = CandleRequest(symbol='XAUUSD', timeframe='m1', date_from=100000, date_to=1000000)
        rows = list(range_rows(payload, terminal))
        self.assertGreater(len(rows), 10000)
        self.assertEqual(len(rows), len({r['time'] for r in rows}))
        payload.order = 'desc'
        self.assertEqual(list(range_rows(payload, terminal)), rows[::-1])
        self.assertEqual(json.loads(''.join(encode(iter(rows), 'json'))), rows)
        self.assertEqual(len(list(csv.DictReader(io.StringIO(''.join(encode(iter(rows), 'csv')))))), len(rows))
        self.assertEqual(''.join(encode(iter([]), 'json')), '[]')

    def test_validation_and_schema(self):
        for extra in [{'count': 10001}, {'offset': 1}, {'timeframe': 'BAD'}]:
            with self.assertRaises(ValidationError):
                CandleRequest(**({'symbol': 'XAUUSD', 'timeframe': 'M1', 'date_from': 1, 'date_to': 2} | extra))
        schema = app.openapi()
        for path in ['/history/candles', '/history/candles/export']:
            self.assertIn('Request parameters', schema['paths'][path]['post']['description'])
        self.assertEqual(set(schema['components']['schemas']['CandleRequest']['required']), {'symbol', 'timeframe'})


if __name__ == '__main__':
    unittest.main()
