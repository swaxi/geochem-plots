"""
Tests for ree_lambdas (O'Neill 2016 REE shape coefficients). No QGIS needed:

    python -m unittest discover -s tests
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ree_lambdas as rl  # noqa: E402

# O'Neill (2016) Table 1: f1, f2 (x1e-3), f3 (x1e-3), f4 (x1e-6) for each REE.
TABLE_1_TERMS = {
    'La': (0.1052, 4.913, 0.243, 8.29), 'Ce': (0.0882, 2.033, -0.031, -7.16),
    'Pr': (0.0712, -0.270, -0.172, -7.98), 'Nd': (0.0542, -1.994, -0.208, -1.99),
    'Sm': (0.0242, -3.627, -0.108, 8.64), 'Eu': (0.0112, -3.776, -0.032, 9.67),
    'Gd': (-0.0018, -3.587, 0.043, 7.91), 'Tb': (-0.0148, -3.059, 0.105, 3.82),
    'Dy': (-0.0278, -2.194, 0.142, -1.45), 'Ho': (-0.0398, -1.095, 0.140, -5.80),
    'Er': (-0.0508, 0.165, 0.101, -7.63), 'Tm': (-0.0608, 1.521, 0.026, -5.90),
    'Yb': (-0.0698, 2.912, -0.078, -0.16), 'Lu': (-0.0778, 4.284, -0.203, 9.41),
}

# Kimberlite of O'Neill (2016) Fig. 1b.
KIMBERLITE = [3.68, 27.4, -54.0, -544.0, 5172.0]


def pattern(lambdas, elements=rl.ONEILL_2016_RADII):
    """Concentrations (ppm) of a perfectly smooth pattern with `lambdas`."""
    return {e: rl.ONEILL_2016_CI_CHONDRITE[e] * math.exp(
                sum(l * f for l, f in zip(lambdas, rl.orthogonal_terms(rl.ONEILL_2016_RADII[e]))))
            for e in elements}


class OrthogonalTermsTests(unittest.TestCase):

    def test_matches_table_1(self):
        for element, (f1, f2, f3, f4) in TABLE_1_TERMS.items():
            _, g1, g2, g3, g4 = rl.orthogonal_terms(rl.ONEILL_2016_RADII[element])
            self.assertAlmostEqual(g1, f1, delta=1e-4, msg=element)
            self.assertAlmostEqual(g2 * 1e3, f2, delta=2e-3, msg=element)
            self.assertAlmostEqual(g3 * 1e3, f3, delta=2e-3, msg=element)
            self.assertAlmostEqual(g4 * 1e6, f4, delta=2e-2, msg=element)

    def test_orthogonal_over_13_ree(self):
        rows = [rl.orthogonal_terms(rl.ONEILL_2016_RADII[e]) for e in rl.FIT_ELEMENTS]
        for i in range(rl.N_COEFFICIENTS):
            for j in range(i + 1, rl.N_COEFFICIENTS):
                dot = sum(r[i] * r[j] for r in rows)
                norm = math.sqrt(sum(r[i] ** 2 for r in rows) * sum(r[j] ** 2 for r in rows))
                self.assertLess(abs(dot) / norm, 1e-3, (i, j))


class FitTests(unittest.TestCase):

    def test_recovers_smooth_pattern(self):
        lambdas, reason = rl.fit_lambdas(pattern(KIMBERLITE))
        self.assertIsNone(reason)
        for got, expected in zip(lambdas, KIMBERLITE):
            self.assertAlmostEqual(got, expected, delta=1e-6 * max(1, abs(expected)))

    def test_flat_bse_pattern(self):
        # Bulk Silicate Earth: 2.83 x CI, Lambda = {ln(2.83), 0, 0, 0, 0}.
        bse = {e: 2.83 * ci for e, ci in rl.ONEILL_2016_CI_CHONDRITE.items()}
        lambdas, _ = rl.fit_lambdas(bse)
        self.assertAlmostEqual(lambdas[0], math.log(2.83), places=9)
        for value in lambdas[1:]:
            self.assertAlmostEqual(value, 0.0, places=6)

    def test_eu_is_ignored(self):
        data = pattern(KIMBERLITE)
        data['Eu'] *= 5  # strong positive Eu anomaly
        lambdas, _ = rl.fit_lambdas(data)
        self.assertAlmostEqual(lambdas[1], KIMBERLITE[1], places=6)

    def test_lambda0_is_mean_of_logs_for_full_pattern(self):
        data = pattern([2.5, -3.0, -30.0, 0.0, 0.0])
        data['Sm'] *= 1.1  # make it slightly non-smooth
        lambdas, _ = rl.fit_lambdas(data)
        mean_ln = sum(math.log(data[e] / rl.ONEILL_2016_CI_CHONDRITE[e])
                      for e in rl.FIT_ELEMENTS) / len(rl.FIT_ELEMENTS)
        self.assertAlmostEqual(lambdas[0], mean_ln, places=3)

    def test_missing_monoisotopic_ree(self):
        # Pr, Tb, Ho and Tm missing (as in ID-TIMS data): still fitted.
        data = pattern(KIMBERLITE, [e for e in rl.FIT_ELEMENTS if e not in ('Pr', 'Tb', 'Ho', 'Tm')])
        lambdas, reason = rl.fit_lambdas(data)
        self.assertIsNone(reason)
        self.assertAlmostEqual(lambdas[2], KIMBERLITE[2], places=4)

    def test_not_enough_ree(self):
        data = pattern(KIMBERLITE, ['La', 'Ce', 'Nd', 'Sm', 'Yb'])
        lambdas, reason = rl.fit_lambdas(data)
        self.assertIsNone(lambdas)
        self.assertIn('at least 6', reason)

    def test_non_positive_values_ignored(self):
        data = pattern(KIMBERLITE, ['La', 'Ce', 'Nd', 'Sm', 'Gd', 'Yb'])
        data['Gd'] = -0.05  # below detection limit
        lambdas, reason = rl.fit_lambdas(data)
        self.assertIsNone(lambdas)
        self.assertIsNotNone(reason)

    def test_needs_both_ends_of_pattern(self):
        _, reason = rl.fit_lambdas(pattern(KIMBERLITE, ['Sm', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Yb']))
        self.assertIn('LREE', reason)
        _, reason = rl.fit_lambdas(pattern(KIMBERLITE, ['La', 'Ce', 'Pr', 'Nd', 'Sm', 'Gd', 'Dy']))
        self.assertIn('HREE', reason)


if __name__ == '__main__':
    unittest.main()
