"""Contextual product help built from the same lottery rules as the generator."""

import game_analysis
import gerador_loterias as lottery


def get_guide(lottery_type):
    if lottery_type not in lottery.LOTTERY_CONFIGS:
        raise ValueError('Loteria inválida.')
    config = lottery.LOTTERY_CONFIGS[lottery_type]
    count = config['NUM_BALLS_TO_DRAW']
    maximum = config['MAX_NUMBER']
    minimum = lottery.HISTORICAL_PRIZE_FILTERS[lottery_type]['min_matches']
    tiers = ', '.join(str(value) for value in game_analysis.PRIZE_MATCHES[lottery_type])
    parity = f'{count // 2} pares e {count // 2} ímpares' if count % 2 == 0 else (
        f'{count // 2} pares e {count // 2 + 1} ímpares, ou {count // 2 + 1} pares e {count // 2} ímpares')
    month_note = ' Informe também um Mês da Sorte, de janeiro a dezembro. O mês é uma faixa independente, com chance de 1 em 12.' if lottery_type == 'diadesorte' else ''
    exclusions = (' O filtro não cobre faixas numéricas menores.' if minimum > min(game_analysis.PRIZE_MATCHES[lottery_type]) else '')
    if lottery_type == 'diadesorte':
        exclusions += ' O Mês da Sorte não entra nesse filtro e é mantido nas alternativas da consulta.'
    unavailable = [lottery.GENERATION_MODES[mode] for mode in ('even_only', 'odd_only', 'high_numbers', 'lucky_dates')
                   if not lottery.is_generation_mode_available_for_lottery(mode, lottery_type)]
    normal = (' Na Mega-Sena, o modo normal também usa os filtros atuais de soma, paridade e distribuição.'
              if lottery_type == 'megasena' else '')
    return {'lottery_type': lottery_type, 'lottery_name': lottery.LOTTERY_DISPLAY_NAMES[lottery_type],
            'available_modes': [mode for mode in lottery.GENERATION_MODES
                                if lottery.is_generation_mode_available_for_lottery(mode, lottery_type)],
            'topics': [
                {'id': 'start', 'title': 'Como preparo meu jogo?', 'paragraphs': [
                    f'O app trabalha com apostas simples: {count} dezenas diferentes, de 1 a {maximum}.{month_note}',
                    f'As faixas numéricas consideradas são {tiers} acertos. O app simula resultados; não registra apostas nem confirma prêmios recebidos.',
                    'Visitantes e contas Free usam o modo normal, com limite diário. Premium e admin liberam as estratégias, a consulta e o radar.' + normal]},
                {'id': 'strategies', 'title': 'Qual estratégia posso usar?', 'paragraphs': [
                    f'Equilíbrio nesta loteria significa {parity}. Isso é um estilo de seleção, não uma previsão.',
                    ('Modos ocultos nesta loteria: ' + ', '.join(unavailable) + '. Não há dezenas suficientes ou o filtro não muda o universo disponível.') if unavailable else 'Os filtros de pares, ímpares, datas e números altos são viáveis nesta loteria.',
                    'Quentes/frios e ponderação histórica descrevem a base; dezenas atrasadas não ficam obrigadas a sair. Nenhum modo melhora comprovadamente a chance individual.']},
                {'id': 'filter', 'title': 'O que significa o filtro histórico?', 'paragraphs': [
                    f'O filtro evita combinações que teriam {minimum} ou mais acertos numéricos em algum concurso da base consultada.{exclusions}',
                    'Não significa que o jogo nunca teve qualquer prêmio. Base incompleta não permite excluir concursos ausentes. Se o filtro não encontrar combinação, tente outro modo; reduzir a quantidade de jogos não torna uma combinação impossível em possível.']},
                {'id': 'consult', 'title': 'Como interpreto a consulta e a alternativa?', 'paragraphs': [
                    f'Premium/admin podem consultar até 10 jogos, com {count} dezenas cada, e comparar as simulações.{month_note}',
                    'A alternativa preserva o máximo de dezenas e usa o perfil de paridade do radar e coocorrências com as dezenas mantidas. Afinidade não é previsão. Se faltarem dados, nenhuma sinergia é inventada.',
                    'A alternativa só entra no conjunto consultado quando você a adiciona. Jogos repetidos não ampliam a cobertura numérica.']},
                {'id': 'radar', 'title': 'Como leio o radar?', 'paragraphs': [
                    'A porcentagem “após o perfil” conta transições de concursos consecutivos. Compare-a com a referência matemática e o intervalo; amostras abaixo de 30 são sinalizadas como pequenas.',
                    ('No Dia de Sorte há também transições entre meses, cada um com referência matemática de 1 em 12. Meses ausentes não são ligados artificialmente.' if lottery_type == 'diadesorte' else 'Esta loteria não possui Mês da Sorte; o radar de meses não se aplica.'),
                    'Teste histórico não comprova capacidade de antecipar sorteios. Uma frequência do perfil não é a chance de um jogo específico ganhar.']},
                {'id': 'calendar', 'title': 'O calendário mostra “A confirmar”. E agora?', 'paragraphs': [
                    'Confira a data da última consulta. A agenda usa datas reais do cronograma da CAIXA, inclusive domingos e mudanças excepcionais, não uma semana fixa.',
                    'Se a fonte estiver indisponível, a cópia pública anterior é exibida com aviso. Use o link oficial para confirmar prazos e alterações; “A confirmar” não significa que não há sorteio.']},
                {'id': 'privacy', 'title': 'Meus jogos e minha conta estão protegidos?', 'paragraphs': [
                    'O histórico é separado por conta. Não compartilhe senha, token ou código de configuração. Recursos administrativos não ficam disponíveis para contas comuns.',
                    'Esta ajuda é um guia local de respostas prontas, não um atendimento humano ou uma IA preditiva. Não envie documentos ou dados de pagamento. A consulta não grava automaticamente a alternativa no seu histórico.']},
                {'id': 'responsible', 'title': 'Como jogar com responsabilidade?', 'paragraphs': [
                    'Defina um limite de lazer, não use dinheiro de contas e não tente recuperar perdas aumentando apostas. Uso exclusivo para maiores de 18 anos.',
                    'O app não aceita apostas, não efetua pagamentos de jogos e não garante ganhos. Para apostar ou conferir regras, use somente canais oficiais.']},
            ], 'rules_url': game_analysis.RULES_URLS[lottery_type]}
