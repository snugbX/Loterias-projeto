import {
    clearHistory,
    clearSavedAdminToken,
    deleteHistoryFile,
    enterAsGuest,
    generateGames,
    getAdminStatus,
    getAuthSession,
    getBillingPix,
    getDataStatus,
    getHistoryFileContent,
    getHotColdNumbers,
    getLatestResults,
    getSavedAdminToken,
    listAdminUsers,
    listHistoryFiles,
    loginAccount,
    logoutAccount,
    registerAccount,
    setSavedAdminToken,
    updateData,
    updateUserPlan,
} from './api.js';
import { elements, lotteryColors, lotteryDetails, selectedLotteryType, state } from './dom.js';
import { renderDrawCalendar } from './drawCalendar.js';
import { initPreferences, updateDynamicElementColors } from './preferences.js';
import {
    createHistoryFileRow,
    displayDataStatus,
    displayLatestResults,
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


function planLabel(user) {
    if (!user) {
        return 'Visitante';
    }

    if (user.is_guest) {
        return 'Visitante';
    }

    if (user.is_admin) {
        return 'Admin';
    }

    return user.is_premium ? 'Premium' : 'Gratuito';
}


function usageText(user) {
    const usage = user?.usage;

    if (!usage) {
        return 'Uso: carregando...';
    }

    if (usage.is_unlimited) {
        return `Uso hoje: ${usage.used_today} jogos gerados sem limite`;
    }

    return `Uso hoje: ${usage.used_today}/${usage.free_daily_limit} jogos`;
}


function renderAccountState(user) {
    state.currentUser = user || null;

    const hasAccess = Boolean(user);

    elements.authGate?.classList.toggle('hidden', hasAccess);
    elements.topNav?.classList.toggle('hidden', !hasAccess);
    elements.appShell?.classList.toggle('hidden', !hasAccess);
    elements.appFooter?.classList.toggle('hidden', !hasAccess);

    if (!elements.accountPanel) {
        return;
    }

    elements.accountPanel.classList.toggle('hidden', !hasAccess);
    elements.accountPlanBadge.textContent = planLabel(user);
    elements.accountPlanBadge.classList.toggle('is-premium', Boolean(user?.is_premium));
    elements.accountPlanBadge.classList.toggle('is-admin', Boolean(user?.is_admin));
    elements.accountPlanBadge.classList.toggle('is-guest', Boolean(user?.is_guest));

    if (!hasAccess) {
        elements.accountUserName.textContent = 'Visitante';
        elements.accountUserEmail.textContent = 'Acesso gratuito';
        elements.accountUsage.textContent = 'Uso: carregando...';
        elements.adminUsersButton.classList.add('hidden');
        elements.navLoginButton?.classList.add('hidden');
        elements.logoutButton?.classList.add('hidden');
        elements.premiumPixButton?.classList.add('hidden');
        elements.billingPixPanel?.classList.add('hidden');
        elements.adminUsersPanel?.classList.add('hidden');
        return;
    }

    const isGuest = Boolean(user.is_guest);
    elements.accountUserName.textContent = user.name || 'Visitante';
    elements.accountUserEmail.textContent = isGuest ? 'Versao gratuita sem cadastro' : user.email;
    elements.accountUsage.textContent = usageText(user);
    elements.adminUsersButton.classList.toggle('hidden', !user.is_admin);
    elements.navLoginButton?.classList.toggle('hidden', !isGuest);
    elements.logoutButton?.classList.toggle('hidden', isGuest);
    elements.premiumPixButton?.classList.toggle('hidden', isGuest);
}


async function refreshAuthSession() {
    try {
        const data = await getAuthSession();
        renderAccountState(data.user);
        adminTokenRequired = Boolean(data.admin_configured || adminTokenRequired);
    } catch (error) {
        renderAccountState(null);
        console.error('Erro ao carregar sessao:', error);
    }
}


async function handleLogin(event) {
    event.preventDefault();
    showLoading('Entrando...');
    setActionButtonsDisabled(true);

    try {
        const data = await loginAccount({
            email: elements.loginEmail.value,
            password: elements.loginPassword.value,
        });
        renderAccountState(data.user);
        elements.loginForm.reset();
        showSuccessMessageModal('Login realizado com sucesso.');
    } catch (error) {
        showError(`Erro: ${error.message}`);
    } finally {
        hideLoading();
        setActionButtonsDisabled(false);
    }
}


async function handleRegister(event) {
    event.preventDefault();
    showLoading('Criando conta...');
    setActionButtonsDisabled(true);

    try {
        const data = await registerAccount({
            name: elements.registerName.value,
            email: elements.registerEmail.value,
            password: elements.registerPassword.value,
            setupCode: elements.registerSetupCode.value,
        });
        renderAccountState(data.user);
        elements.registerForm.reset();
        showSuccessMessageModal('Conta criada com sucesso.');
    } catch (error) {
        showError(`Erro: ${error.message}`);
    } finally {
        hideLoading();
        setActionButtonsDisabled(false);
    }
}


async function handleGuestAccess() {
    showLoading('Liberando acesso visitante...');
    setActionButtonsDisabled(true);

    try {
        const data = await enterAsGuest();
        renderAccountState(data.user);
        showSuccessMessageModal('Acesso visitante liberado.');
    } catch (error) {
        showError(`Erro: ${error.message}`);
    } finally {
        hideLoading();
        setActionButtonsDisabled(false);
    }
}


async function handleReturnToLogin() {
    showLoading('Voltando para entrada...');
    setActionButtonsDisabled(true);

    try {
        if (state.currentUser?.is_guest) {
            await logoutAccount();
        }

        clearAllDisplays();
        renderAccountState(null);
        requestAnimationFrame(() => elements.loginEmail?.focus());
    } catch (error) {
        showError(`Erro: ${error.message}`);
    } finally {
        hideLoading();
        setActionButtonsDisabled(false);
    }
}


async function handleLogout() {
    showLoading('Saindo...');
    setActionButtonsDisabled(true);

    try {
        await logoutAccount();
        renderAccountState(null);
        showSuccessMessageModal('Voce saiu da conta.');
    } catch (error) {
        showError(`Erro: ${error.message}`);
    } finally {
        hideLoading();
        setActionButtonsDisabled(false);
    }
}


async function handleBillingPix() {
    elements.billingPixPanel.classList.toggle('hidden');

    if (elements.billingPixPanel.classList.contains('hidden')) {
        return;
    }

    elements.billingPixPanel.textContent = 'Carregando Pix...';

    try {
        const data = await getBillingPix();
        elements.billingPixPanel.innerHTML = '';

        const title = document.createElement('strong');
        title.textContent = data.enabled ? 'Chave Pix Premium' : 'Pix ainda nao configurado';

        const key = document.createElement('p');
        key.textContent = data.enabled
            ? data.pix_key
            : 'Configure a chave Pix no arquivo .env local.';

        const receiver = document.createElement('p');
        receiver.textContent = data.receiver_email
            ? `Responsavel: ${data.receiver_email}`
            : 'Responsavel nao configurado.';

        elements.billingPixPanel.appendChild(title);
        elements.billingPixPanel.appendChild(key);
        elements.billingPixPanel.appendChild(receiver);
    } catch (error) {
        elements.billingPixPanel.textContent = error.message;
    }
}


function createAdminUserRow(user) {
    const row = document.createElement('div');
    row.classList.add('admin-user-row');

    const info = document.createElement('div');
    const name = document.createElement('strong');
    name.textContent = user.name;

    const meta = document.createElement('span');
    meta.textContent = `${user.email} - ${planLabel(user)}`;

    info.appendChild(name);
    info.appendChild(meta);
    row.appendChild(info);

    if (user.is_admin) {
        const locked = document.createElement('span');
        locked.textContent = 'Admin';
        row.appendChild(locked);
        return row;
    }

    const select = document.createElement('select');
    select.setAttribute('aria-label', `Plano de ${user.name}`);
    ['free', 'premium'].forEach(plan => {
        const option = document.createElement('option');
        option.value = plan;
        option.textContent = plan === 'premium' ? 'Premium' : 'Gratuito';
        option.selected = user.plan === plan;
        select.appendChild(option);
    });
    select.addEventListener('change', async () => {
        try {
            await updateUserPlan(user.id, select.value);
            showSuccessMessageModal('Plano atualizado.');
            await handleAdminUsers({ forceOpen: true });
        } catch (error) {
            showError(`Erro: ${error.message}`);
        }
    });

    row.appendChild(select);
    return row;
}


async function handleAdminUsers(options = {}) {
    if (options.forceOpen) {
        elements.adminUsersPanel.classList.remove('hidden');
    } else {
        elements.adminUsersPanel.classList.toggle('hidden');
    }

    if (elements.adminUsersPanel.classList.contains('hidden')) {
        return;
    }

    elements.adminUsersPanel.textContent = 'Carregando usuarios...';

    try {
        const data = await listAdminUsers();
        elements.adminUsersPanel.innerHTML = '';

        if (!data.users || data.users.length === 0) {
            elements.adminUsersPanel.textContent = 'Nenhum usuario encontrado.';
            return;
        }

        data.users.forEach(user => {
            elements.adminUsersPanel.appendChild(createAdminUserRow(user));
        });
    } catch (error) {
        elements.adminUsersPanel.textContent = error.message;
    }
}


function getLotteryOptionButtons() {
    if (!elements.lotteryOptionGrid) {
        return [];
    }

    return Array.from(elements.lotteryOptionGrid.querySelectorAll('[data-lottery]'));
}


function setSelectedLottery(lotteryType) {
    const colors = lotteryColors[lotteryType];
    const details = lotteryDetails[lotteryType];

    if (!colors || !details) {
        return;
    }

    elements.lotterySelect.value = lotteryType;
    document.body.style.setProperty('--active-lottery-primary', colors.primary);
    document.body.style.setProperty('--active-lottery-secondary', colors.secondary);

    if (elements.selectedLotteryName) {
        elements.selectedLotteryName.textContent = details.name;
    }

    if (elements.selectedLotteryMeta) {
        elements.selectedLotteryMeta.textContent = details.summary;
    }

    if (elements.gerarJogosButton) {
        elements.gerarJogosButton.style.background = `linear-gradient(135deg, ${colors.primary}, ${details.accent})`;
        elements.gerarJogosButton.style.boxShadow = `0 10px 22px ${colors.secondary}66`;
    }

    getLotteryOptionButtons().forEach(button => {
        const selected = button.dataset.lottery === lotteryType;
        button.classList.toggle('is-selected', selected);
        button.setAttribute('aria-checked', String(selected));
        button.tabIndex = selected ? 0 : -1;
    });
}


function selectLotteryOption(button) {
    if (!button?.dataset?.lottery) {
        return;
    }

    setSelectedLottery(button.dataset.lottery);
}


function handleLotteryOptionKeydown(event) {
    const buttons = getLotteryOptionButtons();
    const currentIndex = buttons.indexOf(event.currentTarget);

    if (currentIndex === -1) {
        return;
    }

    const keyActions = {
        ArrowRight: 1,
        ArrowDown: 1,
        ArrowLeft: -1,
        ArrowUp: -1,
    };

    if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        selectLotteryOption(event.currentTarget);
        return;
    }

    let nextIndex = null;

    if (event.key in keyActions) {
        nextIndex = (currentIndex + keyActions[event.key] + buttons.length) % buttons.length;
    } else if (event.key === 'Home') {
        nextIndex = 0;
    } else if (event.key === 'End') {
        nextIndex = buttons.length - 1;
    }

    if (nextIndex === null) {
        return;
    }

    event.preventDefault();
    selectLotteryOption(buttons[nextIndex]);
    buttons[nextIndex].focus();
}


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


async function loadLatestResults() {
    if (!elements.latestResultsGrid) {
        return;
    }

    elements.latestResultsGrid.textContent = 'Carregando últimos resultados...';

    try {
        const data = await getLatestResults();
        displayLatestResults(data.results, elements.latestResultsGrid);
    } catch (error) {
        elements.latestResultsGrid.textContent = 'Últimos resultados indisponíveis no momento.';
        elements.latestResultsGrid.classList.add('text-gray-500');
        console.error('Erro ao carregar últimos resultados:', error);
    }
}


async function loadDataStatus() {
    if (!elements.dataStatusGrid) {
        return;
    }

    elements.dataStatusGrid.textContent = 'Carregando status dos dados...';

    try {
        const data = await getDataStatus();
        displayDataStatus(
            data.status,
            elements.dataStatusGrid,
            elements.dataStatusUpdatedAt
        );
    } catch (error) {
        elements.dataStatusGrid.textContent = 'Status dos dados indisponivel no momento.';
        elements.dataStatusGrid.classList.add('text-gray-500');
        console.error('Erro ao carregar status dos dados:', error);
    }
}


function ensureAdminToken() {
    if (state.currentUser?.is_admin) {
        return true;
    }

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
        showError('Acesso admin necessario. Entre com uma conta admin ou informe um token valido.');
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
        const data = await generateGames(lotteryType, String(numGames));
        const jogos = data.games || data;
        state.currentGeneratedGames = jogos;

        if (data.usage && state.currentUser) {
            renderAccountState({ ...state.currentUser, usage: data.usage });
        }

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


async function handleUpdateData() {
    if (!ensureAdminToken()) {
        return;
    }

    showLoading('Atualizando resultados. Isso pode levar alguns instantes...');
    setActionButtonsDisabled(true);

    try {
        const data = await updateData();
        displayDataStatus(
            data.status,
            elements.dataStatusGrid,
            elements.dataStatusUpdatedAt
        );
        await loadLatestResults();
        showSuccessMessageModal(data.message || 'Dados atualizados com sucesso.');
    } catch (error) {
        if (handleAdminError(error)) {
            return;
        }

        showError(`Erro: ${error.message}`);
        console.error('Erro ao atualizar dados:', error);
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


function formatGameForCopy(game) {
    const numbers = [];
    const extras = [];

    game.forEach(value => {
        if (Number.isFinite(Number(value))) {
            numbers.push(String(value).padStart(2, '0'));
        } else {
            extras.push(value);
        }
    });

    if (extras.length === 0) {
        return numbers.join(' ');
    }

    return `${numbers.join(' ')} | Mês da Sorte: ${extras.join(', ')}`;
}


async function handleCopyGames() {
    if (state.currentGeneratedGames.length === 0) {
        showError('Nenhum jogo para copiar.');
        return;
    }

    const formattedGames = state.currentGeneratedGames
        .map(formatGameForCopy)
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
    if (elements.loginForm) {
        elements.loginForm.addEventListener('submit', handleLogin);
    }

    if (elements.registerForm) {
        elements.registerForm.addEventListener('submit', handleRegister);
    }

    if (elements.guestAccessButton) {
        elements.guestAccessButton.addEventListener('click', handleGuestAccess);
    }

    if (elements.navLoginButton) {
        elements.navLoginButton.addEventListener('click', handleReturnToLogin);
    }

    if (elements.logoutButton) {
        elements.logoutButton.addEventListener('click', handleLogout);
    }

    if (elements.premiumPixButton) {
        elements.premiumPixButton.addEventListener('click', handleBillingPix);
    }

    if (elements.adminUsersButton) {
        elements.adminUsersButton.addEventListener('click', () => handleAdminUsers());
    }

    getLotteryOptionButtons().forEach(button => {
        button.addEventListener('click', () => selectLotteryOption(button));
        button.addEventListener('keydown', handleLotteryOptionKeydown);
    });

    elements.lotterySelect.addEventListener('change', () => {
        setSelectedLottery(selectedLotteryType());
    });

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

    if (elements.updateDataButton) {
        elements.updateDataButton.addEventListener('click', handleUpdateData);
    }

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
renderDrawCalendar(elements.drawCalendarGrid);
setSelectedLottery(selectedLotteryType());
bindEvents();
initPreferences({ onFontChanged: handleFontChanged });
loadAdminStatus();
refreshAuthSession();
loadLatestResults();
loadDataStatus();
