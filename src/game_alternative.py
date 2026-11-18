"""Minimal parity edits guided by a descriptive radar, never a winning forecast."""

import gerador_loterias as lottery
import pattern_radar


def suggest_alternative(lottery_type, numbers, month, radar):
    config = lottery.LOTTERY_CONFIGS[lottery_type]
    source = radar['groups'][radar['latest']['even']]
    current_even = sum(number % 2 == 0 for number in numbers)
    use_transitions = source['sample'] >= pattern_radar.MIN_SAMPLE

    def score(profile):
        baseline = profile['theoretical_probability']
        if not use_transitions:
            return baseline
        return (profile['matches'] + pattern_radar.PRIOR_WEIGHT * baseline) / (source['sample'] + pattern_radar.PRIOR_WEIGHT)

    # A tie preserves more of the submitted game; no individual number is ranked as luckier.
    target = max(source['profiles'], key=lambda profile: (
        score(profile), profile['theoretical_probability'], -abs(profile['even'] - current_even), -profile['even']))
    selected = set(numbers)
    difference = target['even'] - current_even
    wanted_parity = 0 if difference > 0 else 1
    changes = []
    for _ in range(abs(difference)):
        pairs = [(old, new) for old in selected if old % 2 != wanted_parity
                 for new in range(config['MIN_NUMBER'], config['MAX_NUMBER'] + 1)
                 if new % 2 == wanted_parity and new not in selected]
        old, new = min(pairs, key=lambda pair: (abs(pair[0] - pair[1]), -pair[0], pair[1] < pair[0], pair[1]))
        selected.remove(old)
        selected.add(new)
        changes.append({'from': old, 'to': new})
    return {
        'status': 'alternative' if changes else 'already_aligned',
        'numbers': sorted(selected), 'month': month, 'changes': changes,
        'preserved_numbers': sorted(set(numbers) & selected),
        'target_even': target['even'], 'target_odd': target['odd'], 'target_label': target['label'],
        'basis': 'smoothed_transitions' if use_transitions else 'theoretical_fallback',
        'source_label': source['label'], 'source_contest': radar['latest']['contest'],
        'source_date': radar['latest']['date'], 'sample': source['sample'],
        'small_sample': not use_transitions, 'matches': target['matches'],
        'conditional_probability': target['conditional_probability'],
        'theoretical_probability': target['theoretical_probability'], 'reference_score': score(target),
        'note': ('Perfil de referência escolhido pelas transições do último perfil, suavizadas pela distribuição matemática. '
                 if use_transitions else
                 'Amostra insuficiente nas transições do último perfil. Usamos o perfil mais provável pela distribuição matemática, não uma previsão do radar. ')
                + 'As trocas preservam o máximo de dezenas e escolhem vizinhas disponíveis; não indicam números mais prováveis. '
                  'A alternativa tem a mesma chance matemática individual do jogo original. Não garante prêmio.',
    }
