import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from liquidity_measurement.collector import record_session


class CollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_writer_failure_stops_recording_without_hanging(self):
        def failed_writer(_):
            raise OSError("simulated disk failure")
        with tempfile.TemporaryDirectory() as temporary:
            with patch("liquidity_measurement.collector.connect", side_effect=OSError("offline")):
                with self.assertRaisesRegex(OSError, "simulated disk failure"):
                    await record_session(Path(temporary) / "raw", seconds=10, processor=failed_writer)
