const panel = document.getElementById('draw-digest-panel');
const content = document.getElementById('draw-digest-content');
const status = document.getElementById('draw-digest-status');
let pending = null;
function node(tag, text) { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; return el; }

export async function refreshDrawDigest() {
    if (!panel.open) return;
    pending?.abort(); const controller = new AbortController(); pending = controller;
    const timeout = setTimeout(() => controller.abort(), 10000);
    status.textContent = 'Carregando os boletins da base atual...';
    try {
        const response = await fetch('/draw_digest', { cache: 'no-store', signal: controller.signal });
        if (!response.ok) throw new Error();
        const data = await response.json();
        if (pending !== controller) return;
        content.replaceChildren(); let waiting = 0;
        for (const result of Object.values(data.digests)) {
            if (result.status !== 'current') { waiting++; continue; }
            const digest = result.digest;
            const article = node('article'); article.dataset.lottery = digest.lottery_type;
            article.append(node('h3', `${digest.lottery_name} · Concurso ${digest.contest} · ${digest.date}`), node('p', digest.text));
            article.append(node('p', `Faixas numéricas: ${digest.ranges.map(range => `${range.from}–${range.to}: ${range.count}`).join(' · ')}. Pares de dezenas consecutivas: ${digest.consecutive_pairs}.`));
            article.append(node('p', `Cobertura: ${digest.coverage.total_draws} concursos válidos; ${digest.coverage.missing_contests} ausentes; ${digest.coverage.skipped_rows} linhas inválidas ou duplicadas excluídas.`));
            content.append(article);
        }
        status.textContent = waiting ? `${waiting} boletim(ns) aguardando processamento da base atual. Os anteriores não são exibidos como atuais.`
            : 'Resumo factual, sem previsão do próximo sorteio. Confira os canais oficiais da CAIXA.';
    } catch {
        if (pending === controller) { content.replaceChildren(); status.textContent = 'Boletins indisponíveis. Reabra este painel para tentar novamente.'; }
    } finally { clearTimeout(timeout); if (pending === controller) pending = null; }
}
panel.addEventListener('toggle', () => { if (panel.open) refreshDrawDigest(); else { pending?.abort(); pending = null; } });
