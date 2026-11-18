import { analyzeGames } from './api.js';

const panel = document.getElementById('game-analysis-panel');
const form = document.getElementById('game-analysis-form');
const entries = document.getElementById('analysis-games');
const addButton = document.getElementById('analysis-add-game');
const MAX_GAMES = 10;
const months = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
const result = document.getElementById('analysis-result');
const feedback = document.getElementById('analysis-feedback');
const submit = form.querySelector('button[type="submit"]');
const lotteries = {
    megasena: { name: 'Mega-Sena', count: 6, max: 60 },
    lotofacil: { name: 'Lotofácil', count: 15, max: 25 },
    quina: { name: 'Quina', count: 5, max: 80 },
    diadesorte: { name: 'Dia de Sorte', count: 7, max: 31 },
};
let currentLottery = 'megasena';
let currentIdentity = null;
let allowed = false;
let controller = null;

const integer = value => Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 0 });
const percentage = value => Number(value).toLocaleString('pt-BR', { maximumSignificantDigits: 4 }) + '%';

function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
}

function heading(text, target = result) {
    target.append(node('h3', text));
}

function table(caption, columns, rows, target = result) {
    const wrapper = node('div', undefined, 'analysis-table-scroll');
    wrapper.tabIndex = 0;
    wrapper.setAttribute('role', 'region');
    wrapper.setAttribute('aria-label', caption);
    const element = node('table');
    element.append(node('caption', caption));
    const head = node('thead');
    const headRow = node('tr');
    columns.forEach(title => {
        const cell = node('th', title);
        cell.scope = 'col';
        headRow.append(cell);
    });
    head.append(headRow);
    const body = node('tbody');
    rows.forEach(values => {
        const row = node('tr');
        values.forEach(value => row.append(node('td', String(value))));
        body.append(row);
    });
    element.append(head, body);
    wrapper.append(element);
    target.append(wrapper);
}

function renderHighlights(data, target) {
    const highlights = node('dl', undefined, 'analysis-highlights');
    const items = [
        ['Faixas no histórico', `${integer(data.history.prize_draws)} concursos`, 'Simulação, não prêmios recebidos'],
        ['Maior acerto numérico', `${data.history.best_matches} acertos`, `Em ${integer(data.coverage.total_draws)} concursos válidos`],
        ['Seu perfil', `${data.profile.even} pares · ${data.profile.odd} ímpares`, 'Distribuição do jogo informado'],
        ['Prêmio principal numérico', `1 em ${integer(data.probabilities.jackpot_one_in)}`, 'Chance matemática da aposta simples'],
    ];
    for (const [label, value, note] of items) {
        const item = node('div');
        item.append(node('dt', label), node('dd', value), node('p', note));
        highlights.append(item);
    }
    target.append(highlights);
}

function renderAlternative(data, target) {
    const alternative = data.alternative;
    if (!alternative) return;
    const section = node('section', undefined, 'analysis-alternative');
    const title = node('h3', alternative.status === 'already_aligned'
        ? 'Seu jogo já segue o perfil de referência' : 'Uma alternativa para o seu jogo');
    title.id = `alternative-title-${data.game_id}`;
    section.setAttribute('aria-labelledby', title.id);
    section.append(title, node('p', `Perfil de referência: ${alternative.target_label}`, 'alternative-profile'));
    const balls = node('div', undefined, 'alternative-numbers');
    balls.setAttribute('aria-label', 'Dezenas da alternativa');
    for (const number of alternative.numbers) {
        const changed = alternative.changes.some(change => change.to === number);
        const ball = node('span', String(number).padStart(2, '0'), `alternative-number${changed ? ' is-changed' : ''}`);
        if (changed) ball.setAttribute('aria-label', `${number}, nova dezena`);
        balls.append(ball);
    }
    section.append(balls);
    if (alternative.month) section.append(node('p', `Mês da Sorte mantido: ${months[alternative.month - 1]}.`));
    if (alternative.changes.length) {
        section.append(node('p', `Trocas: ${alternative.changes.map(change => `${String(change.from).padStart(2, '0')} → ${String(change.to).padStart(2, '0')}`).join('; ')}. ${alternative.preserved_numbers.length} de ${data.numbers.length} dezenas mantidas.`, 'analysis-verdict'));
    } else {
        section.append(node('p', 'Nenhuma troca necessária: mantivemos suas dezenas. Não há motivo estatístico para substituir um número por outro do mesmo perfil.'));
    }
    if (alternative.small_sample) {
        section.append(node('p', `Amostra pequena (${integer(alternative.sample)} transições). Referência usada: distribuição matemática, não tendência do próximo sorteio.`, 'analysis-warning'));
    } else {
        section.append(node('p', `Após ${alternative.source_label}, esse perfil apareceu ${integer(alternative.matches)} vezes em ${integer(alternative.sample)} transições (${percentage(alternative.conditional_probability * 100)}). Frequência do perfil, não chance de ganhar com estas dezenas.`));
    }
    section.append(node('p', `Base do radar: concurso ${integer(alternative.source_contest)}, de ${alternative.source_date}.`));
    if (alternative.changes.length) {
        section.append(node('p', `Na mesma base, a alternativa teria faixa em ${integer(alternative.history.prize_draws)} concursos; seu jogo, em ${integer(data.history.prize_draws)}. Mais ocorrências passadas não significam maior chance futura.`));
        const actions = node('div', undefined, 'alternative-actions');
        const copy = node('button', 'Copiar alternativa');
        copy.type = 'button';
        const compare = node('button', 'Comparar com meu jogo');
        compare.type = 'button';
        compare.disabled = entries.children.length >= MAX_GAMES || alternative.duplicates_game_ids.length > 0;
        if (compare.disabled) {
            section.append(node('p', alternative.duplicates_game_ids.length
                ? `Esta alternativa já está na consulta: ${alternative.duplicates_game_ids.map(id => `Jogo ${id}`).join(', ')}.`
                : `A consulta atingiu o limite de ${MAX_GAMES} jogos. Remova um jogo para comparar a alternativa.`));
        }
        const status = node('p', '', 'alternative-action-status');
        status.setAttribute('role', 'status');
        copy.addEventListener('click', async () => {
            const text = alternative.numbers.map(n => String(n).padStart(2, '0')).join(' ')
                + (alternative.month ? ` · Mês da Sorte: ${months[alternative.month - 1]}` : '');
            try {
                await navigator.clipboard.writeText(text);
                status.textContent = 'Alternativa copiada.';
            } catch {
                status.textContent = 'Não foi possível copiar automaticamente. Selecione as dezenas para copiar.';
            }
        });
        compare.addEventListener('click', () => {
            if (!allowed || entries.children.length >= MAX_GAMES) return;
            addEntry(false);
            const row = entries.lastElementChild;
            row.querySelector('input').value = alternative.numbers.map(n => String(n).padStart(2, '0')).join(' ');
            if (alternative.month) row.querySelector('select').value = String(alternative.month);
            form.requestSubmit();
        });
        actions.append(copy, compare);
        section.append(actions, status);
    }
    const explanation = node('details');
    explanation.append(node('summary', 'Como esta referência foi escolhida'), node('p', alternative.note));
    section.append(explanation, node('p', `Mesma chance individual: 1 em ${integer(alternative.jackpot_one_in)} no prêmio principal numérico. Esta sugestão não aumenta a probabilidade da aposta simples.`, 'analysis-disclaimer'));
    target.append(section);
}

function renderAnalysis(data, result) {
    result.replaceChildren();
    result.append(node('h3', `${data.lottery_name || lotteries[currentLottery].name}: ${data.numbers.map(n => String(n).padStart(2, '0')).join(' · ')}`));
    if (data.month) result.append(node('p', `Mês da Sorte: ${months[data.month - 1]}`));
    const { history, coverage, profile, probabilities } = data;
    renderHighlights(data, result);
    result.append(node('p', history.prize_draws
        ? `Seu jogo teria faixa de premiação em ${integer(history.prize_draws)} dos ${integer(coverage.total_draws)} concursos analisados (${percentage(history.percentage)}).`
        : 'Não encontramos faixa de premiação para esse jogo nos concursos analisados.', 'analysis-verdict'));
    result.append(node('p', `Base local: concursos ${integer(coverage.first_contest)} a ${integer(coverage.last_contest)}, de ${coverage.first_date} a ${coverage.last_date}. Maior acerto numérico: ${history.best_matches}.`));
    if (coverage.skipped_rows || coverage.missing_contests || coverage.missing_months) {
        result.append(node('p', `Base incompleta: ${integer(coverage.skipped_rows)} linhas inválidas ou duplicadas desconsideradas; ${integer(coverage.missing_contests)} concursos ausentes entre os extremos; ${integer(coverage.missing_months)} concursos sem mês válido. A simulação não cobre dados ausentes.`, 'analysis-warning'));
    }
    renderAlternative(data, result);
    heading('Faixas encontradas no histórico', result);
    const historicalRows = history.tiers.map(tier => [`${tier.matches} acertos`, integer(tier.count)]);
    if (data.month) historicalRows.push(['Mês da Sorte (pode coincidir com acertos)', integer(history.month_matches)]);
    table('Premiações simuladas pelas regras atuais', ['Faixa', 'Concursos'], historicalRows, result);
    heading('O perfil do seu jogo', result);
    result.append(node('p', `${profile.even} pares · ${profile.odd} ímpares · Soma ${profile.sum} · ${profile.consecutive_pairs} pares consecutivos`));
    const strategies = node('ul', undefined, 'analysis-strategies');
    data.strategies.forEach(strategy => strategies.append(node('li', strategy.label)));
    if (!data.strategies.length) strategies.append(node('li', 'Sem característica exclusiva dos filtros consultados.'));
    result.append(strategies, node('p', data.strategy_note));
    const radar = data.radar_context;
    if (radar) {
        heading('Seu perfil no radar', result);
        result.append(node('p', `Após ${radar.source_label}, o perfil ${radar.target_label} apareceu ${integer(radar.matches)} vezes em ${integer(radar.sample)} transições (${radar.conditional_probability === null ? 'sem amostra' : percentage(radar.conditional_probability * 100)}). Referência matemática do perfil: ${percentage(radar.theoretical_probability * 100)}.`));
        if (radar.interval) result.append(node('p', `Intervalo aproximado de 95%: ${percentage(radar.interval[0] * 100)} a ${percentage(radar.interval[1] * 100)}.`));
        if (radar.small_sample) result.append(node('p', 'Poucas transições para este perfil; frequências instáveis.', 'analysis-warning'));
        result.append(node('p', 'Essas taxas descrevem o perfil de pares e ímpares, não a chance deste jogo específico ganhar.'));
    }
    heading('Chance matemática por concurso', result);
    result.append(node('p', `Prêmio principal numérico: 1 em ${integer(probabilities.jackpot_one_in)}. Chance de alguma faixa: ${percentage(probabilities.any_prize * 100)}.`, 'analysis-verdict'));
    table('Aposta simples: acertos exatos, não acumulados', ['Faixa', 'Chance aproximada', 'Probabilidade'],
        probabilities.tiers.map(tier => [tier.label, `1 em ${integer(tier.one_in)}`, percentage(tier.probability * 100)]), result);
    result.append(node('p', 'Frequência passada não é chance futura. Uma estratégia mais frequente reúne mais combinações; cada jogo individual continua com a mesma chance.'));
    if (history.recent_occurrences.length) {
        const details = node('details');
        details.append(node('summary', `Ver concursos compatíveis${history.has_more ? ' (30 mais recentes)' : ''}`));
        const list = node('ol', undefined, 'analysis-occurrences');
        history.recent_occurrences.forEach(draw => {
            const label = `${integer(draw.contest)} · ${draw.date}: ${draw.matches} acertos${draw.month_match ? ' + Mês da Sorte' : ''}`;
            list.append(node('li', `${label}. Sorteio: ${draw.numbers.map(n => String(n).padStart(2, '0')).join(' ')}.`));
        });
        details.append(list);
        result.append(details);
    }
    result.append(node('p', data.disclaimer, 'analysis-disclaimer'));
    const source = node('a', 'Regras e probabilidades: CAIXA (abre em nova aba)');
    source.href = data.rules_url;
    source.target = '_blank';
    source.rel = 'noopener noreferrer';
    result.append(source);
}

function renderComparison(data) {
    result.replaceChildren();
    const { summary, analyses, coverage } = data;
    heading(analyses.length > 1 ? 'Comparação dos jogos' : 'Resultado da consulta');
    result.append(node('p', `${summary.submitted} ${summary.submitted === 1 ? 'jogo consultado' : 'jogos consultados'} · ${summary.unique_games} ${summary.unique_games === 1 ? 'aposta diferente' : 'apostas diferentes'} · ${summary.distinct_numbers} dezenas distintas no conjunto.`, 'analysis-verdict'));
    result.append(node('p', `Base até ${coverage.last_date}, concurso ${integer(coverage.last_contest)}. Todas as análises usam os mesmos ${integer(coverage.total_draws)} concursos válidos.`));
    if (coverage.skipped_rows || coverage.missing_contests || coverage.missing_months) {
        result.append(node('p', `Base incompleta: ${integer(coverage.skipped_rows)} linhas inválidas ou duplicadas, ${integer(coverage.missing_contests)} concursos ausentes e ${integer(coverage.missing_months)} concursos sem mês válido. Dados ausentes não entram integralmente na simulação.`, 'analysis-warning'));
    }
    if (summary.duplicate_groups.length) {
        result.append(node('p', `Jogos repetidos: ${summary.duplicate_groups.map(ids => ids.join(' e ')).join('; ')}. Repetir a mesma aposta não amplia a cobertura de resultados.`, 'analysis-warning'));
    }
    analyses.forEach(game => {
        const detail = node('details', undefined, 'analysis-game-detail');
        detail.open = analyses.length === 1;
        detail.append(node('summary', `Jogo ${game.game_id} · ${game.numbers.map(n => String(n).padStart(2, '0')).join(' ')}${game.month ? ` · ${months[game.month - 1]}` : ''} · ${integer(game.history.prize_draws)} concursos com faixa`));
        const body = node('div');
        renderAnalysis(game, body);
        detail.append(body);
        result.append(detail);
    });
    if (analyses.length > 1) {
        result.append(node('p', `No conjunto, pelo menos um jogo teria faixa de premiação em ${integer(summary.historical_prize_draws)} concursos (${percentage(summary.historical_percentage)}). Cada concurso é contado apenas uma vez.`));
        if (summary.most_historical_prizes > 0) {
            result.append(node('p', `Maior frequência de faixas no histórico: ${summary.historical_leaders.map(id => `Jogo ${id}`).join(', ')} (${integer(summary.most_historical_prizes)} concursos por jogo). Isso não indica maior chance futura.`));
        }
        const comparison = node('div', undefined, 'comparison-overview');
        table('Resumo por jogo: resultados históricos, não previsão',
            ['Jogo', 'Dezenas / mês', 'Concursos com faixa', 'Maior acerto', 'Pares / ímpares', 'Perfil após o último concurso'],
            analyses.map(game => [
                `Jogo ${game.game_id}`, `${game.numbers.map(n => String(n).padStart(2, '0')).join(' ')}${game.month ? ` · ${months[game.month - 1]}` : ''}`,
                `${integer(game.history.prize_draws)} (${percentage(game.history.percentage)})`, game.history.best_matches,
                `${game.profile.even} / ${game.profile.odd}`,
                game.radar_context.conditional_probability === null ? 'Sem amostra' : `${percentage(game.radar_context.conditional_probability * 100)} (${integer(game.radar_context.matches)}/${integer(game.radar_context.sample)})`,
            ]), comparison);
        result.append(comparison);
    }
    heading('Cobertura matemática do conjunto');
    result.append(node('p', `${summary.unique_number_combinations} ${summary.unique_number_combinations === 1 ? 'combinação numérica diferente' : 'combinações numéricas diferentes'}: chance do prêmio principal numérico de aproximadamente 1 em ${integer(summary.numeric_jackpot_one_in)} (${percentage(summary.numeric_jackpot_probability * 100)}), considerando todos esses jogos no mesmo concurso.`));
    result.append(node('p', 'Cada aposta simples, individualmente, mantém a mesma chance matemática das demais. A coluna do radar descreve o perfil, não a probabilidade do jogo específico.'));
    if (summary.unique_months !== null) result.append(node('p', `Mês da Sorte: ${summary.unique_months} meses diferentes cobertos (${percentage(summary.month_coverage_probability * 100)} de acertar ao menos um mês). Mesmas dezenas com outro mês não ampliam a chance dos 7 acertos numéricos.`));
    result.append(node('p', data.comparison_note, 'analysis-disclaimer'));
    result.append(node('p', `Radar de referência: concurso ${integer(data.radar.latest.contest)}, ${data.radar.latest.label}. Frequências exploratórias; o concurso anterior não altera a chance matemática em sorteios independentes.`));
    const validation = node('details');
    validation.append(node('summary', 'Teste do radar em concursos posteriores'));
    const test = data.radar.validation;
    if (test.test_transitions) {
        validation.append(node('p', `${integer(test.test_transitions)} transições reservadas para teste. Acerto do perfil: transições ${percentage(test.model_accuracy * 100)}; referência matemática ${percentage(test.baseline_accuracy * 100)}.`));
        validation.append(node('p', `Erro Brier (menor é melhor): transições ${test.model_brier.toLocaleString('pt-BR', { maximumFractionDigits: 4 })}; referência ${test.baseline_brier.toLocaleString('pt-BR', { maximumFractionDigits: 4 })}.`));
    }
    if (!test.enough_data) validation.append(node('p', 'Poucos concursos reservados para uma comparação estável.', 'analysis-warning'));
    validation.append(node('p', test.note));
    result.append(validation);
    if (data.pairs.length) {
        const overlap = node('details', undefined, 'comparison-overlap');
        overlap.append(node('summary', 'Dezenas em comum e jogos repetidos'));
        table('Sobreposição entre cada par de jogos', ['Jogos', 'Dezenas em comum', 'Sobreposição', 'Comparação'],
            data.pairs.map(pair => [
                `${pair.left} × ${pair.right}`,
                pair.common_numbers.length ? pair.common_numbers.map(n => String(n).padStart(2, '0')).join(' ') : 'Nenhuma',
                `${pair.common_numbers.length} (${percentage(pair.overlap_percentage)})`,
                pair.duplicate ? 'Jogo repetido' : pair.same_numbers ? 'Mesmas dezenas, meses diferentes' : 'Combinações diferentes',
            ]), overlap);
        result.append(overlap);
    }
    result.hidden = false;
    result.focus({ preventScroll: true });
}

function invalidateResult() {
    controller?.abort();
    controller = null;
    result.replaceChildren();
    result.hidden = true;
    feedback.textContent = '';
    submit.disabled = false;
    form.removeAttribute('aria-busy');
}

function updateEntryLabels() {
    const rows = Array.from(entries.children);
    const config = lotteries[currentLottery];
    rows.forEach((row, index) => {
        const suffix = index ? `-${index + 1}` : '';
        row.querySelector('legend').textContent = `Jogo ${index + 1}`;
        const input = row.querySelector('input');
        input.id = `analysis-numbers${suffix}`;
        input.placeholder = Array.from({ length: config.count }, (_, i) => String(i + 1).padStart(2, '0')).join(' ');
        row.querySelector('.analysis-numbers-label').htmlFor = input.id;
        const month = row.querySelector('select');
        month.id = `analysis-month${suffix}`;
        row.querySelector('.analysis-month-label').htmlFor = month.id;
        row.querySelector('.analysis-month-field').hidden = currentLottery !== 'diadesorte';
        const remove = row.querySelector('button');
        remove.disabled = rows.length === 1;
        remove.title = `Remover jogo ${index + 1}`;
        remove.setAttribute('aria-label', remove.title);
    });
    addButton.disabled = rows.length >= MAX_GAMES;
}

function addEntry(focus = true) {
    if (entries.children.length >= MAX_GAMES) return;
    invalidateResult();
    const row = node('fieldset', undefined, 'analysis-entry');
    row.append(node('legend'));
    const fields = node('div', undefined, 'analysis-entry-fields');
    const numberField = node('div');
    numberField.append(node('label', 'Dezenas', 'analysis-numbers-label'));
    const input = node('input');
    input.type = 'text';
    input.maxLength = 100;
    input.autocomplete = 'off';
    input.required = true;
    input.setAttribute('aria-describedby', 'analysis-number-hint analysis-feedback');
    numberField.append(input);
    const monthField = node('div', undefined, 'analysis-month-field');
    monthField.append(node('label', 'Mês da Sorte', 'analysis-month-label'));
    const month = node('select');
    months.forEach((name, index) => {
        const option = node('option', name);
        option.value = String(index + 1);
        month.append(option);
    });
    monthField.append(month);
    const remove = node('button', '×', 'analysis-remove-game');
    remove.type = 'button';
    remove.addEventListener('click', () => {
        if (entries.children.length === 1) return;
        const next = row.nextElementSibling || row.previousElementSibling;
        invalidateResult();
        row.remove();
        updateEntryLabels();
        next?.querySelector('input').focus();
    });
    fields.append(numberField, monthField, remove);
    row.append(fields);
    entries.append(row);
    updateEntryLabels();
    if (focus) input.focus();
}

export function syncGameAnalysis(user, lotteryType) {
    const identity = user ? `${user.role}:${user.id}:${Boolean(user.is_premium)}` : null;
    const changed = identity !== currentIdentity || lotteryType !== currentLottery;
    if (identity !== currentIdentity) panel.open = false;
    currentIdentity = identity;
    currentLottery = lotteryType;
    allowed = Boolean(user?.is_premium);
    panel.classList.toggle('hidden', !allowed);
    if (changed || !entries.children.length) {
        entries.replaceChildren();
        addEntry(false);
    }
    const config = lotteries[lotteryType];
    document.getElementById('analysis-lottery-label').textContent = config.name;
    document.getElementById('analysis-number-hint').textContent = `${config.count} dezenas diferentes por jogo, de 1 a ${config.max}, separadas por espaço, vírgula ou ponto e vírgula. Limite: ${MAX_GAMES} jogos.`;
}

addButton.addEventListener('click', () => addEntry());
form.addEventListener('input', event => {
    event.target.removeAttribute('aria-invalid');
    invalidateResult();
});
form.addEventListener('change', invalidateResult);
form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!allowed || submit.disabled) return;
    invalidateResult();
    const config = lotteries[currentLottery];
    const games = [];
    for (const [index, row] of Array.from(entries.children).entries()) {
        const input = row.querySelector('input');
        const text = input.value.trim();
        const parts = text.split(/[\s,;]+/);
        const numbers = parts.map(Number);
        if (!/^\d+(?:[\s,;]+\d+)*$/.test(text) || parts.length !== config.count
            || new Set(numbers).size !== config.count || numbers.some(n => !Number.isInteger(n) || n < 1 || n > config.max)) {
            feedback.textContent = `Confira o jogo ${index + 1}: informe ${config.count} dezenas diferentes, de 1 a ${config.max}.`;
            input.setAttribute('aria-invalid', 'true');
            input.focus();
            return;
        }
        input.removeAttribute('aria-invalid');
        games.push({ numbers, month: currentLottery === 'diadesorte' ? Number(row.querySelector('select').value) : null });
    }
    const pending = new AbortController();
    controller = pending;
    const timeout = setTimeout(() => pending.abort(), 30_000);
    submit.disabled = true;
    form.setAttribute('aria-busy', 'true');
    feedback.textContent = 'Conferindo e comparando os jogos…';
    try {
        const data = await analyzeGames(currentLottery, games, pending.signal);
        if (controller !== pending || pending.signal.aborted) return;
        renderComparison(data.comparison);
        feedback.textContent = 'Consulta concluída.';
    } catch (error) {
        if (controller === pending) feedback.textContent = pending.signal.aborted ? 'A consulta demorou demais. Tente novamente.' : error.message;
    } finally {
        clearTimeout(timeout);
        if (controller === pending) {
            submit.disabled = false;
            form.removeAttribute('aria-busy');
            controller = null;
        }
    }
});
