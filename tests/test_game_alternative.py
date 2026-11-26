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


def synergy_for(kind):
    config = lottery.LOTTERY_CONFIGS[kind]
    maximum = config['MAX_NUMBER']
    return alternative.SynergyIndex(200, config['NUM_BALLS_TO_DRAW'], maximum,
                                    tuple([0] + [60] * maximum),
                                    tuple(tuple(20 if a != b else 0 for b in range(maximum + 1))
                                          for a in range(maximum + 1)))


class AlternativeTests(unittest.TestCase):
    def test_prefers_supported_affinity_over_neighbor_and_raw_popularity(self):
        numbers = [2, 15, 18, 23, 47, 55]
        singles = [0] + [60] * 60
        singles[56] = 150
        matrix = [[10 if a != b else 0 for b in range(61)] for a in range(61)]
        for anchor in [2, 15, 18, 23, 47]:
            matrix[40][anchor] = matrix[anchor][40] = 32
            matrix[56][anchor] = matrix[anchor][56] = 35
        synergy = alternative.SynergyIndex(200, 6, 60, tuple(singles), tuple(map(tuple, matrix)))
        result = alternative.suggest_alternative('megasena', numbers, None, radar_for('megasena', 3), synergy)
        self.assertEqual(result['numbers'], [2, 15, 18, 23, 40, 47])
        self.assertEqual(result['changes'], [{'from': 55, 'to': 40}])
        self.assertEqual(result['preserved_numbers'], [2, 15, 18, 23, 47])
        self.assertEqual(numbers, [2, 15, 18, 23, 47, 55])
        self.assertEqual(result['basis'], 'smoothed_transitions')
        self.assertEqual(result['synergy']['evidence'][0]['positive_count'], 5)
        self.assertFalse(alternative.pair_affinity(synergy, 56, 2)['positive'])

    def test_all_lotteries_and_feasible_parity_profiles_have_minimal_valid_edits(self):
        for kind, config in lottery.LOTTERY_CONFIGS.items():
            count, maximum = config['NUM_BALLS_TO_DRAW'], config['MAX_NUMBER']
            probabilities = pattern_radar.parity_probabilities(count, maximum)
            for initial in probabilities:
                numbers = sorted(list(range(2, 2 * initial + 1, 2)) + list(range(1, 2 * (count - initial), 2)))
                for target in probabilities:
                    with self.subTest(lottery=kind, initial=initial, target=target):
                        result = alternative.suggest_alternative(kind, numbers, 8 if kind == 'diadesorte' else (1, 2) if kind == 'maismilionaria' else None,
                                                                  radar_for(kind, target, 10000), synergy_for(kind))
                        self.assertEqual(sum(n % 2 == 0 for n in result['numbers']), target)
                        self.assertEqual(len(result['numbers']), count)
                        self.assertEqual(len(set(result['numbers'])), count)
                        self.assertTrue(all(1 <= n <= maximum for n in result['numbers']))
                        self.assertEqual(len(result['changes']), abs(target - initial))
                        self.assertEqual(len(result['preserved_numbers']), count - abs(target - initial))
                        self.assertEqual(result['numbers'], sorted(result['numbers']))
                        self.assertEqual(result['month'], 8 if kind == 'diadesorte' else None)
                        self.assertTrue(all(item['majority'] for item in result['synergy']['evidence']))

    def test_insufficient_sample_uses_mathematical_reference_not_noisy_frequency(self):
        for sample in (0, 1, pattern_radar.MIN_SAMPLE - 1):
            result = alternative.suggest_alternative('megasena', [1, 3, 5, 7, 9, 11], None,
                                                      radar_for('megasena', 0, sample), synergy_for('megasena'))
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
        args = ('megasena', [2, 15, 18, 23, 47, 55], None, radar_for('megasena', 3), synergy_for('megasena'))
        self.assertEqual(alternative.suggest_alternative(*args), alternative.suggest_alternative(*args))
        self.assertIn('mesma chance matemática', alternative.suggest_alternative(*args)['note'])

    def test_no_data_or_positive_majority_does_not_invent_synergy(self):
        numbers = [2, 15, 18, 23, 47, 55]
        for synergy in (None, alternative.build_synergy('megasena', ((1, '01/01/2026', tuple(numbers), None),))):
            result = alternative.suggest_alternative('megasena', numbers, None, radar_for('megasena', 3), synergy)
            self.assertEqual(result['status'], 'insufficient_synergy')
            self.assertEqual(result['numbers'], numbers)
            self.assertEqual(result['changes'], [])
            self.assertEqual(result['synergy']['evidence'], [])

    def test_pair_reference_corrects_for_sampling_without_replacement(self):
        matrix = tuple(tuple(10 if a != b else 0 for b in range(6)) for a in range(6))
        index = alternative.SynergyIndex(100, 2, 5, (0, 40, 40, 40, 40, 40), matrix)
        pair = alternative.pair_affinity(index, 1, 2)
        self.assertAlmostEqual(pair['expected_co_draws'], 10)
        self.assertAlmostEqual(pair['adjusted_lift'], 1)
        self.assertFalse(pair['positive'])

    def test_public_snapshot_index_is_symmetric_and_invalidated_by_new_draws(self):
        draws = ((1, '01/01/2026', (1, 2, 3, 4, 5, 6), None),)
        first = alternative.build_synergy('megasena', draws)
        self.assertIs(first, alternative.build_synergy('megasena', draws))
        second = alternative.build_synergy('megasena', draws + ((2, '02/01/2026', (2, 4, 6, 8, 10, 12), None),))
        self.assertEqual(first.total, 1)
        self.assertEqual(second.singles[2], 2)
        self.assertEqual(second.pairs[2][4], 2)
        self.assertEqual(second.pairs[2][4], second.pairs[4][2])


if __name__ == '__main__':
    unittest.main()
