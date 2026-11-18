from contextlib import redirect_stdout, redirect_stderr
import csv
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import auth_storage
import database
import gerador_loterias
import history_database
import history_storage
import manage_database
import publish_lottery_data
import trigger_render_deploy


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment = patch.dict(os.environ, {'DATABASE_URL': '', 'DATABASE_SSLMODE': 'verify-full', 'DATABASE_SSLROOTCERT': ''})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_tls_is_mandatory_except_loopback_test_database(self):
        for value in ('', 'sqlite:///file', 'not-a-url'):
            with self.assertRaises(database.DatabaseUnavailable):
                database.connection_options(value)
        with self.assertRaises(database.DatabaseUnavailable):
            database.connection_options('postgresql://lottery_app:secret@db.example.com/postgres')
        with patch.dict(os.environ, {'DATABASE_SSLMODE': 'disable'}):
            with self.assertRaises(database.DatabaseUnavailable):
                database.connection_options('postgresql://app:secret@remote.example.com/db')
            self.assertEqual(database.connection_options('postgresql://app:secret@127.0.0.1/db')['sslmode'], 'disable')
        certificate = Path(self.directory.name) / 'ca.crt'
        certificate.touch()
        with patch.dict(os.environ, {'DATABASE_SSLROOTCERT': str(certificate)}):
            options = database.connection_options('postgresql://app:secret@db.example.com/db?sslmode=disable')
            self.assertEqual(options['sslmode'], 'verify-full')
            self.assertIsNone(options['prepare_threshold'])

    def test_bound_parameters_are_never_interpolated(self):
        import psycopg
        raw = MagicMock()
        adapter = database.PostgresConnection(raw, psycopg)
        malicious = "x' OR 1=1 --"
        adapter.execute('SELECT * FROM users WHERE email = ?', (malicious,))
        raw.execute.assert_called_once_with('SELECT * FROM users WHERE email = %s', (malicious,))

    def test_windows_unicode_certificate_uses_temporary_ascii_path_without_disabling_tls(self):
        certificate = Path(self.directory.name) / 'certificação.crt'
        certificate.write_bytes(b'public-ca-test')
        options = {'sslrootcert': str(certificate), 'sslmode': 'verify-full'}
        with patch.object(database.sys, 'platform', 'win32'):
            with database.certificate_options(options) as prepared:
                target = Path(prepared['sslrootcert'])
                self.assertTrue(str(target).isascii())
                self.assertEqual(target.read_bytes(), b'public-ca-test')
                self.assertEqual(prepared['sslmode'], 'verify-full')
            self.assertFalse(target.exists())
        self.assertTrue(certificate.exists())

    def test_windows_unicode_password_uses_private_temporary_passfile(self):
        from urllib.parse import quote
        from psycopg.conninfo import make_conninfo
        password = 'senha-sintética:com\\acentos'
        url = f'postgresql://lottery_app:{quote(password, safe="")}@localhost/test'
        options = {'sslmode': 'verify-full'}
        with patch.object(database.sys, 'platform', 'win32'):
            with database.password_options(url, options) as (safe_url, prepared):
                self.assertNotIn('password', safe_url)
                self.assertNotIn('sint', safe_url)
                target = Path(prepared['passfile'])
                self.assertIn('senha-sintética\\:com\\\\acentos', target.read_text(encoding='utf-8'))
                self.assertEqual(prepared['sslmode'], 'verify-full')
                make_conninfo(safe_url, **prepared)
            self.assertFalse(target.exists())

    def test_database_error_never_falls_back_to_sqlite(self):
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://app:private-password@remote/db'}), \
             patch.object(database, 'open_postgres', side_effect=database.DatabaseUnavailable('offline')), \
             patch.object(sqlite3, 'connect') as local:
            for storage in (auth_storage, history_database):
                with self.assertRaises(database.DatabaseUnavailable):
                    storage._connect()
            local.assert_not_called()

    def test_runtime_refuses_administrator_connection_and_hides_connection_errors(self):
        import psycopg
        url = 'postgresql://postgres:private-password@127.0.0.1/lottery_test'
        raw = MagicMock()
        raw.execute.return_value.fetchone.return_value = {'role': 'postgres'}
        with patch.dict(os.environ, {'DATABASE_URL': url, 'DATABASE_SSLMODE': 'disable'}), patch.object(psycopg, 'connect', return_value=raw):
            with self.assertRaises(database.DatabaseUnavailable) as raised:
                database.open_postgres()
            self.assertNotIn('private-password', str(raised.exception))
            raw.close.assert_called_once()
        with patch.dict(os.environ, {'DATABASE_URL': url, 'DATABASE_SSLMODE': 'disable'}), patch.object(psycopg, 'connect', side_effect=psycopg.OperationalError(url)):
            with self.assertRaises(database.DatabaseUnavailable) as raised:
                database.open_postgres()
            self.assertNotIn('private-password', str(raised.exception))

    def test_empty_admin_setup_code_cannot_bootstrap_admin(self):
        import app
        with patch.dict(os.environ, {'ADMIN_EMAIL': 'admin-test@example.com', 'ADMIN_SETUP_CODE': ''}), \
             patch.object(auth_storage, 'admin_exists', return_value=False), \
             patch.object(auth_storage, 'create_user') as create:
            response = app.app.test_client().post('/auth/register', json={
                'name': 'Admin', 'email': 'admin-test@example.com', 'password': 'Password12345!', 'terms_accepted': True,
            })
        self.assertEqual(response.status_code, 403)
        create.assert_not_called()

    def test_database_failure_is_a_safe_503_response(self):
        import app
        with patch.object(auth_storage, '_connect', side_effect=database.DatabaseUnavailable('offline')):
            response = app.app.test_client().get('/health')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('offline', response.get_data(as_text=True))

    def test_postgres_does_not_read_local_history_as_fallback(self):
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://app:secret@remote/db'}), \
             patch.object(history_database, 'read_history_file', return_value=None), \
             patch.object(history_storage.pd, 'read_csv') as read:
            self.assertIsNone(history_storage.read_history_file('megasena_resultados_2026-01-01_12-00-00.csv', 'user:1'))
            read.assert_not_called()

    def test_postgres_saves_only_to_remote_database_and_propagates_failures(self):
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://app:secret@remote/db'}), \
             patch.object(history_database, 'save_history_record') as save, \
             patch.object(gerador_loterias.pd, 'DataFrame') as frame:
            name = gerador_loterias.save_generated_games_to_csv([[1, 2, 3, 4, 5, 6]], 'megasena', self.directory.name, owner_key='user:5')
            self.assertTrue(name.endswith('.csv'))
            self.assertEqual(save.call_args.kwargs['owner_key'], 'user:5')
            frame.assert_not_called()
            save.side_effect = database.DatabaseUnavailable('offline')
            with self.assertRaises(database.DatabaseUnavailable):
                gerador_loterias.save_generated_games_to_csv([[1, 2, 3, 4, 5, 6]], 'megasena', self.directory.name, owner_key='user:5')

    def test_sqlite_still_persists_auth_and_isolated_histories(self):
        with patch.object(auth_storage, 'AUTH_DB_PATH', str(Path(self.directory.name) / 'auth.db')), \
             patch.object(history_database, 'HISTORY_DB_PATH', str(Path(self.directory.name) / 'history.db')):
            user = auth_storage.create_user('Teste', 'tester@example.com', 'Password12345!', terms_accepted=True)
            self.assertEqual(auth_storage.verify_user_credentials('tester@example.com', 'Password12345!')['id'], user['id'])
            auth_storage.record_generated_games(user['id'], 2)
            auth_storage.record_generated_games(user['id'], 3)
            self.assertEqual(auth_storage.get_daily_usage(user['id']), 5)
            history_database.save_history_record('one.csv', 'megasena', [[1, 2]], owner_key='user:1')
            history_database.save_history_record('one.csv', 'megasena', [[3, 4]], owner_key='user:1')
            self.assertEqual(history_database.read_history_file('one.csv', 'user:1'), [[3, 4]])
            self.assertIsNone(history_database.read_history_file('one.csv', 'user:2'))

    def test_only_public_draw_csvs_can_be_published(self):
        for path in ('.env', 'src/auth_storage.py', 'data/loterias_auth.sqlite3', '../secrets.csv'):
            with self.assertRaises(ValueError):
                publish_lottery_data.normalize_paths([path])

    def test_publication_never_commits_other_staged_files(self):
        with patch.object(publish_lottery_data, 'normalize_paths', return_value=['public-draw.csv']), \
             patch.object(publish_lottery_data, 'has_remote', return_value=True), \
             patch.object(publish_lottery_data, 'current_branch', return_value='master'), \
             patch.object(publish_lottery_data, 'staged_changes', return_value=['public-draw.csv']), \
             patch.object(publish_lottery_data, 'run_git') as run, redirect_stdout(io.StringIO()):
            self.assertEqual(publish_lottery_data.publish(['public-draw.csv'], 'test'), 0)
        self.assertIn(unittest.mock.call(['commit', '--only', '-m', 'test', '--', 'public-draw.csv']), run.call_args_list)

    def test_deploy_hook_validation_does_not_leak_secrets(self):
        secret = 'https://attacker.example.com/deploy?key=private-token'
        output = io.StringIO()
        with patch.dict(os.environ, {'RENDER_DEPLOY_HOOK': secret}), redirect_stderr(output):
            self.assertEqual(trigger_render_deploy.main(), 1)
        self.assertNotIn('private-token', output.getvalue())
        self.assertNotIn('attacker.example.com', output.getvalue())


class BackupTests(unittest.TestCase):
    def setUp(self):
        from cryptography.fernet import Fernet
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment = patch.dict(os.environ, {'DATABASE_URL': '', 'LOTTERY_BACKUP_KEY': Fernet.generate_key().decode()})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.path = Path(self.directory.name) / 'backup.enc'
        self.auth = Path(self.directory.name) / 'auth.sqlite3'
        self.history = Path(self.directory.name) / 'history.sqlite3'
        with patch.object(auth_storage, 'AUTH_DB_PATH', str(self.auth)), \
             patch.object(history_database, 'HISTORY_DB_PATH', str(self.history)):
            self.user = auth_storage.create_user('Migração', 'migration@example.com', 'OriginalPassword123!', plan='premium', terms_accepted=True)
            history_database.save_history_record('megasena_resultados_2026-01-01_12-00-00.csv', 'megasena', [[1, 2, 3, 4, 5, 6]], owner_key=f"user:{self.user['id']}")

    def snapshot(self):
        return manage_database.read_legacy(self.auth, self.history)

    def test_encrypted_backup_roundtrip_preserves_ownership_plan_and_hash(self):
        snapshot = self.snapshot()
        manage_database.write_encrypted(snapshot, self.path)
        self.assertNotIn(b'migration@example.com', self.path.read_bytes())
        self.assertNotIn(b'OriginalPassword123!', self.path.read_bytes())
        restored = manage_database.read_encrypted(self.path)
        self.assertEqual(snapshot, restored)
        self.assertEqual(restored['tables']['users'][0]['plan'], 'premium')
        self.assertEqual(restored['tables']['generated_games'][0]['owner_key'], f"user:{self.user['id']}")
        self.assertTrue(restored['tables']['users'][0]['password_hash'].startswith('pbkdf2:'))

    def test_wrong_key_tampering_and_overwrite_are_rejected(self):
        from cryptography.fernet import Fernet
        snapshot = self.snapshot()
        manage_database.write_encrypted(snapshot, self.path)
        with self.assertRaises(FileExistsError):
            manage_database.write_encrypted(snapshot, self.path)
        with patch.dict(os.environ, {'LOTTERY_BACKUP_KEY': Fernet.generate_key().decode()}):
            with self.assertRaises(ValueError):
                manage_database.read_encrypted(self.path)
        data = bytearray(self.path.read_bytes())
        data[-5] ^= 1
        self.path.write_bytes(data)
        with self.assertRaises(ValueError):
            manage_database.read_encrypted(self.path)

    def test_dry_run_never_connects_to_destination_and_does_not_change_source(self):
        before = self.auth.read_bytes()
        with patch.object(manage_database, 'admin_connection') as connect, redirect_stdout(io.StringIO()):
            self.assertEqual(manage_database.main(['migrate', '--auth-db', str(self.auth), '--history-db', str(self.history), '--output', str(self.path)]), 0)
        connect.assert_not_called()
        self.assertEqual(before, self.auth.read_bytes())

    def test_orphaned_history_is_rejected(self):
        snapshot = self.snapshot()
        snapshot['tables']['generated_games'][0]['owner_key'] = 'user:99999'
        with self.assertRaises(ValueError):
            manage_database.validate_snapshot(snapshot)

    def test_csv_migration_includes_legacy_without_duplicate_account_history(self):
        root = Path(self.directory.name) / 'csv-history'
        owner = root / f"user_{self.user['id']}"
        owner.mkdir(parents=True)
        filename = 'megasena_resultados_2026-01-01_12-00-00.csv'
        for path in (owner / filename, root / 'megasena_resultados_2026-01-02_12-00-00_123456.csv'):
            with path.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow([f'bola{i+1}' for i in range(6)])
                writer.writerow([1, 2, 3, 4, 5, 6])
        snapshot = manage_database.read_legacy(self.auth, self.history, root)
        self.assertEqual(snapshot['csv_import']['already_present'], 1)
        self.assertEqual(snapshot['csv_import']['added'], 1)
        self.assertEqual(snapshot['csv_import']['legacy_added'], 1)
        self.assertEqual(len(snapshot['tables']['generated_games']), 2)
        self.assertEqual({row['owner_key'] for row in snapshot['tables']['generated_games']}, {'legacy', f"user:{self.user['id']}"})
        with (owner / filename).open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow([f'bola{i+1}' for i in range(6)])
            writer.writerow([10, 20, 30, 40, 50, 60])
        with self.assertRaises(ValueError):
            manage_database.read_legacy(self.auth, self.history, root)

    def test_missing_source_does_not_create_an_empty_database(self):
        missing = Path(self.directory.name) / 'absent.db'
        with self.assertRaises(ValueError):
            manage_database.read_legacy(missing)
        self.assertFalse(missing.exists())

    def test_local_wizard_encodes_password_and_separates_runtime_secrets(self):
        certificate = Path(self.directory.name) / 'ca.crt'
        certificate.touch()
        with patch('builtins.input', return_value=str(certificate)), patch.object(manage_database.getpass, 'getpass', return_value='synthetic+password#%'), redirect_stdout(io.StringIO()) as output:
            manage_database.configure_locally('abcdefghijklmnopqrst', 'aws-0-region.pooler.supabase.com', self.directory.name)
        from dotenv import dotenv_values
        admin = dotenv_values(Path(self.directory.name) / '.env.admin')
        runtime = dotenv_values(Path(self.directory.name) / '.env.render')
        self.assertIn('synthetic%2Bpassword%23%25', admin['DATABASE_ADMIN_URL'])
        self.assertNotIn('synthetic', output.getvalue())
        self.assertNotIn('DATABASE_ADMIN_URL', runtime)
        self.assertNotIn('DATABASE_APP_PASSWORD', runtime)
        self.assertNotIn('LOTTERY_BACKUP_KEY', runtime)
        self.assertTrue(runtime['DATABASE_URL'].startswith('postgresql://lottery_app.'))
        with self.assertRaises(ValueError):
            manage_database.configure_locally('abcdefghijklmnopqrst', 'aws-0-region.pooler.supabase.com', self.directory.name)

    def test_admin_password_update_preserves_application_and_backup_keys(self):
        from dotenv import dotenv_values
        certificate = Path(self.directory.name) / 'ca.crt'
        certificate.touch()
        with patch('builtins.input', return_value=str(certificate)), patch.object(manage_database.getpass, 'getpass', return_value='synthetic-initial'), redirect_stdout(io.StringIO()):
            manage_database.configure_locally('abcdefghijklmnopqrst', 'aws-0-region.pooler.supabase.com', self.directory.name)
        path = Path(self.directory.name) / '.env.admin'
        before = dotenv_values(path)
        with patch.object(manage_database.getpass, 'getpass', return_value='synthetic-corrected+#%'), redirect_stdout(io.StringIO()) as output:
            manage_database.update_admin_password(path)
        after = dotenv_values(path)
        self.assertIn('synthetic-corrected%2B%23%25', after['DATABASE_ADMIN_URL'])
        self.assertNotIn('synthetic-corrected', output.getvalue())
        for key in ('DATABASE_APP_PASSWORD', 'DATABASE_URL', 'LOTTERY_BACKUP_KEY'):
            self.assertEqual(before[key], after[key])


if __name__ == '__main__':
    unittest.main()
