async function parseResponse(response, fallbackMessage) {
    let payload = null;
    const contentType = response.headers.get('content-type') || '';

    if (contentType.includes('application/json')) {
        try {
            payload = await response.json();
        } catch {
            payload = null;
        }
    }

    if (!response.ok) {
        const statusSuffix = response.status ? ` (HTTP ${response.status})` : '';
        const error = new Error(payload?.error || `${fallbackMessage}${statusSuffix}`);
        error.status = response.status;
        throw error;
    }

    return payload || {};
}


async function requestJson(resource, fallbackMessage, options) {
    try {
        const response = await fetch(resource, options);

        return parseResponse(response, fallbackMessage);
    } catch (error) {
        const isNetworkError = (
            error instanceof TypeError
            || error.message === 'Failed to fetch'
            || error.message === 'NetworkError when attempting to fetch resource.'
        );

        if (isNetworkError) {
            const openedDirectly = window.location.protocol === 'file:';
            const message = openedDirectly
                ? 'O app foi aberto direto pelo arquivo HTML. Abra pelo "Abrir Loterias.cmd" ou rode "py app.py" e mantenha a janela do servidor aberta.'
                : 'O servidor local não está respondendo. Abra novamente pelo "Abrir Loterias.cmd" ou rode "py app.py" e mantenha a janela do servidor aberta.';

            throw new Error(message);
        }

        throw error;
    }
}


export async function getAdminStatus() {
    return requestJson('/admin_status', 'Erro ao verificar protecao admin');
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
    const csrfToken = getSavedCsrfToken();
    const headers = {};

    if (token) {
        headers['X-Admin-Token'] = token;
    }

    if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken;
    }

    return headers;
}

export function getSavedCsrfToken() {
    return sessionStorage.getItem('csrfToken') || '';
}

export function setSavedCsrfToken(token) {
    if (token) {
        sessionStorage.setItem('csrfToken', token);
    }
}

export function clearSavedCsrfToken() {
    sessionStorage.removeItem('csrfToken');
}

function csrfHeaders(extraHeaders = {}) {
    const csrfToken = getSavedCsrfToken();

    return {
        ...extraHeaders,
        ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
    };
}

export async function generateGames(lotteryType, numGames, generationMode = 'normal') {
    const params = new URLSearchParams({
        num_games: numGames,
        mode: generationMode,
    });

    return requestJson(
        `/gerar_jogos/${encodeURIComponent(lotteryType)}?${params.toString()}`,
        'Erro desconhecido ao gerar jogos',
        {
            method: 'POST',
            headers: csrfHeaders(),
        }
    );
}

export async function listHistoryFiles(lotteryType) {
    return requestJson(
        `/get_history_files/${encodeURIComponent(lotteryType)}`,
        'Erro ao carregar histórico'
    );
}

export async function generateConstrainedGames(lotteryType, payload, signal) {
    return requestJson(`/generate_constrained/${encodeURIComponent(lotteryType)}`, 'Não foi possível gerar o lote', {
        method: 'POST', headers: csrfHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload), signal,
    });
}

export async function getStrategyCatalog(lotteryType) {
    return requestJson(`/strategy_catalog/${encodeURIComponent(lotteryType)}`, 'Não foi possível carregar as estratégias', { cache: 'no-store' });
}

export async function getManagedHistory(kind, filters, signal) {
    return requestJson(`/history_games/${encodeURIComponent(kind)}?${new URLSearchParams(filters)}`, 'Não foi possível carregar seus jogos', { cache: 'no-store', signal });
}

export async function updateManagedGame(kind, payload) {
    return requestJson(`/history_game/${encodeURIComponent(kind)}`, 'Não foi possível salvar o jogo', { method: 'POST', headers: csrfHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify(payload) });
}

export async function clearManagedHistory(kind) {
    return requestJson(`/history_clear/${encodeURIComponent(kind)}`, 'Não foi possível apagar o histórico', { method: 'POST', headers: csrfHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({ confirm: kind }) });
}

export async function getHistoryFileContent(filename) {
    return requestJson(
        `/get_file_content/${encodeURIComponent(filename)}`,
        'Erro ao carregar conteúdo do arquivo'
    );
}

export async function getHotColdNumbers(lotteryType) {
    return requestJson(
        `/get_hot_cold_numbers/${encodeURIComponent(lotteryType)}`,
        'Erro ao obter números de assistência'
    );
}

export async function getLatestResults() {
    return requestJson('/latest_results', 'Erro ao carregar últimos resultados');
}

export async function getDataStatus() {
    return requestJson('/data_status', 'Erro ao carregar status dos dados');
}

export async function getStrategyStats(lotteryType) {
    return requestJson(
        `/strategy_stats/${encodeURIComponent(lotteryType)}`,
        'Erro ao carregar estatísticas das estratégias'
    );
}

export async function getPatternRadar(lotteryType, previousEven = '', signal, previousMonth = '') {
    const params = new URLSearchParams();
    if (previousEven !== '') params.set('previous_even', previousEven);
    if (previousMonth !== '') params.set('previous_month', previousMonth);
    return requestJson(
        `/pattern_radar/${encodeURIComponent(lotteryType)}?${params}`,
        'Erro ao carregar o radar de padrões',
        { signal, cache: 'no-store' }
    );
}

export async function analyzeGame(lotteryType, numbers, month = null, signal) {
    return requestJson(
        `/analyze_game/${encodeURIComponent(lotteryType)}`,
        'Erro ao consultar o jogo',
        {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ numbers, month }),
            signal,
        }
    );
}

export async function analyzeGames(lotteryType, games, signal) {
    return requestJson(
        `/analyze_games/${encodeURIComponent(lotteryType)}`,
        'Erro ao consultar e comparar os jogos',
        {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ games }),
            signal,
        }
    );
}

export async function getAuthSession() {
    const data = await requestJson('/auth/me', 'Erro ao carregar conta');
    setSavedCsrfToken(data.csrf_token);
    return data;
}

export async function registerAccount({ name, email, password, setupCode, termsAccepted }) {
    const data = await requestJson(
        '/auth/register',
        'Erro ao criar conta',
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                email,
                password,
                setup_code: setupCode,
                terms_accepted: Boolean(termsAccepted),
            }),
        }
    );
    setSavedCsrfToken(data.csrf_token);
    return data;
}

export async function loginAccount({ email, password }) {
    const data = await requestJson(
        '/auth/login',
        'Erro ao entrar',
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        }
    );
    setSavedCsrfToken(data.csrf_token);
    return data;
}

export async function enterAsGuest() {
    const data = await requestJson(
        '/auth/guest',
        'Erro ao entrar como visitante',
        {
            method: 'POST',
        }
    );
    setSavedCsrfToken(data.csrf_token);
    return data;
}

export async function logoutAccount() {
    const data = await requestJson(
        '/auth/logout',
        'Erro ao sair',
        {
            method: 'POST',
            headers: csrfHeaders(),
        }
    );
    clearSavedCsrfToken();
    return data;
}

export async function getBillingPix() {
    return requestJson('/billing/pix', 'Erro ao carregar dados Pix');
}

export async function listAdminUsers() {
    return requestJson('/admin/users', 'Erro ao carregar usuários');
}

export async function updateUserPlan(userId, plan) {
    return requestJson(
        `/admin/users/${encodeURIComponent(userId)}/plan`,
        'Erro ao atualizar plano',
        {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ plan }),
        }
    );
}

export async function updateData() {
    return requestJson(
        '/admin/update_data',
        'Erro ao atualizar dados',
        {
            method: 'POST',
            headers: adminHeaders(),
        }
    );
}

export async function clearHistory(lotteryType) {
    return requestJson(
        `/clear_history/${encodeURIComponent(lotteryType)}`,
        'Erro ao limpar histórico',
        {
            method: 'POST',
            headers: adminHeaders(),
        }
    );
}

export async function deleteHistoryFile(filename) {
    return requestJson(
        `/delete_file/${encodeURIComponent(filename)}`,
        'Erro ao apagar arquivo',
        {
            method: 'POST',
            headers: adminHeaders(),
        }
    );
}
