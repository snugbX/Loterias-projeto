const panel = document.getElementById('user-assistance-panel');
const select = document.getElementById('help-topic');
const content = document.getElementById('help-content');
const status = document.getElementById('help-status');
let identity = null;
let lottery = null;
let guide = null;
let pending = null;

function node(tag, text) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    return element;
}

function renderTopic() {
    const topic = guide?.topics.find(item => item.id === select.value);
    content.replaceChildren();
    if (!topic) return;
    content.append(node('h3', topic.title));
    topic.paragraphs.forEach(text => content.append(node('p', text)));
    const source = node('a', 'Conferir regras na CAIXA (nova aba)');
    source.href = guide.rules_url;
    source.target = '_blank';
    source.rel = 'noopener noreferrer';
    content.append(source);
}

async function load() {
    if (!identity || !panel.open || pending) return;
    if (guide) { renderTopic(); return; }
    const controller = new AbortController();
    pending = controller;
    const timeout = setTimeout(() => controller.abort(), 10000);
    status.textContent = 'Carregando ajuda para esta loteria...';
    panel.setAttribute('aria-busy', 'true');
    try {
        const response = await fetch(`/user_assistance/${encodeURIComponent(lottery)}`, { cache: 'no-store', signal: controller.signal });
        if (!response.ok) throw new Error('Ajuda indisponível');
        const data = await response.json();
        if (pending !== controller) return;
        guide = data.guide;
        select.replaceChildren();
        guide.topics.forEach(topic => {
            const option = node('option', topic.title); option.value = topic.id; select.append(option);
        });
        document.getElementById('help-lottery-name').textContent = guide.lottery_name;
        select.disabled = false;
        status.textContent = 'Guia contextual. Não é atendimento humano nem previsão de resultados.';
        renderTopic();
    } catch {
        if (pending === controller) status.textContent = 'Não foi possível carregar a ajuda. Feche e reabra para tentar novamente.';
    } finally {
        clearTimeout(timeout);
        if (pending === controller) { pending = null; panel.removeAttribute('aria-busy'); }
    }
}

export function syncUserAssistance(user, lotteryType) {
    const next = user ? `${user.id}:${user.role}:${Boolean(user.is_premium)}` : null;
    if (next !== identity || lottery !== lotteryType) {
        pending?.abort(); pending = null; guide = null;
        content.replaceChildren(); select.replaceChildren(); select.disabled = true; status.textContent = '';
        if (next !== identity) panel.open = false;
        document.getElementById('help-lottery-name').textContent = '';
        panel.removeAttribute('aria-busy');
    }
    identity = next; lottery = lotteryType;
    if (panel.open) load();
}

export function renderAssistanceDetails(data) {
    const target = document.getElementById('assistance-details');
    target.replaceChildren();
    target.append(node('p', `Base: ${data.coverage.total_draws} concursos válidos, até ${data.coverage.last_date} (concurso ${data.coverage.last_contest}). ${data.coverage.skipped_rows} linhas inválidas ou duplicadas excluídas.`), node('p', data.note));
    if (data.months.length) {
        target.append(node('h3', 'Mês da Sorte: frequência histórica'));
        const list = node('dl'); list.className = 'help-month-frequencies';
        data.months.forEach(month => {
            const item = node('div');
            item.append(node('dt', month.label), node('dd', `${month.count} concursos · ${month.percentage === null ? 'Sem dados' : month.percentage.toLocaleString('pt-BR', { maximumFractionDigits: 2 }) + '%'}`));
            list.append(item);
        });
        target.append(list, node('p', `${data.month_coverage.valid} concursos com mês válido; ${data.month_coverage.missing} sem mês válido. Cada mês mantém chance matemática de 1 em 12.`));
    }
}

select.addEventListener('change', renderTopic);
panel.addEventListener('toggle', () => { if (panel.open) load(); });
