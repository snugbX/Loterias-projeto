import os
import pandas as pd
import numpy as np
import datetime
import logging
import joblib

# Define a raiz do projeto (um nível acima da pasta 'src')
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Diretório de saída para os resultados CSV, agora sempre na raiz do projeto
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "resultados_Loterias")

# Criar o diretório se ele não existir
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Configuração do logging
logging.basicConfig(
    filename=os.path.join(PROJECT_ROOT, "loterias.log"), # Log também na raiz do projeto
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Dicionário de configurações para cada tipo de loteria
LOTTERY_CONFIGS = {
    'megasena': {
        'FILE_PATH': os.path.join(PROJECT_ROOT, "mega_sena_asloterias_ate_concurso_3009_crescente - mega_sena_www.asloterias.com.br.csv"),
        'NUM_BALLS_TO_DRAW': 6,
        'MIN_NUMBER': 1,
        'MAX_NUMBER': 60,
        'CSV_COLUMNS_PREFIX': 'bola ',
        'SKIP_ROWS': 6,
        'NUM_GAMES_DEFAULT': 5,
        'COLOR_PRIMARY': '#209869', # Verde da Mega Sena
        'COLOR_SECONDARY': '#8FCBB3' # Cor complementar da Mega Sena
    },
    'lotofacil': {
        'FILE_PATH': os.path.join(PROJECT_ROOT, "loto_facil_asloterias_ate_concurso_3649_sorteio - lotofacil_www.asloterias.com.br.csv"),
        'NUM_BALLS_TO_DRAW': 15,
        'MIN_NUMBER': 1,
        'MAX_NUMBER': 25,
        'CSV_COLUMNS_PREFIX': 'bola ',
        'SKIP_ROWS': 6,
        'NUM_GAMES_DEFAULT': 5,
        'COLOR_PRIMARY': '#930089', # Roxo da Lotofácil
        'COLOR_SECONDARY': '#C87FC3' # Cor complementar da Lotofácil
    },
    'quina': {
        'FILE_PATH': os.path.join(PROJECT_ROOT, "quina_asloterias_ate_concurso_6759_sorteio - quina_www.asloterias.com.br.csv"),
        'NUM_BALLS_TO_DRAW': 5,
        'MIN_NUMBER': 1,
        'MAX_NUMBER': 80,
        'CSV_COLUMNS_PREFIX': 'bola ',
        'SKIP_ROWS': 6,
        'NUM_GAMES_DEFAULT': 5,
        'COLOR_PRIMARY': '#260085', # Azul escuro da Quina
        'COLOR_SECONDARY': '#927FC1' # Cor complementar da Quina
    }
}

# Função para carregar os dados de um arquivo CSV específico da loteria
def load_data(file_path, skiprows):
    """
    Carrega os dados de sorteios de um arquivo CSV.
    Args:
        file_path (str): O caminho para o arquivo CSV.
        skiprows (int): Número de linhas a pular no início do arquivo.
    Returns:
        pandas.DataFrame: Um DataFrame contendo os dados do sorteio, ou None em caso de erro.
    """
    try:
        df = pd.read_csv(file_path, skiprows=skiprows, encoding='utf-8')
    except FileNotFoundError:
        logging.error(f"Erro: Arquivo não encontrado em '{file_path}'")
        return None
    except (pd.errors.EmptyDataError, pd.errors.ParserError) as e:
        logging.error(f"Erro ao ler o arquivo '{file_path}': {e}")
        return None
    return df

# Função para calcular as probabilidades de cada número principal
def calculate_probabilities(df, columns_prefix):
    """
    Calcula a frequência e probabilidade de cada número ter sido sorteado.
    Args:
        df (pandas.DataFrame): DataFrame com os dados dos sorteios.
        columns_prefix (str): Prefixo das colunas de números a considerar (e.g., 'bola ').
    Returns:
        pandas.Series: Uma Série com as probabilidades de cada número, ordenada de forma decrescente.
    """
    # Filtra colunas que começam com o prefixo dado
    bolas_df = pd.concat([df[col] for col in df.columns if col.startswith(columns_prefix)])
    value_counts = bolas_df.value_counts()
    probabilidades = value_counts / len(bolas_df)
    return probabilidades.sort_values(ascending=False)

# Função para gerar um único jogo (números principais ou trevos)
def generate_single_set(probabilidades, num_to_draw, min_num, max_num):
    """
    Gera um conjunto único de números. Prioriza números com base em probabilidades.
    Se não houver probabilidades suficientes ou válidas, usa geração aleatória pura.
    Args:
        probabilidades (pandas.Series): Probabilidades dos números.
        num_to_draw (int): Quantidade de números a sortear.
        min_num (int): Menor número possível.
        max_num (int): Maior número possível.
    Returns:
        list: Uma lista de números inteiros únicos, ordenados.
    """
    set_of_numbers = set() # Usar set para garantir unicidade rapidamente
    
    # Pool de todos os números possíveis dentro da faixa
    all_possible_numbers_in_range = list(range(min_num, max_num + 1))

    # Filtra as probabilidades para incluir apenas números dentro da faixa permitida.
    valid_prob_indices = [idx for idx in probabilidades.index if min_num <= idx <= max_num]
    valid_probs_series = probabilidades[valid_prob_indices].copy()

    # Tenta gerar probabilisticamente se houver dados e eles somarem mais que zero
    if not valid_probs_series.empty and valid_probs_series.sum() > 0:
        # Normaliza as probabilidades para garantir que somem 1
        normalized_probs = valid_probs_series / valid_probs_series.sum()
        
        attempts = 0
        max_attempts_for_prob = num_to_draw * 10 # Tentativas extras para cada número
        
        while len(set_of_numbers) < num_to_draw and attempts < max_attempts_for_prob:
            try:
                # Tenta escolher um número baseado nas probabilidades
                num = np.random.choice(normalized_probs.index.tolist(), p=normalized_probs.values.tolist())
                if min_num <= num <= max_num and num not in set_of_numbers:
                    set_of_numbers.add(int(num))
            except ValueError: # Caso o p não seja válido, por exemplo
                logging.warning("ValueError na escolha probabilística. Prosseguindo para preenchimento aleatório.")
                break # Sai do loop probabilístico e preenche o resto aleatoriamente
            attempts += 1
    
    # Se ainda faltam números, preencha com aleatórios
    if len(set_of_numbers) < num_to_draw:
        logging.info(f"Completando jogos com números aleatórios para a faixa {min_num}-{max_num} ({num_to_draw - len(set_of_numbers)} números restantes).")
        remaining_needed = num_to_draw - len(set_of_numbers)
        # Cria uma pool de números restantes que ainda não foram escolhidos
        pool_for_random_fill = [n for n in all_possible_numbers_in_range if n not in set_of_numbers]
        
        if len(pool_for_random_fill) >= remaining_needed:
            random_numbers = np.random.choice(pool_for_random_fill, remaining_needed, replace=False)
            for num in random_numbers:
                set_of_numbers.add(int(num))
        else:
            logging.error(f"Não foi possível gerar {num_to_draw} números únicos na faixa {min_num}-{max_num}. Apenas {len(set_of_numbers)} números foram gerados.")

    return sorted(list(set_of_numbers))

def load_trained_model(lottery_type):
    model_path = f"{lottery_type}_model.pkl"
    if os.path.exists(model_path):
        return joblib.load(model_path)
    return None

def generate_single_set_with_ml(model, max_num, num_to_draw, training_data=None):
    import numpy as np
    if training_data is not None and len(training_data) > 0:
        base_input = training_data[np.random.randint(0, len(training_data))]
    else:
        base_input = [0] * max_num

    prediction = model.predict([base_input])[0]
    predicted_indices = [i+1 for i, val in enumerate(prediction) if val == 1]

    final_set = sorted(list(set(predicted_indices)))[:num_to_draw]
    while len(final_set) < num_to_draw:
        rand = np.random.randint(1, max_num + 1)
        if rand not in final_set:
            final_set.append(rand)

    return sorted(final_set)

def generate_single_set_with_ml_proba(model, max_num, num_to_draw):
    import numpy as np

    # Dummy input (semelhante ao treino)
    dummy_input = [[0] * max_num]

    try:
        # Obtemos as probabilidades preditas para cada classe (0 ou 1) por número
        proba_list = model.predict_proba(dummy_input)

        # Seleciona a probabilidade de classe 1 (presente no jogo)
        probs = [proba[0][1] if isinstance(proba, list) or isinstance(proba, np.ndarray) else 0.0 for proba in proba_list]

        # Normaliza as probabilidades para somar 1
        prob_sum = sum(probs)
        if prob_sum == 0:
            probs = [1 / max_num] * max_num
        else:
            probs = [p / prob_sum for p in probs]

        # Sorteia sem repetição com base nessas probabilidades
        chosen = np.random.choice(range(1, max_num + 1), size=num_to_draw, replace=False, p=probs)
        return sorted([int(n) for n in chosen])
    except Exception as e:
        print("Erro ao usar predict_proba:", e)
        return sorted(np.random.choice(range(1, max_num + 1), size=num_to_draw, replace=False))

# Função principal para gerar N jogos de uma loteria específica
def generate_n_lottery_games(lottery_type, num_games_to_generate=None):
    """
    Gera uma lista de jogos para uma loteria específica.
    Args:
        lottery_type (str): O tipo de loteria (e.g., 'megasena', 'lotofacil').
        num_games_to_generate (int, optional): Número de jogos a serem gerados.
    Returns:
        list: Uma lista de listas, onde cada sublista é um jogo.
              Retorna uma lista vazia se houver erro ou tipo de loteria inválido.
    """
    if lottery_type not in LOTTERY_CONFIGS:
        logging.error(f"Tipo de loteria inválido: {lottery_type}")
        return []

    config = LOTTERY_CONFIGS[lottery_type]
    num_games = num_games_to_generate if num_games_to_generate is not None else config['NUM_GAMES_DEFAULT']

    df = load_data(config['FILE_PATH'], config['SKIP_ROWS'])
    if df is None:
        return []

    prob_main_numbers = calculate_probabilities(df, config['CSV_COLUMNS_PREFIX'])
    
    all_generated_games = []

    model = load_trained_model(lottery_type)

    for _ in range(num_games):
        if model:
            main_numbers = generate_single_set_with_ml_proba(
                model,
                config['MAX_NUMBER'],
                config['NUM_BALLS_TO_DRAW']
            )
        else:
            main_numbers = generate_single_set(
                prob_main_numbers,
                config['NUM_BALLS_TO_DRAW'],
                config['MIN_NUMBER'],
                config['MAX_NUMBER']
            )
        all_generated_games.append(main_numbers)

    # Conversão para int padrão do Python
    all_generated_games = [[int(num) for num in jogo] for jogo in all_generated_games]
    return all_generated_games


# Função para salvar jogos gerados em um arquivo CSV
def save_generated_games_to_csv(jogos, lottery_type, output_dir):
    """
    Salva uma lista de jogos da loteria em um arquivo CSV.
    Args:
        jogos (list): Uma lista de jogos (listas de números).
        lottery_type (str): O tipo de loteria.
        output_dir (str): Diretório onde o arquivo CSV será salvo.
    """
    if not jogos:
        logging.info(f"Nenhum jogo para salvar para {lottery_type}.")
        return

    now = datetime.datetime.now()
    data_hora = now.strftime("%Y-%m-%d_%H-%M-%S")
    
    file_name = f"{lottery_type}_resultados_{data_hora}.csv"
    file_path = os.path.join(output_dir, file_name)

    try:
        config = LOTTERY_CONFIGS[lottery_type]
        columns = [f"{config['CSV_COLUMNS_PREFIX'].strip()}{i+1}" for i in range(config['NUM_BALLS_TO_DRAW'])]
        df_jogos = pd.DataFrame(jogos, columns=columns)

        df_jogos.to_csv(file_path, index=False)
        logging.info(f"{len(jogos)} jogos de {lottery_type} gerados e salvos em '{file_path}'")
        print(f"Resultados de {lottery_type} salvos em: {file_path}") # Mensagem para o console do servidor
    except Exception as e:
        logging.error(f"Erro ao salvar jogos de {lottery_type} em CSV: {e}")

# Função para obter números quentes e frios
def get_hot_cold_numbers(lottery_type, top_n=10):
    """
    Calcula os números mais e menos frequentes para uma loteria específica.
    Args:
        lottery_type (str): O tipo de loteria.
        top_n (int): Quantidade de números mais/menos frequentes a retornar.
    Returns:
        dict: Um dicionário com 'hot_numbers' e 'cold_numbers'.
    """
    if lottery_type not in LOTTERY_CONFIGS:
        logging.error(f"Tipo de loteria inválido para hot/cold numbers: {lottery_type}")
        return {"hot_numbers": [], "cold_numbers": []}

    config = LOTTERY_CONFIGS[lottery_type]
    df = load_data(config['FILE_PATH'], config['SKIP_ROWS'])
    
    if df is None:
        return {"hot_numbers": [], "cold_numbers": []}

    bolas_df = pd.concat([df[col] for col in df.columns if col.startswith(config['CSV_COLUMNS_PREFIX'])])
    
    # Filtrar números para a faixa válida da loteria
    bolas_validas = bolas_df[(bolas_df >= config['MIN_NUMBER']) & (bolas_df <= config['MAX_NUMBER'])]
    
    value_counts = bolas_validas.value_counts()

    # Números que nunca saíram na faixa (mas estão no range)
    all_possible_numbers = set(range(config['MIN_NUMBER'], config['MAX_NUMBER'] + 1))
    drawn_numbers = set(value_counts.index)
    never_drawn = sorted(list(all_possible_numbers - drawn_numbers))

    # Combinar com os menos frequentes que já saíram
    cold_numbers_series = value_counts.sort_values(ascending=True)
    
    hot_numbers = value_counts.head(top_n).index.tolist()
    
    # Pegar os 'cold_numbers' que já saíram, e adicionar os que nunca saíram
    cold_numbers_drawn = cold_numbers_series.head(top_n - len(never_drawn)).index.tolist()
    cold_numbers = sorted(list(set(never_drawn + cold_numbers_drawn)))[:top_n]


    return {
        "hot_numbers": hot_numbers,
        "cold_numbers": cold_numbers
    }

# Função principal para execução direta do script (para teste)
def main():
    """
    Função principal que pode ser usada para testar a geração de jogos
    diretamente do script.
    """
    print("Testando Mega Sena:")
    ms_games = generate_n_lottery_games('megasena', num_games_to_generate=2)
    if ms_games:
        print(pd.DataFrame(ms_games, columns=[f"bola {i+1}" for i in range(6)]))
        save_generated_games_to_csv(ms_games, 'megasena', OUTPUT_DIR)
        hot_cold = get_hot_cold_numbers('megasena')
        print(f"Mega Sena Hot Numbers: {hot_cold['hot_numbers']}")
        print(f"Mega Sena Cold Numbers: {hot_cold['cold_numbers']}")
    
    print("\nTestando Lotofácil:")
    lf_games = generate_n_lottery_games('lotofacil', num_games_to_generate=2)
    if lf_games:
        print(pd.DataFrame(lf_games, columns=[f"bola {i+1}" for i in range(15)]))
        save_generated_games_to_csv(lf_games, 'lotofacil', OUTPUT_DIR)
        hot_cold = get_hot_cold_numbers('lotofacil')
        print(f"Lotofácil Hot Numbers: {hot_cold['hot_numbers']}")
        print(f"Lotofácil Cold Numbers: {hot_cold['cold_numbers']}")

    print("\nTestando Quina:")
    quina_games = generate_n_lottery_games('quina', num_games_to_generate=2)
    if quina_games:
        print(pd.DataFrame(quina_games, columns=[f"bola {i+1}" for i in range(5)]))
        save_generated_games_to_csv(quina_games, 'quina', OUTPUT_DIR)
        hot_cold = get_hot_cold_numbers('quina')
        print(f"Quina Hot Numbers: {hot_cold['hot_numbers']}")
        print(f"Quina Cold Numbers: {hot_cold['cold_numbers']}")

# Executa a função principal se o script for executado diretamente
if __name__ == "__main__":
    main()
