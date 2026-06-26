import { adjustableFontElements, elements } from './dom.js';


const FONT_STEP = 1;
const MIN_FONT_SIZE = 12;
const MAX_FONT_SIZE = 24;


export function applyTheme(theme) {
    document.body.classList.toggle('dark-theme', theme === 'dark');
    localStorage.setItem('theme', theme);
    updateDynamicElementColors();
}


export function updateDynamicElementColors() {
    const mainContainer = document.querySelector('.container');

    if (mainContainer) {
        mainContainer.style.backgroundColor = 'var(--bg-secondary)';
        mainContainer.style.color = 'var(--text-primary)';
    }

    document.querySelectorAll('label').forEach(label => {
        label.style.color = 'var(--text-secondary)';
    });

    document.querySelectorAll('select, input[type="number"]').forEach(input => {
        input.style.borderColor = 'var(--border-color)';
        input.style.backgroundColor = 'var(--bg-secondary)';
        input.style.color = 'var(--text-secondary)';
    });

    document.querySelectorAll('.modal-overlay:not(.hidden) .modal-content').forEach(modalContent => {
        modalContent.style.backgroundColor = 'var(--bg-secondary)';
        modalContent.style.color = 'var(--text-primary)';

        const title = modalContent.querySelector('h3');
        if (title) {
            title.style.color = 'var(--text-primary)';
        }

        const paragraph = modalContent.querySelector('p');
        if (paragraph) {
            paragraph.style.color = 'var(--text-secondary)';
        }

        const cancelButton = modalContent.querySelector('.cancel-btn');
        if (cancelButton) {
            cancelButton.style.backgroundColor = 'var(--border-color)';
            cancelButton.style.color = 'var(--text-secondary)';
        }
    });

    if (!elements.historyModalOverlay.classList.contains('hidden')) {
        elements.historicoArquivosContainer.style.borderColor = 'var(--border-color)';
        elements.historicoArquivosContainer.querySelector('h2').style.color = 'var(--text-primary)';
        elements.historicoArquivosLista.style.backgroundColor = 'var(--bg-primary)';
        elements.historicoArquivosLista.style.borderColor = 'var(--border-color)';

        document.querySelectorAll('#historico-arquivos-lista-modal > div').forEach(fileDiv => {
            fileDiv.style.backgroundColor = 'var(--border-color)';
            fileDiv.style.color = 'var(--text-secondary)';
            fileDiv.querySelector('span').style.color = 'var(--text-primary)';
        });

        if (!elements.historicoConteudoContainer.classList.contains('hidden')) {
            elements.historicoConteudoContainer.style.borderColor = 'var(--border-color)';
            elements.historicoConteudoContainer.querySelector('h2').style.color = 'var(--text-primary)';
            elements.historicoConteudoJogosWrapper.style.backgroundColor = 'var(--bg-primary)';
            elements.historicoConteudoJogosWrapper.style.borderColor = 'var(--border-color)';
        }
    }

    if (!elements.assistenciaModalOverlay.classList.contains('hidden')) {
        document.getElementById('hot-numbers-display-modal').style.backgroundColor = 'var(--bg-secondary)';
        document.getElementById('hot-numbers-display-modal').style.borderColor = 'var(--border-color)';
        document.getElementById('cold-numbers-display-modal').style.backgroundColor = 'var(--bg-secondary)';
        document.getElementById('cold-numbers-display-modal').style.borderColor = 'var(--border-color)';
        document.querySelector('#hot-numbers-display-modal h3').style.color = 'var(--text-secondary)';
        document.querySelector('#cold-numbers-display-modal h3').style.color = 'var(--text-secondary)';
    }

    elements.mainTitle.style.color = 'var(--text-primary)';
    elements.loadingMessage.style.color = 'var(--text-secondary)';
    elements.errorMessage.style.color = 'var(--text-secondary)';
}


function adjustFontSize(direction, callbacks) {
    const currentBaseFontSize = parseFloat(
        getComputedStyle(document.documentElement).getPropertyValue('--base-font-size')
    );
    let newBaseFontSize = currentBaseFontSize;

    if (direction === 'increase') {
        newBaseFontSize = Math.min(currentBaseFontSize + FONT_STEP, MAX_FONT_SIZE);
    } else if (direction === 'decrease') {
        newBaseFontSize = Math.max(currentBaseFontSize - FONT_STEP, MIN_FONT_SIZE);
    }

    document.documentElement.style.setProperty('--base-font-size', `${newBaseFontSize}px`);
    document.documentElement.style.setProperty('--h1-font-size', `${(newBaseFontSize * 2.25 / 16)}rem`);
    document.documentElement.style.setProperty('--h2-font-size', `${(newBaseFontSize * 1.5 / 16)}rem`);
    document.documentElement.style.setProperty('--h3-font-size', `${(newBaseFontSize * 1.25 / 16)}rem`);
    document.documentElement.style.setProperty('--label-font-size', `${(newBaseFontSize * 0.875 / 16)}rem`);
    document.documentElement.style.setProperty('--ball-font-size', `${(newBaseFontSize / 16)}em`);
    document.documentElement.style.setProperty('--modal-title-size', `${(newBaseFontSize * 1.5 / 16)}em`);
    document.documentElement.style.setProperty('--modal-message-size', `${(newBaseFontSize * 1.1 / 16)}em`);

    localStorage.setItem('baseFontSize', newBaseFontSize);

    adjustableFontElements().forEach(element => {
        const style = getComputedStyle(document.documentElement);

        if (element.id === 'main-title') {
            element.style.fontSize = style.getPropertyValue('--h1-font-size');
        } else if (element === elements.lotterySelect || element === elements.numGamesInput) {
            element.style.fontSize = style.getPropertyValue('--base-font-size');
        } else if (element.tagName === 'LABEL') {
            element.style.fontSize = style.getPropertyValue('--label-font-size');
        } else if (
            element === elements.modalTitle ||
            element === elements.historyModalTitle ||
            element === elements.generatedGamesModalTitle ||
            element === elements.assistenciaModalTitle
        ) {
            element.style.fontSize = style.getPropertyValue('--modal-title-size');
        } else if (element === elements.modalMessage || element === elements.successModalMessage) {
            element.style.fontSize = style.getPropertyValue('--modal-message-size');
        } else {
            element.style.fontSize = style.getPropertyValue('--base-font-size');
        }
    });

    document.querySelectorAll('.number-ball').forEach(ball => {
        ball.style.fontSize = getComputedStyle(document.body).getPropertyValue('--ball-font-size');
    });

    callbacks?.onFontChanged?.();
}


function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    applyTheme(savedTheme);
}


function loadFontSize(callbacks) {
    const savedFontSize = parseFloat(localStorage.getItem('baseFontSize'));

    if (!Number.isNaN(savedFontSize)) {
        document.documentElement.style.setProperty('--base-font-size', `${savedFontSize}px`);
        adjustFontSize(null, callbacks);
        return;
    }

    document.documentElement.style.setProperty('--base-font-size', '16px');
    adjustFontSize('default', callbacks);
}


export function initPreferences(callbacks = {}) {
    elements.themeToggle.addEventListener('click', () => {
        const currentTheme = localStorage.getItem('theme') || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        applyTheme(newTheme);
    });

    elements.increaseFontButton.addEventListener('click', () => adjustFontSize('increase', callbacks));
    elements.decreaseFontButton.addEventListener('click', () => adjustFontSize('decrease', callbacks));

    loadTheme();
    loadFontSize(callbacks);
}
