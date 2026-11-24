from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import gerador_loterias as lottery
import strategy_catalog


class StrategyCatalogTests(unittest.TestCase):
    def test_every_executable_mode_is_registered_and_availability_is_authoritative(self):
        for kind in lottery.LOTTERY_CONFIGS:
            catalog = strategy_catalog.catalog_for(kind)
            self.assertEqual([mode['id'] for mode in catalog['modes']], list(lottery.GENERATION_MODES))
            for mode in catalog['modes']:
                self.assertEqual(mode['available'], lottery.is_generation_mode_available_for_lottery(mode['id'], kind))
                self.assertEqual(mode['premium'], mode['id'] in lottery.PREMIUM_GENERATION_MODES)
            self.assertEqual({tool['method'] for tool in catalog['tools']}, {'uniform', 'constraints'})
            self.assertTrue(all(tool['method'] not in lottery.GENERATION_MODES for tool in catalog['tools']))
        mega = next(item for item in strategy_catalog.catalog_for('megasena')['modes'] if item['id'] == 'never_prize')
        self.assertNotIn('faixas menores', mega['description'])
        dia = next(item for item in strategy_catalog.catalog_for('diadesorte')['modes'] if item['id'] == 'never_prize')
        self.assertIn('Não filtra o Mês da Sorte', dia['description'])

    def test_new_modes_require_catalog_registration(self):
        with patch.dict(lottery.GENERATION_MODES, {'unregistered': 'Future mode'}):
            with self.assertRaises(RuntimeError): strategy_catalog.catalog_for('megasena')
        with self.assertRaises(ValueError):
            lottery.generate_candidate_by_mode('megasena', 'unregistered', {}, None, pd.DataFrame(), lottery.LOTTERY_CONFIGS['megasena'])

    def test_all_visible_executable_modes_generate_valid_games(self):
        for kind, config in lottery.LOTTERY_CONFIGS.items():
            probabilities = pd.Series({n: 1 / config['MAX_NUMBER'] for n in lottery.all_main_numbers(config)})
            for mode in lottery.GENERATION_MODES:
                if not lottery.is_generation_mode_available_for_lottery(mode, kind): continue
                numbers = lottery.generate_main_numbers_with_mode(kind, mode, probabilities, None, pd.DataFrame(), config, set())
                self.assertEqual(len(numbers), config['NUM_BALLS_TO_DRAW'])
                self.assertEqual(len(set(numbers)), len(numbers))
                self.assertTrue(all(config['MIN_NUMBER'] <= n <= config['MAX_NUMBER'] for n in numbers))

    def test_separate_parity_and_historical_filters_are_actually_applied(self):
        for kind, config in lottery.LOTTERY_CONFIGS.items():
            probabilities = pd.Series({n: 1 / config['MAX_NUMBER'] for n in lottery.all_main_numbers(config)})
            threshold = lottery.HISTORICAL_PRIZE_FILTERS[kind]['min_matches']
            known = set(range(1, threshold + 1))
            for mode in ('balanced_parity', 'never_prize'):
                numbers = lottery.generate_main_numbers_with_mode(kind, mode, probabilities, None, pd.DataFrame(), config, {tuple(sorted(known))})
                self.assertEqual(len(numbers), config['NUM_BALLS_TO_DRAW'])
                if mode == 'balanced_parity': self.assertTrue(lottery.has_balanced_parity(numbers))
                else: self.assertFalse(known <= set(numbers))

    def test_route_is_read_only_requires_access_and_contains_no_private_data(self):
        import app
        client = app.app.test_client()
        with patch.object(app, 'current_access_payload', return_value=None):
            self.assertEqual(client.get('/strategy_catalog/megasena').status_code, 401)
        with patch.object(app, 'current_access_payload', return_value={'is_premium': False}):
            response = client.get('/strategy_catalog/diadesorte')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertEqual(client.get('/strategy_catalog/invalid').status_code, 400)
            self.assertNotIn('games', response.json)
        self.assertEqual(client.post('/strategy_catalog/megasena').status_code, 405)


if __name__ == '__main__':
    unittest.main()
