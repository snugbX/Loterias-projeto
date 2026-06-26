async function parseResponse(response, fallbackMessage) {
    let payload = null;

    try {
        payload = await response.json();
    } catch {
        payload = null;
    }

    if (!response.ok) {
        const error = new Error(payload?.error || fallbackMessage);
        error.status = response.status;
        throw error;
    }

    return payload;
}

export async function getAdminStatus() {
    const response = await fetch('/admin_status');

    return parseResponse(response, 'Erro ao verificar protecao admin');
}

export function getSavedAdminToken() {
    return sessionStorage.getItem('adminToken') || '';
}

export function setSavedAdminToken(token) {
    sessionStorage.setItem('adminToken', token);
}

export function clearSavedAdminToken() {
    sessionStorage.removeItem('adminToken');
}

function adminHeaders() {
    const token = getSavedAdminToken();

    return token ? { 'X-Admin-Token': token } : {};
}

export async function generateGames(lotteryType, numGames) {
    const params = new URLSearchParams({ num_games: numGames });
    const response = await fetch(
        `/gerar_jogos/${encodeURIComponent(lotteryType)}?${params.toString()}`
    );

    return parseResponse(response, 'Erro desconhecido ao gerar jogos');
}

export async function listHistoryFiles(lotteryType) {
    const response = await fetch(
        `/get_history_files/${encodeURIComponent(lotteryType)}`
    );

    return parseResponse(response, 'Erro ao carregar historico');
}

export async function getHistoryFileContent(filename) {
    const response = await fetch(
        `/get_file_content/${encodeURIComponent(filename)}`
    );

    return parseResponse(response, 'Erro ao carregar conteudo do arquivo');
}

export async function getHotColdNumbers(lotteryType) {
    const response = await fetch(
        `/get_hot_cold_numbers/${encodeURIComponent(lotteryType)}`
    );

    return parseResponse(response, 'Erro ao obter numeros de assistencia');
}

export async function clearHistory(lotteryType) {
    const response = await fetch(
        `/clear_history/${encodeURIComponent(lotteryType)}`,
        {
            method: 'POST',
            headers: adminHeaders(),
        }
    );

    return parseResponse(response, 'Erro ao limpar historico');
}

export async function deleteHistoryFile(filename) {
    const response = await fetch(
        `/delete_file/${encodeURIComponent(filename)}`,
        {
            method: 'POST',
            headers: adminHeaders(),
        }
    );

    return parseResponse(response, 'Erro ao apagar arquivo');
}
