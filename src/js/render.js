import { lotteryColors } from './dom.js';


export function formatHistoryFilename(filename) {
    const match = filename.match(/_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})\.csv$/);

    if (!match) {
        return filename;
    }

    const date = match[1].replace(/-/g, '/');
    const time = match[2].replace(/-/g, ':');

    return `${date} ${time}`;
}


export function formatLotteryName(lotteryType) {
    const names = {
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

        jogo.forEach(value => {
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


export function displayLatestResults(results, targetElement) {
    const orderedLotteryTypes = ['megasena', 'lotofacil', 'quina', 'diadesorte'];
    targetElement.innerHTML = '';

    if (!results || Object.keys(results).length === 0) {
        targetElement.textContent = 'Últimos resultados indisponíveis.';
        targetElement.classList.add('text-gray-500');
        return;
    }

    targetElement.classList.remove('text-gray-500');

    orderedLotteryTypes.forEach(lotteryType => {
        const result = results[lotteryType];

        if (!result) {
            return;
        }

        const card = document.createElement('article');
        card.classList.add('latest-result-card');
        applyLotteryColorVars(card, lotteryType, {
            primary: result.color_primary,
            secondary: result.color_secondary,
        });
        card.style.borderColor = 'var(--lottery-border)';

        const header = document.createElement('div');
        header.classList.add('latest-result-card-header');

        const name = document.createElement('h3');
        name.textContent = result.name;
        name.style.color = 'var(--lottery-readable)';

        const meta = document.createElement('p');
        meta.textContent = `Concurso ${result.contest} • ${result.date}`;

        header.appendChild(name);
        header.appendChild(meta);

        const balls = document.createElement('div');
        balls.classList.add('latest-result-balls');

        result.numbers.forEach(number => {
            const ball = document.createElement('span');
            ball.classList.add('latest-result-ball');
            ball.textContent = String(number).padStart(2, '0');
            balls.appendChild(ball);
        });

        card.appendChild(header);
        card.appendChild(balls);

        if (result.extras) {
            const extras = document.createElement('div');
            extras.classList.add('latest-result-extras');

            Object.entries(result.extras).forEach(([label, value]) => {
                const extra = document.createElement('span');
                applyLotteryColorVars(extra, lotteryType, {
                    primary: result.color_primary,
                    secondary: result.color_secondary,
                });
                extra.textContent = `${label}: ${value}`;
                extras.appendChild(extra);
            });

            card.appendChild(extras);
        }

        targetElement.appendChild(card);
    });
}


export function displayDataStatus(status, targetElement, updatedAtElement) {
    const orderedLotteryTypes = ['megasena', 'lotofacil', 'quina', 'diadesorte'];
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
