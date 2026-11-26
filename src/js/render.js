import { lotteryColors } from './dom.js';


export function formatHistoryFilename(filename) {
    const match = filename.match(/_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})(?:_\d{6})?\.csv$/);

    if (!match) {
        return filename;
    }

    const date = match[1].replace(/-/g, '/');
    const time = match[2].replace(/-/g, ':');

    return `${date} ${time}`;
}


export function formatLotteryName(lotteryType) {
    const names = {
        maismilionaria: '+Milionária',
        megasena: 'Mega Sena',
        lotofacil: 'Lotofácil',
        quina: 'Quina',
        diadesorte: 'Dia de Sorte',
    };

    return names[lotteryType] || lotteryType;
}


function isNumericValue(value) {
    return Number.isFinite(Number(value));
}


function applyLotteryColorVars(element, lotteryType, fallback = {}) {
    const colors = lotteryColors[lotteryType] || {};

    element.dataset.lottery = lotteryType;
    element.style.setProperty('--lottery-primary', colors.primary || fallback.primary || '#209869');
    element.style.setProperty('--lottery-secondary', colors.secondary || fallback.secondary || '#8FCBB3');
    element.style.setProperty('--lottery-ball-bg', colors.ball || fallback.primary || '#047857');
}


function appendNumberBall(container, value, color) {
    const span = document.createElement('span');
    span.classList.add(
        'number-ball',
        'transition',
        'duration-200',
        'ease-in-out',
        'hover:scale-110',
        'hover:shadow-lg'
    );
    span.textContent = String(value).padStart(2, '0');
    span.style.backgroundColor = color;
    span.style.fontSize = getComputedStyle(document.body).getPropertyValue('--ball-font-size');
    container.appendChild(span);
}


function appendExtraBadge(container, value, lotteryType, color) {
    const badge = document.createElement('span');
    badge.classList.add('game-extra-badge');
    applyLotteryColorVars(badge, lotteryType, { primary: color });
    badge.textContent = `Mês da Sorte: ${value}`;
    container.appendChild(badge);
}


export function displayGamesAsBalls(games, targetContainer, lotteryType) {
    targetContainer.innerHTML = '';
    targetContainer.classList.remove('text-center', 'text-gray-500', 'py-4');

    if (!games || games.length === 0) {
        targetContainer.textContent = 'Nenhum jogo para exibir.';
        targetContainer.classList.add('text-center', 'text-gray-500', 'py-4');
        return;
    }

    const colors = lotteryColors[lotteryType];

    games.forEach((jogo, index) => {
        const jogoLineDiv = document.createElement('div');
        jogoLineDiv.classList.add(
            'flex',
            'flex-wrap',
            'justify-center',
            'items-center',
            'gap-2',
            'mb-2',
            'p-3',
            'rounded-md',
            'shadow-md',
            'animate-fadeInScale'
        );
        applyLotteryColorVars(jogoLineDiv, lotteryType);
        jogoLineDiv.style.background = 'linear-gradient(135deg, var(--lottery-soft-bg), var(--bg-secondary) 72%)';
        jogoLineDiv.style.animationDelay = `${index * 0.05}s`;

        jogo.forEach((value, position) => {
            if (lotteryType === 'maismilionaria' && position >= 6) {
                const badge = document.createElement('span'); badge.className = 'trevo-badge';
                badge.textContent = `Trevo ${value}`; jogoLineDiv.append(badge); return;
            }
            if (isNumericValue(value)) {
                appendNumberBall(jogoLineDiv, value, colors.ball || colors.primary);
            } else {
                appendExtraBadge(jogoLineDiv, value, lotteryType, colors.primary);
            }
        });

        targetContainer.appendChild(jogoLineDiv);
    });
}


export function displayNumberBalls(numbers, targetElement, typeClass) {
    targetElement.innerHTML = '';
    targetElement.classList.remove('text-gray-500');

    if (!numbers || numbers.length === 0) {
        targetElement.textContent = 'Nenhum número encontrado.';
        targetElement.classList.add('text-gray-500');
        return;
    }

    numbers.forEach(num => {
        const span = document.createElement('span');
        span.classList.add(
            'number-ball',
            typeClass,
            'transition',
            'duration-200',
            'ease-in-out',
            'hover:scale-110',
            'hover:shadow-lg'
        );
        span.textContent = String(num).padStart(2, '0');
        span.style.backgroundColor = typeClass === 'hot' ? '#B91C1C' : '#6B7280';
        span.style.fontSize = getComputedStyle(document.body).getPropertyValue('--ball-font-size');
        targetElement.appendChild(span);
    });
}


export function displayLatestResults(results, targetElement, status = null) {
    const orderedLotteryTypes = ['megasena', 'lotofacil', 'quina', 'diadesorte', 'maismilionaria'];
    const formats = { megasena: [6,60,6], lotofacil: [15,25,5], quina: [5,80,5], diadesorte: [7,31,7], maismilionaria: [6,50,6] };
    const previousFocus = targetElement.contains(document.activeElement) ? {
        kind: document.activeElement.dataset.resultsKind, action: document.activeElement.dataset.resultsAction,
    } : null;
    targetElement.innerHTML = '';
    targetElement.classList.remove('text-gray-500');
    orderedLotteryTypes.forEach(lotteryType => {
        const result = results?.[lotteryType];
        const [count, maximum, columns] = formats[lotteryType];
        const validTrevos = lotteryType !== 'maismilionaria' || (() => {
            const raw = [result?.extras?.['Trevo 1'], result?.extras?.['Trevo 2']];
            const valid = raw.every(n => (typeof n === 'number' || typeof n === 'string' && /^[1-6]$/.test(n))
                && Number.isInteger(Number(n)) && Number(n) >= 1 && Number(n) <= 6);
            return valid && new Set(raw.map(Number)).size === 2;
        })();
        const available = result && validTrevos && Number.isInteger(result.contest) && result.contest > 0
            && typeof result.date === 'string' && /^\d{2}\/\d{2}\/\d{4}$/.test(result.date)
            && Array.isArray(result.numbers) && result.numbers.length === count && new Set(result.numbers).size === count
            && result.numbers.every(n => Number.isInteger(n) && n >= 1 && n <= maximum);
        const card = document.createElement('article');
        card.classList.add('latest-result-card');
        applyLotteryColorVars(card, lotteryType, {
            primary: result?.color_primary,
            secondary: result?.color_secondary,
        });
        card.dataset.state = available ? 'available' : 'unavailable';
        const header = document.createElement('div');
        header.classList.add('latest-result-card-header');
        const identity = document.createElement('div'); identity.className = 'result-identity';
        const ticket = document.createElement('span'); ticket.className = 'lab-icon';
        ticket.style.setProperty('--icon', "url('icons/lucide/ticket.svg')"); ticket.setAttribute('aria-hidden','true');
        const name = document.createElement('h3');
        name.textContent = formatLotteryName(lotteryType); identity.append(ticket, name);
        header.append(identity);
        if (available) {
            const contest = document.createElement('div'); contest.className = 'result-contest';
            const label = document.createElement('span'); label.textContent = 'Concurso';
            const value = document.createElement('strong'); value.textContent = result.contest.toLocaleString('pt-BR');
            contest.append(label, value); header.append(contest);
        }
        card.append(header);
        if (!available) {
            const empty = document.createElement('p'); empty.className = 'result-unavailable';
            empty.textContent = 'Resultado indisponível nesta consulta.'; card.append(empty);
            targetElement.append(card); return;
        }
        const meta = document.createElement('div'); meta.className = 'result-draw-date';
        const drawnLabel = document.createElement('span'); drawnLabel.textContent = 'Sorteio';
        const drawnDate = document.createElement('time'); drawnDate.textContent = result.date;
        const [day, month, year] = result.date.split('/'); drawnDate.dateTime = `${year}-${month}-${day}`;
        meta.append(drawnLabel, drawnDate); card.append(meta);
        const balls = document.createElement('div');
        balls.classList.add('latest-result-balls');
        balls.setAttribute('aria-label', 'Dezenas sorteadas');
        balls.style.setProperty('--number-cols', String(columns));
        balls.style.maxWidth = `${columns*38+(columns-1)*6}px`;
        result.numbers.forEach(number => {
            const ball = document.createElement('span');
            ball.classList.add('latest-result-ball');
            ball.textContent = String(number).padStart(2, '0');
            balls.appendChild(ball);
        });
        card.append(balls);
        if (lotteryType === 'maismilionaria') {
            const trevos = document.createElement('div'); trevos.className = 'result-lucky-month';
            const label = document.createElement('span'); label.textContent = 'Trevos sorteados';
            const value = document.createElement('strong');
            value.textContent = [result.extras?.['Trevo 1'], result.extras?.['Trevo 2']].join(' · ');
            trevos.append(label, value); card.append(trevos);
        }
        if (lotteryType === 'diadesorte') {
            const extras = document.createElement('div'); extras.className = 'result-lucky-month';
            const label = document.createElement('span'); label.textContent = 'Mês da Sorte';
            const value = document.createElement('strong'); value.textContent = result.extras?.['Mês da Sorte'] || 'Não informado na base';
            extras.append(label, value); card.append(extras);
        }
        const statusItem = status?.[lotteryType];
        if (statusItem && (!statusItem.file_exists || statusItem.contest && Number(statusItem.contest) !== result.contest)) {
            card.dataset.state = 'outdated';
            const notice = document.createElement('p'); notice.className = 'result-state-note';
            notice.textContent = statusItem.file_exists ? 'A base mudou. Recarregue o painel para conferir a nova edição.' : 'A base está indisponível. Resultado recebido na última consulta.';
            card.append(notice);
        }
        const footer = document.createElement('div'); footer.className = 'result-ticket-footer';
        const countLabel = document.createElement('span'); countLabel.className = 'result-number-count'; countLabel.textContent = `${count} dezenas`;
        const actions = document.createElement('div'); actions.className = 'result-card-actions';
        for (const [action, icon, title, caption] of [
            ['digest', 'newspaper', `Ler o boletim de ${name.textContent}`, 'Boletim'],
            ['copy', 'copy', `Copiar resultado de ${name.textContent}`, null],
        ]) {
            const button = document.createElement('button'); button.type = 'button'; button.dataset.resultsAction = action; button.dataset.resultsKind = lotteryType;
            button.title = title; button.setAttribute('aria-label', title);
            const glyph = document.createElement('span'); glyph.className = 'lab-icon'; glyph.style.setProperty('--icon', `url('icons/lucide/${icon}.svg')`); glyph.setAttribute('aria-hidden','true'); button.append(glyph);
            if (caption) { const text = document.createElement('span'); text.textContent = caption; button.append(text); }
            actions.append(button);
        }
        footer.append(countLabel, actions); card.append(footer);
        if (statusItem) {
            const source = document.createElement('details'); source.className = 'result-data-record';
            const label = document.createElement('summary'); label.textContent = 'Registro na base';
            const details = document.createElement('p');
            details.textContent = statusItem.modified_at
                ? `Arquivo disponível: ${statusItem.file_exists ? 'sim' : 'não'}. Alteração registrada em ${String(statusItem.modified_at).replace('T',' ')}.`
                : 'Data de alteração da base não informada.';
            source.append(label, details); card.append(source);
        }
        targetElement.append(card);
    });
    if (previousFocus?.kind && previousFocus.action) targetElement.querySelector(`[data-results-kind="${previousFocus.kind}"][data-results-action="${previousFocus.action}"]`)?.focus({preventScroll:true});
}


export function displayDataStatus(status, targetElement, updatedAtElement) {
    const orderedLotteryTypes = ['megasena', 'lotofacil', 'quina', 'diadesorte', 'maismilionaria'];
    targetElement.innerHTML = '';

    if (!status || Object.keys(status).length === 0) {
        targetElement.textContent = 'Status dos dados indisponível.';
        targetElement.classList.add('text-gray-500');
        return;
    }

    targetElement.classList.remove('text-gray-500');

    orderedLotteryTypes.forEach(lotteryType => {
        const item = status[lotteryType];

        if (!item) {
            return;
        }

        const card = document.createElement('article');
        card.classList.add('data-status-card');
        applyLotteryColorVars(card, lotteryType, {
            primary: item.color_primary,
            secondary: item.color_secondary,
        });
        card.style.borderColor = item.file_exists ? 'var(--lottery-border)' : '#B91C1C';

        const title = document.createElement('h3');
        title.textContent = item.name;
        title.style.color = item.file_exists ? 'var(--lottery-readable)' : '#B91C1C';

        const contest = document.createElement('p');
        contest.classList.add('data-status-contest');
        contest.textContent = item.contest
            ? `Concurso ${item.contest}`
            : 'CSV não encontrado';

        const date = document.createElement('p');
        date.textContent = item.date ? `Sorteio: ${item.date}` : 'Sem data local';

        const fileInfo = document.createElement('p');
        fileInfo.classList.add('data-status-file');
        fileInfo.textContent = item.modified_at
            ? `Arquivo atualizado: ${new Date(item.modified_at).toLocaleString('pt-BR')}`
            : 'Arquivo ainda não carregado';

        card.appendChild(title);
        card.appendChild(contest);
        card.appendChild(date);
        card.appendChild(fileInfo);
        targetElement.appendChild(card);
    });

    if (updatedAtElement) {
        updatedAtElement.textContent = `Verificado em ${new Date().toLocaleString('pt-BR')}`;
    }
}


function iconButton(label, svgMarkup, onClick) {
    const button = document.createElement('button');
    button.type = 'button';
    button.classList.add('p-1', 'rounded-full', 'focus:outline-none', 'focus:ring-2', 'focus:ring-blue-500');
    button.setAttribute('aria-label', label);
    button.title = label;
    button.innerHTML = svgMarkup;
    button.addEventListener('click', event => {
        event.stopPropagation();
        onClick();
    });

    return button;
}


export function createHistoryFileRow(filename, onView, onDelete) {
    const fileDiv = document.createElement('div');
    fileDiv.classList.add(
        'p-2',
        'rounded-md',
        'transition',
        'text-sm',
        'truncate',
        'mb-2',
        'flex',
        'items-center',
        'justify-between'
    );
    fileDiv.style.backgroundColor = 'var(--border-color)';
    fileDiv.style.color = 'var(--text-secondary)';
    fileDiv.dataset.filename = filename;

    const textSpan = document.createElement('span');
    textSpan.textContent = formatHistoryFilename(filename);
    textSpan.classList.add('font-medium', 'flex-grow', 'text-left');
    textSpan.style.color = 'var(--text-primary)';

    const actionsDiv = document.createElement('div');
    actionsDiv.classList.add('flex', 'items-center', 'gap-2');

    const viewButton = iconButton(
        'Visualizar conteúdo',
        `<svg class="w-5 h-5 text-blue-500 hover:text-blue-700 transition" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
        </svg>`,
        onView
    );

    actionsDiv.appendChild(viewButton);

    if (onDelete) {
        const deleteButton = iconButton(
            'Apagar arquivo',
            `<svg class="w-5 h-5 text-red-500 hover:text-red-700 transition" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
            </svg>`,
            onDelete
        );

        actionsDiv.appendChild(deleteButton);
    }

    fileDiv.appendChild(textSpan);
    fileDiv.appendChild(actionsDiv);

    return fileDiv;
}
