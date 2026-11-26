import { state } from './dom.js';
import { openDigestEdition } from './drawDigest.js';

const grid = document.getElementById('latest-results-grid');
const refresh = document.getElementById('results-reload');
const feedback = document.getElementById('results-action-feedback');
let timer = null, busy = false;
const pagination = document.getElementById('results-pagination');
const previous = document.getElementById('results-prev');
const next = document.getElementById('results-next');
const pageSelect = document.getElementById('results-page-select');
const pageStrip = document.getElementById('results-page-strip');
const position = document.getElementById('results-position');
const mobile = matchMedia('(max-width: 600px)');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
let page = 0, pageSize = mobile.matches ? 1 : 2, pageAnimation = null;

function showPage(animate = false, focus = false) {
    const focusedPage = pageStrip.contains(document.activeElement) ? document.activeElement.closest('button')?.dataset.resultsPage : null;
    const cards = [...grid.querySelectorAll(':scope > .latest-result-card')];
    const pages = Math.max(1, Math.ceil(cards.length / pageSize));
    page = Math.max(0, Math.min(page, pages - 1));
    const start = page * pageSize;
    cards.forEach((card, index) => {
        const hidden = index < start || index >= start + pageSize;
        card.hidden = hidden;
        card.inert = hidden;
    });
    pagination.hidden = cards.length <= pageSize;
    previous.disabled = busy || page === 0;
    next.disabled = busy || page === pages - 1;
    pageSelect.disabled = busy;
    if (pageSelect.options.length !== pages) {
        pageSelect.replaceChildren(...Array.from({length: pages}, (_, index) => {
            const option = document.createElement('option');
            option.value = String(index); option.textContent = `Página ${index + 1} de ${pages}`;
            return option;
        }));
    }
    pageSelect.value = String(page);
    const firstPage = Math.max(0, Math.min(page - 1, pages - 3));
    pageStrip.replaceChildren(...Array.from({length: Math.min(3, pages)}, (_, offset) => {
        const index = firstPage + offset, group = cards.slice(index * pageSize, (index + 1) * pageSize);
        const button = document.createElement('button'); button.type = 'button';
        button.dataset.resultsPage = String(index); button.disabled = busy;
        button.setAttribute('aria-controls', 'latest-results-grid');
        button.setAttribute('aria-label', `Página ${index + 1}: ${group.map(card => card.querySelector('h3').textContent).join(' e ')}`);
        button.title = button.getAttribute('aria-label');
        if (index === page) button.setAttribute('aria-current', 'page');
        button.dataset.lottery = group[0]?.dataset.lottery || '';
        const number = document.createElement('strong'); number.textContent = String(index + 1).padStart(2, '0');
        const swatches = document.createElement('span'); swatches.className = 'results-page-swatches'; swatches.setAttribute('aria-hidden', 'true');
        group.forEach(card => {const swatch = document.createElement('i'); swatch.dataset.lottery = card.dataset.lottery; swatches.append(swatch);});
        button.append(number, swatches); return button;
    }));
    const visible = cards.slice(start, start + pageSize);
    const message = cards.length ? `${start + 1}–${Math.min(start + pageSize, cards.length)} de ${cards.length} loterias · ${visible.map(card => card.querySelector('h3').textContent).join(' / ')}` : '';
    if (position.textContent !== message) position.textContent = message;
    if (focus || grid.contains(document.activeElement) && document.activeElement.closest('[hidden]')) pageSelect.focus({preventScroll: true});
    else if (focusedPage != null) (pageStrip.querySelector(`[data-results-page="${focusedPage}"]`) || pageSelect).focus({preventScroll: true});
    pageAnimation?.cancel();
    if (animate && !reduced.matches && typeof grid.animate === 'function') pageAnimation = grid.animate([{opacity: .45}, {opacity: 1}], {duration: 180, easing: 'ease-out'});
}

function goToPage(value, focusNumber = false) {
    if (busy || value === page) return;
    page = value; showPage(true, !focusNumber);
    if (focusNumber) pageStrip.querySelector(`[data-results-page="${page}"]`)?.focus({preventScroll: true});
}

function announce(message) {
    clearTimeout(timer); feedback.textContent = message;
    timer = setTimeout(() => { feedback.textContent = ''; }, 6000);
}

export function initResultsBoard(reload) {
    grid.addEventListener('results:rendered', () => showPage());
    previous.addEventListener('click', () => goToPage(page - 1));
    next.addEventListener('click', () => goToPage(page + 1));
    pageStrip.addEventListener('click', event => {
        const button = event.target.closest('[data-results-page]');
        if (button && !button.disabled) goToPage(Number(button.dataset.resultsPage), true);
    });
    pageSelect.addEventListener('change', () => goToPage(Number(pageSelect.value)));
    pagination.addEventListener('keydown', event => {
        if (event.target.tagName !== 'BUTTON' || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const last = Math.max(0, Math.ceil(grid.children.length / pageSize) - 1);
        goToPage(event.key === 'Home' ? 0 : event.key === 'End' ? last : Math.max(0, Math.min(last, page + (event.key === 'ArrowRight' ? 1 : -1))), event.target.hasAttribute('data-results-page'));
    });
    mobile.addEventListener('change', () => {
        const first = page * pageSize;
        pageSize = mobile.matches ? 1 : 2;
        page = Math.floor(first / pageSize); showPage();
    });
    reduced.addEventListener('change', () => { if (reduced.matches) pageAnimation?.cancel(); });
    refresh.addEventListener('click', async () => {
        if (busy) return;
        busy = true; refresh.disabled = true; grid.setAttribute('aria-busy', 'true');
        showPage();
        clearTimeout(timer); feedback.textContent = 'Consultando os resultados disponíveis na base...';
        try {
            const available = await reload();
            announce(available ? 'Painel recarregado com os dados disponíveis na base.' : 'Não foi possível carregar os resultados. Tente novamente.');
        } catch { announce('Não foi possível recarregar o painel. Tente novamente.'); }
        finally { busy = false; refresh.disabled = false; grid.setAttribute('aria-busy', 'false'); showPage(); }
    });
    grid.addEventListener('click', async event => {
        const button = event.target.closest('[data-results-action]');
        if (!button || button.disabled || busy) return;
        const kind = button.dataset.resultsKind;
        const result = state.latestResults?.[kind];
        if (!result) return;
        if (button.dataset.resultsAction === 'digest') { await openDigestEdition(kind); return; }
        if (button.dataset.resultsAction !== 'copy') return;
        button.disabled = true;
        try {
            const extras = kind === 'diadesorte' ? `\nMês da Sorte: ${result.extras?.['Mês da Sorte'] || 'não informado na base'}`
                : kind === 'maismilionaria' ? `\nTrevos: ${result.extras?.['Trevo 1']} · ${result.extras?.['Trevo 2']}` : '';
            const text = `${result.name}\nConcurso ${result.contest} · ${result.date}\n${result.numbers.map(n => String(n).padStart(2,'0')).join(' · ')}${extras}\nResultado da base do app; confira os canais oficiais da CAIXA.`;
            await navigator.clipboard.writeText(text);
            announce(`Resultado de ${result.name} copiado.`);
        } catch { announce('Não foi possível copiar o resultado neste navegador.'); }
        finally { button.disabled = false; }
    });
}
