import {
    clearHistory,
    clearSavedAdminToken,
    deleteHistoryFile,
    generateGames,
    getAdminStatus,
    getHistoryFileContent,
    getHotColdNumbers,
    getSavedAdminToken,
    listHistoryFiles,
    setSavedAdminToken,
} from './api.js';
import { elements, selectedLotteryType, state } from './dom.js';
import { initPreferences, updateDynamicElementColors } from './preferences.js';
import {
    createHistoryFileRow,
    displayGamesAsBalls,
    displayNumberBalls,
    formatHistoryFilename,
    formatLotteryName,
} from './render.js';
import {
    clearAllDisplays,
    closeModal,
    hideLoading,
    openModal,
    setActionButtonsDisabled,
    showCustomConfirmModal,
    showError,
    showLoading,
    showSuccessMessageModal,
} from './ui.js';

let adminTokenRequired = false;


function validateNumGames() {
    const numGames = Number.parseInt(elements.numGamesInput.value, 10);

    if (Number.isNaN(numGames) || numGames < 1 || numGames > 100) {
        showError('Por favor, insira uma quantidade de jogos entre 1 e 100.');
        return null;
    }

    return numGames;
}


async function loadAdminStatus() {
    try {
        const data = await getAdminStatus();
        adminTokenRequired = Boolean(data.admin_token_required);
    } catch (error) {
        adminTokenRequired = true;
        console.error('Erro ao verificar protecao admin:', error);
    }
}


function ensureAdminToken() {
    if (!adminTokenRequired) {
        return true;
    }

    if (getSavedAdminToken()) {
        return true;
    }

    const token = window.prompt('Digite o token admin para continuar:');

    if (!token) {
        showError('Ação cancelada. Token admin não informado.');
        return false;
    }

    setSavedAdminToken(token.trim());
    return true;
}


function handleAdminError(error) {
    if (error.status === 401) {
        clearSavedAdminToken();
        showError('Token admin inválido ou ausente. Tente novamente.');
        return true;
    }

    return false;
}


async function handleGenerateGames() {
    clearAllDisplays();

    const lotteryType = selectedLotteryType();
    const numGames = validateNumGames();

    if (numGames === null) {
        return;
    }

    showLoading('Gerando jogos...');
    setActionButtonsDisabled(true);

    try {
        const jogos = await generateGames(lotteryType, String(numGames));
        state.currentGeneratedGames = jogos;

        displayGamesAsBalls(jogos, elements.jogosGeradosModalDisplay, lotteryType);
        openModal(elements.generatedGamesModalOverlay);
        elements.copyGamesButtonModal.classList.remove('hidden');
        elements.generatedGamesModalCloseBtn.focus();

        showSuccessMessageModal(`Foram gerados ${jogos.length} jogos para ${formatLotteryName(lotteryType)}.`);
    } catch (error) {
        showError(`Erro: ${error.message}`);
        console.error('Erro ao buscar jogos:', error);
    } finally {
        hideLoading();
        setActionButtonsDisabled(false);
    }
}


function copyWithFallback(text) {
    const tempTextArea = document.createElement('textarea');
    tempTextArea.value = text;
    document.body.appendChild(tempTextArea);
    tempTextArea.select();

    const successful = document.execCommand('copy');
    document.body.removeChild(tempTextArea);

    if (!successful) {
        throw new Error('Falha ao copiar jogos. Por favor, copie manualmente.');
    }
}


async function handleCopyGames() {
    if (state.currentGeneratedGames.length === 0) {
        showError('Nenhum jogo para copiar.');
        return;
    }

    const formattedGames = state.currentGeneratedGames
        .map(game => game.join(' '))
        .join('\n');

    try {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(formattedGames);
        } else {
            copyWithFallback(formattedGames);
        }

        showSuccessMessageModal('Jogos copiados para a area de transferencia!');
    } catch (error) {
        showError(error.message || 'Falha ao copiar jogos. Por favor, copie manualmente.');
        console.error('Erro ao copiar:', error);
    }
}


async function fetchFilesAndDisplayHistory(lotteryType, options = {}) {
    const { reset = true } = options;

    if (reset) {
        clearAllDisplays();
        openModal(elements.historyModalOverlay);
        elements.historyModalCloseBtn.focus();
    }

    showLoading('Carregando historico...');
    elements.historicoArquivosContainer.classList.remove('hidden');
    elements.historicoConteudoContainer.classList.add('hidden');
    setActionButtonsDisabled(true);

    try {
        const data = await listHistoryFiles(lotteryType);
        elements.historicoArquivosLista.innerHTML = '';
        elements.historicoArquivosLista.classList.remove('text-gray-500');

        if (data.files && data.files.length > 0) {
            data.files.forEach(filename => {
                const row = createHistoryFileRow(
                    filename,
                    () => loadHistoricalFile(filename, lotteryType),
                    () => showCustomConfirmModal(
                        'Confirmar Exclusao',
                        `Tem certeza que deseja apagar o arquivo "${filename}"? Esta acao e irreversivel!`,
                        () => confirmDeleteFileAction(filename, lotteryType)
                    )
                );

                elements.historicoArquivosLista.appendChild(row);
            });
        } else {
            elements.historicoArquivosLista.textContent = 'Nenhum arquivo de historico encontrado para esta loteria.';
            elements.historicoArquivosLista.classList.add('text-gray-500');
        }

        elements.historicoArquivosLista.style.backgroundColor = 'var(--bg-primary)';
        elements.historicoArquivosLista.style.borderColor = 'var(--border-color)';
        updateDynamicElementColors();
    } catch (error) {
        showError(`Erro: ${error.message}`);
        console.error('Erro ao listar arquivos de historico:', error);
        closeModal(elements.historyModalOverlay);
    } finally {
        hideLoading();
        setActionButtonsDisabled(false);
    }
}


async function confirmDeleteFileAction(filename, lotteryType) {
    if (!ensureAdminToken()) {
        return;
    }

    showLoading(`Apagando ${filename}...`);
    setActionButtonsDisabled(true);

    try {
        const data = await deleteHistoryFile(filename);
        await fetchFilesAndDisplayHistory(lotteryType, { reset: false });
        showSuccessMessageModal(data.message);
    } catch (error) {
        if (handleAdminError(error)) {
            return;
        }

        showError(`Erro: ${error.message}`);
        console.error(`Erro ao apagar o arquivo ${filename}:`, error);
    } finally {
        hideLoading();
        setActionButtonsDisabled(false);
    }
}


async function loadHistoricalFile(filename, lotteryType) {
    elements.historicoArquivosContainer.classList.add('hidden');
    elements.historicoConteudoContainer.classList.remove('hidden');

    showLoading(`Carregando ${filename}...`);
    setActionButtonsDisabled(true);

    try {
        const data = await getHistoryFileContent(filename);
        elements.currentFilenameSpan.textContent = (
            `Historico de ${formatLotteryName(lotteryType)} - ${formatHistoryFilename(filename)}`
        );

        displayGamesAsBalls(data.content, elements.historicoConteudoJogosWrapper, lotteryType);
        elements.historicoConteudoJogosWrapper.style.backgroundColor = 'var(--bg-primary)';
        elements.historicoConteudoJogosWrapper.style.borderColor = 'var(--border-color)';
    } catch (error) {
        showError(`Erro: ${error.message}`);
        console.error(`Erro ao carregar o arquivo ${filename}:`, error);
        elements.historicoArquivosContainer.classList.remove('hidden');
        elements.historicoConteudoContainer.classList.add('hidden');
    } finally {
        hideLoading();
        setActionButtonsDisabled(false);
    }
}


async function fetchHotColdNumbers(lotteryType) {
    showLoading('Obtendo numeros de assistencia...');

    try {
        const data = await getHotColdNumbers(lotteryType);
        displayNumberBalls(data.hot_numbers, elements.hotNumbersList, 'hot');
        displayNumberBalls(data.cold_numbers, elements.coldNumbersList, 'cold');
        updateDynamicElementColors();
    } catch (error) {
        showError(`Erro: ${error.message}`);
        console.error('Erro ao obter assistencia:', error);
        closeModal(elements.assistenciaModalOverlay);
    } finally {
        hideLoading();
    }
}


async function handleAssistance() {
    clearAllDisplays();

    const lotteryType = selectedLotteryType();

    openModal(elements.assistenciaModalOverlay);
    elements.assistenciaModalCloseBtn.focus();
    setActionButtonsDisabled(true);

    try {
        await fetchHotColdNumbers(lotteryType);
    } finally {
        setActionButtonsDisabled(false);
    }
}


function confirmClearHistory(lotteryType) {
    showCustomConfirmModal(
        'Limpar Historico',
        `Tem certeza que deseja DELETAR TODOS os arquivos de historico para ${formatLotteryName(lotteryType)}? Esta acao e irreversivel!`,
        async () => {
            if (!ensureAdminToken()) {
                return;
            }

            showLoading(`Limpando historico para ${formatLotteryName(lotteryType)}...`);
            setActionButtonsDisabled(true);

            try {
                const data = await clearHistory(lotteryType);
                await fetchFilesAndDisplayHistory(lotteryType);
                showSuccessMessageModal(data.message);
            } catch (error) {
                if (handleAdminError(error)) {
                    return;
                }

                showError(`Erro: ${error.message}`);
                console.error('Erro ao limpar historico:', error);
            } finally {
                hideLoading();
                setActionButtonsDisabled(false);
            }
        }
    );
}


function handleFontChanged() {
    const lotteryType = selectedLotteryType();

    if (!elements.generatedGamesModalOverlay.classList.contains('hidden') && state.currentGeneratedGames.length > 0) {
        displayGamesAsBalls(state.currentGeneratedGames, elements.jogosGeradosModalDisplay, lotteryType);
    }

    if (!elements.assistenciaModalOverlay.classList.contains('hidden')) {
        fetchHotColdNumbers(lotteryType);
    }
}


function bindEvents() {
    elements.gerarJogosButton.addEventListener('click', handleGenerateGames);
    elements.visualizarHistoricoButton.addEventListener('click', () => {
        fetchFilesAndDisplayHistory(selectedLotteryType());
    });
    elements.assistenciaBtn.addEventListener('click', handleAssistance);
    elements.limparHistoricoBtn.addEventListener('click', () => {
        confirmClearHistory(selectedLotteryType());
    });
    elements.limparHistoricoDiretoBtn.addEventListener('click', () => {
        closeModal(elements.historyModalOverlay);
        confirmClearHistory(selectedLotteryType());
    });

    elements.copyGamesButtonModal.addEventListener('click', handleCopyGames);
    elements.generatedGamesModalCloseBtn.addEventListener('click', () => {
        closeModal(elements.generatedGamesModalOverlay);
        elements.gerarJogosButton.focus();
    });
    elements.historyModalCloseBtn.addEventListener('click', () => {
        closeModal(elements.historyModalOverlay);
        elements.visualizarHistoricoButton.focus();
    });
    elements.assistenciaModalCloseBtn.addEventListener('click', () => {
        closeModal(elements.assistenciaModalOverlay);
        elements.assistenciaBtn.focus();
    });
    elements.voltarHistoricoButton.addEventListener('click', () => {
        elements.historicoConteudoContainer.classList.add('hidden');
        elements.historicoArquivosContainer.classList.remove('hidden');

        requestAnimationFrame(() => {
            const firstFile = elements.historicoArquivosLista.querySelector('[data-filename]');

            if (firstFile) {
                firstFile.focus();
            } else {
                elements.historyModalCloseBtn.focus();
            }
        });
    });
}

function setFooterYear() {
    if (elements.footerYear) {
        elements.footerYear.textContent = String(new Date().getFullYear());
    }
}


setFooterYear();
bindEvents();
initPreferences({ onFontChanged: handleFontChanged });
loadAdminStatus();
