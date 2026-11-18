"""Runs against the disposable PostgreSQL service in CI, never a Supabase project."""

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit, urlunsplit, quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import auth_storage
import database
import history_database
import manage_database


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'PostgreSQL de teste não configurado; executado no GitHub Actions.')
class PostgresIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = os.environ['TEST_DATABASE_URL']
        parsed = urlsplit(url)
        if parsed.hostname not in {'localhost', '127.0.0.1', '::1'} or not parsed.path.endswith('lottery_test'):
            raise RuntimeError('Os testes PostgreSQL só aceitam banco local descartável chamado lottery_test.')
        cls.password = 'local-integration-password-12345'
        cls.env = patch.dict(os.environ, {'DATABASE_URL': '', 'DATABASE_ADMIN_URL': url, 'DATABASE_SSLMODE': 'disable', 'DATABASE_APP_PASSWORD': cls.password})
        cls.env.start()
        manage_database.initialize_database()
        host = f'[{parsed.hostname}]' if ':' in parsed.hostname else parsed.hostname
        cls.runtime_url = urlunsplit((parsed.scheme, f'lottery_app:{quote(cls.password)}@{host}:{parsed.port or 5432}', parsed.path, '', ''))

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()

    def setUp(self):
        connection = manage_database.admin_connection()
        try:
            connection.raw.execute('TRUNCATE lottery_private.generated_games, lottery_private.usage_days, lottery_private.audit_logs, lottery_private.users RESTART IDENTITY CASCADE')
            connection.commit()
        finally:
            connection.close()
        self.runtime = patch.dict(os.environ, {'DATABASE_URL': self.runtime_url})
        self.runtime.start()
        self.addCleanup(self.runtime.stop)

    def test_auth_plans_usage_and_history_survive_new_connections(self):
        user = auth_storage.create_user('Cloud', 'cloud@example.com', 'CloudPassword123!', terms_accepted=True)
        self.assertEqual(auth_storage.verify_user_credentials('cloud@example.com', 'CloudPassword123!')['id'], user['id'])
        with self.assertRaises(ValueError):
            auth_storage.create_user('Duplicate', 'cloud@example.com', 'CloudPassword123!', terms_accepted=True)
        self.assertEqual(auth_storage.update_user_plan(user['id'], 'premium')['plan'], 'premium')
        auth_storage.record_generated_games(user['id'], 3)
        auth_storage.record_generated_games(user['id'], 4)
        self.assertEqual(auth_storage.get_daily_usage(user['id']), 7)
        self.assertEqual(len(auth_storage.list_users()), 1)
        history_database.save_history_record('same.csv', 'megasena', [[1]], owner_key=f"user:{user['id']}")
        history_database.save_history_record('same.csv', 'megasena', [[2]], owner_key=f"user:{user['id']}")
        self.assertEqual(history_database.read_history_file('same.csv', f"user:{user['id']}"), [[2]])
        self.assertIsNone(history_database.read_history_file('same.csv', 'user:999'))
        self.assertEqual(history_database.clear_history('megasena', f"user:{user['id']}"), ['same.csv'])

    def test_runtime_role_cannot_create_tables(self):
        connection = database.open_postgres()
        try:
            self.assertEqual(connection.execute("SELECT has_schema_privilege(current_user, 'lottery_private', 'CREATE') AS allowed").fetchone()['allowed'], False)
            with self.assertRaises(database.DatabaseUnavailable):
                connection.execute('CREATE TABLE lottery_private.not_allowed (id INT)')
        finally:
            connection.close()

    def test_migration_preserves_ids_passwords_and_rejects_nonempty_target(self):
        with tempfile.TemporaryDirectory() as directory:
            auth_path = str(Path(directory) / 'old-auth.db')
            history_path = str(Path(directory) / 'old-history.db')
            with patch.dict(os.environ, {'DATABASE_URL': ''}), patch.object(auth_storage, 'AUTH_DB_PATH', auth_path), patch.object(history_database, 'HISTORY_DB_PATH', history_path):
                user = auth_storage.create_user('Original', 'original@example.com', 'OriginalPassword123!', plan='premium', terms_accepted=True)
                history_database.save_history_record('saved.csv', 'megasena', [[1, 2]], owner_key=f"user:{user['id']}")
                snapshot = manage_database.read_legacy(auth_path, history_path)
            manage_database.import_snapshot(snapshot)
            self.assertEqual(auth_storage.verify_user_credentials('original@example.com', 'OriginalPassword123!')['plan'], 'premium')
            self.assertEqual(history_database.read_history_file('saved.csv', f"user:{user['id']}"), [[1, 2]])
            next_user = auth_storage.create_user('Next', 'next@example.com', 'NextPassword123!', terms_accepted=True)
            self.assertGreater(next_user['id'], user['id'])
            with self.assertRaises(ValueError):
                manage_database.import_snapshot(snapshot)
            self.assertEqual(len(auth_storage.list_users()), 2)


if __name__ == '__main__':
    unittest.main()
