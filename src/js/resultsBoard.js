import { state } from './dom.js';
import { openDigestEdition } from './drawDigest.js';

const grid = document.getElementById('latest-results-grid');
const refresh = document.getElementById('results-reload');
const feedback = document.getElementById('results-action-feedback');
let timer = null, busy = false;

function announce(message) {
    clearTimeout(timer); feedback.textContent = message;
    timer = setTimeout(() => { feedback.textContent = ''; }, 6000);
}

export function initResultsBoard(reload) {
    refresh.addEventListener('click', async () => {
        if (busy) return;
        busy = true; refresh.disabled = true; grid.setAttribute('aria-busy', 'true');
        clearTimeout(timer); feedback.textContent = 'Consultando os resultados disponíveis na base...';
        try {
            const available = await reload();
            announce(available ? 'Painel recarregado com os dados disponíveis na base.' : 'Não foi possível carregar os resultados. Tente novamente.');
        } catch { announce('Não foi possível recarregar o painel. Tente novamente.'); }
        finally { busy = false; refresh.disabled = false; grid.setAttribute('aria-busy', 'false'); }
    });
    grid.addEventListener('click', async event => {
        const button = event.target.closest('[data-results-action]');
        if (!button || button.disabled || busy) return;
        const kind = button.dataset.resultsKind;
        const result = state.latestResults?.[kind];
        if (!result) return;
        if (button.dataset.resultsAction === 'digest') { await openDigestEdition(kind); return; }
        if (button.dataset.resultsAction !== 'copy') return;
        button.disabled = true;
        try {
            const extras = kind === 'diadesorte' ? `\nMês da Sorte: ${result.extras?.['Mês da Sorte'] || 'não informado na base'}`
                : kind === 'maismilionaria' ? `\nTrevos: ${result.extras?.['Trevo 1']} · ${result.extras?.['Trevo 2']}` : '';
            const text = `${result.name}\nConcurso ${result.contest} · ${result.date}\n${result.numbers.map(n => String(n).padStart(2,'0')).join(' · ')}${extras}\nResultado da base do app; confira os canais oficiais da CAIXA.`;
            await navigator.clipboard.writeText(text);
            announce(`Resultado de ${result.name} copiado.`);
        } catch { announce('Não foi possível copiar o resultado neste navegador.'); }
        finally { button.disabled = false; }
    });
}
