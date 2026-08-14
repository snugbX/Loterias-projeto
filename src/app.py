from flask import Flask, jsonify, request, session
import auth_storage
import datetime
import hmac
import history_storage
import gerador_loterias # Importa o módulo de geração de loterias
import os
import secrets
import subprocess
import sys
import threading
import webbrowser
import time
import socket
from lottery_validation import normalize_lottery_type

# Inicializa a aplicação Flask.
# O parâmetro static_folder='.' indica que o Flask deve procurar arquivos estáticos
# (como index.html, style.css e os módulos em js/) no diretório atual (src).
app = Flask(__name__, static_folder='.')
app.secret_key = os.environ.get("APP_SECRET_KEY") or secrets.token_urlsafe(48)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0").strip() == "1",
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=7),
)

LOGIN_ATTEMPTS = {}
LOGIN_ATTEMPT_LIMIT = 5
LOGIN_LOCK_SECONDS = 10 * 60

ALLOWED_STATIC_FILES = {
    'index.html',
    'style.css',
    'js/api.js',
    'js/dom.js',
    'js/drawCalendar.js',
    'js/main.js',
    'js/preferences.js',
    'js/render.js',
    'js/ui.js',
}

def env_flag(name, default=False):
    value = os.environ.get(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    value = os.environ.get(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def configured_admin_email():
    return auth_storage.normalize_email(os.environ.get("ADMIN_EMAIL", ""))


def free_daily_game_limit():
    return env_int("FREE_DAILY_GAME_LIMIT", 20)


def today_key():
    return datetime.date.today().isoformat()


def current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    user = auth_storage.get_user_by_id(user_id)

    if not user or not user.get("is_active"):
        session.clear()
        return None

    return user


def reset_guest_usage_if_needed():
    if session.get("guest_usage_date") != today_key():
        session["guest_usage_date"] = today_key()
        session["guest_used_today"] = 0


def guest_usage_summary():
    reset_guest_usage_if_needed()
    used = int(session.get("guest_used_today", 0))
    limit = free_daily_game_limit()

    return {
        "used_today": used,
        "free_daily_limit": limit,
        "remaining_today": max(limit - used, 0),
        "is_unlimited": False,
    }


def current_guest_payload():
    if not session.get("guest_access"):
        return None

    return {
        "id": session.get("guest_id", "guest"),
        "name": "Visitante",
        "email": "",
        "role": "guest",
        "plan": "free",
        "is_active": True,
        "is_admin": False,
        "is_premium": False,
        "is_guest": True,
        "created_at": session.get("guest_created_at"),
        "last_login_at": None,
        "usage": guest_usage_summary(),
    }


def current_user_payload():
    user = current_user()

    if user is not None:
        return {
            **user,
            "is_guest": False,
            "usage": auth_storage.usage_summary(user, free_daily_game_limit()),
        }

    return current_guest_payload()


def current_access_payload():
    return current_user_payload()


def can_generate_for_access(access_user, requested_games):
    if access_user.get("is_guest"):
        usage = guest_usage_summary()

        if usage["used_today"] + requested_games > usage["free_daily_limit"]:
            return (
                False,
                "Visitantes podem gerar até "
                f"{usage['free_daily_limit']} jogos por dia. Entre ou crie uma conta "
                "para continuar com mais controle.",
            )

        return True, ""

    return auth_storage.can_generate_games(
        access_user,
        requested_games,
        free_daily_game_limit(),
    )


def record_generated_for_access(access_user, generated_count):
    if access_user.get("is_guest"):
        reset_guest_usage_if_needed()
        session["guest_used_today"] = int(session.get("guest_used_today", 0)) + generated_count

        return guest_usage_summary()

    auth_storage.record_generated_games(access_user["id"], generated_count)
    return auth_storage.usage_summary(access_user, free_daily_game_limit())


def get_csrf_token():
    token = session.get("csrf_token")

    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token

    return token


def validate_csrf_token():
    expected_token = session.get("csrf_token", "")
    provided_token = request.headers.get("X-CSRF-Token", "")

    return bool(
        expected_token
        and provided_token
        and hmac.compare_digest(expected_token, provided_token)
    )


def require_login():
    if current_user() is not None:
        return None

    return jsonify({"error": "Entre na sua conta para continuar."}), 401


def require_access():
    if current_access_payload() is not None:
        return None

    return jsonify({"error": "Entre ou acesse como visitante para continuar."}), 401


def require_csrf():
    if validate_csrf_token():
        return None

    return jsonify({"error": "Sessao expirada. Recarregue a pagina e tente novamente."}), 403


def require_premium_access():
    user = current_access_payload()

    if user is None:
        return jsonify({"error": "Entre ou acesse como visitante para continuar."}), 401

    if user["is_premium"]:
        return None

    return jsonify({"error": "Recurso disponível no plano Premium."}), 403


def admin_token_configured():
    return bool(os.environ.get("ADMIN_TOKEN", "").strip())


def validate_admin_token_request():
    expected_token = os.environ.get("ADMIN_TOKEN", "").strip()

    if not expected_token:
        return False

    provided_token = request.headers.get("X-Admin-Token", "").strip()

    if not provided_token:
        provided_token = request.form.get("admin_token", "").strip()

    return bool(
        provided_token
        and hmac.compare_digest(provided_token, expected_token)
    )


def require_admin_access():
    user = current_user()

    if user and user["is_admin"]:
        csrf_error = require_csrf()

        if csrf_error is not None:
            return csrf_error

        return None

    if validate_admin_token_request():
        return None

    return jsonify({"error": "Acesso admin necessário."}), 401

def login_rate_key(email):
    return f"{request.remote_addr or 'local'}:{auth_storage.normalize_email(email)}"


def login_is_limited(email):
    key = login_rate_key(email)
    record = LOGIN_ATTEMPTS.get(key)

    if not record:
        return False

    attempts, first_attempt_at = record
    now = time.time()

    if now - first_attempt_at > LOGIN_LOCK_SECONDS:
        LOGIN_ATTEMPTS.pop(key, None)
        return False

    return attempts >= LOGIN_ATTEMPT_LIMIT


def record_failed_login(email):
    key = login_rate_key(email)
    attempts, first_attempt_at = LOGIN_ATTEMPTS.get(key, (0, time.time()))
    LOGIN_ATTEMPTS[key] = (attempts + 1, first_attempt_at)


def clear_failed_logins(email):
    LOGIN_ATTEMPTS.pop(login_rate_key(email), None)


@app.route('/')
def home():
    """
    Rota principal que serve o arquivo index.html.
    """
    return app.send_static_file('index.html')

@app.route('/<path:path>')
def static_files(path):
    """
    Rota para servir arquivos estáticos (CSS, JS, imagens, etc.) da pasta 'src'.
    """
    if path not in ALLOWED_STATIC_FILES:
        return jsonify({"error": "Arquivo estático não encontrado"}), 404

    return app.send_static_file(path)


@app.route('/auth/me')
def auth_me():
    return jsonify({
        "user": current_user_payload(),
        "csrf_token": get_csrf_token(),
        "free_daily_game_limit": free_daily_game_limit(),
        "admin_configured": auth_storage.admin_exists(),
    })


@app.route('/auth/register', methods=['POST'])
def auth_register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = auth_storage.normalize_email(data.get("email"))
    password = data.get("password") or ""
    terms_accepted = bool(data.get("terms_accepted"))
    admin_email = configured_admin_email()
    is_configured_admin = bool(admin_email and email == admin_email)
    role = auth_storage.ROLE_USER
    plan = auth_storage.PLAN_FREE

    if is_configured_admin and not auth_storage.admin_exists():
        setup_code = os.environ.get("ADMIN_SETUP_CODE", "").strip()

        if setup_code and not hmac.compare_digest(
            data.get("setup_code", "").strip(),
            setup_code
        ):
            return jsonify({"error": "Código admin inicial inválido."}), 403

        role = auth_storage.ROLE_ADMIN
        plan = auth_storage.PLAN_PREMIUM

    try:
        user = auth_storage.create_user(
            name=name,
            email=email,
            password=password,
            role=role,
            plan=plan,
            terms_accepted=terms_accepted,
            terms_version=auth_storage.TERMS_VERSION,
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    get_csrf_token()

    return jsonify({
        "message": "Conta criada com sucesso.",
        "user": current_user_payload(),
        "csrf_token": session["csrf_token"],
    }), 201


@app.route('/auth/login', methods=['POST'])
def auth_login():
    data = request.get_json(silent=True) or {}
    email = auth_storage.normalize_email(data.get("email"))
    password = data.get("password") or ""

    if login_is_limited(email):
        return jsonify({
            "error": "Muitas tentativas de login. Aguarde alguns minutos e tente novamente."
        }), 429

    user = auth_storage.verify_user_credentials(email, password)

    if user is None:
        record_failed_login(email)
        return jsonify({"error": "E-mail ou senha inválidos."}), 401

    clear_failed_logins(email)
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    get_csrf_token()

    return jsonify({
        "message": "Login realizado com sucesso.",
        "user": current_user_payload(),
        "csrf_token": session["csrf_token"],
    })


@app.route('/auth/guest', methods=['POST'])
def auth_guest():
    session.clear()
    session.permanent = True
    session["guest_access"] = True
    session["guest_id"] = secrets.token_urlsafe(12)
    session["guest_created_at"] = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat(timespec="seconds")
    session["guest_usage_date"] = today_key()
    session["guest_used_today"] = 0
    get_csrf_token()

    return jsonify({
        "message": "Acesso visitante liberado.",
        "user": current_user_payload(),
        "csrf_token": session["csrf_token"],
    })


@app.route('/auth/logout', methods=['POST'])
def auth_logout():
    csrf_error = require_csrf()

    if csrf_error is not None:
        return csrf_error

    session.clear()
    return jsonify({"message": "Você saiu da conta."})


@app.route('/billing/pix')
def billing_pix():
    login_error = require_login()

    if login_error is not None:
        return login_error

    return jsonify({
        "plan": "premium",
        "pix_key": os.environ.get("PIX_KEY", "").strip(),
        "receiver_email": configured_admin_email(),
        "enabled": bool(os.environ.get("PIX_KEY", "").strip()),
    })


@app.route('/admin/users')
def admin_users():
    user = current_user()

    if not user or not user["is_admin"]:
        return jsonify({"error": "Acesso admin necessário."}), 401

    return jsonify({"users": auth_storage.list_users()})


@app.route('/admin/users/<int:user_id>/plan', methods=['POST'])
def admin_update_user_plan(user_id):
    admin_error = require_admin_access()

    if admin_error is not None:
        return admin_error

    data = request.get_json(silent=True) or {}
    plan = (data.get("plan") or "").strip().lower()

    try:
        updated_user = auth_storage.update_user_plan(user_id, plan)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    if updated_user is None:
        return jsonify({"error": "Usuário não encontrado ou não editável."}), 404

    actor = current_user()
    auth_storage.log_audit(
        actor["id"] if actor else None,
        "admin.user.plan_updated",
        user_id,
        {"plan": plan},
    )

    return jsonify({"message": "Plano atualizado.", "user": updated_user})


@app.route('/gerar_jogos/<lottery_type>', methods=['POST']) # Agora aceita o tipo de loteria na URL
def gerar_jogos(lottery_type):
    """
    Rota da API que gera jogos para uma loteria específica e os retorna como JSON.
    Aceita um parâmetro 'num_games' opcional para a quantidade de jogos.
    Além disso, salva os jogos gerados em um arquivo CSV.
    """
    access_error = require_access()

    if access_error is not None:
        return access_error

    csrf_error = require_csrf()

    if csrf_error is not None:
        return csrf_error

    # Valida o tipo de loteria recebido
    lottery_type = normalize_lottery_type(lottery_type)

    if lottery_type is None:
        return jsonify({"error": "Tipo de loteria inválido"}), 400 # Bad Request

    generation_mode = gerador_loterias.normalize_generation_mode(
        request.args.get("mode", "normal")
    )

    if generation_mode is None:
        return jsonify({"error": "Modo de geração inválido."}), 400

    if not gerador_loterias.is_generation_mode_available_for_lottery(
        generation_mode,
        lottery_type,
    ):
        return jsonify({
            "error": "Essa estratégia não está disponível para a loteria escolhida."
        }), 422

    # Obtém a quantidade de jogos do parâmetro de consulta, se fornecido
    num_games_str = request.args.get('num_games')
    num_games = None
    if num_games_str:
        try:
            num_games = int(num_games_str)
            if not (1 <= num_games <= 100): # Exemplo de validação: entre 1 e 100
                return jsonify({"error": "Quantidade de jogos inválida. Deve ser entre 1 e 100."}), 400
        except ValueError:
            return jsonify({"error": "Quantidade de jogos inválida. Deve ser um número inteiro."}), 400


    try:
        # 1. Gera os jogos usando a função genérica, passando a quantidade se fornecida
        requested_games = num_games or gerador_loterias.LOTTERY_CONFIGS[lottery_type]['NUM_GAMES_DEFAULT']
        access_user = current_access_payload()

        if (
            generation_mode in gerador_loterias.PREMIUM_GENERATION_MODES
            and not access_user["is_premium"]
        ):
            return jsonify({
                "error": "Esse modo de geração faz parte do plano Premium."
            }), 403

        can_generate, plan_message = can_generate_for_access(access_user, requested_games)

        if not can_generate:
            return jsonify({"error": plan_message}), 403

        jogos_gerados = gerador_loterias.generate_n_lottery_games(
            lottery_type,
            num_games_to_generate=num_games,
            generation_mode=generation_mode,
        )

        if not jogos_gerados:
            gerador_loterias.logging.error(f"Nenhum jogo pôde ser gerado para {lottery_type}. Verifique o log do servidor.")
            return jsonify({"error": "Nenhum jogo pôde ser gerado. Verifique o log do servidor."}), 500

        # 2. Salva os jogos gerados em um arquivo CSV
        # Usa o OUTPUT_DIR já corrigido em gerador_loterias
        gerador_loterias.save_generated_games_to_csv(
            jogos_gerados,
            lottery_type,
            gerador_loterias.OUTPUT_DIR
        )
        usage = record_generated_for_access(access_user, len(jogos_gerados))

        # 3. Retorna os jogos gerados como uma resposta JSON para o frontend
        return jsonify({
            "games": jogos_gerados,
            "generation_mode": generation_mode,
            "usage": usage,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        gerador_loterias.logging.error(f"Erro na rota /gerar_jogos/{lottery_type}: {e}")
        return jsonify({"error": "Erro interno ao gerar ou salvar jogos"}), 500

@app.route('/get_history_files/<lottery_type>')
def get_history_files(lottery_type):
    """
    Retorna uma lista de arquivos CSV de histórico para o tipo de loteria especificado.
    """
    login_error = require_access()

    if login_error is not None:
        return login_error

    lottery_type = normalize_lottery_type(lottery_type)

    if lottery_type is None:
        return jsonify({"error": "Tipo de loteria inválido"}), 400

    try:
        files = history_storage.list_history_files(lottery_type)
        return jsonify({"files": files})
    except Exception as e:
        gerador_loterias.logging.error(f"Erro ao listar arquivos de histórico para {lottery_type}: {e}")
        return jsonify({"error": "Erro ao listar histórico"}), 500

@app.route('/get_file_content/<filename>')
def get_file_content(filename):
    """
    Lê o conteúdo de um arquivo CSV de histórico e o retorna como JSON.
    """
    login_error = require_access()

    if login_error is not None:
        return login_error

    try:
        data = history_storage.read_history_file(filename)

        if data is None:
            return jsonify({"error": "Arquivo não encontrado ou acesso negado"}), 404

        return jsonify({"content": data})
    except Exception as e:
        gerador_loterias.logging.error(f"Erro ao ler conteúdo do arquivo {filename}: {e}")
        return jsonify({"error": "Erro ao carregar conteúdo do arquivo"}), 500

@app.route('/get_hot_cold_numbers/<lottery_type>')
def get_hot_cold_numbers_api(lottery_type):
    """
    Retorna os números mais e menos frequentes para a loteria especificada.
    """
    premium_error = require_premium_access()

    if premium_error is not None:
        return premium_error

    lottery_type = normalize_lottery_type(lottery_type)

    if lottery_type is None:
        return jsonify({"error": "Tipo de loteria inválido"}), 400
    
    try:
        hot_cold_data = gerador_loterias.get_hot_cold_numbers(lottery_type)
        return jsonify(hot_cold_data)
    except Exception as e:
        gerador_loterias.logging.error(f"Erro ao obter números quentes/frios para {lottery_type}: {e}")
        return jsonify({"error": "Erro ao obter números quentes e frios"}), 500

@app.route('/latest_results')
def latest_results():
    try:
        return jsonify({"results": gerador_loterias.get_latest_results()})
    except Exception as e:
        gerador_loterias.logging.error(f"Erro ao obter últimos resultados: {e}")
        return jsonify({"error": "Erro ao obter últimos resultados"}), 500

@app.route('/data_status')
def data_status():
    try:
        return jsonify({"status": gerador_loterias.get_data_status()})
    except Exception as e:
        gerador_loterias.logging.error(f"Erro ao obter status dos dados: {e}")
        return jsonify({"error": "Erro ao obter status dos dados"}), 500

@app.route('/strategy_stats/<lottery_type>')
def strategy_stats(lottery_type):
    lottery_type = normalize_lottery_type(lottery_type)

    if lottery_type is None:
        return jsonify({"error": "Tipo de loteria invÃ¡lido"}), 400

    try:
        stats = gerador_loterias.get_generation_strategy_stats(lottery_type)

        if stats is None:
            return jsonify({"error": "Tipo de loteria invÃ¡lido"}), 400

        return jsonify({"stats": stats})
    except Exception as e:
        gerador_loterias.logging.error(f"Erro ao obter estatÃ­sticas de estratÃ©gia: {e}")
        return jsonify({"error": "Erro ao obter estatÃ­sticas de estratÃ©gia"}), 500

@app.route('/admin_status')
def admin_status():
    return jsonify({"admin_token_required": admin_token_configured()})

@app.route('/admin/update_data', methods=['POST'])
def admin_update_data():
    admin_error = require_admin_access()

    if admin_error is not None:
        return admin_error

    timeout = env_int("LOTTERY_UPDATE_TIMEOUT", 240)
    script_path = os.path.join(gerador_loterias.BASE_DIR, "update_lottery_data.py")
    command = [
        sys.executable,
        script_path,
        "--no-publish",
    ]

    try:
        completed = subprocess.run(
            command,
            cwd=gerador_loterias.PROJECT_ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return jsonify({
            "error": "Atualizacao demorou demais e foi interrompida.",
        }), 504
    except Exception as e:
        gerador_loterias.logging.error(f"Erro ao executar atualizador: {e}")
        return jsonify({"error": "Erro ao executar atualizador"}), 500

    output = completed.stdout.strip()
    error_output = completed.stderr.strip()

    if completed.returncode != 0:
        gerador_loterias.logging.error(
            f"Atualizador retornou erro {completed.returncode}: {error_output or output}"
        )
        return jsonify({
            "error": "Falha ao atualizar dados.",
            "output": output,
            "error_output": error_output,
        }), 500

    return jsonify({
        "message": "Atualização concluída.",
        "output": output,
        "status": gerador_loterias.get_data_status(),
    })

@app.route('/clear_history/<lottery_type>', methods=['POST'])
def clear_history(lottery_type):
    """
    Deleta todos os arquivos CSV de histórico para o tipo de loteria especificado.
    """
    lottery_type = normalize_lottery_type(lottery_type)

    if lottery_type is None:
        return jsonify({"error": "Tipo de loteria inválido"}), 400

    admin_error = require_admin_access()

    if admin_error is not None:
        return admin_error

    try:
        deleted_files_count = history_storage.clear_history(lottery_type)
        return jsonify({"message": f"{deleted_files_count} arquivos de histórico para {lottery_type} foram deletados."}), 200
    except Exception as e:
        gerador_loterias.logging.error(f"Erro ao limpar histórico para {lottery_type}: {e}")
        return jsonify({"error": "Erro ao limpar histórico"}), 500

@app.route('/delete_file/<filename>', methods=['POST'])
def delete_single_file(filename):
    """
    Deleta um único arquivo CSV de histórico.
    """
    admin_error = require_admin_access()

    if admin_error is not None:
        return admin_error

    result = history_storage.delete_history_file(filename)

    if result == "invalid":
        return jsonify({"error": "Nome de arquivo inválido ou acesso negado."}), 400

    if result == "missing":
        return jsonify({"message": f"Arquivo '{filename}' não encontrado."}), 404

    if result == "deleted":
        return jsonify({"message": f"Arquivo '{filename}' deletado com sucesso."}), 200

    return jsonify({"error": "Erro ao deletar arquivo."}), 500

def abrir_navegador(host, port):
    time.sleep(1)

    if host in {"0.0.0.0", "::"}:
        hostname = socket.gethostname()
        host = socket.gethostbyname(hostname)

    url = f"http://{host}:{port}"
    webbrowser.open_new(url)

if __name__ == '__main__':
    # Certifica-se de que o diretório de saída para os resultados CSV exista.
    os.makedirs(gerador_loterias.OUTPUT_DIR, exist_ok=True)

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    debug = env_flag("FLASK_DEBUG", default=False)
    auto_open_browser = env_flag("LOTTERY_AUTO_OPEN_BROWSER", default=True)

    if auto_open_browser and (not debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'):
        threading.Thread(target=abrir_navegador, args=(host, port)).start()

    app.run(debug=debug, host=host, port=port)

