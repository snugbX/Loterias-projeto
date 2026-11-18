from datetime import date, datetime, timedelta
import importlib
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import draw_calendar as calendar


def month_days(year=2026, month=11):
    return {(date(year, month, 1) + timedelta(days=i)).isoformat(): [] for i in range(30)}


def document():
    headings = ['DATA', 'LOTECA', 'LOTOFACIL', 'FEDERAL', 'LOTOMANIA', 'QUINA', 'DUPLA SENA',
                'TIMEMANIA', 'MEGA-SENA', 'DIA DE SORTE', 'SUPER SETE', '+ MILIONARIA', 'LOCAL DO SORTEIO']
    lines = [''.join(h.center(20) for h in headings)]
    for i in range(1, 31):
        cells = [''] * len(headings)
        cells[0] = f'{i:02d}/11/2026'
        if i != 20:
            for index in (2, 5, 8, 9):
                cells[index] = str(1000 + i)
        if i == 29:
            cells[5] += '(8)'
        lines.append(''.join(cell.center(20) for cell in cells))
    return '\n'.join(lines)


class CalendarTests(unittest.TestCase):
    def setUp(self):
        calendar._cache.clear()
        calendar._next_attempt.clear()
        calendar._refreshing.clear()

    def tearDown(self):
        calendar._cache.clear()
        calendar._next_attempt.clear()
        calendar._refreshing.clear()

    def test_monthly_pdf_columns_sunday_holiday_and_footnotes(self):
        page = MagicMock()
        page.extract_text.return_value = document()
        with patch.object(calendar, 'PdfReader', return_value=MagicMock(pages=[page])):
            days = calendar.parse_schedule(b'%PDF-fixture', 2026, 11)
        self.assertEqual(len(days), 30)
        self.assertEqual(days['2026-11-20'], [])
        self.assertEqual(len(days['2026-11-29']), 4)
        self.assertEqual(next(d for d in days['2026-11-29'] if d['lottery'] == 'quina')['contest'], 1029)

    def test_invalid_and_changed_pdf_are_not_a_schedule(self):
        with self.assertRaises(ValueError):
            calendar.parse_schedule(b'<html>blocked</html>', 2026, 11)
        page = MagicMock()
        page.extract_text.return_value = 'Unknown table'
        with patch.object(calendar, 'PdfReader', return_value=MagicMock(pages=[page])):
            with self.assertRaises(ValueError):
                calendar.parse_schedule(b'%PDF-fixture', 2026, 11)

    def test_only_official_https_links_and_redirects(self):
        parser = calendar.ScheduleLinks()
        parser.feed('<a href="https://www.caixa.gov.br/Downloads/caixa-loterias/Cronograma_11_novembro_2026.pdf">PDF</a>'
                    '<a href="https://evil.example/Cronograma_11_novembro_2026.pdf">bad</a>')
        self.assertEqual(len(parser.links), 1)
        for url in ('http://www.caixa.gov.br/x', 'https://www.caixa.gov.br.evil.example/x',
                    'https://user:pass@www.caixa.gov.br/x', 'https://www.caixa.gov.br:8080/x'):
            self.assertFalse(calendar.allowed_url(url))
        with self.assertRaises(ValueError):
            calendar.OfficialRedirects().redirect_request(None, None, 302, '', {}, 'https://evil.example/')

    def test_cache_avoids_repeated_downloads(self):
        html = b'<a href="https://www.caixa.gov.br/Downloads/caixa-loterias/Cronograma_11_novembro_2026.pdf">PDF</a>'
        with patch.object(calendar, 'download', side_effect=[html, b'%PDF-test']) as download, \
             patch.object(calendar, 'parse_schedule', return_value=month_days()), \
             patch.object(calendar.time, 'monotonic', return_value=100):
            first = calendar.load_month(2026, 11)
            self.assertIs(calendar.load_month(2026, 11), first)
            self.assertEqual(download.call_count, 2)

    def test_failure_backoff_and_stale_cache(self):
        old = {'days': month_days(), 'source': calendar.SOURCE, 'checked_at': '2026-11-17T10:00:00-03:00', 'checked_monotonic': 1}
        calendar._cache[(2026, 11)] = old
        with patch.object(calendar, 'download', side_effect=TimeoutError) as download, \
             patch.object(calendar.time, 'monotonic', return_value=4000):
            result = calendar.get_calendar(date(2026, 11, 17))
            calendar.get_calendar(date(2026, 11, 17))
            self.assertEqual(result['status'], 'stale')
            self.assertFalse(result['days'][1]['confirmed'])
            self.assertTrue(result['days'][1]['available'])
            self.assertEqual(download.call_count, 1)
            self.assertIn('confirmar', result['tips'][1]['text'])

    def test_unavailable_is_not_reported_as_no_draws(self):
        with patch.object(calendar, 'load_month', return_value=None):
            result = calendar.get_calendar(date(2026, 11, 22))
        self.assertEqual(result['status'], 'unavailable')
        self.assertTrue(result['days'][-1]['today'])
        self.assertTrue(all(not day['available'] for day in result['days']))

    def test_week_crosses_months_and_new_year(self):
        with patch.object(calendar, 'load_month', return_value=None) as loader:
            result = calendar.get_calendar(date(2027, 1, 1))
        self.assertEqual(result['days'][0]['date'], '2026-12-28')
        self.assertEqual(result['days'][-1]['date'], '2027-01-03')
        self.assertEqual({call.args for call in loader.call_args_list}, {(2026, 12), (2027, 1)})

    def test_brazil_date_and_daily_tips_rotation(self):
        with patch.object(calendar, 'datetime') as clock, patch.object(calendar, 'load_month', return_value=None):
            clock.now.return_value = datetime(2026, 11, 17, 23, 30, tzinfo=calendar.TIMEZONE)
            result = calendar.get_calendar()
            clock.now.assert_called_with(calendar.TIMEZONE)
        self.assertEqual(result['today'], '2026-11-17')
        day = {'confirmed': True, 'draws': []}
        self.assertNotEqual(calendar.daily_tips(date(2026, 11, 17), day)[0],
                            calendar.daily_tips(date(2026, 11, 18), day)[0])

    def test_public_route_is_read_only_and_not_cached(self):
        with patch.dict(os.environ, {'DATABASE_URL': '', 'RENDER': ''}):
            module = importlib.import_module('app')
        with patch.object(calendar, 'cached_month', return_value=None):
            response = module.app.test_client().get('/draw_calendar')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(len(response.json['days']), 7)
        self.assertNotIn('users', response.json)
        self.assertEqual(module.app.test_client().post('/draw_calendar').status_code, 405)

    def test_background_refresh_does_not_block_or_duplicate_jobs(self):
        with patch.object(calendar.threading, 'Thread') as thread:
            first = calendar.get_calendar(date(2026, 11, 17), background=True)
            calendar.get_calendar(date(2026, 11, 17), background=True)
        self.assertEqual(first['status'], 'loading')
        thread.assert_called_once()
        thread.return_value.start.assert_called_once()

    def test_truncated_month_is_not_treated_as_no_draws(self):
        page = MagicMock()
        page.extract_text.return_value = '\n'.join(document().splitlines()[:25])
        with patch.object(calendar, 'PdfReader', return_value=MagicMock(pages=[page])):
            with self.assertRaises(ValueError):
                calendar.parse_schedule(b'%PDF-fixture', 2026, 11)


if __name__ == '__main__':
    unittest.main()
