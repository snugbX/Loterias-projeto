from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import game_alternative as alternative
import gerador_loterias as lottery
import pattern_radar


def radar_for(kind, target_even, sample=100):
    config = lottery.LOTTERY_CONFIGS[kind]
    count = config['NUM_BALLS_TO_DRAW']
    probabilities = pattern_radar.parity_probabilities(count, config['MAX_NUMBER'])
    return {'latest': {'even': target_even, 'contest': 42, 'date': '17/11/2026'},
            'groups': {target_even: {'sample': sample, 'label': pattern_radar.profile_label(target_even, count),
                'profiles': [{'even': even, 'odd': count - even, 'label': pattern_radar.profile_label(even, count),
                              'matches': sample if even == target_even else 0,
                              'conditional_probability': (1 if even == target_even else 0) if sample else None,
                              'theoretical_probability': probability} for even, probability in probabilities.items()]}}}


class AlternativeTests(unittest.TestCase):
    def test_user_example_preserves_five_numbers_and_prefers_neighbor(self):
        numbers = [2, 15, 18, 23, 47, 55]
        result = alternative.suggest_alternative('megasena', numbers, None, radar_for('megasena', 3))
        self.assertEqual(result['numbers'], [2, 15, 18, 23, 47, 56])
        self.assertEqual(result['changes'], [{'from': 55, 'to': 56}])
        self.assertEqual(result['preserved_numbers'], [2, 15, 18, 23, 47])
        self.assertEqual(numbers, [2, 15, 18, 23, 47, 55])
        self.assertEqual(result['basis'], 'smoothed_transitions')

    def test_all_lotteries_and_feasible_parity_profiles_have_minimal_valid_edits(self):
        for kind, config in lottery.LOTTERY_CONFIGS.items():
            count, maximum = config['NUM_BALLS_TO_DRAW'], config['MAX_NUMBER']
            probabilities = pattern_radar.parity_probabilities(count, maximum)
            for initial in probabilities:
                numbers = sorted(list(range(2, 2 * initial + 1, 2)) + list(range(1, 2 * (count - initial), 2)))
                for target in probabilities:
                    with self.subTest(lottery=kind, initial=initial, target=target):
                        result = alternative.suggest_alternative(kind, numbers, 8 if kind == 'diadesorte' else None,
                                                                  radar_for(kind, target, 10000))
                        self.assertEqual(sum(n % 2 == 0 for n in result['numbers']), target)
                        self.assertEqual(len(result['numbers']), count)
                        self.assertEqual(len(set(result['numbers'])), count)
                        self.assertTrue(all(1 <= n <= maximum for n in result['numbers']))
                        self.assertEqual(len(result['changes']), abs(target - initial))
                        self.assertEqual(len(result['preserved_numbers']), count - abs(target - initial))
                        self.assertEqual(result['numbers'], sorted(result['numbers']))
                        self.assertEqual(result['month'], 8 if kind == 'diadesorte' else None)

    def test_insufficient_sample_uses_mathematical_reference_not_noisy_frequency(self):
        for sample in (0, 1, pattern_radar.MIN_SAMPLE - 1):
            result = alternative.suggest_alternative('megasena', [1, 3, 5, 7, 9, 11], None,
                                                      radar_for('megasena', 0, sample))
            self.assertEqual(result['target_even'], 3)
            self.assertEqual(result['basis'], 'theoretical_fallback')
            self.assertTrue(result['small_sample'])

    def test_aligned_game_is_not_changed_unnecessarily(self):
        numbers = [2, 15, 18, 23, 47, 56]
        result = alternative.suggest_alternative('megasena', numbers, None, radar_for('megasena', 3))
        self.assertEqual(result['status'], 'already_aligned')
        self.assertEqual(result['numbers'], numbers)
        self.assertEqual(result['changes'], [])

    def test_tied_reference_preserves_current_profile(self):
        numbers = [1, 2, 3, 4, 5]
        result = alternative.suggest_alternative('quina', numbers, None, radar_for('quina', 0, 0))
        self.assertEqual(result['target_even'], 2)
        self.assertEqual(result['status'], 'already_aligned')

    def test_deterministic_suggestion_and_no_prediction_claim(self):
        args = ('megasena', [2, 15, 18, 23, 47, 55], None, radar_for('megasena', 3))
        self.assertEqual(alternative.suggest_alternative(*args), alternative.suggest_alternative(*args))
        self.assertIn('mesma chance matemática', alternative.suggest_alternative(*args)['note'])


if __name__ == '__main__':
    unittest.main()
