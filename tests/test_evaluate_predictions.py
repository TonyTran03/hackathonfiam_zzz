"""Known-answer checks for our evaluator."""
import unittest
import numpy as np
import pandas as pd
from tests.evaluate_predictions import evaluate_predictions, make_prediction_frame


class EvaluationChecks(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({
            "permno": [1, 2, 1, 2],
            "eom": ["2020-12-31"] * 2 + ["2021-01-31"] * 2,
            "ret_exc_lead1m": [0.1, 0.2, -0.2, -0.1],
        })

    def test_perfect_predictions(self):
        frame = make_prediction_frame(self.data, [0.1, 0.2, -0.2, -0.1])
        self.assertEqual(str(frame.loc[0, "target_month"]), "2021-01")
        stats = evaluate_predictions(frame)
        self.assertEqual(stats["mse"], 0)
        self.assertEqual(stats["mae"], 0)
        self.assertEqual(stats["oos_r2"], 1)
        self.assertAlmostEqual(stats["rank_ic"], 1)

    def test_zero_baseline(self):
        stats = evaluate_predictions(make_prediction_frame(self.data, np.zeros(4)))
        self.assertAlmostEqual(stats["mse"], 0.025)
        self.assertAlmostEqual(stats["mae"], 0.15)
        self.assertEqual(stats["oos_r2"], 0)
        self.assertTrue(np.isnan(stats["rank_ic"]))

    def test_monthly_ic(self):
        stats = evaluate_predictions(make_prediction_frame(self.data, [0.1, 0.2, 0.2, 0.1]))
        self.assertAlmostEqual(stats["rank_ic"], 0)
        self.assertEqual(len(stats["monthly_ic"]), 2)

    def test_missing_outcome(self):
        self.data.loc[0, "ret_exc_lead1m"] = np.nan
        stats = evaluate_predictions(make_prediction_frame(self.data, np.zeros(4)))
        self.assertEqual(stats["n_predictions"], 3)
        self.assertEqual(stats["n_missing_outcomes"], 1)

    def test_invalid_inputs(self):
        for values in ([1], [[1], [2], [3], [4]], [1, 2, 3, np.nan]):
            with self.assertRaises(ValueError):
                make_prediction_frame(self.data, values)
        frame = make_prediction_frame(self.data, np.zeros(4))
        with self.assertRaises(ValueError):
            evaluate_predictions(pd.concat([frame, frame]))


if __name__ == "__main__":
    unittest.main()
