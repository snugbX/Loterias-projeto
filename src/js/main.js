import {
    clearHistory,
    clearSavedAdminToken,
    deleteHistoryFile,
    enterAsGuest,
    generateGames,
    getAuthSession,
    getBillingPix,
    getDataStatus,
    getHistoryFileContent,
    getHotColdNumbers,
    getLatestResults,
    getStrategyStats,
    listAdminUsers,
    listHistoryFiles,
    loginAccount,
    logoutAccount,
    registerAccount,
    updateData,
    updateUserPlan,
} from './api.js';
import {
    elements,
    lotteryColors,
    lotteryDetails,
    selectedGenerationMode,
    selectedLotteryType,
    state,
} from './dom.js';
import { renderDrawCalendar } from './drawCalendar.js';
import { initPreferences, updateDynamicElementColors } from './preferences.js';
import {
    createHistoryFileRow,
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

let adminConfigured = true;

const generationModeLabels = {
    normal: 'Jogo normal',
    balanced_never_prize: 'Recomendado',
    balanced_parity: 'Pares e ímpares',
    even_only: 'Só pares',
    odd_only: 'Só ímpares',
    spread: 'Bem distribuído',
    hot_cold_mix: 'Quentes e frios',
    lucky_dates: 'Datas da sorte',
    high_numbers: 'Números altos',
    never_prize: 'Sem prêmio histórico',
    mixed: 'Tudo misturado',
};

const generationModeSummaries = {
    normal: 'Probabilidade e filtros atuais.',
    balanced_never_prize: 'Pares/ímpares + filtro sem prêmio histórico.',
    balanced_parity: 'Equilibra a divisão do jogo.',
    even_only: 'Uma superstição direta e ousada.',
    odd_only: 'Para quem joga no instinto.',
    spread: 'Espalha por faixas numéricas.',
    hot_cold_mix: 'Mistura frequentes e esquecidos.',
    lucky_dates: 'Prioriza dezenas até 31.',
    high_numbers: 'Foca na metade superior.',
    never_prize: 'Foge das faixas históricas fortes.',
    mixed: 'Alterna estratégias a cada jogo.',
};

const unavailableGenerationModesByLottery = {
    lotofacil: new Set(['even_only', 'odd_only', 'high_numbers', 'lucky_dates']),
    diadesorte: new Set(['lucky_dates']),
};

// Tempo da tela de boas-vindas antes de fechar sozinha.
// Altere este valor em milissegundos: 15000 = 15 segundos.
const WELCOME_AUTO_DISMISS_MS = 15000;
const WELCOME_EXIT_MS = 650;
const WELCOME_STORAGE_KEY = 'snugbx-welcome-seen';
let welcomeDismissTimer = null;
let lastPrivacyTermsFocus = null;


function isAdminUser(user = state.currentUser) {
    return Boolean(user?.is_admin);
}


function hasPremiumAccess(user = state.currentUser) {
    return Boolean(user?.is_premium);
}


function updateAdminVisibility(user = state.currentUser) {
    const isAdmin = isAdminUser(user);

    [
        elements.adminUsersButton,
        elements.updateDataButton,
        elements.limparHistoricoBtn,
        elements.limparHistoricoDiretoBtn,
    ].filter(Boolean).forEach(element => {
        element.classList.toggle('hidden', !isAdmin);
    });

    if (!isAdmin) {
        elements.adminUsersPanel?.classList.add('hidden');
    }
}


function updateAdminSetupVisibility() {
    elements.registerSetupCode?.classList.toggle('hidden', adminConfigured);
}


function getGenerationModeButtons() {
    if (!elements.generationModeGrid) {
        return [];
    }

    return Array.from(elements.generationModeGrid.querySelectorAll('[data-generation-mode]'));
}


function setGenerationModePickerOpen(open) {
    elements.generationModeGrid?.classList.toggle('hidden', !open);
    elements.generationModeToggle?.setAttribute('aria-expanded', String(open));
}


function toggleGenerationModePicker() {
    const isOpen = elements.generationModeToggle?.getAttribute('aria-expanded') === 'true';
    setGenerationModePickerOpen(!isOpen);
}


function formatStrategyPercentage(value) {
    const percentage = Number(value);

    if (!Number.isFinite(percentage)) {
        return '';
    }

    return percentage.toLocaleString('pt-BR', {
        minimumFractionDigits: percentage > 0 && percentage < 1 ? 2 : 0,
        maximumFractionDigits: 2,
    });
}


function getGenerationModeStatBadge(button) {
    let badge = button.querySelector('.generation-mode-stat');

    if (!badge) {
        badge = document.createElement('small');
        badge.classList.add('generation-mode-stat');
        button.appendChild(badge);
    }

    return badge;
}


function setGenerationModeStatsLoading() {
    getGenerationModeButtons().forEach(button => {
        const badge = getGenerationModeStatBadge(button);

        badge.classList.add('is-muted');
        badge.textContent = 'Calculando histórico...';
        badge.removeAttribute('title');
    });
}


function clearGenerationModeStats() {
    getGenerationModeButtons().forEach(button => {
        const badge = button.querySelector('.generation-mode-stat');

        if (badge) {
            badge.remove();
        }
    });
}


function renderGenerationStrategyStats(stats) {
    const modes = stats?.modes || {};

    getGenerationModeButtons().forEach(button => {
        const mode = button.dataset.generationMode;
        const stat = modes[mode];
        const badge = getGenerationModeStatBadge(button);

        if (!stat) {
            badge.classList.add('is-muted');
            badge.textContent = 'Sem leitura histórica';
            badge.removeAttribute('title');
            return;
        }

        badge.classList.toggle('is-muted', !stat.has_stat);

        if (stat.has_stat) {
            const formattedPercentage = formatStrategyPercentage(stat.percentage);
            badge.textContent = `${formattedPercentage}% dos sorteios`;
            badge.title = `${stat.matches} de ${stat.total} concursos da ${stats.lottery_name || 'loteria'} bateram com essa estratégia.`;
            return;
        }

        badge.textContent = stat.message || 'Sem base histórica direta';
        badge.removeAttribute('title');
    });
}


async function loadGenerationStrategyStats(lotteryType = selectedLotteryType()) {
    if (!elements.generationModeGrid || !hasPremiumAccess()) {
        clearGenerationModeStats();
        return;
    }

    const cachedStats = state.strategyStatsByLottery[lotteryType];

    if (cachedStats) {
        renderGenerationStrategyStats(cachedStats);
        return;
    }

    setGenerationModeStatsLoading();

    try {
        const data = await getStrategyStats(lotteryType);
        state.strategyStatsByLottery[lotteryType] = data.stats;

        if (selectedLotteryType() === lotteryType) {
            renderGenerationStrategyStats(data.stats);
        }
    } catch (error) {
        getGenerationModeButtons().forEach(button => {
            const badge = getGenerationModeStatBadge(button);
            badge.classList.add('is-muted');
            badge.textContent = 'Estatística indisponível';
            badge.removeAttribute('title');
        });
        console.error('Erro ao carregar estatísticas das estratégias:', error);
    }
}


function isGenerationModeAvailableForLottery(mode, lotteryType = selectedLotteryType()) {
    return !unavailableGenerationModesByLottery[lotteryType]?.has(mode);
}


function canUseGenerationMode(mode, user = state.currentUser) {
    if (!isGenerationModeAvailableForLottery(mode)) {
        return false;
    }

    if (mode === 'normal') {
        return true;
    }

    if (!hasPremiumAccess(user)) {
        return false;
    }

    return true;
}


function setSelectedGenerationMode(mode) {
    const nextMode = canUseGenerationMode(mode) ? mode : 'normal';
    state.selectedGenerationMode = nextMode;

    if (elements.selectedGenerationModeLabel) {
        elements.selectedGenerationModeLabel.textContent = generationModeLabels[nextMode] || 'Jogo normal';
    }

    if (elements.selectedGenerationModeSummary) {
        elements.selectedGenerationModeSummary.textContent = (
            generationModeSummaries[nextMode] || generationModeSummaries.normal
        );
    }

    getGenerationModeButtons().forEach(button => {
        const buttonMode = button.dataset.generationMode;
        const selected = buttonMode === nextMode;
        const availableForLottery = isGenerationModeAvailableForLottery(buttonMode);
        const available = canUseGenerationMode(buttonMode);

        button.classList.toggle('hidden', !availableForLottery);
        button.classList.toggle('is-selected', selected);
        button.setAttribute('aria-checked', String(selected));
        button.dataset.available = String(available);
        button.disabled = !available;
        button.tabIndex = available ? 0 : -1;
        button.removeAttribute('title');
    });
}


function renderGenerationModeAccess(user = state.currentUser) {
    const premium = hasPremiumAccess(user);

    elements.generationModePicker?.classList.toggle('hidden', !premium);
    setGenerationModePickerOpen(false);
    elements.premiumUpsellPanel?.classList.toggle('hidden', premium);

    if (!premium) {
        clearGenerationModeStats();
        setSelectedGenerationMode('normal');
        return;
    }

    setSelectedGenerationMode(state.selectedGenerationMode);
    loadGenerationStrategyStats();
}


function rememberWelcomeSeen() {
    try {
        window.sessionStorage.setItem(WELCOME_STORAGE_KEY, '1');
    } catch (error) {
        console.warn('Não foi possível salvar a exibição da abertura.', error);
    }
}


function wasWelcomeSeen() {
    try {
        return window.sessionStorage.getItem(WELCOME_STORAGE_KEY) === '1';
    } catch (error) {
        console.warn('Não foi possível ler a exibição da abertura.', error);
        return false;
    }
}


function dismissWelcomeScreen() {
    if (!elements.welcomeScreen || elements.welcomeScreen.classList.contains('hidden')) {
        return;
    }

    window.clearTimeout(welcomeDismissTimer);
    rememberWelcomeSeen();
    elements.welcomeScreen.classList.add('is-leaving');

    window.setTimeout(() => {
        elements.welcomeScreen.classList.add('hidden');
    }, WELCOME_EXIT_MS);
}


function initWelcomeScreen() {
    if (!elements.welcomeScreen) {
        return;
    }

    if (wasWelcomeSeen()) {
        elements.welcomeScreen.classList.add('hidden');
        return;
    }

    elements.welcomeSkipButton?.addEventListener('click', dismissWelcomeScreen);
    welcomeDismissTimer = window.setTimeout(dismissWelcomeScreen, WELCOME_AUTO_DISMISS_MS);
}


function closePrivacyTermsModal() {
    if (!elements.privacyTermsModalOverlay) {
        return;
    }

    closeModal(elements.privacyTermsModalOverlay);

    requestAnimationFrame(() => {
        const focusTarget = lastPrivacyTermsFocus || elements.registerTermsAccepted;
        focusTarget?.focus();
    });
}


function openPrivacyTermsModal() {
    if (!elements.privacyTermsModalOverlay) {
        return;
    }

    lastPrivacyTermsFocus = document.activeElement;
    openModal(elements.privacyTermsModalOverlay);

    requestAnimationFrame(() => {
        elements.privacyTermsContent?.focus();
    });
}


function acceptPrivacyTermsFromModal() {
    if (elements.registerTermsAccepted) {
        elements.registerTermsAccepted.checked = true;
    }

    closePrivacyTermsModal();
}


function handlePrivacyTermsKeydown(event) {
    if (event.key === 'Escape') {
        closePrivacyTermsModal();
        return;
    }

    if (event.key !== 'Tab') {
        return;
    }

    const focusableElements = Array.from(
        elements.privacyTermsModalOverlay.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
    ).filter(element => !element.disabled && element.offsetParent !== null);

    if (focusableElements.length === 0) {
        return;
    }

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
    } else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
    }
}


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
        elements.navLoginButton?.classList.add('hidden');
        elements.logoutButton?.classList.add('hidden');
        elements.premiumPixButton?.classList.add('hidden');
        elements.billingPixPanel?.classList.add('hidden');
        elements.adminUsersPanel?.classList.add('hidden');
        updateAdminVisibility(null);
        renderGenerationModeAccess(null);
        return;
    }

    const isGuest = Boolean(user.is_guest);
    elements.accountUserName.textContent = user.name || 'Visitante';
    elements.accountUserEmail.textContent = isGuest ? 'Versao gratuita sem cadastro' : user.email;
    elements.accountUsage.textContent = usageText(user);
    updateAdminVisibility(user);
    elements.navLoginButton?.classList.toggle('hidden', !isGuest);
    elements.logoutButton?.classList.toggle('hidden', isGuest);
    elements.premiumPixButton?.classList.toggle('hidden', isGuest);
    renderGenerationModeAccess(user);
}


async function refreshAuthSession() {
    try {
        const data = await getAuthSession();
        renderAccountState(data.user);
        adminConfigured = Boolean(data.admin_configured);
        updateAdminSetupVisibility();
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

    if (!elements.registerTermsAccepted?.checked) {
        showError('Para criar sua conta, leia e aceite a Política de Privacidade e os Termos de Uso.');
        elements.registerTermsAccepted?.focus();
        return;
    }

    showLoading('Criando conta...');
    setActionButtonsDisabled(true);

    try {
        const data = await registerAccount({
            name: elements.registerName.value,
            email: elements.registerEmail.value,
            password: elements.registerPassword.value,
            setupCode: elements.registerSetupCode.value,
            termsAccepted: elements.registerTermsAccepted.checked,
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
        showSuccessMessageModal('Você saiu da conta.');
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
        title.textContent = data.enabled ? 'Chave Pix Premium' : 'Pix ainda não configurado';

        const key = document.createElement('p');
        key.textContent = data.enabled
            ? data.pix_key
            : 'Configure a chave Pix no arquivo .env local.';

        const receiver = document.createElement('p');
        receiver.textContent = data.receiver_email
            ? `Responsável: ${data.receiver_email}`
            : 'Responsável não configurado.';

        elements.billingPixPanel.appendChild(title);
        elements.billingPixPanel.appendChild(key);
        elements.billingPixPanel.appendChild(receiver);
    } catch (error) {
        elements.billingPixPanel.textContent = error.message;
    }
}


async function handlePremiumUpsell() {
    if (state.currentUser?.is_guest) {
        await handleReturnToLogin();
        showError('Entre ou crie uma conta para ativar o plano Premium.');
        return;
    }

    if (!state.currentUser) {
        renderAccountState(null);
        elements.loginEmail?.focus();
        return;
    }

    await handleBillingPix();
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
    if (!isAdminUser()) {
        showError('Recurso exclusivo do administrador.');
        return;
    }

    if (options.forceOpen) {
        elements.adminUsersPanel.classList.remove('hidden');
    } else {
        elements.adminUsersPanel.classList.toggle('hidden');
    }

    if (elements.adminUsersPanel.classList.contains('hidden')) {
        return;
    }

    elements.adminUsersPanel.textContent = 'Carregando usuários...';

    try {
        const data = await listAdminUsers();
        elements.adminUsersPanel.innerHTML = '';

        if (!data.users || data.users.length === 0) {
            elements.adminUsersPanel.textContent = 'Nenhum usuário encontrado.';
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
    const darkTheme = document.body.classList.contains('dark-theme');

    document.body.style.setProperty('--active-lottery-primary', colors.primary);
    document.body.style.setProperty('--active-lottery-secondary', colors.secondary);
    document.body.style.setProperty('--active-lottery-readable', darkTheme ? colors.readableDark : colors.readable);
    document.body.style.setProperty('--active-lottery-border', darkTheme ? colors.readableDark : colors.border);
    document.body.style.setProperty('--active-lottery-soft-bg', darkTheme ? colors.softBgDark : colors.softBg);

    if (elements.selectedLotteryName) {
        elements.selectedLotteryName.textContent = details.name;
    }

    if (elements.selectedLotteryMeta) {
        elements.selectedLotteryMeta.textContent = details.summary;
    }

    if (elements.gerarJogosButton) {
        elements.gerarJogosButton.style.background = `linear-gradient(135deg, ${colors.action || colors.primary}, ${details.accent})`;
        elements.gerarJogosButton.style.boxShadow = `0 10px 22px ${colors.secondary}66`;
    }

    getLotteryOptionButtons().forEach(button => {
        const selected = button.dataset.lottery === lotteryType;
        button.classList.toggle('is-selected', selected);
        button.setAttribute('aria-checked', String(selected));
        button.tabIndex = selected ? 0 : -1;
    });

    setSelectedGenerationMode(state.selectedGenerationMode);

    if (hasPremiumAccess()) {
        loadGenerationStrategyStats(lotteryType);
    }
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


function updateDataStatusTimestamp() {
    if (elements.dataStatusUpdatedAt) {
        elements.dataStatusUpdatedAt.textContent = `Verificado em ${new Date().toLocaleString('pt-BR')}`;
    }
}


function renderResultsOverview() {
    if (!elements.latestResultsGrid || !state.latestResults) {
        return;
    }

    displayLatestResults(state.latestResults, elements.latestResultsGrid, state.dataStatus);
}


async function loadLatestResults() {
    if (!elements.latestResultsGrid) {
        return;
    }

    elements.latestResultsGrid.textContent = 'Carregando últimos resultados...';

    try {
        const data = await getLatestResults();
        state.latestResults = data.results;
        renderResultsOverview();
    } catch (error) {
        state.latestResults = null;
        elements.latestResultsGrid.textContent = 'Últimos resultados indisponíveis no momento.';
        elements.latestResultsGrid.classList.add('text-gray-500');
        console.error('Erro ao carregar últimos resultados:', error);
    }
}


async function loadDataStatus() {
    if (!elements.dataStatusUpdatedAt && !elements.latestResultsGrid) {
        return;
    }

    try {
        const data = await getDataStatus();
        state.dataStatus = data.status;
        updateDataStatusTimestamp();
        renderResultsOverview();
    } catch (error) {
        if (elements.dataStatusUpdatedAt) {
            elements.dataStatusUpdatedAt.textContent = 'Status dos dados indisponível no momento.';
        }
        console.error('Erro ao carregar status dos dados:', error);
    }
}


function ensureAdminToken() {
    if (isAdminUser()) {
        return true;
    }

    showError('Recurso exclusivo do administrador.');
    return false;
}


function handleAdminError(error) {
    if (error.status === 401) {
        clearSavedAdminToken();
        showError('Acesso admin necessário. Entre com uma conta admin ou informe um token válido.');
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
        const data = await generateGames(lotteryType, String(numGames), selectedGenerationMode());
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
        state.dataStatus = data.status;
        updateDataStatusTimestamp();
        renderResultsOverview();
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

        showSuccessMessageModal('Jogos copiados para a área de transferência!');
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

    showLoading('Carregando histórico...');
    elements.historicoArquivosContainer.classList.remove('hidden');
    elements.historicoConteudoContainer.classList.add('hidden');
    setActionButtonsDisabled(true);

    try {
        const data = await listHistoryFiles(lotteryType);
        elements.historicoArquivosLista.innerHTML = '';
        elements.historicoArquivosLista.classList.remove('text-gray-500');

        if (data.files && data.files.length > 0) {
            data.files.forEach(filename => {
                const deleteAction = isAdminUser()
                    ? () => showCustomConfirmModal(
                        'Confirmar Exclusão',
                        `Tem certeza que deseja apagar o arquivo "${filename}"? Esta ação é irreversível!`,
                        () => confirmDeleteFileAction(filename, lotteryType)
                    )
                    : null;

                const row = createHistoryFileRow(
                    filename,
                    () => loadHistoricalFile(filename, lotteryType),
                    deleteAction
                );

                elements.historicoArquivosLista.appendChild(row);
            });
        } else {
            elements.historicoArquivosLista.textContent = 'Nenhum arquivo de histórico encontrado para esta loteria.';
            elements.historicoArquivosLista.classList.add('text-gray-500');
        }

        elements.historicoArquivosLista.style.backgroundColor = 'var(--bg-primary)';
        elements.historicoArquivosLista.style.borderColor = 'var(--border-color)';
        updateDynamicElementColors();
    } catch (error) {
        showError(`Erro: ${error.message}`);
        console.error('Erro ao listar arquivos de histórico:', error);
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
            `Histórico de ${formatLotteryName(lotteryType)} - ${formatHistoryFilename(filename)}`
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
    showLoading('Obtendo números de assistência...');

    try {
        const data = await getHotColdNumbers(lotteryType);
        displayNumberBalls(data.hot_numbers, elements.hotNumbersList, 'hot');
        displayNumberBalls(data.cold_numbers, elements.coldNumbersList, 'cold');
        updateDynamicElementColors();
    } catch (error) {
        showError(`Erro: ${error.message}`);
        console.error('Erro ao obter assistência:', error);
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
        'Limpar Histórico',
        `Tem certeza que deseja DELETAR TODOS os arquivos de histórico para ${formatLotteryName(lotteryType)}? Esta ação é irreversível!`,
        async () => {
            if (!ensureAdminToken()) {
                return;
            }

            showLoading(`Limpando histórico para ${formatLotteryName(lotteryType)}...`);
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
                console.error('Erro ao limpar histórico:', error);
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

    if (elements.openPrivacyTermsButton) {
        elements.openPrivacyTermsButton.addEventListener('click', openPrivacyTermsModal);
    }

    if (elements.privacyTermsCloseButton) {
        elements.privacyTermsCloseButton.addEventListener('click', closePrivacyTermsModal);
    }

    if (elements.privacyTermsDismissButton) {
        elements.privacyTermsDismissButton.addEventListener('click', closePrivacyTermsModal);
    }

    if (elements.privacyTermsAcceptButton) {
        elements.privacyTermsAcceptButton.addEventListener('click', acceptPrivacyTermsFromModal);
    }

    if (elements.privacyTermsModalOverlay) {
        elements.privacyTermsModalOverlay.addEventListener('keydown', handlePrivacyTermsKeydown);
        elements.privacyTermsModalOverlay.addEventListener('click', event => {
            if (event.target === elements.privacyTermsModalOverlay) {
                closePrivacyTermsModal();
            }
        });
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

    if (elements.generationModeToggle) {
        elements.generationModeToggle.addEventListener('click', toggleGenerationModePicker);
    }

    getGenerationModeButtons().forEach(button => {
        button.addEventListener('click', () => {
            setSelectedGenerationMode(button.dataset.generationMode);
            setGenerationModePickerOpen(false);
            elements.generationModeToggle?.focus();
        });
    });

    if (elements.premiumUpsellButton) {
        elements.premiumUpsellButton.addEventListener('click', handlePremiumUpsell);
    }

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
initWelcomeScreen();
renderDrawCalendar(elements.drawCalendarGrid);
setSelectedLottery(selectedLotteryType());
bindEvents();
initPreferences({
    onFontChanged: handleFontChanged,
    onThemeChanged: () => setSelectedLottery(selectedLotteryType()),
});
refreshAuthSession();
loadLatestResults();
loadDataStatus();
