from datetime import date, timedelta
import csv
import json
from itertools import combinations
from math import comb
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
from urllib.request import Request

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import mais_milionaria as rules
import game_analysis as analysis
import game_comparison
import gerador_loterias as lottery
import history_manager
import constrained_generation
import pattern_radar
import update_lottery_data
import manage_database


class MaisMilionariaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'results.csv'
        config = dict(lottery.LOTTERY_CONFIGS['maismilionaria'], FILE_PATH=str(self.path), SKIP_ROWS=0)
        replacement = patch.dict(lottery.LOTTERY_CONFIGS, {'maismilionaria': config})
        replacement.start(); self.addCleanup(replacement.stop)
        analysis._read_draws.cache_clear()

    def seed(self, profiles):
        rows = []
        for index, (hits, trevos) in enumerate(profiles, 1):
            numbers = list(range(1, hits + 1)) + list(range(7, 13 - hits))
            extra = [(3, 4), (1, 3), (1, 2)][trevos]
            rows.append({'Concurso': index, 'Data': (date(2026, 1, 1) + timedelta(days=index)).strftime('%d/%m/%Y'),
                         **{f'bola {i + 1}': n for i, n in enumerate(numbers)}, 'Trevo 1': extra[0], 'Trevo 2': extra[1]})
        pd.DataFrame(rows).to_csv(self.path, index=False)

    def test_trevos_are_distinct_strict_integers_and_required(self):
        for invalid in (None, [], [1], [1, 1], [0, 6], [2, 7], [True, 2], [1.0, 2], ['1', 2], [1, 2, 3]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                analysis.validate_game('maismilionaria', {'numbers': list(range(1, 7)), 'trevos': invalid})
        self.assertEqual(analysis.validate_game('maismilionaria', {'numbers': list(range(1, 7)), 'trevos': [6, 1]})[1], (1, 6))
        with self.assertRaises(ValueError): analysis.validate_game('megasena', {'numbers': list(range(1, 7)), 'trevos': [1, 2]})

    def test_all_twenty_one_hit_profiles_follow_joint_prize_rules(self):
        for hits in range(7):
            for trevos in range(3):
                self.assertEqual(bool(rules.prize_label(hits, trevos)), hits >= 4 or hits >= 2 and trevos >= 1)

    def test_all_ten_tiers_and_non_prizes_in_historical_analysis(self):
        profiles = [(h, t[0]) for h, t in rules.TIERS] + [(2, 0), (3, 0), (1, 2), (0, 2)]
        self.seed(profiles)
        result = analysis.analyze_game('maismilionaria', {'numbers': list(range(1, 7)), 'trevos': [1, 2]})
        self.assertEqual(result['history']['prize_draws'], 10)
        self.assertEqual(len(result['history']['tiers']), 10)
        self.assertTrue(all(tier['count'] == 1 for tier in result['history']['tiers']))
        self.assertEqual(result['trevos'], [1, 2]); self.assertIsNone(result['month'])

    def test_joint_probabilities_are_exact_and_disjoint(self):
        summary = analysis.probability_summary('maismilionaria')
        self.assertEqual(summary['jackpot_one_in'], 238360500)
        self.assertEqual(summary['numeric_jackpot_one_in'], comb(50, 6))
        self.assertAlmostEqual(summary['tiers'][0]['probability'], 1 / 238360500)
        expected = sum(comb(6, h) * comb(44, 6-h) * comb(2, t) * comb(4, 2-t)
                       for h in range(7) for t in range(3) if rules.prize_label(h, t)) / (comb(50, 6) * 15)
        self.assertAlmostEqual(summary['any_prize'], expected)

    def test_history_only_checks_effective_bets_and_counts_trevos(self):
        game = [1, 2, 3, 4, 5, 6, 1, 2]
        self.assertEqual(history_manager.check_game('maismilionaria', game, {}, {}, 1)['status'], 'not_effective')
        for extra, expected in [((3, 4), 'no_prize'), ((1, 4), 'prize')]:
            result = history_manager.check_game('maismilionaria', game, {'effective': True, 'contest': 1},
                                               {1: (1, '01/01/2026', (1, 2, 7, 8, 9, 10), extra)}, 1)
            self.assertEqual(result['status'], expected)
            self.assertEqual(result['trevo_hits'], int(expected == 'prize'))

    def test_comparison_distinguishes_same_numbers_with_other_trevos(self):
        self.seed([(6, 2), (2, 0), (3, 1)])
        game = {'numbers': [1, 2, 3, 4, 5, 6], 'trevos': [1, 2]}
        result = game_comparison.analyze_games('maismilionaria', {'games': [game, {**game, 'trevos': [2, 1]}, {**game, 'trevos': [3, 4]}]})
        self.assertEqual(result['summary']['unique_games'], 2)
        self.assertEqual(result['summary']['unique_number_combinations'], 1)
        self.assertAlmostEqual(result['summary']['complete_jackpot_probability'], 2 / 238360500)
        self.assertEqual(result['analyses'][0]['alternative']['trevos'], [1, 2])
        self.assertFalse(result['pairs'][1]['duplicate'])

    def test_generation_keeps_trevos_separate_and_unique(self):
        for _ in range(30):
            self.assertEqual(len(set(lottery.generate_extra_values(pd.DataFrame(), lottery.LOTTERY_CONFIGS['maismilionaria']))), 2)
        ruleset = constrained_generation.validate_request('maismilionaria', {'method': 'uniform', 'num_games': 2, 'trevos': [6, 1]})
        result = constrained_generation.generate_batch('maismilionaria', ruleset)
        self.assertTrue(all(game[-2:] == [1, 6] and len(game) == 8 for game in result['games']))
        self.assertAlmostEqual(result['portfolio']['jackpot_probability'], 2 / 238360500)
        self.assertAlmostEqual(result['portfolio']['numeric_jackpot_probability'], 2 / comb(50, 6))
        self.assertEqual(result['portfolio']['unique_complete_games'], 2)
        self.assertEqual(result['portfolio']['unique_trevo_pairs'], 1)
        self.assertIn('fixado por você', result['method_note'])

    def test_history_numeric_filter_does_not_match_only_a_trevo(self):
        self.seed([(6, 2)])
        record = {'filename': 'maismilionaria_resultados_2026-01-01_12-00-00.csv', 'created_at': None,
                  'settings_json': None, 'games_json': json.dumps([[10, 20, 30, 40, 45, 50, 1, 2]])}
        with patch.object(history_manager, '_records', return_value=([record], False)):
            self.assertEqual(history_manager.list_games('maismilionaria', 'user:test', {'numbers': '1'})['matched'], 0)
            self.assertEqual(history_manager.list_games('maismilionaria', 'user:test', {'numbers': '10'})['matched'], 1)

    def test_legacy_csv_import_accepts_trevos_without_changing_owners(self):
        root = Path(self.temp.name) / 'history'; folder = root / 'user_9'; folder.mkdir(parents=True)
        path = folder / 'maismilionaria_resultados_2026-01-01_12-00-00.csv'
        with path.open('w', encoding='utf-8', newline='') as stream:
            csv.writer(stream).writerows([rules.COLUMNS[2:], [10, 20, 30, 40, 45, 50, 1, 2]])
        snapshot = {'tables': {'users': [{'id': 9}], 'generated_games': []}}
        manage_database.include_csv_history(snapshot, root)
        saved = snapshot['tables']['generated_games'][0]
        self.assertEqual(saved['owner_key'], 'user:9')
        self.assertEqual(json.loads(saved['games_json'])[0][-2:], [1, 2])

    def test_trevo_radar_has_fifteen_uniform_pairs_and_no_gap_bridging(self):
        raw = ((4, '04/01/2026', (1, 2, 3, 4, 5, 6), (1, 2)),
               (2, '02/01/2026', (1, 2, 3, 4, 5, 6), (3, 4)),
               (1, '01/01/2026', (1, 2, 3, 4, 5, 6), (1, 2)))
        radar = pattern_radar.build_trevo_radar(raw)
        self.assertEqual(len(radar['profiles']), 15)
        self.assertEqual(radar['sample'], 1)
        self.assertAlmostEqual(sum(p['theoretical_probability'] for p in radar['profiles']), 1)
        self.assertTrue(radar['small_sample'])

    def result(self, contest):
        return [str(contest), '01/01/2026', '1', '2', '3', '4', '5', '6', '1', '2']

    def write_import(self, rows):
        with self.path.open('w', encoding='utf-8', newline='') as stream:
            csv.writer(stream).writerows(rows)

    def test_import_is_incremental_and_current_check_only_requests_latest(self):
        with patch.object(rules, 'fetch_result', side_effect=lambda contest, timeout: self.result(contest or 3)) as fetch, patch.object(rules.time, 'sleep'):
            rows = rules.collect_rows(self.path)
            self.assertEqual(fetch.call_count, 3)
            self.write_import(rows); before = self.path.read_bytes(); fetch.reset_mock()
            self.assertIsNone(rules.collect_rows(self.path))
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(self.path.read_bytes(), before)
        with patch.object(rules, 'fetch_result', side_effect=lambda contest, timeout: self.result(contest or 4)) as fetch:
            self.assertEqual(rules.collect_rows(self.path)[7][0], '4')
            self.assertEqual(fetch.call_count, 1)

    def test_failed_import_preserves_csv_and_cache_resumes_without_repeat(self):
        def interrupted(contest, timeout):
            if contest == 2: raise TimeoutError('temporary')
            return self.result(contest or 3)
        with patch.object(rules, 'fetch_result', side_effect=interrupted), patch.object(rules.time, 'sleep'):
            with self.assertRaises(TimeoutError): rules.collect_rows(self.path)
        self.assertFalse(self.path.exists())
        with patch.object(rules, 'fetch_result', side_effect=lambda contest, timeout: self.result(contest or 3)) as fetch, patch.object(rules.time, 'sleep'):
            self.assertEqual(len(rules.collect_rows(self.path)), 10)
            self.assertEqual([call.args[0] for call in fetch.call_args_list], [None, 2])

    def test_source_requires_correct_lottery_contest_complete_trevos_and_date(self):
        payload = {'tipoJogo': 'MAIS_MILIONARIA', 'numero': 1, 'dataApuracao': '01/01/2026',
                   'listaDezenas': ['01', '02', '03', '04', '05', '06'], 'trevosSorteados': ['1', '2']}
        self.assertEqual(rules.validated_result(payload, 1), self.result(1))
        for field, value in [('tipoJogo', 'MEGA_SENA'), ('numero', 2), ('trevosSorteados', ['1', '1']),
                             ('trevosSorteados', None), ('dataApuracao', '31/02/2026')]:
            with self.subTest(field=field), self.assertRaises((ValueError, TypeError)):
                rules.validated_result({**payload, field: value}, 1)

    def test_force_repairs_invalid_header_or_rows_without_modifying_file_itself(self):
        for content in ('invalid header\n', '\n'*6 + ','.join(rules.COLUMNS) + '\ninvalid,row\n'):
            self.path.write_text(content, encoding='utf-8')
            with patch.object(rules, 'fetch_result', side_effect=lambda contest, timeout: self.result(contest or 3)), patch.object(rules.time, 'sleep'):
                with self.assertRaises(ValueError): rules.collect_rows(self.path)
                rows = rules.collect_rows(self.path, force=True)
                self.assertEqual([row[0] for row in rows[7:]], ['3', '2', '1'])
                self.assertEqual(self.path.read_text(encoding='utf-8'), content)

    def test_force_rebuilds_conflicting_rows_and_keeps_rollback_protection(self):
        rows = [['']]*6 + [rules.COLUMNS, self.result(1), self.result(1)]
        rows[-1] = [*self.result(1)[:8], '3', '4']
        self.write_import(rows)
        with patch.object(rules, 'fetch_result', side_effect=lambda contest, timeout: self.result(contest or 2)), patch.object(rules.time, 'sleep'):
            with self.assertRaises(ValueError): rules.collect_rows(self.path)
            self.assertEqual(rules.collect_rows(self.path, force=True)[-1], self.result(1))
        self.write_import([['']]*6 + [rules.COLUMNS, self.result(4)])
        with patch.object(rules, 'fetch_result', return_value=self.result(3)):
            with self.assertRaises(ValueError): rules.collect_rows(self.path, force=True)

    def test_force_repairs_bad_encoding_but_failed_source_never_changes_existing_csv(self):
        original = b'\xff\xfeinvalid encoding'
        self.path.write_bytes(original)
        with patch.object(rules, 'fetch_result', side_effect=lambda contest, timeout: self.result(contest or 2)), patch.object(rules.time, 'sleep'):
            rows = rules.collect_rows(self.path, force=True)
            self.assertEqual(rows[-1], self.result(1))
            self.assertEqual(self.path.read_bytes(), original)
        self.write_import([['']]*6 + [rules.COLUMNS, self.result(1)])
        original = self.path.read_bytes()
        def source(contest, timeout):
            if contest == 2: raise TimeoutError('temporary')
            return self.result(contest or 3)
        with patch.object(rules, 'fetch_result', side_effect=source):
            with self.assertRaises(TimeoutError): rules.collect_rows(self.path)
        self.assertEqual(self.path.read_bytes(), original)

    def test_fetch_honors_retry_after_and_stops_instead_of_retrying_too_early(self):
        payload = {'tipoJogo': 'MAIS_MILIONARIA', 'numero': 1, 'dataApuracao': '01/01/2026',
                   'listaDezenas': ['01', '02', '03', '04', '05', '06'], 'trevosSorteados': ['1', '2']}
        response = MagicMock(); response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        opener = MagicMock(); opener.open.side_effect = [HTTPError(rules.SOURCE, 429, 'limit', {'Retry-After': '7'}, None), response]
        with patch.object(rules, 'build_opener', return_value=opener), patch.object(rules.time, 'sleep') as sleep:
            self.assertEqual(rules.fetch_result(1, 10), self.result(1)); sleep.assert_called_once_with(7)
        opener.open.reset_mock(); opener.open.side_effect = HTTPError(rules.SOURCE, 429, 'limit', {'Retry-After': '120'}, None)
        with patch.object(rules, 'build_opener', return_value=opener), patch.object(rules.time, 'sleep') as sleep:
            with self.assertRaises(HTTPError): rules.fetch_result(1, 10)
            self.assertEqual(opener.open.call_count, 1); sleep.assert_not_called()

    def test_source_rejects_redirects_to_other_hosts_or_unencrypted_urls(self):
        handler = rules.OfficialRedirects()
        for url in ('http://servicebus2.caixa.gov.br/portaldeloterias/api/maismilionaria',
                    'https://example.com/result', 'https://127.0.0.1/result',
                    'https://servicebus2.caixa.gov.br/private',
                    'https://servicebus2.caixa.gov.br/portaldeloterias/api/maismilionaria/../../private'):
            with self.assertRaises(ValueError): handler.redirect_request(Request(rules.SOURCE), None, 302, '', {}, url)


if __name__ == '__main__':
    unittest.main()
