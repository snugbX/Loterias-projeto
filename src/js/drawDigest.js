const el = id => document.getElementById(id);
const panel = el('draw-digest-panel');
const content = el('draw-digest-content');
const status = el('draw-digest-status');
const tabs = el('digest-tabs');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const editions = [
    { kind: 'megasena', name: 'Mega-Sena', count: 6, maximum: 60, url: 'Mega-Sena' },
    { kind: 'lotofacil', name: 'Lotofácil', count: 15, maximum: 25, url: 'Lotofacil' },
    { kind: 'quina', name: 'Quina', count: 5, maximum: 80, url: 'Quina' },
    { kind: 'diadesorte', name: 'Dia de Sorte', count: 7, maximum: 31, url: 'Dia-de-Sorte' },
];
let pending = null, index = 0, pages = [], pageAnimation = null;
function node(tag, text, className) { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (className) n.className = className; return n; }
const number = n => Number(n).toLocaleString('pt-BR');
const dozen = n => String(n).padStart(2, '0');

function validDigest(digest, edition) {
    if (!digest || digest.lottery_type !== edition.kind || !Number.isInteger(digest.contest) || digest.contest < 1 || typeof digest.date !== 'string' || !/^\d{2}\/\d{2}\/\d{4}$/.test(digest.date)) return false;
    const balls = digest.numbers;
    if (!Array.isArray(balls) || balls.length !== edition.count || new Set(balls).size !== balls.length || balls.some(n => !Number.isInteger(n) || n < 1 || n > edition.maximum)) return false;
    if (digest.even !== balls.filter(n => n % 2 === 0).length || digest.odd !== balls.length - digest.even || digest.sum !== balls.reduce((a,b) => a+b,0)) return false;
    if (digest.repeated_numbers !== null && (!Array.isArray(digest.repeated_numbers) || new Set(digest.repeated_numbers).size !== digest.repeated_numbers.length || digest.repeated_numbers.some(n => !balls.includes(n)))) return false;
    const sorted = [...balls].sort((a,b) => a-b);
    if (digest.consecutive_pairs !== sorted.slice(1).filter((n,i) => n === sorted[i]+1).length) return false;
    const ranges = digest.ranges;
    return Array.isArray(ranges) && ranges.length > 0 && ranges.length <= 5 && ranges[0].from === 1 && ranges.at(-1).to === edition.maximum
        && ranges.every((r,i) => Number.isInteger(r.from) && Number.isInteger(r.to) && r.from <= r.to && r.from >= 1 && r.to <= edition.maximum
            && (i === 0 || r.from === ranges[i-1].to + 1) && r.count === balls.filter(n => n >= r.from && n <= r.to).length)
        && digest.coverage && digest.coverage.total_draws > 0
        && ['total_draws','missing_contests','skipped_rows'].every(key => Number.isInteger(digest.coverage[key]) && digest.coverage[key] >= 0);
}

function metric(label, value, detail) {
    const item = node('div'); item.append(node('dt', label), node('dd', value));
    if (detail) item.append(node('p', detail));
    return item;
}

function makePage(edition, result) {
    const article = node('article', undefined, 'digest-page');
    article.id = `digest-page-${edition.kind}`; article.dataset.lottery = edition.kind;
    article.setAttribute('role', 'tabpanel'); article.setAttribute('aria-labelledby', `digest-tab-${edition.kind}`);
    article.tabIndex = 0;
    const current = result?.status === 'current' && validDigest(result.digest, edition);
    article.dataset.state = current ? 'current' : 'pending';
    const header = node('header', undefined, 'digest-edition-heading');
    header.append(node('span', current ? `CONCURSO ${number(result.digest.contest)}` : 'EDIÇÃO EM PREPARAÇÃO', 'digest-issue'), node('h3', edition.name, 'digest-title'));
    article.append(header);
    if (!current) {
        const empty = node('div', undefined, 'digest-pending');
        empty.append(node('h4', 'O próximo retrato está sendo preparado.'), node('p', 'Aguardando um boletim correspondente à base atual. Dados antigos não aparecem aqui como atualizados.'));
        article.append(empty); return article;
    }
    const digest = result.digest;
    header.append(node('p', digest.date, 'digest-date'));
    const draw = node('div', undefined, 'digest-drawn-numbers'); draw.setAttribute('aria-label', 'Dezenas sorteadas');
    digest.numbers.forEach(value => draw.append(node('span', dozen(value), 'digest-ball')));
    article.append(draw);
    if (edition.kind === 'diadesorte') {
        const month = node('div', undefined, 'digest-month');
        month.append(node('span', 'Mês da Sorte'), node('strong', digest.month || 'Não informado na base')); article.append(month);
    }
    const story = node('div', undefined, 'digest-story');
    const parity = node('section', undefined, 'digest-parity');
    const ring = node('div', undefined, 'digest-parity-ring');
    ring.style.setProperty('--even-share', `${digest.even / digest.numbers.length * 100}%`);
    ring.setAttribute('role', 'img'); ring.setAttribute('aria-label', `${digest.even} pares e ${digest.odd} ímpares`);
    const center = node('span'); center.append(node('strong', String(digest.numbers.length)), node('small', 'dezenas')); ring.append(center);
    const legend = node('div', undefined, 'digest-parity-legend');
    legend.append(node('h4', 'O perfil do concurso'), node('p', `${digest.even} pares · ${digest.odd} ímpares`),
        node('span', digest.even === digest.odd ? 'Mesma quantidade de pares e ímpares.' : digest.even > digest.odd ? 'Mais pares nesta edição.' : 'Mais ímpares nesta edição.'));
    parity.append(ring, legend); story.append(parity);
    const stats = node('dl', undefined, 'digest-metrics');
    stats.append(metric('Soma das dezenas', number(digest.sum)),
        metric('Repetidas do anterior', digest.repeated_numbers === null ? '—' : String(digest.repeated_numbers.length), digest.repeated_numbers === null ? 'Comparação indisponível' : undefined),
        metric('Duplas consecutivas', String(digest.consecutive_pairs)));
    story.append(stats); article.append(story);
    const ranges = node('section', undefined, 'digest-ranges'); ranges.append(node('h4', 'Por onde as dezenas passaram'));
    const chart = node('div', undefined, 'digest-range-chart');
    digest.ranges.forEach(range => {
        const row = node('div', undefined, 'digest-range-row');
        const meter = document.createElement('meter'); meter.min = 0; meter.max = digest.numbers.length; meter.value = range.count;
        meter.setAttribute('aria-hidden', 'true');
        row.append(node('span', `${dozen(range.from)}–${dozen(range.to)}`), meter, node('strong', String(range.count))); chart.append(row);
    }); ranges.append(chart); article.append(ranges);
    const repeated = node('p', undefined, 'digest-repeated');
    repeated.textContent = digest.repeated_numbers === null ? 'O concurso anterior não está disponível para comparação.'
        : digest.repeated_numbers.length ? `Voltaram do concurso anterior: ${digest.repeated_numbers.map(dozen).join(' · ')}.` : 'Nenhuma dezena se repetiu em relação ao concurso anterior.';
    article.append(repeated);
    const source = node('details', undefined, 'digest-coverage'); source.append(node('summary', 'Sobre estes dados'));
    const coverage = digest.coverage;
    source.append(node('p', `${number(coverage.total_draws)} ${coverage.total_draws === 1 ? 'concurso válido' : 'concursos válidos'} no histórico de apoio · ${number(coverage.missing_contests)} ${coverage.missing_contests === 1 ? 'concurso ausente' : 'concursos ausentes'} na sequência · ${number(coverage.skipped_rows)} ${coverage.skipped_rows === 1 ? 'linha inválida ou duplicada excluída' : 'linhas inválidas ou duplicadas excluídas'}.`));
    const link = node('a', 'Consultar a modalidade na CAIXA'); link.href = `https://loterias.caixa.gov.br/Paginas/${edition.url}.aspx`; link.target = '_blank'; link.rel = 'noopener noreferrer'; source.append(link);
    article.append(source);
    return article;
}

function showPage(next, animate = true, moveFocus = false) {
    if (!pages.length) return;
    const previous = index; index = Math.max(0, Math.min(editions.length - 1, next));
    pageAnimation?.cancel(); pageAnimation = null;
    pages.forEach((page, position) => { page.hidden = position !== index; page.inert = position !== index; page.setAttribute('aria-hidden', String(position !== index)); });
    [...tabs.children].forEach((tab, position) => { tab.setAttribute('aria-selected', String(position === index)); tab.tabIndex = position === index ? 0 : -1; });
    el('digest-prev').disabled = index === 0; el('digest-next').disabled = index === editions.length - 1;
    el('digest-position').textContent = `${dozen(index + 1)} / ${dozen(editions.length)}`;
    el('digest-position').setAttribute('aria-label', `Edição ${index + 1} de ${editions.length}`);
    const current = pages[index].dataset.state === 'current';
    status.textContent = `${editions[index].name} · ${current ? 'boletim da base atual' : 'aguardando processamento'} · edição ${index + 1} de ${editions.length}.`;
    if (moveFocus) tabs.children[index].focus({ preventScroll: true });
    if (animate && previous !== index && !reduced.matches && typeof pages[index].animate === 'function') {
        pageAnimation = pages[index].animate([{ opacity: .15, transform: `translateX(${next > previous ? 14 : -14}px)` }, { opacity: 1, transform: 'none' }], { duration: 240, easing: 'cubic-bezier(.2,.7,.2,1)' });
    }
}

editions.forEach((edition, position) => {
    const tab = node('button'); tab.type = 'button'; tab.id = `digest-tab-${edition.kind}`;
    tab.setAttribute('role', 'tab'); tab.setAttribute('aria-controls', `digest-page-${edition.kind}`);
    tab.setAttribute('aria-selected', String(position === index)); tab.tabIndex = position === index ? 0 : -1;
    const swatch = node('span', undefined, 'digest-tab-swatch'); swatch.dataset.lottery = edition.kind; swatch.setAttribute('aria-hidden','true');
    tab.append(swatch, node('span', edition.name)); tab.addEventListener('click', () => showPage(position));
    tab.addEventListener('keydown', event => {
        if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? editions.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + editions.length) % editions.length;
        showPage(next, true, true);
    }); tabs.append(tab);
});
function turnPage(direction) {
    showPage(index + direction);
    if (pages[index]) {
        pages[index].focus({ preventScroll: true });
        pages[index].scrollIntoView({ block: 'start', behavior: reduced.matches ? 'auto' : 'smooth' });
    }
}
el('digest-prev').addEventListener('click', () => turnPage(-1));
el('digest-next').addEventListener('click', () => turnPage(1));
el('digest-refresh').addEventListener('click', refreshDrawDigest);

export async function refreshDrawDigest() {
    if (!panel.open) return;
    pending?.abort(); const controller = new AbortController(); pending = controller;
    const timeout = setTimeout(() => controller.abort(), 10000);
    status.textContent = 'Carregando as edições da base atual...'; content.setAttribute('aria-busy', 'true');
    if (!pages.length) {
        [...tabs.children].forEach(tab => { tab.disabled = true; });
        el('digest-prev').disabled = true; el('digest-next').disabled = true;
    }
    try {
        const response = await fetch('/draw_digest', { cache: 'no-store', signal: controller.signal });
        if (!response.ok) throw new Error();
        const data = await response.json();
        if (pending !== controller || !panel.open) return;
        const focusedTab = [...tabs.children].includes(document.activeElement);
        pages = editions.map(edition => makePage(edition, data.digests?.[edition.kind]));
        content.replaceChildren(...pages); showPage(index, false, focusedTab);
    } catch {
        if (pending === controller && panel.open) {
            pages = editions.map(edition => makePage(edition, null)); content.replaceChildren(...pages); showPage(index, false);
            status.textContent = 'Não foi possível buscar os boletins. Use o botão Atualizar boletins para tentar novamente.';
        }
    } finally { clearTimeout(timeout); if (pending === controller) { pending = null; content.setAttribute('aria-busy', 'false'); [...tabs.children].forEach(tab => { tab.disabled = false; }); } }
}
export async function openDigestEdition(kind) {
    const selected = editions.findIndex(edition => edition.kind === kind);
    if (selected < 0) return false;
    index = selected; panel.open = true;
    await refreshDrawDigest();
    if (!panel.open || index !== selected) return false;
    tabs.children[index].focus({ preventScroll: true });
    panel.scrollIntoView({ block: 'start', behavior: reduced.matches ? 'auto' : 'smooth' });
    return true;
}
panel.addEventListener('toggle', () => {
    if (panel.open) { if (!pending) refreshDrawDigest(); } else { pending?.abort(); pending = null; pageAnimation?.cancel(); content.setAttribute('aria-busy', 'false'); }
});
reduced.addEventListener('change', () => { if (reduced.matches) pageAnimation?.cancel(); });
