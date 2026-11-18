"""Explicit provisioning, encrypted backups and all-or-nothing migration."""

import argparse
import csv
from contextlib import ExitStack
import datetime
import getpass
import json
import os
from pathlib import Path
import sqlite3
import re
import secrets
import sys
from urllib.parse import quote, urlsplit, urlunsplit

import database
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / '.env')


TABLE_COLUMNS = {
    'users': ('id', 'name', 'email', 'password_hash', 'role', 'plan', 'is_active', 'created_at', 'updated_at', 'last_login_at', 'terms_accepted_at', 'terms_version'),
    'usage_days': ('user_id', 'usage_date', 'generated_games'),
    'audit_logs': ('id', 'actor_user_id', 'action', 'target_user_id', 'details_json', 'created_at'),
    'generated_games': ('owner_key', 'filename', 'lottery_type', 'created_at', 'games_json'),
}


def write_private_text(path, text):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        stream.write(text)


def configure_locally(project_ref=None, host=None, directory=None):
    from cryptography.fernet import Fernet
    root = Path(directory or PROJECT_ROOT)
    admin_file, render_file = root / '.env.admin', root / '.env.render'
    if admin_file.exists() or render_file.exists():
        raise ValueError('Já existe uma configuração local. Nenhum arquivo foi sobrescrito; edite os arquivos existentes com cuidado.')
    project_ref = project_ref or input('Referência do projeto Supabase: ').strip()
    host = host or input('Host do Session pooler: ').strip()
    if not re.fullmatch(r'[a-z0-9]{20}', project_ref) or not re.fullmatch(r'[a-z0-9-]+\.pooler\.supabase\.com', host):
        raise ValueError('Referência ou host do Session pooler inválido.')
    certificate = Path(input('Caminho do certificado raiz baixado do Supabase: ').strip().strip('"')).expanduser().resolve()
    if not certificate.is_file():
        raise ValueError('Certificado não encontrado. Baixe o certificado no painel do Supabase.')
    password = getpass.getpass('Nova senha do banco (digitação oculta, não envie ao chat): ')
    if not password or any(char in password for char in '\r\n\0'):
        raise ValueError('Senha inválida.')
    if password != getpass.getpass('Confirme a nova senha do banco (digitação oculta): '):
        raise ValueError('As senhas não conferem. Nenhum arquivo foi criado.')
    app_password = secrets.token_urlsafe(32)
    admin_url = f'postgresql://postgres.{project_ref}:{quote(password, safe="")}@{host}:5432/postgres'
    app_url = f'postgresql://lottery_app.{project_ref}:{quote(app_password, safe="")}@{host}:5432/postgres'
    admin_values = {
        'DATABASE_ADMIN_URL': admin_url, 'DATABASE_APP_PASSWORD': app_password,
        'DATABASE_URL': app_url, 'DATABASE_SSLMODE': 'verify-full',
        'DATABASE_SSLROOTCERT': certificate.as_posix(), 'LOTTERY_BACKUP_KEY': Fernet.generate_key().decode(),
    }
    render_values = {
        'DATABASE_URL': app_url, 'DATABASE_SSLMODE': 'verify-full',
        'DATABASE_SSLROOTCERT': '/etc/secrets/supabase-ca.crt',
        'SESSION_COOKIE_SECURE': '1', 'LOTTERY_USE_ML': '0', 'LOTTERY_AUTO_UPDATE': '0',
        'LOTTERY_PUBLISH_AFTER_UPDATE': '0', 'LOTTERY_AUTO_OPEN_BROWSER': '0',
    }
    # JSON string quoting is compatible with dotenv and escapes local path syntax.
    write_private_text(admin_file, ''.join(f'{key}={json.dumps(value, ensure_ascii=False)}\n' for key, value in admin_values.items()))
    write_private_text(render_file, ''.join(f'{key}={json.dumps(value, ensure_ascii=False)}\n' for key, value in render_values.items()))
    print('Configuração local preparada em .env.admin e .env.render. Nenhuma conexão externa foi feita.')
    print('Não envie esses arquivos ao chat ou ao GitHub. Guarde a chave de backup separadamente.')


def update_admin_password(env_file):
    from dotenv import dotenv_values, set_key
    if not env_file or not Path(env_file).is_file():
        raise ValueError('Informe o arquivo administrativo existente com --env-file .env.admin.')
    values = dotenv_values(env_file)
    url = values.get('DATABASE_ADMIN_URL', '')
    parsed = urlsplit(url)
    if parsed.scheme not in {'postgres', 'postgresql'} or not parsed.hostname or not parsed.username or parsed.fragment:
        raise ValueError('Conexão administrativa inválida no arquivo local.')
    password = getpass.getpass('Senha atual correta do banco no Supabase (digitação oculta): ')
    if not password or any(char in password for char in '\r\n\0'):
        raise ValueError('Senha inválida.')
    if password != getpass.getpass('Confirme a senha (digitação oculta): '):
        raise ValueError('As senhas não conferem. A configuração não foi alterada.')
    server = parsed.netloc.rsplit('@', 1)[-1]
    updated = urlunsplit((parsed.scheme, f'{parsed.username}:{quote(password, safe="")}@{server}', parsed.path, parsed.query, ''))
    set_key(str(env_file), 'DATABASE_ADMIN_URL', updated, quote_mode='always')
    print('Senha administrativa atualizada apenas no arquivo local. A senha do app e a chave de backup não foram alteradas.')


def admin_connection():
    url = os.environ.get('DATABASE_ADMIN_URL', '').strip()
    if not url:
        raise ValueError('Configure DATABASE_ADMIN_URL somente no ambiente administrativo local.')
    return database.open_postgres(url)


def initialize_database():
    from psycopg import sql
    password = os.environ.get('DATABASE_APP_PASSWORD', '')
    if len(password) < 24:
        raise ValueError('DATABASE_APP_PASSWORD precisa ter pelo menos 24 caracteres.')
    connection = admin_connection()
    try:
        connection.raw.execute(Path(__file__).with_name('migrations').joinpath('001_private_postgres.sql').read_text(encoding='utf-8'))
        existing = connection.raw.execute("SELECT 1 FROM pg_roles WHERE rolname = 'lottery_app'").fetchone()
        command = 'ALTER ROLE' if existing else 'CREATE ROLE'
        connection.raw.execute(sql.SQL(command + ' {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD {}').format(
            sql.Identifier('lottery_app'), sql.Literal(password)))
        connection.raw.execute('GRANT USAGE ON SCHEMA lottery_private TO lottery_app')
        connection.raw.execute('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA lottery_private TO lottery_app')
        connection.raw.execute('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA lottery_private TO lottery_app')
        connection.commit()
    finally:
        connection.close()


def read_sqlite_tables(path, names):
    if not Path(path).is_file():
        raise ValueError('Arquivo SQLite de origem não encontrado. Nenhuma base vazia foi criada.')
    connection = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute('BEGIN')
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if ('users' in names and 'users' not in tables) or ('generated_games' in names and 'generated_games' not in tables):
            raise ValueError('O arquivo de origem não contém a tabela esperada.')
        result = {}
        for name in names:
            if name not in tables:
                result[name] = []
                continue
            rows = [dict(row) for row in connection.execute(f'SELECT * FROM {name}')]
            for row in rows:
                if name == 'users':
                    row.setdefault('terms_accepted_at', None)
                    row.setdefault('terms_version', None)
                elif name == 'generated_games':
                    row.setdefault('owner_key', 'legacy')
            result[name] = rows
        return result
    finally:
        connection.close()


def include_csv_history(snapshot, directory):
    root = Path(directory).resolve()
    if not root.is_dir():
        raise ValueError('Diretório de histórico CSV não encontrado.')
    counts = {'megasena': (6, 60), 'quina': (5, 80), 'lotofacil': (15, 25), 'diadesorte': (7, 31)}
    pattern = re.compile(r'^(megasena|quina|lotofacil|diadesorte)_resultados_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(?:_\d{6})?)\.csv$')
    user_ids = {row['id'] for row in snapshot['tables']['users']}
    records = snapshot['tables']['generated_games']
    existing = {(row['owner_key'], row['filename']): row for row in records}
    summary = {'files': 0, 'added': 0, 'already_present': 0, 'legacy_added': 0}
    for path in sorted(root.rglob('*.csv')):
        try:
            path.resolve().relative_to(root)
        except ValueError:
            raise ValueError('CSV fora do diretório de origem. Importação cancelada.') from None
        relative = path.relative_to(root)
        if len(relative.parts) == 1:
            owner = 'legacy'
        elif len(relative.parts) == 2 and re.fullmatch(r'user_[1-9]\d*', relative.parts[0]):
            user_id = int(relative.parts[0][5:])
            if user_id not in user_ids:
                raise ValueError('Pasta de histórico sem conta correspondente na origem.')
            owner = f'user:{user_id}'
        elif len(relative.parts) == 2 and re.fullmatch(r'guest_[A-Za-z0-9_-]+', relative.parts[0]):
            owner = 'guest:' + relative.parts[0][6:]
        else:
            raise ValueError('Pasta CSV sem proprietário identificável. Nenhum arquivo foi atribuído automaticamente.')
        match = pattern.fullmatch(path.name)
        if not match:
            raise ValueError('CSV com nome de histórico não reconhecido. Revise a origem antes de importar.')
        kind, stamp = match.groups()
        ball_count, maximum = counts[kind]
        games = []
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.reader(stream)
            header = next(reader, [])
            width = ball_count + int(kind == 'diadesorte')
            if len(header) != width:
                raise ValueError('CSV com quantidade inesperada de colunas.')
            for values in reader:
                if not values or not any(value.strip() for value in values):
                    continue
                if len(values) != width:
                    raise ValueError('CSV com linha incompleta.')
                try:
                    numbers = [int(value.strip()) for value in values[:ball_count]]
                except ValueError:
                    raise ValueError('CSV contém dezenas inválidas.') from None
                if len(set(numbers)) != ball_count or not all(1 <= number <= maximum for number in numbers):
                    raise ValueError('CSV contém dezenas repetidas ou fora da faixa.')
                game = numbers + ([values[-1].strip()] if kind == 'diadesorte' else [])
                games.append(game)
        if not games:
            raise ValueError('CSV de histórico vazio. Revise a origem antes de importar.')
        summary['files'] += 1
        key = (owner, path.name)
        if key in existing:
            if json.loads(existing[key]['games_json']) != games:
                raise ValueError('CSV e banco divergem para o mesmo histórico. Nenhum registro foi sobrescrito.')
            summary['already_present'] += 1
            continue
        created_at = datetime.datetime.strptime(stamp, '%Y-%m-%d_%H-%M-%S_%f' if stamp.count('_') == 2 else '%Y-%m-%d_%H-%M-%S')
        row = {'owner_key': owner, 'filename': path.name, 'lottery_type': kind,
               'created_at': created_at.isoformat(timespec='microseconds'),
               'games_json': json.dumps(games, ensure_ascii=False)}
        records.append(row)
        existing[key] = row
        summary['added'] += 1
        summary['legacy_added'] += int(owner == 'legacy')
    snapshot['csv_import'] = summary
    return snapshot


def read_legacy(auth_path, history_path=None, history_directory=None):
    data = read_sqlite_tables(auth_path, ('users', 'usage_days', 'audit_logs'))
    data.update(read_sqlite_tables(history_path, ('generated_games',)) if history_path else {'generated_games': []})
    snapshot = validate_snapshot({'version': 1, 'tables': data})
    if history_directory:
        include_csv_history(snapshot, history_directory)
    return validate_snapshot(snapshot)


def validate_snapshot(snapshot):
    if not isinstance(snapshot, dict) or snapshot.get('version') != 1 or not isinstance(snapshot.get('tables'), dict):
        raise ValueError('Formato de backup inválido.')
    tables = snapshot['tables']
    if set(tables) != set(TABLE_COLUMNS):
        raise ValueError('Backup incompleto: tabelas ausentes ou inesperadas.')
    user_ids = set()
    emails = set()
    for name, columns in TABLE_COLUMNS.items():
        if not isinstance(tables[name], list):
            raise ValueError('Tabela inválida no backup.')
        for row in tables[name]:
            if not isinstance(row, dict) or any(column not in row for column in columns):
                raise ValueError('Backup com colunas ausentes.')
            if name == 'users':
                if row['id'] in user_ids or row['email'] in emails or row['role'] not in {'user', 'admin'} or row['plan'] not in {'free', 'premium'}:
                    raise ValueError('Contas conflitantes no backup.')
                user_ids.add(row['id'])
                emails.add(row['email'])
    for row in tables['usage_days']:
        if row['user_id'] not in user_ids:
            raise ValueError('Uso diário sem proprietário na origem.')
    for row in tables['audit_logs']:
        if any(row[key] is not None and row[key] not in user_ids for key in ('actor_user_id', 'target_user_id')):
            raise ValueError('Auditoria com referência a conta ausente.')
    for row in tables['generated_games']:
        owner = row['owner_key']
        if not isinstance(owner, str) or (owner.startswith('user:') and (not owner[5:].isdigit() or int(owner[5:]) not in user_ids)):
            raise ValueError('Histórico com proprietário inválido. Migração cancelada.')
        if not isinstance(json.loads(row['games_json']), list):
            raise ValueError('Histórico inválido no backup.')
    return snapshot


def cipher():
    from cryptography.fernet import Fernet
    key = os.environ.get('LOTTERY_BACKUP_KEY', '').strip()
    if not key:
        raise ValueError('Configure LOTTERY_BACKUP_KEY e guarde a chave fora do backup.')
    try:
        return Fernet(key.encode('ascii'))
    except (ValueError, UnicodeError):
        raise ValueError('LOTTERY_BACKUP_KEY inválida.') from None


def write_encrypted(snapshot, output):
    output = Path(output)
    if output.suffix != '.enc':
        raise ValueError('O backup deve terminar em .enc.')
    payload = cipher().encrypt(json.dumps(validate_snapshot(snapshot), ensure_ascii=False).encode('utf-8'))
    output.parent.mkdir(parents=True, exist_ok=True)
    # Refuse overwrites and restrict permissions on systems supporting POSIX modes.
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(payload)


def read_encrypted(path):
    from cryptography.fernet import InvalidToken
    try:
        data = cipher().decrypt(Path(path).read_bytes())
    except InvalidToken:
        raise ValueError('Chave incorreta ou backup alterado. Nenhum dado foi importado.') from None
    return validate_snapshot(json.loads(data))


def backup_postgres(output):
    connection = admin_connection()
    try:
        connection.raw.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        tables = {name: connection.raw.execute(f'SELECT * FROM lottery_private.{name}').fetchall() for name in TABLE_COLUMNS}
        snapshot = {'version': 1, 'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'tables': tables}
        write_encrypted(snapshot, output)
    finally:
        connection.close()
    return snapshot


def import_snapshot(snapshot):
    from psycopg import sql
    snapshot = validate_snapshot(snapshot)
    connection = admin_connection()
    try:
        connection.raw.execute('LOCK TABLE lottery_private.users, lottery_private.usage_days, lottery_private.audit_logs, lottery_private.generated_games IN ACCESS EXCLUSIVE MODE')
        if any(connection.raw.execute(f'SELECT EXISTS(SELECT 1 FROM lottery_private.{name}) AS present').fetchone()['present'] for name in TABLE_COLUMNS):
            raise ValueError('O destino precisa estar vazio. Nenhum registro existente será sobrescrito.')
        for name, columns in TABLE_COLUMNS.items():
            statement = sql.SQL('INSERT INTO {}.{} ({}) VALUES ({})').format(
                sql.Identifier('lottery_private'), sql.Identifier(name),
                sql.SQL(',').join(map(sql.Identifier, columns)),
                sql.SQL(',').join(sql.Placeholder() for _ in columns))
            for row in snapshot['tables'][name]:
                connection.raw.execute(statement, tuple(row[column] for column in columns))
        for name in ('users', 'audit_logs'):
            connection.raw.execute(f"SELECT setval(pg_get_serial_sequence('lottery_private.{name}', 'id'), COALESCE((SELECT MAX(id) FROM lottery_private.{name}), 0) + 1, false)")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Prepara o banco privado, migra e protege backups.')
    parser.add_argument('--env-file', help='Arquivo local de configuração administrativa, nunca versionado.')
    commands = parser.add_subparsers(dest='command', required=True)
    configure = commands.add_parser('configure')
    configure.add_argument('--project-ref')
    configure.add_argument('--host')
    commands.add_parser('init')
    commands.add_parser('check')
    commands.add_parser('update-admin-password')
    migrate = commands.add_parser('migrate')
    migrate.add_argument('--auth-db', required=True)
    migrate.add_argument('--history-db')
    migrate.add_argument('--history-dir', help='Inclui CSVs locais, conferindo duplicatas e proprietários.')
    migrate.add_argument('--output', required=True, help='Backup criptografado obrigatório antes da migração.')
    migrate.add_argument('--apply', action='store_true')
    backup = commands.add_parser('backup')
    backup.add_argument('--output', required=True)
    verify = commands.add_parser('verify-backup')
    verify.add_argument('file')
    restore = commands.add_parser('restore')
    restore.add_argument('file')
    restore.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    sources = ExitStack()
    try:
        if args.command == 'configure':
            configure_locally(args.project_ref, args.host)
            return 0
        if args.env_file:
            from dotenv import load_dotenv
            if not Path(args.env_file).is_file():
                raise ValueError('Arquivo administrativo não encontrado.')
            load_dotenv(args.env_file, override=True)
        if args.command == 'update-admin-password':
            update_admin_password(args.env_file)
            return 0
        if args.command == 'check':
            connection = database.open_postgres()
            try:
                for name in TABLE_COLUMNS:
                    connection.execute(f'SELECT 1 FROM {name} LIMIT 1')
                print('Conexão segura e acesso às quatro tabelas confirmados.')
            finally:
                connection.close()
            return 0
        if args.command == 'init':
            initialize_database()
            print('Estrutura privada e usuário restrito preparados. Nenhuma conta do app foi criada.')
            return 0
        if args.command == 'migrate':
            if args.apply:
                for path in dict.fromkeys(filter(None, (args.auth_db, args.history_db))):
                    if not Path(path).is_file():
                        raise ValueError('Banco de origem não encontrado.')
                    source = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=rw', uri=True, timeout=10)
                    sources.callback(source.close)
                    source.execute('BEGIN IMMEDIATE')
            snapshot = read_legacy(args.auth_db, args.history_db, args.history_dir)
            write_encrypted(snapshot, args.output)
            if read_encrypted(args.output) != snapshot:
                raise ValueError('Não foi possível validar o backup criptografado. Importação cancelada.')
        elif args.command == 'backup':
            snapshot = backup_postgres(args.output)
        else:
            snapshot = read_encrypted(args.file)
        print('Registros verificados:', ', '.join(f'{name}={len(rows)}' for name, rows in snapshot['tables'].items()))
        if args.command in {'migrate', 'restore'}:
            if args.apply:
                import_snapshot(snapshot)
                print('Importação confirmada. IDs, planos e hashes de senha foram preservados.')
            else:
                print('Somente verificação. Use --apply para importar em um destino vazio.')
        return 0
    except Exception as error:
        # Never print driver exceptions: they may contain connection credentials or rows.
        message = str(error) if isinstance(error, (ValueError, database.DatabaseUnavailable, FileExistsError)) else 'Falha na operação. Verifique a configuração e a estrutura dos dados; detalhes privados foram omitidos.'
        print(message, file=sys.stderr)
        return 1
    finally:
        sources.close()


if __name__ == '__main__':
    raise SystemExit(main())
