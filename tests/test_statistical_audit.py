from datetime import date, timedelta
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.stats import binom, false_discovery_control

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import pattern_radar
import public_reports
import statistical_audit as audit


def draws_for(sequences, contests=None):
    return tuple(reversed([(contests[i] if contests else i + 1, (date(2026, 1, 1) + timedelta(days=i)).strftime('%d/%m/%Y'), tuple(numbers), None)
                           for i, numbers in enumerate(sequences)]))


class StatisticalAuditTests(unittest.TestCase):
    def test_pair_counts_do_not_overflow_and_fdr_tests_every_pair(self):
        draws = draws_for([[1, 2, 3, 4, 5, 6]] * 140)
        result = audit.audit_draws('megasena', draws, 19)
        self.assertEqual(audit.pair_counts([row[2] for row in draws], 60)[0, 1], 140)
        self.assertEqual(result['family_size'], 1770)
        expected_p = binom.sf(139, 140, 6 * 5 / (60 * 59))
        ps = np.ones(1770); ps[:15] = expected_p
        self.assertAlmostEqual(result['q_values'][0][1], false_discovery_control(ps, method='by')[0])
        self.assertEqual(result['q_values'][0][0], 1)
        self.assertTrue(result['stable_positive'][0][1])

    def test_monte_carlo_is_reproducible_and_never_reports_zero_p(self):
        draws = draws_for([[1, 2, 3, 4, 5, 6]] * 40)
        one = audit.audit_draws('megasena', draws, 19, 123)
        self.assertEqual(one, audit.audit_draws('megasena', draws, 19, 123))
        self.assertGreaterEqual(one['global_p_value'], 1 / 20)
        self.assertLessEqual(one['global_p_value'], 1)
        balanced = next(strategy for strategy in one['strategies'] if strategy['mode'] == 'balanced_parity')
        self.assertEqual(balanced['observed'], 40)
        self.assertTrue(0 <= balanced['q_value'] <= 1)

    def test_vectorized_strategy_definitions_match_existing_generator(self):
        from math import comb
        import gerador_loterias as lottery
        rng = np.random.default_rng(123)
        for kind, config in lottery.LOTTERY_CONFIGS.items():
            count, maximum = config['NUM_BALLS_TO_DRAW'], config['MAX_NUMBER']
            incidence = rng.multivariate_hypergeometric(np.ones(maximum, dtype=int), count, size=30)
            modes = [mode for mode in ('balanced_parity', 'even_only', 'odd_only', 'spread', 'lucky_dates', 'high_numbers') if lottery.is_generation_mode_available_for_lottery(mode, kind)]
            vectorized = audit.strategy_counts(incidence, modes, count, maximum)
            for mode in modes:
                expected = sum(bool(lottery.strategy_matches_historical_draw((np.flatnonzero(row) + 1).tolist(), mode, config)) for row in incidence)
                self.assertEqual(vectorized[mode], expected)
                self.assertTrue(0 < audit.strategy_reference(mode, count, maximum) <= 1)
        self.assertAlmostEqual(audit.strategy_reference('spread', 6, 60), 5 * comb(12, 2) * 12 ** 4 / comb(60, 6))

    def test_gaps_and_absent_numbers_do_not_get_invented_intervals(self):
        draws = draws_for([[1, 2, 3, 4, 5, 6], [10, 11, 12, 13, 14, 15]], [1, 3])
        result = audit.draw_intervals('megasena', draws)
        self.assertIsNone(result[0]['gap'])
        self.assertIsNone(result[59]['gap'])
        self.assertEqual(result[9]['gap'], 0)
        self.assertEqual(result[9]['tail_probability'], 1)

    def test_walk_forward_has_no_future_training_or_overlapping_tests(self):
        draws = [(i + 1, '01/01/2026', 0 if i < 6 else 6) for i in range(10)]
        baseline = pattern_radar.parity_probabilities(6, 60)
        result = pattern_radar.walk_forward_validation(draws, baseline)
        self.assertEqual(len(result['folds']), 3)
        self.assertEqual(result['sample'], 6)
        changed = draws[:6] + [(i + 1, '01/01/2026', 3) for i in range(6, 10)]
        self.assertEqual(result['folds'][0], pattern_radar.walk_forward_validation(changed, baseline)['folds'][0])
        for left, right in zip(result['folds'], result['folds'][1:]):
            self.assertLess(left['test_last_contest'], right['test_first_contest'])
        self.assertTrue(all(fold['train_last_contest'] < fold['test_first_contest'] for fold in result['folds']))

    def test_fingerprints_are_line_ending_independent_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'results.csv'
            path.write_bytes(b'a,b\r\n1,2\r\n')
            first = public_reports._fingerprint(str(path), 1, path.stat().st_size)
            path.write_bytes(b'a,b\n1,2\n')
            self.assertEqual(first, public_reports._fingerprint(str(path), 2, path.stat().st_size))
            with patch.object(public_reports, 'REPORT_PATH', Path(directory) / 'missing.json'):
                self.assertEqual(public_reports.get_report('megasena')['status'], 'unavailable')

    def test_reporting_route_is_private_read_only_and_does_not_compute(self):
        import app
        client = app.app.test_client()
        for user, code in ((None, 401), ({'is_premium': False}, 403)):
            with patch.object(app, 'current_access_payload', return_value=user):
                self.assertEqual(client.get('/statistical_report/megasena').status_code, code)
        with patch.object(app, 'current_access_payload', return_value={'is_premium': True}), patch.object(public_reports, 'get_report', return_value={'status': 'pending'}):
            result = client.get('/statistical_report/megasena')
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.headers['Cache-Control'], 'no-store')
        self.assertEqual(client.post('/statistical_report/megasena').status_code, 405)


if __name__ == '__main__':
    unittest.main()
