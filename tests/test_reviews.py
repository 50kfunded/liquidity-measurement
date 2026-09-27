import tempfile
import unittest
from pathlib import Path

from liquidity_measurement.reviews import read_reviews


class ReviewTests(unittest.TestCase):
    def test_blank_template_is_not_counted_as_manual_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "reviews.csv"
            path.write_text("event_id,reviewed_label,reviewer,reason\none,,,\n")
            self.assertEqual(read_reviews([{"id": "one"}], path), {})

    def test_review_keeps_the_automatic_result(self):
        event = {"id": "one", "classification": "uncertain"}
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "reviews.csv"
            path.write_text("event_id,reviewed_label,reviewer,reason\none,feed_problem,reviewer,missing snapshot\n")
            reviews = read_reviews([event], path)
            self.assertEqual(reviews["one"]["reviewed_label"], "feed_problem")
            self.assertEqual(event["classification"], "uncertain")
