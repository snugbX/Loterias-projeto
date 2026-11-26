import { getManagedHistory, updateManagedGame, clearManagedHistory } from './api.js';
import { lotteryColors } from './dom.js';
import { formatLotteryName } from './render.js';

const el = id => document.getElementById(id);
const overlay = el('history-modal-overlay');
const root = el('history-manager');
const form = el('history-filters');
const list = el('history-games');
const feedback = el('history-feedback');
let identity = null, kind = null, page = 1, pages = 1, pending = null, timer = null, busy = false, dirty = false;
let filters = {};
const visible = () => identity && !overlay.classList.contains('hidden') && !document.hidden;
function node(tag, text, className) { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (className) n.className = className; return n; }
function button(text, action) { const b = node('button', text); b.type = 'button'; b.addEventListener('click', action); return b; }
function schedule() {
    clearTimeout(timer);
    if (visible()) timer = setTimeout(() => { if (!dirty && !busy) load(true); else schedule(); }, 60000);
}
export function syncHistoryManager(user, lottery) {
    const next = user ? `${user.is_guest ? 'guest' : 'user'}:${user.id}` : null;
    if (next === identity && kind === lottery) return;
    pending?.abort(); pending = null; clearTimeout(timer); timer = null;
    list.replaceChildren(); el('history-summary').replaceChildren(); feedback.textContent = ''; el('history-source').textContent = '';
    form.reset(); el('history-filter-panel').open = false; filters = {}; page = 1; dirty = false;
    overlay.classList.add('hidden'); overlay.setAttribute('aria-hidden', 'true');
    identity = next; kind = lottery;
}
export function openHistoryManager(lottery, user) {
    syncHistoryManager(user, lottery);
    for (const id of ['historico-arquivos-container-modal', 'historico-conteudo-container-modal']) el(id).classList.add('hidden');
    el('history-modal-title').textContent = `Meus jogos · ${formatLotteryName(kind)}`;
    overlay.classList.remove('hidden'); overlay.setAttribute('aria-hidden', 'false');
    el('history-modal-close-btn').focus();
    if (dirty) schedule(); else load();
}
async function mutate(payload) {
    if (busy || !identity) return;
    if (dirty && !('effective' in payload)) { feedback.textContent = 'Salve a efetivação que está editando antes de alterar outro item.'; return; }
    const context = identity, lottery = kind;
    busy = true; root.setAttribute('aria-busy', 'true');
    try {
        await updateManagedGame(lottery, payload);
        if (identity !== context || kind !== lottery) return;
        dirty = false; await load(); feedback.textContent = payload.deleted ? 'Jogo excluído.' : 'Jogo atualizado.';
    } catch (error) { if (identity === context && kind === lottery) feedback.textContent = error.message; }
    finally { busy = false; root.removeAttribute('aria-busy'); schedule(); }
}
function renderGame(item) {
    const article = node('article', undefined, 'history-game');
    article.dataset.status = item.check.status;
    const head = node('div', undefined, 'history-game-head');
    const title = node('strong', `Jogo ${item.index + 1} · ${item.date.split('-').reverse().join('/')}`);
    const favorite = button(item.favorite ? '★' : '☆', () => mutate({ filename: item.filename, index: item.index, favorite: !item.favorite }));
    favorite.className = 'history-favorite'; favorite.setAttribute('aria-pressed', String(item.favorite));
    favorite.setAttribute('aria-label', item.favorite ? 'Remover dos favoritos' : 'Adicionar aos favoritos'); favorite.title = favorite.getAttribute('aria-label');
    head.append(title, favorite); article.append(head);
    const balls = node('div', undefined, 'history-balls');
    item.game.forEach((value, position) => {
        if (kind === 'maismilionaria' && position >= 6) { balls.append(node('span', `Trevo ${value}`, 'trevo-badge')); return; }
        const number = typeof value === 'number';
        const ball = node('span', number ? String(value).padStart(2, '0') : `Mês da Sorte: ${value}`, number ? 'number-ball' : 'game-extra-badge');
        if (number) ball.style.backgroundColor = lotteryColors[kind].ball;
        balls.append(ball);
    }); article.append(balls);
    const check = node('p', item.check.label, 'history-check-result'); article.append(check);
    if (item.check.hits !== undefined) {
        if (item.check.trevo_hits !== undefined) article.append(node('p', `${item.check.trevo_hits} trevos corretos · Sorteados: ${item.check.drawn_trevos.join(' · ')}`));
        article.append(node('p', `Concurso ${item.contest} · ${item.check.drawn_at} · ${item.check.hits} acertos numéricos${item.check.month_hit === true ? ' + Mês da Sorte' : ''}`));
        if (item.check.partial) article.append(node('p', 'O Mês da Sorte ainda não está disponível na base.'));
    } else if (item.contest) article.append(node('p', `Concurso informado: ${item.contest}`));
    const edit = node('form', undefined, 'history-effective-form');
    const markLabel = node('label', undefined, 'history-check'), mark = document.createElement('input'); mark.type = 'checkbox'; mark.checked = item.effective;
    markLabel.append(mark, document.createTextNode('Efetivado'));
    const contestLabel = node('label', 'Concurso do bilhete'), contest = document.createElement('input');
    contest.type = 'number'; contest.min = '1'; contest.max = '99999999'; contest.value = item.contest || ''; contest.inputMode = 'numeric';
    contestLabel.append(contest);
    const save = node('button', 'Salvar efetivação'); save.type = 'submit';
    const remove = button('Excluir jogo', () => {
        if (confirm('Excluir somente este jogo? Os outros jogos do lote serão preservados.')) mutate({ filename: item.filename, index: item.index, deleted: true });
    });
    const changed = () => {
        dirty = true;
        root.querySelectorAll('.history-effective-form').forEach(other => other.querySelectorAll('input,button').forEach(control => { control.disabled = other !== edit; }));
    };
    const cancel = button('Cancelar edição', () => {
        mark.checked = item.effective; contest.value = item.contest || ''; contest.required = mark.checked; dirty = false;
        root.querySelectorAll('.history-effective-form input,.history-effective-form button').forEach(control => { control.disabled = false; });
        feedback.textContent = 'Edição cancelada.'; schedule();
    });
    mark.addEventListener('change', () => { contest.required = mark.checked; changed(); });
    contest.addEventListener('input', changed); contest.required = mark.checked;
    edit.append(markLabel, contestLabel, save, remove, cancel);
    edit.addEventListener('submit', event => { event.preventDefault(); mutate({ filename: item.filename, index: item.index, effective: mark.checked, contest: mark.checked ? Number(contest.value) : null }); });
    article.append(edit); return article;
}
async function load(automatic = false) {
    if (!visible() || automatic && (dirty || root.contains(document.activeElement))) { schedule(); return; }
    pending?.abort(); const controller = new AbortController(); pending = controller;
    const timeout = setTimeout(() => controller.abort(), 20000);
    const context = identity, lottery = kind;
    if (!automatic) feedback.textContent = 'Carregando seus jogos...';
    try {
        const data = await getManagedHistory(lottery, { ...filters, page: String(page) }, controller.signal);
        if (pending !== controller || identity !== context || kind !== lottery || !visible() || dirty) return;
        pages = data.pages;
        if (page > pages) { page = pages; pending = null; return load(automatic); }
        const s = data.summary;
        const count = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
        el('history-summary').textContent = `${count(s.total, 'jogo')} · ${count(s.effective, 'efetivado')} · ${count(s.favorites, 'favorito')} · ${count(s.checked, 'conferido')} · ${s.prizes} com faixa de prêmio`;
        list.replaceChildren(...data.items.map(renderGame));
        if (!data.items.length) list.append(node('p', 'Nenhum jogo encontrado com estes filtros.'));
        feedback.textContent = data.truncated ? 'Exibindo os lotes mais recentes dentro do limite de consulta.' : `${data.matched} ${data.matched === 1 ? 'jogo encontrado' : 'jogos encontrados'}.`;
        el('history-source').textContent = `Base: ${data.source.latest_contest ? `até o concurso ${data.source.latest_contest}` : 'indisponível'} · conferência atualizada às ${new Date(data.source.checked_at).toLocaleTimeString('pt-BR')} · atualização automática enquanto este painel estiver aberto.`;
        el('history-page').textContent = `Página ${page} de ${pages}`;
        el('history-prev').disabled = page <= 1; el('history-next').disabled = page >= pages;
        dirty = false;
    } catch (error) { if (pending === controller) feedback.textContent = controller.signal.aborted ? 'A consulta demorou demais. Tente atualizar novamente.' : error.message; }
    finally { clearTimeout(timeout); if (pending === controller) pending = null; schedule(); }
}
form.addEventListener('submit', event => {
    event.preventDefault(); if (dirty) { feedback.textContent = 'Salve ou cancele a edição antes de filtrar.'; return; }
    filters = Object.fromEntries(new FormData(form)); page = 1; load();
});
el('history-reset').addEventListener('click', () => { if (dirty) { feedback.textContent = 'Salve ou cancele a edição antes de limpar os filtros.'; return; } form.reset(); filters = {}; page = 1; load(); });
el('history-refresh').addEventListener('click', () => { if (dirty) feedback.textContent = 'Salve a efetivação que está editando antes de atualizar.'; else load(); });
el('history-prev').addEventListener('click', () => { if (dirty) { feedback.textContent = 'Salve ou cancele a edição antes de trocar de página.'; return; } if (page > 1) { page--; load(); } });
el('history-next').addEventListener('click', () => { if (dirty) { feedback.textContent = 'Salve ou cancele a edição antes de trocar de página.'; return; } if (page < pages) { page++; load(); } });
el('history-clear-own').addEventListener('click', async () => {
    if (busy || !confirm(`Apagar todos os seus jogos de ${formatLotteryName(kind)}, incluindo favoritos e efetivados? Esta ação não pode ser desfeita.`)) return;
    const context = identity, lottery = kind; busy = true;
    try { await clearManagedHistory(lottery); if (context === identity && lottery === kind) { dirty = false; page = 1; await load(); } }
    catch (error) { if (context === identity && lottery === kind) feedback.textContent = error.message; }
    finally { busy = false; schedule(); }
});
new MutationObserver(() => {
    if (!visible()) { pending?.abort(); pending = null; clearTimeout(timer); }
}).observe(overlay, { attributes: true, attributeFilter: ['class'] });
document.addEventListener('visibilitychange', () => { if (visible() && !dirty && !busy) load(true); else clearTimeout(timer); });
overlay.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); el('history-modal-close-btn').click(); }
    if (event.key !== 'Tab') return;
    const controls = [...overlay.querySelectorAll('button,input,select,a')].filter(n => !n.disabled && n.getClientRects().length);
    const first = controls[0], last = controls.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
});
