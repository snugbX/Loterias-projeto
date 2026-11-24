"""Single public presentation catalog for executable modes and configuration tools."""

import gerador_loterias as lottery
import game_analysis

MODE_PRESENTATION = {
    'normal': ('Jogo normal', 'Probabilidade e filtros atuais.'),
    'balanced_never_prize': ('Pares/ímpares + filtro histórico', 'Equilíbrio com filtro de faixas históricas fortes.'),
    'balanced_parity': ('Pares e ímpares', 'Equilibra a divisão do jogo.'),
    'even_only': ('Só pares', 'Seleciona somente dezenas pares.'),
    'odd_only': ('Só ímpares', 'Seleciona somente dezenas ímpares.'),
    'spread': ('Bem distribuído', 'Espalha as dezenas por faixas numéricas.'),
    'hot_cold_mix': ('Quentes e frios', 'Mistura dezenas mais e menos frequentes na base.'),
    'lucky_dates': ('Datas da sorte', 'Seleciona dezenas até 31.'),
    'high_numbers': ('Números altos', 'Seleciona dezenas da metade superior.'),
    'never_prize': ('Filtro histórico forte', 'Evita faixas históricas fortes, não necessariamente todos os prêmios.'),
    'mixed': ('Tudo misturado', 'Alterna os estilos viáveis desta loteria a cada jogo.'),
}


def catalog_for(lottery_type):
    if lottery_type not in lottery.LOTTERY_CONFIGS:
        raise ValueError('Loteria inválida.')
    if set(MODE_PRESENTATION) != set(lottery.GENERATION_MODES):
        raise RuntimeError('Atualize o catálogo ao cadastrar ou remover modos de geração.')
    count = lottery.LOTTERY_CONFIGS[lottery_type]['NUM_BALLS_TO_DRAW']
    parity = f'{count // 2} pares e {count // 2} ímpares' if count % 2 == 0 else f'{count // 2}/{count // 2 + 1} ou {count // 2 + 1}/{count // 2} pares/ímpares'
    modes = []
    for mode in lottery.GENERATION_MODES:
        label, description = MODE_PRESENTATION[mode]
        if mode == 'balanced_parity':
            description = f'Divisão: {parity}.'
        if mode in ('never_prize', 'balanced_never_prize'):
            threshold = lottery.HISTORICAL_PRIZE_FILTERS[lottery_type]['min_matches']
            description = f'Evita {threshold}+ acertos numéricos na base.'
            if threshold > min(game_analysis.PRIZE_MATCHES[lottery_type]): description += ' Pode permitir faixas menores.'
            if mode == 'balanced_never_prize': description = f'{parity}; ' + description
            if lottery_type == 'diadesorte': description += ' Não filtra o Mês da Sorte.'
        modes.append({'id': mode, 'label': label, 'description': description,
                      'available': lottery.is_generation_mode_available_for_lottery(mode, lottery_type),
                      'premium': mode in lottery.PREMIUM_GENERATION_MODES,
                      'recommended': mode == 'balanced_never_prize'})
    return {'lottery_type': lottery_type, 'modes': modes, 'tools': [
        {'id': 'uniform', 'label': 'Configurar aleatório uniforme', 'description': 'Sem pesos históricos, sem repetir combinações no lote.', 'method': 'uniform'},
        {'id': 'constraints', 'label': 'Configurar minhas regras e diversificação', 'description': 'Fixas, exclusões, paridade, soma e limite de sobreposição.', 'method': 'constraints'},
    ]}
