import { lotteryColors } from './dom.js';

const dateFormat = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', timeZone: 'America/Sao_Paulo' });
const checkedFormat = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', timeZone: 'America/Sao_Paulo' });

function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text) element.textContent = text;
    if (className) element.className = className;
    return element;
}

function paintCalendar(target, data) {
    target.replaceChildren();
    for (const day of data.days) {
        const row = node('div', '', `draw-calendar-day${day.today ? ' is-today' : ''}`);
        if (day.today) row.setAttribute('aria-current', 'date');
        const info = node('div', '', 'draw-calendar-day-info');
        info.append(node('span', day.label.slice(0, 3), 'draw-calendar-day-short'),
            node('span', `${dateFormat.format(new Date(`${day.date}T12:00:00-03:00`))}${day.today ? ' · Hoje' : ''}`, 'draw-calendar-day-label'));
        const lotteries = node('div', '', 'draw-calendar-lotteries');
        if (!day.available) {
            lotteries.append(node('span', 'A confirmar', 'draw-calendar-empty'));
        } else if (!day.draws.length) {
            lotteries.append(node('span', day.confirmed ? 'Sem sorteios previstos' : 'Agenda desatualizada', 'draw-calendar-empty'));
        } else {
            for (const draw of day.draws) {
                const pill = node('span', draw.name, 'draw-calendar-pill');
                pill.append(node('span', `, concurso ${draw.contest}`, 'calendar-screen-reader'));
                pill.dataset.lottery = draw.lottery;
                const colors = lotteryColors[draw.lottery];
                if (colors) {
                    pill.style.setProperty('--lottery-primary', colors.primary);
                    pill.style.setProperty('--lottery-secondary', colors.secondary);
                }
                pill.title = `${draw.name}, concurso ${draw.contest}${day.confirmed ? '' : ' — informação ainda não reconfirmada'}`;
                lotteries.append(pill);
            }
        }
        row.append(info, lotteries);
        target.append(row);
    }
    const status = document.getElementById('draw-calendar-status');
    const checked = data.checked_at ? checkedFormat.format(new Date(data.checked_at)) : '';
    status.textContent = data.status === 'loading' ? 'Consultando o cronograma oficial da CAIXA...'
        : data.status === 'current'
        ? `Cronograma CAIXA · consultado em ${checked}. Horário de Brasília.`
        : `Agenda não confirmada agora.${checked ? ` Última consulta: ${checked}.` : ''} Confira a fonte oficial.`;
    status.classList.toggle('calendar-warning', !['current', 'loading'].includes(data.status));
    const tips = document.getElementById('daily-tips-content');
    tips.replaceChildren();
    document.getElementById('daily-tips-date').textContent = dateFormat.format(new Date(`${data.today}T12:00:00-03:00`));
    for (const tip of data.tips) {
        const item = node('div', '', 'daily-tip');
        item.append(node('h3', tip.title), node('p', tip.text));
        tips.append(item);
    }
}

export function renderDrawCalendar(target) {
    if (!target) return;
    let pending = false;
    let lastRefresh = 0;
    let displayedDay = '';
    const refresh = document.getElementById('draw-calendar-refresh');
    async function load(force = false) {
        const day = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Sao_Paulo' }).format(new Date());
        if (pending || (!force && day === displayedDay && Date.now() - lastRefresh < 15 * 60 * 1000)) return;
        pending = true;
        refresh.disabled = true;
        target.setAttribute('aria-busy', 'true');
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 28000);
        try {
            const response = await fetch('/draw_calendar', { cache: 'no-store', signal: controller.signal });
            if (!response.ok) throw new Error('Agenda indisponível');
            const data = await response.json();
            paintCalendar(target, data);
            displayedDay = day;
            lastRefresh = Date.now();
            if (data.status === 'loading') {
                setTimeout(() => { if (!document.hidden) load(true); }, 5000);
            }
        } catch {
            const status = document.getElementById('draw-calendar-status');
            status.textContent = 'Não foi possível atualizar a agenda. Confira o cronograma oficial.';
            status.classList.add('calendar-warning');
            if (!target.children.length) target.textContent = 'Agenda temporariamente indisponível.';
            const tips = document.getElementById('daily-tips-content');
            if (!tips.children.length) tips.textContent = 'Jogue por diversão, respeite seu orçamento e lembre: não há estratégia que garanta prêmio.';
        } finally {
            clearTimeout(timeout);
            pending = false;
            refresh.disabled = false;
            target.setAttribute('aria-busy', 'false');
        }
    }
    refresh.addEventListener('click', () => load(true));
    // Detects the date change in Brazil, including tabs left open overnight.
    setInterval(() => { if (!document.hidden) load(); }, 60000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
    load();
}
