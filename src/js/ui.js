import { elements, state } from './dom.js';

const ERROR_AUTO_HIDE_MS = 7000;
let errorHideTimer = null;


export function showError(message) {
    clearTimeout(errorHideTimer);
    elements.errorMessageText.textContent = message;
    elements.errorMessage.classList.remove('hidden');
    errorHideTimer = setTimeout(hideError, ERROR_AUTO_HIDE_MS);
}


export function hideError() {
    clearTimeout(errorHideTimer);
    errorHideTimer = null;
    elements.errorMessageText.textContent = '';
    elements.errorMessage.classList.add('hidden');
}


export function showLoading(message) {
    elements.loadingMessage.textContent = message;
    elements.loadingMessage.classList.remove('hidden');
}


export function hideLoading() {
    elements.loadingMessage.classList.add('hidden');
}


elements.errorCloseButton?.addEventListener('click', hideError);


export function setActionButtonsDisabled(disabled) {
    elements.gerarJogosButton.disabled = disabled;
    elements.visualizarHistoricoButton.disabled = disabled;
    elements.assistenciaBtn.disabled = disabled;
    elements.limparHistoricoBtn.disabled = disabled;

    if (elements.updateDataButton) {
        elements.updateDataButton.disabled = disabled;
    }

    [
        elements.premiumPixButton,
        elements.adminUsersButton,
        elements.logoutButton,
        elements.navLoginButton,
        elements.guestAccessButton,
        elements.premiumUpsellButton,
        elements.openPrivacyTermsButton,
        elements.privacyTermsCloseButton,
        elements.privacyTermsAcceptButton,
        elements.privacyTermsDismissButton,
        elements.loginForm?.querySelector('button[type="submit"]'),
        elements.registerForm?.querySelector('button[type="submit"]'),
    ].filter(Boolean).forEach(button => {
        button.disabled = disabled;
    });

    if (elements.generationModeGrid) {
        elements.generationModeGrid.querySelectorAll('button').forEach(button => {
            button.disabled = disabled || button.dataset.available === 'false';
        });
    }

    if (elements.lotteryOptionGrid) {
        elements.lotteryOptionGrid.querySelectorAll('button').forEach(button => {
            button.disabled = disabled;
        });
    }
}


export function clearAllDisplays() {
    hideError();
    hideLoading();

    if (elements.jogosGeradosMainDisplay) {
        elements.jogosGeradosMainDisplay.innerHTML = '';
    }

    elements.historicoArquivosLista.innerHTML = '';
    elements.historicoConteudoJogosWrapper.innerHTML = '';
    elements.currentFilenameSpan.textContent = '';
    elements.hotNumbersList.innerHTML = '';
    elements.coldNumbersList.innerHTML = '';
    elements.jogosGeradosModalDisplay.innerHTML = '';

    if (elements.copyGamesButtonModal) {
        elements.copyGamesButtonModal.classList.add('hidden');
    }

    state.currentGeneratedGames = [];
    closeModal(elements.customConfirmModal);
    closeModal(elements.successModal);
    closeModal(elements.historyModalOverlay);
    closeModal(elements.generatedGamesModalOverlay);
    closeModal(elements.assistenciaModalOverlay);
    closeModal(elements.privacyTermsModalOverlay);
}


export function openModal(modal) {
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
}


export function closeModal(modal) {
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
}


export function showSuccessMessageModal(message, duration = 3000) {
    elements.successModalMessage.textContent = message;
    openModal(elements.successModal);

    setTimeout(() => {
        closeModal(elements.successModal);
    }, duration);
}


export function showCustomConfirmModal(title, message, onConfirmCallback) {
    elements.modalTitle.textContent = title;
    elements.modalMessage.textContent = message;
    openModal(elements.customConfirmModal);

    requestAnimationFrame(() => elements.modalConfirmBtn.focus());

    elements.modalConfirmBtn.onclick = null;
    elements.modalCancelBtn.onclick = null;

    elements.modalConfirmBtn.onclick = () => {
        closeModal(elements.customConfirmModal);
        onConfirmCallback();
    };

    elements.modalCancelBtn.onclick = () => {
        closeModal(elements.customConfirmModal);
    };
}
