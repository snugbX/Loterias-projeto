import { lotteryColors } from './dom.js';


const lotteryNames = {
    megasena: 'Mega Sena',
    lotofacil: 'Lotofácil',
    quina: 'Quina',
    diadesorte: 'Dia de Sorte',
};

const drawDays = [
    {
        dayIndex: 1,
        shortLabel: 'Seg',
        label: 'Segunda',
        lotteries: ['lotofacil', 'quina'],
    },
    {
        dayIndex: 2,
        shortLabel: 'Ter',
        label: 'Terça',
        lotteries: ['megasena', 'lotofacil', 'quina', 'diadesorte'],
    },
    {
        dayIndex: 3,
        shortLabel: 'Qua',
        label: 'Quarta',
        lotteries: ['lotofacil', 'quina'],
    },
    {
        dayIndex: 4,
        shortLabel: 'Qui',
        label: 'Quinta',
        lotteries: ['megasena', 'lotofacil', 'quina', 'diadesorte'],
    },
    {
        dayIndex: 5,
        shortLabel: 'Sex',
        label: 'Sexta',
        lotteries: ['lotofacil', 'quina'],
    },
    {
        dayIndex: 6,
        shortLabel: 'Sáb',
        label: 'Sábado',
        lotteries: ['megasena', 'lotofacil', 'quina', 'diadesorte'],
    },
    {
        dayIndex: 0,
        shortLabel: 'Dom',
        label: 'Domingo',
        lotteries: [],
    },
];


function createLotteryPill(lotteryType) {
    const colors = lotteryColors[lotteryType];
    const pill = document.createElement('span');

    pill.classList.add('draw-calendar-pill');
    pill.textContent = lotteryNames[lotteryType] || lotteryType;
    pill.style.borderColor = colors.primary;
    pill.style.color = colors.primary;
    pill.style.background = `${colors.secondary}33`;

    return pill;
}


export function renderDrawCalendar(targetElement) {
    if (!targetElement) {
        return;
    }

    const today = new Date().getDay();
    targetElement.innerHTML = '';

    drawDays.forEach(day => {
        const row = document.createElement('div');
        row.classList.add('draw-calendar-day');

        if (day.dayIndex === today) {
            row.classList.add('is-today');
        }

        const dayInfo = document.createElement('div');
        dayInfo.classList.add('draw-calendar-day-info');

        const shortLabel = document.createElement('span');
        shortLabel.classList.add('draw-calendar-day-short');
        shortLabel.textContent = day.shortLabel;

        const fullLabel = document.createElement('span');
        fullLabel.classList.add('draw-calendar-day-label');
        fullLabel.textContent = day.dayIndex === today ? `${day.label} • Hoje` : day.label;

        dayInfo.appendChild(shortLabel);
        dayInfo.appendChild(fullLabel);

        const lotteries = document.createElement('div');
        lotteries.classList.add('draw-calendar-lotteries');

        if (day.lotteries.length === 0) {
            const empty = document.createElement('span');
            empty.classList.add('draw-calendar-empty');
            empty.textContent = 'Sem sorteios';
            lotteries.appendChild(empty);
        } else {
            day.lotteries.forEach(lotteryType => {
                lotteries.appendChild(createLotteryPill(lotteryType));
            });
        }

        row.appendChild(dayInfo);
        row.appendChild(lotteries);
        targetElement.appendChild(row);
    });
}
