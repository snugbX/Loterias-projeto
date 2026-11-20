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
import user_assistance


class AdaptationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def seed(self, kind, sequences, months=None):
        config = dict(lottery.LOTTERY_CONFIGS[kind])
        path = Path(self.temp.name) / f'{kind}.csv'
        rows = []
        for index, numbers in enumerate(sequences):
            row = {'Concurso': index + 1, 'Data': (date(2026, 1, 1) + timedelta(days=index)).strftime('%d/%m/%Y')}
            row.update({f'bola {i + 1}': value for i, value in enumerate(numbers)})
            if months:
                row['Mês da Sorte'] = months[index]
            rows.append(row)
        pd.DataFrame(rows).to_csv(path, index=False)
        config.update(FILE_PATH=str(path), SKIP_ROWS=0)
        p = patch.dict(lottery.LOTTERY_CONFIGS, {kind: config})
        p.start(); self.addCleanup(p.stop)
        return config

    def test_hot_cold_and_strategy_stats_share_validated_history_for_all_lotteries(self):
        for kind, config in lottery.LOTTERY_CONFIGS.items():
            numbers = list(range(1, config['NUM_BALLS_TO_DRAW'] + 1))
            self.seed(kind, [numbers, numbers, [1.5] + numbers[1:]],
                      ['Janeiro', 'invalido', 'Março'] if kind == 'diadesorte' else None)
            hotcold = lottery.get_hot_cold_numbers(kind)
            stats = lottery.get_generation_strategy_stats(kind)
            self.assertEqual(hotcold['coverage']['total_draws'], 2)
            self.assertEqual(hotcold['coverage']['skipped_rows'], 1)
            self.assertEqual(stats['total_draws'], 2)
            self.assertEqual(stats['skipped_rows'], 1)
            self.assertEqual(len(hotcold['months']), 12 if kind == 'diadesorte' else 0)
            if kind == 'diadesorte':
                self.assertEqual(hotcold['month_coverage'], {'valid': 1, 'missing': 1})
                self.assertEqual(hotcold['months'][0]['percentage'], 100)

    def test_cold_rank_is_frequency_order_not_numeric_order(self):
        self.seed('megasena', [[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 60]])
        result = lottery.get_hot_cold_numbers('megasena', 60)
        self.assertLess(result['cold_numbers'].index(60), result['cold_numbers'].index(6))
        self.assertEqual(result['cold_numbers'][0], 7)
        for invalid in (0, 61, True):
            with self.assertRaises(ValueError):
                lottery.get_hot_cold_numbers('megasena', invalid)

    def test_guides_explain_lottery_specific_counts_parity_and_filter_thresholds(self):
        for kind, config in lottery.LOTTERY_CONFIGS.items():
            guide = user_assistance.get_guide(kind)
            text = ' '.join(p for topic in guide['topics'] for p in topic['paragraphs'])
            self.assertIn(f"{config['NUM_BALLS_TO_DRAW']} dezenas", text)
            self.assertIn(f"{lottery.HISTORICAL_PRIZE_FILTERS[kind]['min_matches']} ou mais acertos", text)
            self.assertEqual(guide['available_modes'], [mode for mode in lottery.GENERATION_MODES if lottery.is_generation_mode_available_for_lottery(mode, kind)])
            self.assertEqual(len({topic['id'] for topic in guide['topics']}), 8)
        with self.assertRaises(ValueError):
            user_assistance.get_guide('invalid')

    def test_available_generation_modes_respect_each_lottery_constraints(self):
        for kind, config in lottery.LOTTERY_CONFIGS.items():
            probabilities = {n: 1 / config['MAX_NUMBER'] for n in lottery.all_main_numbers(config)}
            for mode in ('balanced_parity', 'even_only', 'odd_only', 'spread', 'hot_cold_mix', 'lucky_dates', 'high_numbers'):
                if not lottery.is_generation_mode_available_for_lottery(mode, kind):
                    continue
                numbers = lottery.generate_candidate_by_mode(kind, mode, probabilities, None, pd.DataFrame(), config)
                self.assertEqual(len(numbers), config['NUM_BALLS_TO_DRAW'])
                self.assertEqual(len(set(numbers)), len(numbers))
                self.assertTrue(all(1 <= n <= config['MAX_NUMBER'] for n in numbers))
                if mode != 'hot_cold_mix':
                    self.assertTrue(lottery.strategy_matches_historical_draw(numbers, mode, config))

    def test_help_route_allows_signed_in_free_and_guest_but_stats_remain_premium(self):
        module = importlib.import_module('app')
        client = module.app.test_client()
        with patch.object(module, 'current_access_payload', return_value=None):
            self.assertEqual(client.get('/user_assistance/megasena').status_code, 401)
        for role in ('guest', 'user', 'admin'):
            user = {'role': role, 'is_premium': role == 'admin'}
            with patch.object(module, 'current_access_payload', return_value=user):
                response = client.get('/user_assistance/diadesorte')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                self.assertEqual(client.get('/user_assistance/invalid').status_code, 400)
                if role != 'admin':
                    self.assertEqual(client.get('/get_hot_cold_numbers/diadesorte').status_code, 403)
        self.assertEqual(client.post('/user_assistance/megasena').status_code, 405)

    def test_statistics_report_unavailable_history_instead_of_empty_rankings(self):
        module = importlib.import_module('app')
        with patch.object(module, 'current_access_payload', return_value={'is_premium': True}), \
             patch.object(game_analysis, 'load_validated_history', side_effect=game_analysis.HistoryUnavailable('Base indisponível')):
            self.assertEqual(module.app.test_client().get('/get_hot_cold_numbers/diadesorte').status_code, 503)
            self.assertEqual(module.app.test_client().get('/strategy_stats/diadesorte').status_code, 503)


if __name__ == '__main__':
    unittest.main()
