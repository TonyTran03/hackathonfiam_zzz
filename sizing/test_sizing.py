"""Small deterministic checks of optimization, timing and trading accounting."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
import tempfile
import json

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cvxpy as cp
from optimizer.constraints import SETTINGS, build_constraints
from _engine import account, covariance_for, sizing_inputs, solve_weights, summarize, load_stages
from _engine import new_run_folder, run_number, write_constraints_note


def fixture():
    return pd.DataFrame({
        'score': [1., .8, -.9, -1.1], 'side': [1., 1., -1., -1.],
        'beta_use': [1.2, .8, .9, 1.1], 'size': [-1., 1., -1., 1.],
        'sector': ['A', 'B', 'A', 'B'], 'rvol_21d': [.02] * 4,
    }, index=pd.Index([1, 2, 3, 4], name='permno'))


class SizingTests(unittest.TestCase):
    def test_beta_matched_reference_caps_and_beta_balance(self):
        stages = load_stages('beta_matched')
        settings = stages['constraints'].SETTINGS
        g = fixture()
        weights = stages['constraints'].size_positions(g, settings)
        self.assertLessEqual(weights.abs().max(), settings.position_limit + 1e-12)
        self.assertLessEqual(weights.abs().sum(), settings.gross_limit + 1e-12)
        self.assertAlmostEqual(float(weights @ g.beta_use), 0., places=10)

    def test_inverse_vol_reference_redistributes_capped_weights(self):
        sizing = load_stages('beta_matched')['constraints']
        weights = sizing.capped_inverse_vol(np.array([.001, .1, .1]), .03, .015)
        self.assertAlmostEqual(weights.sum(), .03)
        self.assertLessEqual(weights.max(), .015 + 1e-12)
        self.assertGreater(weights[0], weights[1])

    def test_numbered_runs_and_historical_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            old = parent / '20261028T120000Z'
            old.mkdir()
            (old / 'run.json').write_text(json.dumps({'constraints_source': 'LIMIT = 0.1'}))
            self.assertEqual(new_run_folder(parent).name, '2')
            self.assertIn('LIMIT = 0.1', (parent / '1/constraints.md').read_text())
            (parent / '10').mkdir()
            self.assertEqual(new_run_folder(parent).name, '11')
            self.assertEqual(sorted([parent / '10', parent / '2'], key=run_number)[-1].name, '10')

    def test_constraints_note_uses_recorded_source(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            write_constraints_note(out, {'settings': {'beta_limit': 0.1},
                                        'step_sources': {'constraints.py': 'EXACT_RULE = 123'}})
            note = (out / 'constraints.md').read_text()
            self.assertIn('EXACT_RULE = 123', note)
            self.assertIn('"beta_limit": 0.1', note)

    def test_editable_ranking_can_use_an_added_feature(self):
        stages = load_stages('optimizer')
        rng = np.random.default_rng(17)
        frame = pd.DataFrame({'permno': np.arange(20), 'target_month': '2021-01',
                              'forecast': rng.normal(size=20), 'extra': rng.normal(size=20),
                              'me': np.arange(1, 21), 'beta_use': rng.uniform(.5, 1.5, 20),
                              'sector': ['A', 'B'] * 10})
        features = stages['features'].add_features(frame)
        pd.testing.assert_frame_equal(features, frame)
        original = stages['ranking'].build_ranking(features, SETTINGS)
        stages['ranking'].SIGNAL_WEIGHTS = {'extra': .5}
        changed = stages['ranking'].build_ranking(features, SETTINGS)
        self.assertGreater(np.linalg.norm(original.score - changed.score), .1)

    def test_price_only_selection_has_no_extra_eligibility_filters(self):
        step = load_stages('price_only')['selection']
        frame = pd.DataFrame({'target_month': ['2021-01'] * 4,
                              'prc': [5., 6., 7., 4.], 'me': [1., 10., np.nan, 1.],
                              'beta_use': [np.nan, 1., 1., 1.], 'rvol_21d': [0., .02, .02, .02],
                              'size_grp': ['nano', 'micro', 'small', 'large']})
        eligible = step.prepare_universe(frame, SETTINGS)
        self.assertEqual(len(eligible), 3)
        self.assertEqual(eligible.size_grp.tolist(), ['nano', 'micro', 'small'])

    def test_comparison_with_legacy_only_columns(self):
        g = fixture()
        weights = pd.Series([.05, .05, -.05, -.05], index=g.index)
        row, _, _, _ = account('2021-01', g, weights, pd.Series(dtype=float),
                               pd.Series(0., index=g.index), .001, np.eye(4) * .01, SETTINGS)
        current = {**row, 'method': 'optimizer', 'market_return': .01}
        old = {**row, 'method': 'old_sizing', 'market_return': .01, 'shorts_below_500m': 7}
        result = summarize(pd.DataFrame([current, old])).set_index('method')
        self.assertEqual(result.loc['old_sizing', 'max_shorts_below_500m'], 7)
        self.assertTrue(pd.isna(result.loc['optimizer', 'max_shorts_below_500m']))

    def test_undecided_bounds_are_disabled_and_size_can_be_enabled(self):
        g = fixture()
        inputs = sizing_inputs(g, pd.Series(dtype=float), SETTINGS)
        rules = build_constraints(cp.Variable(4), inputs, SETTINGS)
        for name in ('market_beta', 'sector', 'size', 'turnover'):
            self.assertNotIn(name, rules)
        settings = replace(SETTINGS, size_limit=0.)
        weights, _, _ = solve_weights(g, np.eye(4) * .01, inputs, settings)
        self.assertLessEqual(abs(weights @ g['size']), 1e-6)

    def test_exact_beta_sector_and_turnover_with_forced_exit(self):
        g = fixture()
        settings = replace(SETTINGS, position_limit=.05, beta_limit=0., sector_limit=0.,
                           turnover_limit=.15)
        previous = pd.Series({99: .01})
        inputs = sizing_inputs(g, previous, settings)
        weights, checks, _ = solve_weights(g, np.eye(4) * .01, inputs, settings)
        self.assertGreater(weights.abs().sum(), .01)
        self.assertLessEqual(abs(weights @ g.beta_use), 1e-6)
        self.assertLessEqual(weights.groupby(g.sector).sum().abs().max(), 1e-6)
        self.assertLessEqual(weights.abs().sum() + .01, .15 + 1e-6)
        self.assertLessEqual(max(c['max_violation'] for c in checks), 1e-6)

    def test_impossible_turnover_fails_instead_of_relaxing(self):
        g = fixture()
        settings = replace(SETTINGS, turnover_limit=.01)
        inputs = sizing_inputs(g, pd.Series({99: .1}), settings)
        with self.assertRaisesRegex(ValueError, 'infeasible'):
            solve_weights(g, np.eye(4) * .01, inputs, settings)

    def test_covariance_cannot_see_target_or_future_returns(self):
        rng = np.random.default_rng(4)
        history = pd.DataFrame(rng.normal(0, .05, (40, 4)),
                               index=pd.period_range('2018-01', periods=40, freq='M').astype(str),
                               columns=fixture().index)
        first, audit = covariance_for(history, '2021-01', fixture(), SETTINGS)
        history.loc[history.index >= '2021-01'] = 1000
        second, _ = covariance_for(history, '2021-01', fixture(), SETTINGS)
        np.testing.assert_array_equal(first, second)
        self.assertLess(audit['history_end'], '2021-01')
        self.assertGreater(np.linalg.eigvalsh(first).min(), 0)

    def test_turnover_drift_and_cash_for_zero_return_stocks(self):
        g = fixture()
        weights = pd.Series([.05, .05, -.05, -.05], index=g.index)
        previous = pd.Series({1: .04, 99: -.02})
        realized = pd.Series(0., index=g.index)
        row, drifted, _, _ = account('2021-01', g, weights, previous, realized,
                                     .001, np.eye(4) * .01, SETTINGS)
        expected_turnover = .01 + .05 + .05 + .05 + .02
        self.assertAlmostEqual(row['turnover'], expected_turnover)
        self.assertAlmostEqual(row['one_way_turnover'], expected_turnover / 2)
        self.assertAlmostEqual(row['total_net'], .001 - expected_turnover * .002)
        np.testing.assert_allclose(drifted, weights / (1 + row['total_net']))


if __name__ == '__main__':
    unittest.main()
