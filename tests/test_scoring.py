import unittest

from rocalog.scoring import ControlScoreInput, calculate_score_summary


class TestScoring(unittest.TestCase):
    def test_weighted_scoring_and_semaphore(self):
        summary = calculate_score_summary(
            [
                ControlScoreInput("network", 1.0, 1.0),
                ControlScoreInput("software", 0.8, 1.0),
                ControlScoreInput("hardware", 0.5, 2.0),
            ]
        )
        self.assertAlmostEqual(summary.score_global, 70.0)
        self.assertEqual(summary.semaphore, "yellow")

    def test_critical_failure_forces_red(self):
        summary = calculate_score_summary(
            [
                ControlScoreInput("network", 0.9, 1.0),
                ControlScoreInput("software", 0.4, 2.0),
            ]
        )
        self.assertEqual(summary.semaphore, "red")


if __name__ == "__main__":
    unittest.main()
