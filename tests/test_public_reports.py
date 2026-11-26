from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from build_draw_digest import build_digest
import build_statistical_reports as builder
import gerador_loterias as lottery
import public_reports
import publish_lottery_data
from test_statistical_audit import draws_for


class PublicReportTests(unittest.TestCase):
    def test_digest_is_factual_and_does_not_bridge_missing_previous_contest(self):
        draws = draws_for([[1, 2, 3, 4, 5, 6], [2, 4, 6, 8, 10, 12]], [1, 3])
        result = build_digest('megasena', draws, 2)
        self.assertEqual(result['sum'], 42)
        self.assertEqual(result['even'], 6)
        self.assertIsNone(result['repeated_numbers'])
        self.assertEqual(result['coverage']['missing_contests'], 1)
        self.assertEqual(sum(item['count'] for item in result['ranges']), 6)
        self.assertIsNone(result['month'])
        dia = ((1, '01/01/2026', (1, 2, 3, 4, 5, 6, 7), 6),)
        self.assertEqual(build_digest('diadesorte', dia, 0)['month'], 'Junho')

    def test_builder_creates_complete_bundle_and_skips_unchanged_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'public_lottery_reports.json'
            def history(kind):
                count = lottery.LOTTERY_CONFIGS[kind]['NUM_BALLS_TO_DRAW']
                draws = draws_for([list(range(1, count + 1))] * 5)
                if kind == 'maismilionaria': draws = tuple((*row[:3], (1, 2)) for row in draws)
                return draws, 0, type('Stat', (), {'st_mtime_ns': 1})()
            with patch.object(public_reports, 'REPORT_PATH', path), \
                 patch.object(public_reports, 'fingerprint', return_value='a' * 64), \
                 patch.object(builder.game_analysis, 'load_validated_history', side_effect=history):
                self.assertEqual(builder.main(['--resamples', '19']), 0)
                bundle = public_reports.read_bundle()
                self.assertEqual(set(bundle['reports']), set(lottery.LOTTERY_CONFIGS))
                self.assertEqual(public_reports.get_report('megasena')['status'], 'current')
                self.assertEqual(len(public_reports.get_digests()), len(lottery.LOTTERY_CONFIGS))
                (Path(directory) / 'src').mkdir()
                destination = Path(directory) / 'src' / path.name
                destination.write_bytes(path.read_bytes())
                with patch.object(publish_lottery_data, 'PROJECT_ROOT', Path(directory)):
                    self.assertEqual(publish_lottery_data.normalize_paths([destination]), ['src/public_lottery_reports.json'])
                    with patch.object(public_reports, 'fingerprint', return_value='b' * 64), self.assertRaises(ValueError):
                        publish_lottery_data.normalize_paths([destination])
                before = path.read_bytes()
                with patch.object(builder, 'build_reports') as build:
                    self.assertEqual(builder.main(['--resamples', '19']), 0)
                    build.assert_not_called()
                self.assertEqual(path.read_bytes(), before)
                with patch.object(public_reports, 'fingerprint', return_value='b' * 64):
                    self.assertEqual(public_reports.get_report('megasena')['status'], 'pending')
                    self.assertEqual(public_reports.get_digests()['megasena']['status'], 'pending')
                payload = json.loads(path.read_text(encoding='utf-8')); payload['private'] = 'not-allowed'
                path.write_text(json.dumps(payload), encoding='utf-8')
                with self.assertRaises(ValueError): public_reports.read_bundle()

    def test_publication_never_accepts_an_arbitrary_json_file(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(publish_lottery_data, 'PROJECT_ROOT', Path(directory)):
            path = Path(directory) / 'private.json'; path.write_text('{}', encoding='utf-8')
            with self.assertRaises(ValueError): publish_lottery_data.normalize_paths([path])

    def test_failed_build_preserves_previous_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'public_lottery_reports.json'
            path.write_text('{"old": "untouched"}', encoding='utf-8')
            before = path.read_bytes()
            with patch.object(public_reports, 'REPORT_PATH', path), patch.object(builder, 'build_reports', side_effect=RuntimeError('changed source')):
                with self.assertRaises(RuntimeError): builder.main(['--resamples', '19'])
            self.assertEqual(path.read_bytes(), before)

    def test_digest_endpoint_is_public_read_only_and_never_exposes_audit_matrix(self):
        import app
        with patch.object(public_reports, 'get_digests', return_value={'megasena': {'status': 'pending'}}):
            response = app.app.test_client().get('/draw_digest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertNotIn('q_values', response.json)
        self.assertEqual(app.app.test_client().post('/draw_digest').status_code, 405)


if __name__ == '__main__':
    unittest.main()
