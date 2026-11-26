import { getPatternRadar } from './api.js';

const panel = document.getElementById('pattern-radar-panel');
const source = document.getElementById('radar-source');
const content = document.getElementById('radar-content');
const status = document.getElementById('radar-status');
const latest = document.getElementById('radar-latest');
const monthControls = document.getElementById('radar-month-controls');
const monthSource = document.getElementById('radar-month-source');
const REFRESH_MS = 60_000;
let lottery = 'megasena';
let identity = null;
let allowed = false;
let pending = null;
let timer = null;
let revision = null;

const number = (value, decimals = 2) => Number(value).toLocaleString('pt-BR', { maximumFractionDigits: decimals });
const percent = value => value === null ? 'Sem amostra' : `${number(value * 100)}%`;
function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
}

function appendWalkForward(test, target) {
    const walk = test.walk_forward;
    if (!walk) return;
    target.append(node('h4', 'Consistência em janelas posteriores'));
    walk.folds.forEach((fold, index) => target.append(node('p',
        `Janela ${index + 1}: treino até ${number(fold.train_last_contest, 0)}, teste ${number(fold.test_first_contest, 0)} a ${number(fold.test_last_contest, 0)} · ${number(fold.sample, 0)} transições. Brier do modelo: ${fold.model_brier === null ? 'sem amostra' : number(fold.model_brier, 4)}; referência: ${fold.baseline_brier === null ? 'sem amostra' : number(fold.baseline_brier, 4)}.`)));
    if (!walk.enough_data) target.append(node('p', 'Amostras insuficientes para comparar todas as janelas com estabilidade.', 'analysis-warning'));
    target.append(node('p', walk.note));
}

function renderMonths(data) {
    if (!data) return;
    const previous = monthSource.value;
    monthSource.replaceChildren(node('option', 'Usar o mês do último concurso'));
    monthSource.firstElementChild.value = '';
    data.profiles.forEach(profile => {
        const option = node('option', profile.label);
        option.value = String(profile.month);
        monthSource.append(option);
    });
    monthSource.value = previous;
    const section = node('section', undefined, 'radar-months');
    section.append(node('h3', 'Mês da Sorte no radar'), node('p', `Último concurso: ${number(data.latest.contest, 0)} · ${data.latest.date} · ${data.latest.label}.`));
    section.append(node('p', `${number(data.coverage.total_draws, 0)} concursos com mês válido · ${number(data.coverage.valid_transitions, 0)} transições consecutivas · ${number(data.coverage.missing_months, 0)} concursos sem mês válido. Não ligamos transições através de dados ausentes.`));
    const selected = data.selected;
    if (!selected) {
        section.append(node('p', 'O último concurso não possui mês válido. Escolha um mês de referência para consultar as transições históricas.', 'analysis-warning'));
    } else {
        section.append(node('p', `Depois de ${selected.label}: ${number(selected.sample, 0)} transições analisadas.`, 'analysis-verdict'));
        if (selected.small_sample) section.append(node('p', 'Amostra pequena: menos de 30 transições. As porcentagens dos meses são instáveis.', 'analysis-warning'));
        const region = node('div', undefined, 'radar-table-scroll');
        region.tabIndex = 0;
        region.setAttribute('role', 'region');
        region.setAttribute('aria-label', 'Transições do Mês da Sorte');
        const table = node('table');
        table.append(node('caption', 'Meses: histórico observado, não previsão. Chance matemática: 1 em 12 para cada mês.'));
        const head = node('thead');
        const headings = node('tr');
        ['Mês seguinte', 'Após o mês escolhido', 'Histórico geral', 'Chance matemática', 'Diferença', 'Intervalo aprox. 95%'].forEach(text => {
            const cell = node('th', text); cell.scope = 'col'; headings.append(cell);
        });
        head.append(headings);
        const body = node('tbody');
        selected.profiles.forEach(profile => {
            const row = node('tr');
            const label = node('th', profile.label); label.scope = 'row'; row.append(label);
            [`${percent(profile.conditional_probability)} (${number(profile.matches, 0)}/${number(selected.sample, 0)})`,
                percent(profile.historical_probability), percent(profile.theoretical_probability),
                profile.difference_pp === null ? 'Sem amostra' : `${number(profile.difference_pp)} pp`,
                profile.interval ? `${percent(profile.interval[0])} a ${percent(profile.interval[1])}` : 'Sem amostra',
            ].forEach(text => row.append(node('td', text)));
            body.append(row);
        });
        table.append(head, body); region.append(table); section.append(region);
    }
    const validation = node('details');
    validation.append(node('summary', 'Teste dos meses em concursos posteriores'));
    const test = data.validation;
    if (test.test_transitions) {
        validation.append(node('p', `${number(test.test_transitions, 0)} transições de teste, após treino nos primeiros 70% dos concursos com mês válido. Acerto: transições ${percent(test.model_accuracy)}; referência uniforme ${percent(test.baseline_accuracy)}.`));
        validation.append(node('p', `Erro Brier (menor é melhor): transições ${number(test.model_brier, 4)}; referência ${number(test.baseline_brier, 4)}.`));
    }
    if (!test.enough_data) validation.append(node('p', 'Poucos concursos de teste para uma comparação estável.', 'analysis-warning'));
    validation.append(node('p', test.note));
    appendWalkForward(test, validation);
    section.append(validation, node('p', data.disclaimer, 'analysis-disclaimer'));
    content.append(section);
}

function render(data) {
    content.replaceChildren();
    latest.textContent = `${data.lottery_name} · Concurso ${number(data.latest.contest, 0)} (${data.latest.date}): ${data.latest.label}.`;
    const previous = source.value;
    source.replaceChildren(node('option', 'Usar o último concurso'));
    source.firstElementChild.value = '';
    data.profiles.forEach(profile => {
        const option = node('option', profile.label);
        option.value = String(profile.even);
        source.append(option);
    });
    source.value = previous;
    const selected = data.selected;
    content.append(node('p', `Depois de ${selected.label}: ${number(selected.sample, 0)} transições analisadas.`, 'analysis-verdict'));
    if (selected.small_sample) {
        content.append(node('p', `Amostra pequena: menos de 30 transições. As porcentagens são instáveis e não sustentam conclusões.`, 'analysis-warning'));
    }
    content.append(node('p', `${number(data.coverage.total_draws, 0)} concursos válidos · ${number(data.coverage.valid_transitions, 0)} transições consecutivas. Base até ${data.latest.date}.`));
    if (data.coverage.excluded_gaps || data.coverage.skipped_rows) {
        content.append(node('p', `${number(data.coverage.excluded_gaps, 0)} saltos de concurso excluídos; ${number(data.coverage.skipped_rows, 0)} linhas inválidas ou duplicadas desconsideradas.`, 'analysis-warning'));
    }
    const region = node('div', undefined, 'radar-table-scroll');
    region.tabIndex = 0;
    region.setAttribute('role', 'region');
    region.setAttribute('aria-label', 'Comparação dos perfis de pares e ímpares');
    const table = node('table');
    table.append(node('caption', 'Frequência observada não é previsão do próximo sorteio. Diferenças em pontos percentuais (pp).'));
    const head = node('thead');
    const headings = node('tr');
    ['Perfil seguinte', 'Após o perfil escolhido', 'Histórico geral', 'Chance matemática', 'Diferença', 'Intervalo aprox. 95%'].forEach(text => {
        const cell = node('th', text);
        cell.scope = 'col';
        headings.append(cell);
    });
    head.append(headings);
    const body = node('tbody');
    [...selected.profiles].sort((a, b) => b.theoretical_probability - a.theoretical_probability).forEach(profile => {
        const row = node('tr');
        const title = node('th', profile.label);
        title.scope = 'row';
        row.append(title);
        const observed = node('td', `${percent(profile.conditional_probability)} (${number(profile.matches, 0)}/${number(selected.sample, 0)})`);
        if (profile.conditional_probability !== null) {
            const track = node('span', undefined, 'radar-bar-track');
            track.setAttribute('aria-hidden', 'true');
            const bar = node('span', undefined, 'radar-bar');
            bar.style.width = `${profile.conditional_probability * 100}%`;
            track.append(bar);
            observed.append(track);
        }
        row.append(observed);
        [percent(profile.historical_probability), percent(profile.theoretical_probability),
            profile.difference_pp === null ? 'Sem amostra' : `${profile.difference_pp > 0 ? '+' : ''}${number(profile.difference_pp)} pp`,
            profile.interval ? `${percent(profile.interval[0])} a ${percent(profile.interval[1])}` : 'Sem amostra',
        ].forEach(text => row.append(node('td', text)));
        body.append(row);
    });
    table.append(head, body);
    region.append(table);
    content.append(region);
    const validation = node('details', undefined, 'radar-validation');
    validation.append(node('summary', 'Teste em concursos posteriores'));
    const test = data.validation;
    if (test.test_transitions) {
        validation.append(node('p', `Treino: ${number(test.train_draws, 0)} concursos, até o concurso ${number(test.train_last_contest, 0)}. Teste: ${number(test.test_transitions, 0)} transições, a partir do concurso ${number(test.test_first_contest, 0)}.`));
        validation.append(node('p', `Acerto do perfil mais provável: transições ${percent(test.model_accuracy)}; referência matemática ${percent(test.baseline_accuracy)}.`));
        validation.append(node('p', `Erro Brier (menor é melhor): transições ${number(test.model_brier, 4)}; referência matemática ${number(test.baseline_brier, 4)}.`));
    }
    if (!test.enough_data) validation.append(node('p', 'Poucos concursos de teste para uma comparação estável.', 'analysis-warning'));
    validation.append(node('p', test.note));
    appendWalkForward(test, validation);
    content.append(validation, node('p', data.disclaimer, 'analysis-disclaimer'));
    renderMonths(data.months);
    if (data.trevos) {
        const section = node('section', undefined, 'radar-trevos');
        section.append(node('h3', 'Trevos no radar'), node('p', `Após os trevos ${data.trevos.latest.trevos.join(' e ')}: ${number(data.trevos.sample, 0)} transições consecutivas.`));
        if (data.trevos.small_sample) section.append(node('p', 'Amostra pequena: menos de 30 transições. Não use essa frequência como previsão.', 'analysis-warning'));
        const region = node('div', undefined, 'radar-table-scroll'); region.tabIndex = 0; region.setAttribute('role', 'region'); region.setAttribute('aria-label', 'Frequência e transições dos pares de trevos');
        const table = node('table'), head = node('thead'), labels = node('tr'), body = node('tbody');
        table.append(node('caption', 'Pares de trevos: observação histórica e referência matemática'));
        ['Trevos', 'Após o último par', 'Histórico geral', 'Chance matemática', 'Intervalo aprox. 95%'].forEach(text => {const th = node('th', text); th.scope = 'col'; labels.append(th);});
        head.append(labels);
        data.trevos.profiles.forEach(profile => {
            const row = node('tr');
            [profile.trevos.join(' + '), `${percent(profile.conditional_probability)} (${profile.matches}/${data.trevos.sample})`, percent(profile.historical_probability), percent(profile.theoretical_probability), profile.interval ? `${percent(profile.interval[0])} a ${percent(profile.interval[1])}` : 'Sem amostra'].forEach(text => row.append(node('td', text)));
            body.append(row);
        });
        table.append(head, body); region.append(table); section.append(region, node('p', data.trevos.note, 'analysis-disclaimer'));
        const validation = node('details'); validation.append(node('summary', 'Teste dos trevos em concursos posteriores'));
        const test = data.trevos.validation;
        validation.append(node('p', test.test_transitions ? `${test.test_transitions} transições de teste. Erro Brier: ${number(test.model_brier, 4)}; referência uniforme: ${number(test.baseline_brier, 4)}.` : 'Sem transições suficientes para teste.'));
        appendWalkForward(test, validation); validation.append(node('p', test.note)); section.append(validation); content.append(section);
    }
    content.hidden = false;
}

async function load(silent = false) {
    if (!allowed || !panel.open || document.hidden) return;
    pending?.abort();
    const controller = new AbortController();
    pending = controller;
    const timeout = setTimeout(() => controller.abort(), 20_000);
    if (!silent) status.textContent = 'Analisando os padrões da base local…';
    panel.setAttribute('aria-busy', 'true');
    try {
        const { radar } = await getPatternRadar(lottery, source.value, controller.signal, lottery === 'diadesorte' ? monthSource.value : '');
        if (pending !== controller || controller.signal.aborted) return;
        const nextRevision = `${radar.data_updated_at}:${radar.selected.even}:${radar.months?.selected?.month}`;
        if (nextRevision !== revision) {
            render(radar);
            revision = nextRevision;
            status.textContent = `Base do radar atualizada em ${new Date(radar.data_updated_at).toLocaleString('pt-BR')}.`;
        }
    } catch (error) {
        if (pending !== controller) return;
        content.hidden = true;
        revision = null;
        status.textContent = controller.signal.aborted ? 'A consulta demorou demais. Reabra o radar para tentar novamente.' : error.message;
    } finally {
        clearTimeout(timeout);
        if (pending === controller) {
            pending = null;
            panel.removeAttribute('aria-busy');
        }
    }
}

export function syncPatternRadar(user, lotteryType) {
    const nextIdentity = user ? `${user.role}:${user.id}:${Boolean(user.is_premium)}` : null;
    const changed = nextIdentity !== identity || lotteryType !== lottery;
    if (changed) {
        pending?.abort();
        pending = null;
        revision = null;
        source.replaceChildren(node('option', 'Usar o último concurso'));
        source.firstElementChild.value = '';
        monthSource.replaceChildren(node('option', 'Usar o mês do último concurso'));
        monthSource.firstElementChild.value = '';
        content.replaceChildren();
        content.hidden = true;
        status.textContent = '';
        latest.textContent = '';
        panel.removeAttribute('aria-busy');
        if (nextIdentity !== identity) panel.open = false;
    }
    identity = nextIdentity;
    lottery = lotteryType;
    allowed = Boolean(user?.is_premium);
    monthControls.hidden = lotteryType !== 'diadesorte';
    document.getElementById('radar-heading').textContent = lotteryType === 'diadesorte'
        ? 'Pares, ímpares e Mês da Sorte' : lotteryType === 'maismilionaria' ? 'Dezenas e trevos em perspectiva' : 'Pares e ímpares em perspectiva';
    panel.classList.toggle('hidden', !allowed);
    clearInterval(timer);
    timer = allowed ? setInterval(() => load(true), REFRESH_MS) : null;
    if (changed) load();
}

export function refreshPatternRadar() {
    revision = null;
    load(true);
}
panel.addEventListener('toggle', () => {
    if (panel.open) load(true);
    else {
        pending?.abort();
        pending = null;
        panel.removeAttribute('aria-busy');
    }
});
source.addEventListener('change', () => {
    revision = null;
    content.hidden = true;
    load();
});
monthSource.addEventListener('change', () => {
    revision = null;
    content.hidden = true;
    load();
});
document.addEventListener('visibilitychange', () => { if (!document.hidden) load(true); });
