"""PostgreSQL connections for private data; SQLite remains the local default."""

import logging
import os
import sys
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qs, unquote


class DatabaseUnavailable(Exception):
    pass


class IntegrityError(Exception):
    pass


def postgres_enabled():
    return bool(os.environ.get('DATABASE_URL', '').strip())


def connection_options(url):
    try:
        parsed = urlsplit(url)
        valid = (parsed.scheme in {'postgres', 'postgresql'} and parsed.hostname and parsed.username
                 and not parsed.fragment and not (set(parse_qs(parsed.query)) - {'sslmode', 'sslrootcert'}))
    except ValueError:
        valid = False
    if not valid:
        raise DatabaseUnavailable('Configure uma conexão PostgreSQL válida no ambiente do servidor.')
    mode = os.environ.get('DATABASE_SSLMODE', 'verify-full').strip()
    if mode != 'verify-full' and not (mode == 'disable' and parsed.hostname in {'localhost', '127.0.0.1', '::1'}):
        raise DatabaseUnavailable('O banco externo exige TLS com verificação do certificado (verify-full).')
    options = {
        'sslmode': mode, 'connect_timeout': 10, 'prepare_threshold': None,
        'application_name': 'snugbx-loterias',
        'options': '-c search_path=lottery_private,pg_catalog -c statement_timeout=15000',
    }
    if mode == 'verify-full':
        certificate = os.environ.get('DATABASE_SSLROOTCERT', '').strip()
        if not certificate or not Path(certificate).is_file():
            raise DatabaseUnavailable('Configure DATABASE_SSLROOTCERT com o certificado do banco.')
        options['sslrootcert'] = certificate
    return options


def _driver():
    try:
        import psycopg
        return psycopg
    except ImportError:
        raise DatabaseUnavailable('Instale as dependências do servidor para conectar ao banco externo.') from None


@contextmanager
def certificate_options(options):
    certificate = options.get('sslrootcert', '')
    if sys.platform != 'win32' or not certificate or certificate.isascii():
        yield options
        return
    # libpq/OpenSSL on Windows can reject valid Unicode file paths. Only the
    # public CA is copied; verification stays enabled and no credentials move.
    with tempfile.TemporaryDirectory(prefix='lottery-ca-') as directory:
        target = os.path.join(directory, 'root.crt')
        if not target.isascii():
            raise DatabaseUnavailable('Use um caminho sem acentos para o certificado e para a pasta temporária do Windows.')
        shutil.copyfile(certificate, target)
        yield {**options, 'sslrootcert': target}


@contextmanager
def password_options(url, options):
    parsed = urlsplit(url)
    password = unquote(parsed.password or '')
    if sys.platform != 'win32' or password.isascii():
        yield url, options
        return
    if any(character in password for character in '\r\n\0'):
        raise DatabaseUnavailable('A senha não pode conter quebras de linha ou caracteres de controle.')
    # Use libpq's documented password-file support for Windows Unicode parsing.
    # The file is local, private, never logged, and removed after the handshake.
    with tempfile.TemporaryDirectory(prefix='lottery-pgpass-') as directory:
        target = os.path.join(directory, 'pgpass.conf')
        if not target.isascii():
            raise DatabaseUnavailable('Use uma pasta temporária sem acentos para a conexão no Windows.')
        fields = [parsed.hostname, str(parsed.port or 5432), unquote(parsed.path.lstrip('/')) or 'postgres', unquote(parsed.username), password]
        escaped = [field.replace('\\', '\\\\').replace(':', '\\:') for field in fields]
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(':'.join(escaped) + '\n')
        server = parsed.netloc.rsplit('@', 1)[-1]
        safe_url = urlunsplit(parsed._replace(netloc=f'{parsed.username}@{server}'))
        yield safe_url, {**options, 'passfile': target}


def open_postgres(url=None):
    url = url if url is not None else os.environ.get('DATABASE_URL', '').strip()
    options = connection_options(url)
    driver = _driver()
    from psycopg.rows import dict_row
    raw = None
    try:
        with certificate_options(options) as driver_options:
            with password_options(url, driver_options) as (driver_url, driver_options):
                raw = driver.connect(driver_url, row_factory=dict_row, **driver_options)
        if url == os.environ.get('DATABASE_URL', '').strip():
            role = raw.execute('SELECT current_user AS role').fetchone()['role']
            if role != 'lottery_app':
                raw.close()
                raise DatabaseUnavailable('DATABASE_URL deve usar o usuário restrito lottery_app, não o administrador.')
        return PostgresConnection(raw, driver)
    except driver.Error:
        if raw is not None:
            raw.close()
        raise DatabaseUnavailable('Banco externo indisponível. Tente novamente em alguns instantes.') from None


class PostgresConnection:
    def __init__(self, raw, driver):
        self.raw = raw
        self.driver = driver

    def execute(self, statement, parameters=()):
        # Only application-owned SQL uses qmark placeholders. Values remain bound.
        try:
            return self.raw.execute(statement.replace('?', '%s'), parameters)
        except self.driver.IntegrityError:
            raise IntegrityError('Restrição de integridade do banco.') from None
        except self.driver.Error as error:
            logging.error('Falha no banco externo (SQLSTATE %s).', error.sqlstate or 'indisponivel')
            raise DatabaseUnavailable('Não foi possível acessar os dados persistentes.') from None

    def commit(self):
        try:
            self.raw.commit()
        except self.driver.Error:
            raise DatabaseUnavailable('Não foi possível confirmar a gravação dos dados.') from None

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()
