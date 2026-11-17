import { getPatternRadar } from './api.js';

const panel = document.getElementById('pattern-radar-panel');
const source = document.getElementById('radar-source');
const content = document.getElementById('radar-content');
const status = document.getElementById('radar-status');
const latest = document.getElementById('radar-latest');
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
    content.append(validation, node('p', data.disclaimer, 'analysis-disclaimer'));
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
        const { radar } = await getPatternRadar(lottery, source.value, controller.signal);
        if (pending !== controller || controller.signal.aborted) return;
        const nextRevision = `${radar.data_updated_at}:${radar.selected.even}`;
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
document.addEventListener('visibilitychange', () => { if (!document.hidden) load(true); });
