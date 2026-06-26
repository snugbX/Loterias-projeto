from flask import Flask, jsonify, request
import history_storage
import gerador_loterias # Importa o módulo de geração de loterias
import os
import threading
import webbrowser
import time
import socket
from lottery_validation import normalize_lottery_type

# Inicializa a aplicação Flask.
# O parâmetro static_folder='.' indica que o Flask deve procurar arquivos estáticos
# (como index.html, style.css e os módulos em js/) no diretório atual (src).
app = Flask(__name__, static_folder='.')

ALLOWED_STATIC_FILES = {
    'index.html',
    'style.css',
    'js/api.js',
    'js/dom.js',
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


@app.route('/gerar_jogos/<lottery_type>') # Agora aceita o tipo de loteria na URL
def gerar_jogos(lottery_type):
    """
    Rota da API que gera jogos para uma loteria específica e os retorna como JSON.
    Aceita um parâmetro 'num_games' opcional para a quantidade de jogos.
    Além disso, salva os jogos gerados em um arquivo CSV.
    """
    # Valida o tipo de loteria recebido
    lottery_type = normalize_lottery_type(lottery_type)

    if lottery_type is None:
        return jsonify({"error": "Tipo de loteria inválido"}), 400 # Bad Request

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
        jogos_gerados = gerador_loterias.generate_n_lottery_games(lottery_type, num_games_to_generate=num_games)

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

        # 3. Retorna os jogos gerados como uma resposta JSON para o frontend
        return jsonify(jogos_gerados)
    except Exception as e:
        gerador_loterias.logging.error(f"Erro na rota /gerar_jogos/{lottery_type}: {e}")
        return jsonify({"error": "Erro interno ao gerar ou salvar jogos"}), 500

@app.route('/get_history_files/<lottery_type>')
def get_history_files(lottery_type):
    """
    Retorna uma lista de arquivos CSV de histórico para o tipo de loteria especificado.
    """
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
    lottery_type = normalize_lottery_type(lottery_type)

    if lottery_type is None:
        return jsonify({"error": "Tipo de loteria inválido"}), 400
    
    try:
        hot_cold_data = gerador_loterias.get_hot_cold_numbers(lottery_type)
        return jsonify(hot_cold_data)
    except Exception as e:
        gerador_loterias.logging.error(f"Erro ao obter números quentes/frios para {lottery_type}: {e}")
        return jsonify({"error": "Erro ao obter números quentes e frios"}), 500

@app.route('/clear_history/<lottery_type>', methods=['POST'])
def clear_history(lottery_type):
    """
    Deleta todos os arquivos CSV de histórico para o tipo de loteria especificado.
    """
    lottery_type = normalize_lottery_type(lottery_type)

    if lottery_type is None:
        return jsonify({"error": "Tipo de loteria inválido"}), 400

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

