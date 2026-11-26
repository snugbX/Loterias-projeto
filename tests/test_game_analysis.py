import importlib
import os
from math import comb
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import game_analysis as analysis
import gerador_loterias as lottery


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        analysis._read_draws.cache_clear()

    def use_draws(self, lottery_type, hits, months=None):
        config = dict(lottery.LOTTERY_CONFIGS[lottery_type])
        count = config["NUM_BALLS_TO_DRAW"]
        rows = []
        for index, match in enumerate(hits):
            numbers = list(range(1, match + 1)) + list(range(count + 1, count + 1 + count - match))
            row = {"Concurso": index + 1, "Data": f"{index + 1:02d}/01/2026"}
            row.update({f"bola {i + 1}": n for i, n in enumerate(numbers)})
            if lottery_type == 'maismilionaria': row.update({'Trevo 1': 1, 'Trevo 2': 2})
            if months:
                row["Mês da Sorte"] = months[index]
            rows.append(row)
        path = Path(self.temp.name) / f"{lottery_type}.csv"
        pd.DataFrame(rows).to_csv(path, index=False)
        config.update(FILE_PATH=str(path), SKIP_ROWS=0)
        replacement = patch.dict(lottery.LOTTERY_CONFIGS, {lottery_type: config})
        replacement.start()
        self.addCleanup(replacement.stop)
        return {"numbers": list(range(1, count + 1)), **({"month": 1} if lottery_type == "diadesorte" else {'trevos': [1, 2]} if lottery_type == 'maismilionaria' else {})}

    def test_all_prize_tiers(self):
        for kind, tiers in analysis.PRIZE_MATCHES.items():
            with self.subTest(kind=kind):
                payload = self.use_draws(kind, tiers)
                result = analysis.analyze_game(kind, payload)
                self.assertEqual(result["history"]["prize_draws"], len(tiers))
                if kind == 'maismilionaria': self.assertEqual(sum(t['count'] for t in result['history']['tiers']), len(tiers))
                else: self.assertTrue(all(tier["count"] == 1 for tier in result["history"]["tiers"]))
                self.assertEqual(result["history"]["best_matches"], max(tiers))
                self.assertIn("numbers", result["history"]["recent_occurrences"][0])

    def test_month_only_and_overlapping_prizes_count_once(self):
        payload = self.use_draws("diadesorte", [0, 4, 7], ["Janeiro", "Janeiro", "Fevereiro"])
        result = analysis.analyze_game("diadesorte", payload)
        self.assertEqual(result["history"]["prize_draws"], 3)
        self.assertEqual(result["history"]["month_matches"], 2)
        self.assertEqual(result["coverage"]["missing_months"], 0)

    def test_missing_month_is_reported(self):
        payload = self.use_draws("diadesorte", [0, 4])
        result = analysis.analyze_game("diadesorte", payload)
        self.assertEqual(result["coverage"]["missing_months"], 2)

    def test_invalid_game_payloads(self):
        for payload in (None, [], "123456", {}, {"numbers": [1] * 6},
                        {"numbers": [True, 2, 3, 4, 5, 6]}, {"numbers": [1.0, 2, 3, 4, 5, 6]},
                        {"numbers": [0, 2, 3, 4, 5, 6]}, {"numbers": [1, 2, 3, 4, 5, 61]},
                        {"numbers": [1, 2, 3, 4, 5, "6"]}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                analysis.validate_game("megasena", payload)
        for month in (None, 0, 13, True, "1"):
            with self.assertRaises(ValueError):
                analysis.validate_game("diadesorte", {"numbers": list(range(1, 8)), "month": month})

    def test_probabilities(self):
        expected = {"megasena": 50063860, "quina": 24040016, "lotofacil": 3268760, "diadesorte": 2629575}
        for kind, total in expected.items():
            summary = analysis.probability_summary(kind)
            self.assertEqual(summary["jackpot_one_in"], total)
            self.assertAlmostEqual(summary["tiers"][0]["probability"], 1 / total)
            self.assertGreater(summary["any_prize"], 0)
            self.assertLess(summary["any_prize"], 1)
        mega = analysis.probability_summary("megasena")
        self.assertAlmostEqual(mega["tiers"][2]["probability"], comb(6, 4) * comb(54, 2) / comb(60, 6))
        day = analysis.probability_summary("diadesorte")
        numeric = sum(t["probability"] for t in day["tiers"] if t["matches"] is not None)
        self.assertAlmostEqual(day["any_prize"], numeric + (1 - numeric) / 12)

    def test_cache_refreshes_after_csv_update(self):
        payload = self.use_draws("megasena", [4])
        self.assertEqual(analysis.analyze_game("megasena", payload)["history"]["best_matches"], 4)
        path = lottery.LOTTERY_CONFIGS["megasena"]["FILE_PATH"]
        frame = pd.read_csv(path)
        frame.loc[0, "bola 5"] = 5
        frame.to_csv(path, index=False)
        self.assertEqual(analysis.analyze_game("megasena", payload)["history"]["best_matches"], 5)

    def test_strategies_use_existing_filter_threshold(self):
        payload = self.use_draws("quina", [2])
        result = analysis.analyze_game("quina", payload)
        self.assertEqual(result["history"]["prize_draws"], 1)
        modes = {s["mode"] for s in result["strategies"]}
        self.assertIn("balanced_parity", modes)
        self.assertIn("never_prize", modes)
        self.assertIn("balanced_never_prize", modes)
        self.assertNotIn("even_only", modes)

    def test_corrupt_and_missing_data(self):
        payload = self.use_draws("megasena", [6])
        path = lottery.LOTTERY_CONFIGS["megasena"]["FILE_PATH"]
        frame = pd.read_csv(path)
        frame.loc[0, "bola 1"] = 61
        frame.to_csv(path, index=False)
        with self.assertRaises(analysis.HistoryUnavailable):
            analysis.analyze_game("megasena", payload)
        Path(path).unlink()
        with self.assertRaises(analysis.HistoryUnavailable):
            analysis.analyze_game("megasena", payload)


class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment_patch = patch.dict(os.environ, {'DATABASE_URL': '', 'RENDER': ''})
        cls.environment_patch.start()
        cls.module = importlib.import_module("app")
        cls.temp = tempfile.TemporaryDirectory()
        cls.db_patch = patch.object(cls.module.auth_storage, "AUTH_DB_PATH", str(Path(cls.temp.name) / "auth.sqlite3"))
        cls.db_patch.start()
        cls.users = {}
        for role, plan in (("user", "free"), ("user", "premium"), ("admin", "premium")):
            cls.users[role if role == "admin" else plan] = cls.module.auth_storage.create_user(
                "Teste", f"{role}-{plan}@example.com", "TesteSeguro123!", role=role, plan=plan, terms_accepted=True)

    @classmethod
    def tearDownClass(cls):
        cls.db_patch.stop()
        cls.environment_patch.stop()
        cls.temp.cleanup()

    def client_for(self, kind):
        client = self.module.app.test_client()
        with client.session_transaction() as session:
            if kind == "guest":
                session["guest_access"] = True
                session["guest_id"] = "test-guest"
            else:
                session["user_id"] = self.users[kind]["id"]
            session["csrf_token"] = "test-csrf"
        return client

    def test_access_control_and_csrf(self):
        path = "/analyze_game/megasena"
        payload = {"numbers": [1, 2, 3, 4, 5, 6]}
        self.assertEqual(self.module.app.test_client().post(path, json=payload).status_code, 401)
        for kind in ("guest", "free"):
            self.assertEqual(self.client_for(kind).post(path, json=payload).status_code, 403)
        for kind in ("premium", "admin"):
            client = self.client_for(kind)
            self.assertEqual(client.post(path, json=payload).status_code, 403)
            with patch.object(analysis, "analyze_game", return_value={"ok": True}) as service:
                response = client.post(path, json=payload, headers={"X-CSRF-Token": "test-csrf"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                service.assert_called_once()

    def test_bad_payloads_and_errors(self):
        client = self.client_for("premium")
        headers = {"X-CSRF-Token": "test-csrf"}
        for payload in ([], None, {}, {"numbers": [True] * 6}):
            self.assertEqual(client.post("/analyze_game/megasena", json=payload, headers=headers).status_code, 400)
        self.assertEqual(client.post("/analyze_game/invalid", json={}, headers=headers).status_code, 400)
        self.assertEqual(client.post("/analyze_game/megasena", data="{" , content_type="application/json", headers=headers).status_code, 400)
        self.assertEqual(client.post("/analyze_game/megasena", data="x" * 17000, content_type="application/json", headers=headers).status_code, 413)
        with patch.object(analysis, "analyze_game", side_effect=analysis.HistoryUnavailable("Indisponível")):
            self.assertEqual(client.post("/analyze_game/megasena", json={}, headers=headers).status_code, 503)

    def test_static_files_are_explicitly_allowed(self):
        client = self.module.app.test_client()
        for path in ("/app.py", "/game_analysis.py", "/static/app.py", "/./app.py", "/%2e/app.py", "/.env", "/models/quina_model.json"):
            self.assertEqual(client.get(path).status_code, 404, path)
        for path in ("/", "/style.css", "/js/main.js", "/js/gameAnalysis.js"):
            with client.get(path) as response:
                self.assertEqual(response.status_code, 200, path)


if __name__ == "__main__":
    unittest.main()
