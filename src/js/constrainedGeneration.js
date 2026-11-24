import { generateConstrainedGames } from './api.js';
import { compareGeneratedGames } from './gameAnalysis.js';

const panel = document.getElementById('constrained-panel');
const form = document.getElementById('constrained-form');
const fields = document.getElementById('constrained-fields');
const status = document.getElementById('constrained-status');
const summary = document.getElementById('constrained-summary');
const method = document.getElementById('constrained-method');
let identity = null;
let lottery = null;
let caps = null;
let pending = null;
let onGenerated = () => {};
let focusRequested = false;
const input = name => document.getElementById(`constrained-${name}`);

function node(tag, text) {
    const el = document.createElement(tag); if (text !== undefined) el.textContent = text; return el;
}
function updateMethod() {
    const rules = document.getElementById('constrained-rules');
    rules.hidden = method.value === 'uniform';
    rules.querySelectorAll('input,select').forEach(control => { control.disabled = rules.hidden; });
}

async function load() {
    if (!identity || !panel.open || caps || pending) return;
    const controller = new AbortController(); pending = controller;
    const timeout = setTimeout(() => controller.abort(), 10000);
    status.textContent = 'Carregando as regras desta loteria...';
    try {
        const response = await fetch(`/generation_rules/${lottery}`, { signal: controller.signal, cache: 'no-store' });
        if (!response.ok) throw new Error();
        const data = await response.json();
        if (pending !== controller) return;
        caps = data;
        input('quantity').max = String(caps.max_games);
        input('overlap').min = String(caps.min_overlap); input('overlap').max = String(caps.count - 1);
        input('overlap').value = String(caps.count - 1);
        input('parity').replaceChildren(node('option', 'Qualquer distribuição'));
        input('parity').firstElementChild.value = '';
        caps.parities.forEach(value => { const option = node('option', `${value} pares e ${caps.count - value} ímpares`); option.value = String(value); input('parity').append(option); });
        input('month').replaceChildren(node('option', 'Escolher aleatoriamente'));
        input('month').firstElementChild.value = '';
        caps.months.forEach((name, index) => { const option = node('option', name); option.value = String(index + 1); input('month').append(option); });
        document.getElementById('constrained-month-field').hidden = !caps.months.length;
        document.getElementById('constrained-lottery').textContent = `${caps.count} dezenas de 1 a ${caps.maximum} · até ${caps.max_games} jogos por lote`;
        document.getElementById('constrained-overlap-note').textContent = `Menor sobreposição possível no universo completo: ${caps.min_overlap} dezenas. Dezenas fixas e exclusões podem elevar esse mínimo.`;
        status.textContent = ''; fields.disabled = false; updateMethod();
        if (focusRequested) { method.focus(); focusRequested = false; }
    } catch {
        if (pending === controller) status.textContent = 'Não foi possível carregar as regras. Feche e reabra este painel.';
    } finally { clearTimeout(timeout); if (pending === controller) pending = null; }
}

export function syncConstrainedGeneration(user, kind) {
    const next = user?.is_premium ? `${user.id}:${user.role}` : null;
    if (next !== identity || lottery !== kind) {
        pending?.abort(); pending = null; caps = null;
        focusRequested = false;
        form.reset(); updateMethod(); fields.disabled = true; summary.replaceChildren(); status.textContent = ''; form.removeAttribute('aria-busy');
        if (next !== identity) panel.open = false;
    }
    identity = next; lottery = kind; panel.classList.toggle('hidden', !next);
    if (panel.open) load();
}

export function initConstrainedGeneration(callback) { onGenerated = callback; }

export function openConstrainedGeneration(nextMethod) {
    if (!identity || !['uniform', 'constraints'].includes(nextMethod) || (pending && caps)) return false;
    focusRequested = true; panel.open = true; method.value = nextMethod; updateMethod();
    panel.scrollIntoView({ block: 'start', behavior: 'auto' });
    if (caps && !fields.disabled) { method.focus(); focusRequested = false; }
    else load();
    return true;
}

function numberList(text) {
    text = text.trim();
    if (!text) return [];
    if (!/^\d+(?:[\s,;]+\d+)*$/.test(text)) throw new Error('Use somente dezenas separadas por espaços, vírgulas ou ponto e vírgula.');
    return text.split(/[\s,;]+/).map(Number);
}

form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!identity || !caps || pending || fields.disabled) return;
    let payload;
    try {
        payload = { method: method.value, num_games: Number(input('quantity').value) };
        if (caps.months.length && input('month').value) payload.month = Number(input('month').value);
        if (method.value === 'constraints') {
            payload.fixed = numberList(input('fixed').value); payload.excluded = numberList(input('excluded').value);
            payload.max_overlap = Number(input('overlap').value);
            for (const [field, key] of [['parity', 'even_count'], ['min-sum', 'sum_min'], ['max-sum', 'sum_max']]) {
                if (input(field).value !== '') payload[key] = Number(input(field).value);
            }
        }
    } catch (error) { status.textContent = error.message; return; }
    const kind = lottery;
    const controller = new AbortController(); pending = controller;
    const timeout = setTimeout(() => controller.abort(), 25000);
    fields.disabled = true; summary.replaceChildren(); status.textContent = 'Buscando um lote compatível...';
    form.setAttribute('aria-busy', 'true');
    try {
        const data = await generateConstrainedGames(kind, payload, controller.signal);
        if (pending !== controller) return;
        status.textContent = 'Lote gerado e salvo no histórico da sua conta.';
        const p = data.portfolio;
        summary.append(node('p', `${p.unique_combinations} combinações distintas · ${p.distinct_numbers} dezenas diferentes no conjunto · maior sobreposição: ${p.max_overlap ?? 'não se aplica'}.`),
            node('p', data.method_note), node('p', p.note));
        if (p.unique_months !== undefined) summary.append(node('p', `${p.unique_months} meses distintos no lote; cobertura do Mês da Sorte no mesmo concurso: ${(p.month_probability * 100).toLocaleString('pt-BR', { maximumFractionDigits: 2 })}%. Isso não indica lucro nem amplia a chance dos 7 acertos numéricos.`));
        const compare = node('button', 'Consultar e comparar este lote'); compare.type = 'button';
        compare.disabled = data.games.length > 10;
        if (compare.disabled) compare.title = 'A consulta aceita até 10 jogos por vez.';
        compare.addEventListener('click', () => compareGeneratedGames(data.games, kind)); summary.append(compare);
        onGenerated(data, kind);
    } catch (error) {
        if (pending === controller) status.textContent = controller.signal.aborted
            ? 'A resposta demorou demais. Confira seu histórico antes de tentar novamente.' : error.message;
    } finally {
        clearTimeout(timeout);
        if (pending === controller) { pending = null; fields.disabled = false; form.removeAttribute('aria-busy'); }
    }
});
method.addEventListener('change', updateMethod);
panel.addEventListener('toggle', () => { if (panel.open) load(); });
