"""Isolated server used only by the browser smoke test."""

import logging
import os
from pathlib import Path
import sys
import tempfile


def main():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        os.environ['DATABASE_URL'] = ''
        os.environ['RENDER'] = ''
        for key, filename in {
            "AUTH_DB_PATH": "auth.sqlite3", "LOTTERY_HISTORY_DB": "history.sqlite3",
            "LOTTERY_OUTPUT_DIR": "history", "LOTTERY_LOG_FILE": "preview.log",
        }.items():
            os.environ[key] = str(Path(directory) / filename)
        os.environ["LOTTERY_USE_ML"] = "0"
        os.environ["SESSION_COOKIE_SECURE"] = "0"
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        import app
        for plan in ("premium", "free"):
            user = app.auth_storage.create_user("Conta de teste", f"{plan}@example.com", "PreviewTeste123!", plan=plan, terms_accepted=True)
            if '--history' in sys.argv and plan == 'premium':
                import game_analysis
                import history_database
                for kind, config in app.gerador_loterias.LOTTERY_CONFIGS.items():
                    draws, _, _ = game_analysis.load_validated_history(kind)
                    game = list(draws[0][2])
                    if kind == 'diadesorte':
                        game.append(config['EXTRA_CHOICES']['Mês da Sorte'][(draws[0][3] or 1) - 1])
                    if kind == 'maismilionaria':
                        game.extend(draws[0][3])
                    history_database.save_history_record(f'{kind}_resultados_2026-11-24_11-00-00.csv', kind, [game]*22, owner_key=f"user:{user['id']}")
        try:
            app.app.run(host="127.0.0.1", port=int(sys.argv[1]), debug=False, use_reloader=False)
        finally:
            logging.shutdown()


if __name__ == "__main__":
    main()
