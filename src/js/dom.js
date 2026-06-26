export const elements = {
    gerarJogosButton: document.getElementById('gerar-jogos'),
    visualizarHistoricoButton: document.getElementById('visualizar-historico'),
    loadingMessage: document.getElementById('loading-message'),
    errorMessage: document.getElementById('error-message'),
    lotterySelect: document.getElementById('lottery-select'),
    numGamesInput: document.getElementById('num-games-input'),
    historicoArquivosContainer: document.getElementById('historico-arquivos-container-modal'),
    historicoArquivosLista: document.getElementById('historico-arquivos-lista-modal'),
    historicoConteudoContainer: document.getElementById('historico-conteudo-container-modal'),
    historicoConteudoJogosWrapper: document.getElementById('historico-conteudo-jogos-wrapper-modal'),
    currentFilenameSpan: document.getElementById('current-filename-modal'),
    voltarHistoricoButton: document.getElementById('voltar-historico-modal'),
    assistenciaBtn: document.getElementById('assistencia-btn'),
    hotNumbersList: document.getElementById('hot-numbers-list-modal'),
    coldNumbersList: document.getElementById('cold-numbers-list-modal'),
    limparHistoricoBtn: document.getElementById('limpar-historico-btn'),
    limparHistoricoDiretoBtn: document.getElementById('limpar-historico-direto-btn-modal'),
    customConfirmModal: document.getElementById('custom-confirm-modal'),
    modalTitle: document.getElementById('modal-title'),
    modalMessage: document.getElementById('modal-message'),
    modalConfirmBtn: document.getElementById('modal-confirm-btn'),
    modalCancelBtn: document.getElementById('modal-cancel-btn'),
    successModal: document.getElementById('success-modal'),
    successModalMessage: document.getElementById('success-modal-message'),
    themeToggle: document.getElementById('theme-toggle'),
    increaseFontButton: document.getElementById('increase-font'),
    decreaseFontButton: document.getElementById('decrease-font'),
    historyModalOverlay: document.getElementById('history-modal-overlay'),
    historyModalCloseBtn: document.getElementById('history-modal-close-btn'),
    generatedGamesModalOverlay: document.getElementById('generated-games-modal-overlay'),
    generatedGamesModalCloseBtn: document.getElementById('generated-games-modal-close-btn'),
    jogosGeradosModalDisplay: document.getElementById('jogos-gerados-modal-display'),
    copyGamesButtonModal: document.getElementById('copy-games-btn-modal'),
    assistenciaModalOverlay: document.getElementById('assistencia-modal-overlay'),
    assistenciaModalCloseBtn: document.getElementById('assistencia-modal-close-btn'),
    assistenciaModalTitle: document.getElementById('assistencia-modal-title'),
    mainTitle: document.getElementById('main-title'),
    latestResultsGrid: document.getElementById('latest-results-grid'),
    historyModalTitle: document.getElementById('history-modal-title'),
    generatedGamesModalTitle: document.getElementById('generated-games-modal-title'),
    jogosGeradosMainDisplay: document.getElementById('jogos-gerados-main-display'),
    footerYear: document.getElementById('footer-year'),
};

export const lotteryColors = {
    megasena: {
        primary: '#209869',
        secondary: '#8FCBB3',
    },
    lotofacil: {
        primary: '#930089',
        secondary: '#C87FC3',
    },
    quina: {
        primary: '#260085',
        secondary: '#927FC1',
    },
};

export const state = {
    currentGeneratedGames: [],
};

export function selectedLotteryType() {
    return elements.lotterySelect.value;
}

export function adjustableFontElements() {
    return [
        elements.mainTitle,
        elements.latestResultsGrid,
        elements.lotterySelect,
        elements.numGamesInput,
        ...Array.from(document.querySelectorAll('label')),
        elements.modalTitle,
        elements.modalMessage,
        elements.successModalMessage,
        elements.historyModalTitle,
        elements.historicoArquivosLista,
        elements.historicoConteudoJogosWrapper,
        elements.assistenciaModalTitle,
        elements.jogosGeradosModalDisplay,
        elements.generatedGamesModalTitle,
        elements.footerYear,
    ].filter(Boolean);
}
