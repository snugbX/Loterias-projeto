from itertools import combinations
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import constrained_generation as generator
import gerador_loterias as lottery


class ConstrainedTests(unittest.TestCase):
    def test_all_lotteries_obey_fixed_excluded_parity_and_overlap(self):
        for kind, config in lottery.LOTTERY_CONFIGS.items():
            count = config['NUM_BALLS_TO_DRAW']
            overlap = 10 if kind == 'lotofacil' else 3
            rules = generator.validate_request(kind, {'num_games': 3, 'fixed': [1, 2], 'excluded': [config['MAX_NUMBER']],
                                                      'even_count': count // 2, 'max_overlap': overlap,
                                                      **({'month': 6} if kind == 'diadesorte' else {})})
            result = generator.generate_batch(kind, rules)
            games = [game[:count] for game in result['games']]
            self.assertEqual(len(games), 3)
            for game in games:
                self.assertEqual(len(set(game)), count)
                self.assertTrue({1, 2} <= set(game))
                self.assertNotIn(config['MAX_NUMBER'], game)
                self.assertEqual(sum(n % 2 == 0 for n in game), count // 2)
                self.assertTrue(rules.sum_min <= sum(game) <= rules.sum_max)
            self.assertTrue(all(len(set(a) & set(b)) <= overlap for a, b in combinations(games, 2)))
            if kind == 'diadesorte':
                self.assertTrue(all(game[-1] == 'Junho' for game in result['games']))
                self.assertEqual(result['portfolio']['unique_months'], 1)
                self.assertEqual(result['portfolio']['month_probability'], 1 / 12)

    def test_impossible_and_malformed_rules_fail_before_solver(self):
        payloads = [None, [], {'num_games': True}, {'num_games': 21}, {'fixed': [1, 1]}, {'excluded': [61]},
                    {'fixed': [1], 'excluded': [1]}, {'even_count': True}, {'sum_min': 1000},
                    {'sum_min': 200, 'sum_max': 100}, {'month': 1}, {'unknown': 'x'},
                    {'fixed': [1, 2, 3, 4, 5, 6], 'num_games': 2}, {'method': 'uniform', 'even_count': 3}]
        with patch.object(generator, 'milp') as solve:
            for payload in payloads:
                with self.subTest(payload=payload), self.assertRaises(ValueError):
                    generator.validate_request('megasena', payload)
            with self.assertRaises(ValueError):
                generator.validate_request('lotofacil', {'max_overlap': 4})
            with self.assertRaises(ValueError):
                generator.validate_request('lotofacil', {'even_count': 15})
        solve.assert_not_called()

    def test_uniform_mode_uses_unique_full_range_combinations_without_solver(self):
        for kind, config in lottery.LOTTERY_CONFIGS.items():
            rules = generator.validate_request(kind, {'method': 'uniform', 'num_games': 10})
            with patch.object(generator, 'milp') as solve:
                result = generator.generate_batch(kind, rules)
            solve.assert_not_called()
            games = [tuple(game[:config['NUM_BALLS_TO_DRAW']]) for game in result['games']]
            self.assertEqual(len(set(games)), 10)
            self.assertTrue(all(len(row) == config['NUM_BALLS_TO_DRAW'] and min(row) >= 1 and max(row) <= config['MAX_NUMBER'] for row in games))

    def test_fixed_exact_sum_and_numeric_coverage(self):
        rules = generator.validate_request('megasena', {'num_games': 1, 'fixed': [1, 2, 3, 4, 5, 6], 'sum_min': 21, 'sum_max': 21})
        result = generator.generate_batch('megasena', rules)
        self.assertEqual(result['games'], [[1, 2, 3, 4, 5, 6]])
        self.assertEqual(result['portfolio']['jackpot_probability'], 1 / 50063860)

    def test_timeout_and_invalid_solver_solutions_are_not_returned(self):
        rules = generator.validate_request('megasena', {'num_games': 1})
        for result in (MagicMock(status=1, x=None), MagicMock(status=0, x=[0] * 60)):
            with patch.object(generator, 'milp', return_value=result), self.assertRaises(generator.GenerationBusy):
                generator.generate_batch('megasena', rules)
        with patch.object(generator, 'TIME_BUDGET', 0), self.assertRaises(generator.GenerationBusy):
            generator.generate_batch('megasena', rules)


class ConstrainedRouteTests(unittest.TestCase):
    def test_access_csrf_and_saving_only_complete_private_batches(self):
        import app
        client = app.app.test_client()
        path = '/generate_constrained/megasena'
        for user, code in ((None, 401), ({'is_premium': False}, 403)):
            with patch.object(app, 'current_access_payload', return_value=user):
                self.assertEqual(client.post(path, json={}).status_code, code)
                self.assertEqual(client.get('/generation_rules/megasena').status_code, code)
        with patch.object(app, 'current_access_payload', return_value={'id': 42, 'is_premium': True}), \
             patch.object(app, 'can_generate_for_access', return_value=(True, '')), \
             patch.object(app.gerador_loterias, 'save_generated_games_to_csv') as save, \
             patch.object(app, 'record_generated_for_access', return_value={}) as usage:
            self.assertEqual(client.post(path, json={}).status_code, 403)
            with client.session_transaction() as session:
                session['csrf_token'] = 'test-generation'
            headers = {'X-CSRF-Token': 'test-generation'}
            self.assertEqual(client.post(path, json={'num_games': 0}, headers=headers).status_code, 422)
            with patch.object(generator, 'generate_batch', side_effect=generator.GenerationBusy('Limite de tempo')):
                self.assertEqual(client.post(path, json={'num_games': 1}, headers=headers).status_code, 503)
            save.assert_not_called(); usage.assert_not_called()
            result = {'games': [[1, 2, 3, 4, 5, 6]], 'portfolio': {}}
            with patch.object(generator, 'generate_batch', return_value=result):
                response = client.post(path, json={'num_games': 1}, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertEqual(save.call_args.kwargs['owner_key'], 'user:42')
            usage.assert_called_once()
            self.assertEqual(client.get('/generation_rules/megasena').status_code, 200)


if __name__ == '__main__':
    unittest.main()
