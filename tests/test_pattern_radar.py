from contextlib import nullcontext
from datetime import date, timedelta
import importlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import game_analysis
import gerador_loterias as lottery
import pattern_radar as radar
import update_lottery_data as updater


class RadarTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        config = dict(lottery.LOTTERY_CONFIGS['megasena'])
        self.path = Path(self.directory.name) / 'results.csv'
        config.update(FILE_PATH=str(self.path), SKIP_ROWS=0)
        replacement = patch.dict(lottery.LOTTERY_CONFIGS, {'megasena': config})
        replacement.start()
        self.addCleanup(replacement.stop)
        radar._build_radar.cache_clear()
        game_analysis._read_draws.cache_clear()

    def write_profiles(self, profiles, contests=None, reverse=False):
        rows = []
        for index, even in enumerate(profiles):
            numbers = list(range(2, 2 * even + 1, 2)) + list(range(1, 2 * (6 - even), 2))
            row = {'Concurso': contests[index] if contests else index + 1,
                   'Data': (date(2025, 1, 1) + timedelta(days=index)).strftime('%d/%m/%Y')}
            row.update({f'bola {i + 1}': value for i, value in enumerate(numbers)})
            rows.append(row)
        pd.DataFrame(list(reversed(rows)) if reverse else rows).to_csv(self.path, index=False)

    def test_mathematical_distribution(self):
        for config in lottery.LOTTERY_CONFIGS.values():
            probabilities = radar.parity_probabilities(config['NUM_BALLS_TO_DRAW'], config['MAX_NUMBER'])
            self.assertAlmostEqual(sum(probabilities.values()), 1)
            self.assertTrue(all(value > 0 for value in probabilities.values()))
        self.assertAlmostEqual(radar.parity_probabilities(6, 60)[2], 0.23811937393560946)

    def test_transitions_and_conditional_sample(self):
        self.write_profiles([3, 2, 3, 2, 4], reverse=True)
        result = radar.get_radar('megasena', 3)
        self.assertEqual(result['latest']['even'], 4)
        self.assertEqual(result['selected']['sample'], 2)
        target = next(p for p in result['selected']['profiles'] if p['even'] == 2)
        self.assertEqual(target['matches'], 2)
        self.assertEqual(target['conditional_probability'], 1)
        self.assertAlmostEqual(target['historical_probability'], 2 / 5)
        self.assertEqual(radar.get_radar('megasena')['selected']['even'], 4)

    def test_gaps_are_not_treated_as_next_draw(self):
        self.write_profiles([3, 2, 4], contests=[1, 3, 4])
        result = radar.get_radar('megasena', 3)
        self.assertEqual(result['coverage']['valid_transitions'], 1)
        self.assertEqual(result['coverage']['excluded_gaps'], 1)
        self.assertEqual(result['selected']['sample'], 0)
        self.assertIsNone(result['selected']['profiles'][0]['conditional_probability'])

    def test_single_draw_and_unknown_source(self):
        self.write_profiles([3])
        result = radar.get_radar('megasena')
        self.assertEqual(result['selected']['sample'], 0)
        self.assertTrue(result['selected']['small_sample'])
        self.assertIsNone(result['validation']['model_brier'])
        for value in (-1, 7, True, '3'):
            with self.assertRaises(ValueError):
                radar.get_radar('megasena', value)

    def test_wilson_intervals(self):
        self.assertIsNone(radar.wilson_interval(0, 0))
        low, high = radar.wilson_interval(5, 10)
        self.assertAlmostEqual(low, 0.236593090512564)
        self.assertAlmostEqual(high, 0.763406909487436)
        self.assertAlmostEqual(radar.wilson_interval(0, 10)[0], 0)
        self.assertAlmostEqual(radar.wilson_interval(10, 10)[1], 1)

    def test_holdout_does_not_learn_from_future_results(self):
        draws = [(i + 1, '01/01/2025', value) for i, value in enumerate([0] * 7 + [6] * 3)]
        probabilities = radar.parity_probabilities(6, 60)
        result = radar.validate_chronologically(draws, probabilities)
        self.assertEqual(result['train_last_contest'], 7)
        self.assertEqual(result['test_first_contest'], 8)
        self.assertEqual(result['test_transitions'], 3)
        self.assertEqual(result['model_accuracy'], 0)
        first_model = {key: ((6 if key == 0 else 0) + radar.PRIOR_WEIGHT * value) / (6 + radar.PRIOR_WEIGHT)
                       for key, value in probabilities.items()}
        first_loss = sum((value - int(key == 6)) ** 2 for key, value in first_model.items())
        baseline_loss = sum((value - int(key == 6)) ** 2 for key, value in probabilities.items())
        self.assertAlmostEqual(result['model_brier'], (first_loss + 2 * baseline_loss) / 3)

    def test_radar_refreshes_without_restarting_after_csv_change(self):
        self.write_profiles([3, 2])
        first = radar.get_radar('megasena')
        self.write_profiles([3, 2, 4])
        second = radar.get_radar('megasena')
        self.assertNotEqual(first['data_updated_at'], second['data_updated_at'])
        self.assertEqual(second['latest']['contest'], 3)
        self.assertEqual(second['latest']['even'], 4)

    def test_updater_refreshes_radar_only_when_csv_changes(self):
        args = updater.parse_args(['--lottery', 'megasena', '--no-clean-backups', '--no-publish'])
        for path, expected in ((None, 0), (self.path, 1)):
            with patch.object(updater, 'update_lottery', return_value=path), patch.object(updater, 'refresh_radar') as refresh:
                self.assertEqual(updater.run_update_cycle(args), 0)
                self.assertEqual(refresh.call_count, expected)

    def test_watch_sleeps_and_retries_failed_cycle(self):
        with patch.object(updater, 'update_guard', return_value=nullcontext(True)), \
             patch.object(updater, 'run_update_cycle', side_effect=[1, 0]) as cycle, \
             patch.object(updater.time, 'sleep', side_effect=[None, KeyboardInterrupt]) as sleep:
            self.assertEqual(updater.main(['--watch', '--interval', '900', '--no-publish']), 0)
            self.assertEqual(cycle.call_count, 2)
            self.assertEqual(sleep.call_count, 2)
            sleep.assert_called_with(900)

    def test_watch_retries_unexpected_errors(self):
        with patch.object(updater, 'update_guard', return_value=nullcontext(True)), \
             patch.object(updater, 'run_update_cycle', side_effect=OSError('temporary')), \
             patch.object(updater.time, 'sleep', side_effect=KeyboardInterrupt) as sleep:
            self.assertEqual(updater.main(['--watch', '--no-publish']), 0)
            sleep.assert_called_once()

    def test_update_guard_blocks_concurrent_update(self):
        with updater.update_guard() as first:
            self.assertTrue(first)
            with updater.update_guard() as second:
                self.assertFalse(second)
        with updater.update_guard() as next_cycle:
            self.assertTrue(next_cycle)


class MonthRadarTests(unittest.TestCase):
    def raw(self, months, contests=None):
        return tuple(reversed([(contests[i] if contests else i + 1, '01/01/2026', (1, 2, 3, 4, 5, 6, 7), month)
                               for i, month in enumerate(months)]))

    def test_month_frequencies_transitions_and_uniform_reference(self):
        result = radar.build_month_radar(self.raw([1, 2, 1, 2, 3]))
        self.assertEqual(result['latest']['month'], 3)
        selected = result['groups'][1]
        self.assertEqual(selected['sample'], 2)
        february = selected['profiles'][1]
        self.assertEqual(february['matches'], 2)
        self.assertEqual(february['conditional_probability'], 1)
        self.assertEqual(february['historical_probability'], 2 / 5)
        self.assertAlmostEqual(sum(p['theoretical_probability'] for p in selected['profiles']), 1)
        self.assertTrue(all(p['theoretical_probability'] == 1 / 12 for p in selected['profiles']))
        self.assertIsNotNone(february['interval'])

    def test_missing_month_and_contest_gaps_do_not_bridge_transitions(self):
        result = radar.build_month_radar(self.raw([1, None, 2, 3], [1, 2, 3, 5]))
        self.assertEqual(result['coverage']['missing_months'], 1)
        self.assertEqual(result['coverage']['valid_transitions'], 0)
        self.assertEqual(result['groups'][1]['sample'], 0)
        self.assertIsNone(result['groups'][1]['profiles'][0]['conditional_probability'])

    def test_missing_latest_and_all_missing_months_are_explicit(self):
        result = radar.build_month_radar(self.raw([None, None]))
        self.assertIsNone(result['latest']['month'])
        self.assertEqual(result['coverage']['total_draws'], 0)
        self.assertIsNone(result['groups'][1]['profiles'][0]['historical_probability'])
        self.assertIsNone(result['validation']['model_brier'])

    def test_month_holdout_does_not_learn_future_months(self):
        result = radar.build_month_radar(self.raw([1] * 7 + [12] * 3))
        self.assertEqual(result['validation']['train_last_contest'], 7)
        self.assertEqual(result['validation']['model_accuracy'], 0)
        self.assertEqual(result['validation']['test_transitions'], 3)

    def test_selection_rejects_invalid_month_and_hides_internal_groups(self):
        snapshot = radar.build_radar_from_draws('diadesorte', self.raw([1, 2, 1]), 0, 1)
        with patch.object(radar, '_build_radar', return_value=snapshot):
            for month in (0, 13, True, '1'):
                with self.assertRaises(ValueError):
                    radar.get_radar('diadesorte', previous_month=month)
            result = radar.get_radar('diadesorte', previous_month=2)
            self.assertEqual(result['months']['selected']['month'], 2)
            self.assertNotIn('groups', result['months'])
            self.assertEqual(radar.get_radar('diadesorte')['months']['selected']['month'], 1)


class RadarRouteTests(unittest.TestCase):
    def test_premium_only_and_query_validation(self):
        module = importlib.import_module('app')
        client = module.app.test_client()
        for user, code in ((None, 401), ({'is_premium': False}, 403)):
            with patch.object(module, 'current_access_payload', return_value=user):
                self.assertEqual(client.get('/pattern_radar/megasena').status_code, code)
        with patch.object(module, 'current_access_payload', return_value={'is_premium': True}):
            for source in ('-1', 'x', '1.5', '999999', '٣'):
                self.assertEqual(client.get('/pattern_radar/megasena', query_string={'previous_even': source}).status_code, 400)
            self.assertEqual(client.get('/pattern_radar/invalid').status_code, 400)
            with patch.object(radar, 'get_radar', return_value={'latest': {'contest': 123}}) as service:
                response = client.get('/pattern_radar/megasena?previous_even=3')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                service.assert_called_once_with('megasena', 3)
            with patch.object(radar, 'get_radar', side_effect=game_analysis.HistoryUnavailable('Indisponível')):
                self.assertEqual(client.get('/pattern_radar/megasena').status_code, 503)

    def test_month_query_validation_and_premium_access(self):
        module = importlib.import_module('app')
        client = module.app.test_client()
        with patch.object(module, 'current_access_payload', return_value={'is_premium': True}):
            for month in ('0', '13', '-1', 'x', '1.5', '٣', ''):
                self.assertEqual(client.get('/pattern_radar/diadesorte', query_string={'previous_month': month}).status_code, 400)
            self.assertEqual(client.get('/pattern_radar/megasena?previous_month=1').status_code, 400)
            with patch.object(radar, 'get_radar', return_value={'months': {}}) as service:
                response = client.get('/pattern_radar/diadesorte?previous_month=12')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                service.assert_called_once_with('diadesorte', None, 12)


if __name__ == '__main__':
    unittest.main()
