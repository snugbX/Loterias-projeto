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
import game_comparison as comparison
import gerador_loterias as lottery


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        game_analysis._read_draws.cache_clear()

    def seed(self, kind, draws, months=None):
        config = dict(lottery.LOTTERY_CONFIGS[kind])
        path = Path(self.directory.name) / f'{kind}.csv'
        records = []
        for index, numbers in enumerate(draws):
            row = {'Concurso': index + 1, 'Data': (date(2026, 1, 1) + timedelta(days=index)).strftime('%d/%m/%Y')}
            row.update({f'bola {i + 1}': number for i, number in enumerate(numbers)})
            if months:
                row['Mês da Sorte'] = months[index]
            records.append(row)
        pd.DataFrame(records).to_csv(path, index=False)
        config.update(FILE_PATH=str(path), SKIP_ROWS=0)
        replacement = patch.dict(lottery.LOTTERY_CONFIGS, {kind: config})
        replacement.start()
        self.addCleanup(replacement.stop)

    def test_single_game_matches_existing_analysis_for_all_lotteries(self):
        for kind, config in lottery.LOTTERY_CONFIGS.items():
            numbers = list(range(1, config['NUM_BALLS_TO_DRAW'] + 1))
            self.seed(kind, [numbers], ['Janeiro'] if kind == 'diadesorte' else None)
            game = {'numbers': numbers, **({'month': 1} if kind == 'diadesorte' else {})}
            result = comparison.analyze_games(kind, {'games': [game]})
            original = game_analysis.analyze_game(kind, game)
            self.assertEqual(result['analyses'][0]['history'], original['history'])
            self.assertEqual(result['summary']['historical_prize_draws'], 1)
            self.assertEqual(result['summary']['numeric_jackpot_one_in'], original['probabilities']['jackpot_one_in'])

    def test_duplicate_permutations_do_not_inflate_coverage(self):
        game = {'numbers': [1, 2, 3, 4, 5, 6]}
        other = {'numbers': [10, 20, 30, 40, 50, 60]}
        self.seed('megasena', [game['numbers'], other['numbers']])
        result = comparison.analyze_games('megasena', {'games': [game, {'numbers': list(reversed(game['numbers']))}, other]})
        summary = result['summary']
        self.assertEqual(summary['unique_games'], 2)
        self.assertEqual(summary['duplicate_groups'], [[1, 2]])
        self.assertEqual(summary['unique_number_combinations'], 2)
        self.assertAlmostEqual(summary['numeric_jackpot_probability'], 2 / 50063860)
        self.assertEqual(summary['historical_prize_draws'], 2)
        self.assertTrue(result['pairs'][0]['duplicate'])
        self.assertEqual(result['pairs'][0]['overlap_percentage'], 100)
        self.assertEqual(result['pairs'][1]['common_numbers'], [])

    def test_historical_union_not_sum_and_not_limited_to_recent_thirty(self):
        numbers = [1, 2, 3, 4, 5, 6]
        self.seed('megasena', [numbers] * 40)
        result = comparison.analyze_games('megasena', {'games': [{'numbers': numbers}, {'numbers': [1, 2, 3, 4, 7, 8]}]})
        self.assertEqual(result['summary']['historical_prize_draws'], 40)
        self.assertEqual(result['summary']['historical_percentage'], 100)
        self.assertEqual(len(result['analyses'][0]['history']['recent_occurrences']), 30)
        self.assertEqual(result['summary']['historical_leaders'], [1, 2])
        self.assertEqual(result['pairs'][0]['common_numbers'], [1, 2, 3, 4])

    def test_months_are_individual_and_numeric_jackpot_is_deduplicated(self):
        numbers = list(range(1, 8))
        self.seed('diadesorte', [numbers, list(range(10, 17))], ['Janeiro', 'Fevereiro'])
        result = comparison.analyze_games('diadesorte', {'games': [
            {'numbers': numbers, 'month': 1}, {'numbers': numbers, 'month': 2}, {'numbers': numbers, 'month': 2},
        ]})
        self.assertEqual(result['summary']['unique_games'], 2)
        self.assertEqual(result['summary']['unique_number_combinations'], 1)
        self.assertAlmostEqual(result['summary']['month_coverage_probability'], 2 / 12)
        self.assertEqual(result['summary']['duplicate_groups'], [[2, 3]])
        self.assertFalse(result['pairs'][0]['duplicate'])
        self.assertFalse(result['pairs'][0]['same_month'])
        self.assertTrue(result['pairs'][0]['same_numbers'])
        self.assertEqual(result['analyses'][0]['history']['month_matches'], 1)
        self.assertEqual(result['summary']['historical_prize_draws'], 2)

    def test_batch_uses_one_snapshot_and_returns_radar_context(self):
        self.seed('megasena', [[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 7, 8]])
        with patch.object(game_analysis, 'load_validated_history', wraps=game_analysis.load_validated_history) as load:
            result = comparison.analyze_games('megasena', {'games': [{'numbers': [1, 2, 3, 4, 5, 6]}] * 10})
        load.assert_called_once_with('megasena')
        self.assertEqual(len(result['pairs']), 45)
        self.assertEqual(result['radar']['latest']['contest'], 2)
        context = result['analyses'][0]['radar_context']
        self.assertEqual(context['sample'], 1)
        self.assertEqual(context['matches'], 1)
        self.assertTrue(context['small_sample'])

    def test_rejects_invalid_batches_before_reading_any_history(self):
        valid = {'numbers': [1, 2, 3, 4, 5, 6]}
        for payload in (None, [], {}, {'games': []}, {'games': [valid] * 11},
                        {'games': 'x'}, {'games': [valid, None]}, {'games': [valid, {'numbers': [True] * 6}]}):
            with self.subTest(payload=payload), patch.object(game_analysis, 'load_validated_history') as load:
                with self.assertRaises(ValueError):
                    comparison.analyze_games('megasena', payload)
                load.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'Jogo 2'):
            comparison.analyze_games('megasena', {'games': [valid, {}]})

    def test_existing_updates_are_reflected_on_next_comparison(self):
        game = {'numbers': [1, 2, 3, 4, 5, 6]}
        self.seed('megasena', [game['numbers']])
        first = comparison.analyze_games('megasena', {'games': [game]})
        path = lottery.LOTTERY_CONFIGS['megasena']['FILE_PATH']
        frame = pd.read_csv(path)
        frame.loc[len(frame)] = [2, '02/01/2026', 10, 20, 30, 40, 50, 60]
        frame.to_csv(path, index=False)
        second = comparison.analyze_games('megasena', {'games': [game]})
        self.assertEqual(first['coverage']['total_draws'], 1)
        self.assertEqual(second['coverage']['total_draws'], 2)
        self.assertEqual(second['radar']['latest']['contest'], 2)


class BatchRouteTests(unittest.TestCase):
    def test_access_csrf_and_no_store(self):
        module = importlib.import_module('app')
        client = module.app.test_client()
        path = '/analyze_games/megasena'
        payload = {'games': [{'numbers': [1, 2, 3, 4, 5, 6]}]}
        for user, status in ((None, 401), ({'is_premium': False}, 403)):
            with patch.object(module, 'current_access_payload', return_value=user):
                self.assertEqual(client.post(path, json=payload).status_code, status)
        with patch.object(module, 'current_access_payload', return_value={'is_premium': True}):
            self.assertEqual(client.post(path, json=payload).status_code, 403)
            with client.session_transaction() as session:
                session['csrf_token'] = 'batch-test'
            with patch.object(comparison, 'analyze_games', return_value={'ok': True}) as service:
                response = client.post(path, json=payload, headers={'X-CSRF-Token': 'batch-test'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                service.assert_called_once_with('megasena', payload)
            self.assertEqual(client.post(path, json={'games': []}, headers={'X-CSRF-Token': 'batch-test'}).status_code, 400)
            self.assertEqual(client.post(path, data='x' * 17000, content_type='application/json', headers={'X-CSRF-Token': 'batch-test'}).status_code, 413)
            with patch.object(comparison, 'analyze_games', side_effect=game_analysis.HistoryUnavailable('Indisponível')):
                self.assertEqual(client.post(path, json=payload, headers={'X-CSRF-Token': 'batch-test'}).status_code, 503)


if __name__ == '__main__':
    unittest.main()
