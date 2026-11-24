const panel = document.getElementById('research-report-panel');
const content = document.getElementById('research-report-content');
const status = document.getElementById('research-report-status');
let identity = null;
let lottery = 'megasena';
let pending = null;
let revision = null;

function node(tag, text) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    return el;
}
const number = value => Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 4 });
const pNumber = value => value === 0 ? 'Abaixo da precisão numérica' : value < 0.0001 ? Number(value).toExponential(2).replace('.', ',') : number(value);

async function load() {
    if (!identity || !panel.open) return;
    pending?.abort();
    const controller = new AbortController(); pending = controller;
    const timeout = setTimeout(() => controller.abort(), 10000);
    status.textContent = 'Conferindo o relatório desta base...';
    try {
        const response = await fetch(`/statistical_report/${encodeURIComponent(lottery)}`, { signal: controller.signal, cache: 'no-store' });
        if (!response.ok) throw new Error();
        const data = await response.json();
        if (pending !== controller) return;
        if (data.status !== 'current') { content.replaceChildren(); revision = null; status.textContent = data.message; return; }
        const { audit, coverage, intervals } = data.report;
        status.textContent = `Relatório gerado em ${new Date(data.generated_at).toLocaleString('pt-BR')}, para ${number(coverage.total_draws)} concursos, até ${coverage.last_contest}.`;
        const nextRevision = `${data.generated_at}:${data.report.fingerprint}`;
        if (nextRevision === revision) return;
        revision = nextRevision; content.replaceChildren();
        content.append(node('h3', 'Padrões versus coincidências'),
            node('p', `${audit.significant_pairs} de ${number(audit.family_size)} pares com excesso de coocorrências após correção BY de falsas descobertas (nível de 5%).`),
            node('p', `Teste global com ${audit.resamples} históricos simulados: valor p ${number(audit.global_p_value)}. Resolução mínima: ${number(audit.minimum_p_resolution)}. Este valor não é a chance de uma aposta ganhar.`),
            node('p', audit.note));
        const lab = node('details'); lab.append(node('summary', 'Laboratório de estratégias'));
        lab.append(node('p', 'Compara a ocorrência dos perfis no histórico com sorteios uniformes de mesmo tamanho. Não é taxa de prêmios de jogos gerados nem previsão. O valor q usa correção BY separada entre os modos listados.'));
        const labRegion = node('div'); labRegion.className = 'analysis-table-scroll'; labRegion.tabIndex = 0;
        labRegion.setAttribute('role', 'region'); labRegion.setAttribute('aria-label', 'Comparação de estratégias com a referência aleatória');
        const labTable = node('table'); const labHead = node('thead'); const labHeader = node('tr');
        ['Perfil', 'Histórico', 'Referência matemática', 'Faixa central simulada (95%)', 'Valor q ajustado'].forEach(text => { const cell = node('th', text); cell.scope = 'col'; labHeader.append(cell); });
        labHead.append(labHeader); const labBody = node('tbody');
        audit.strategies.forEach(strategy => { const row = node('tr');
            [strategy.label, `${strategy.observed}/${strategy.total} (${number(strategy.observed / strategy.total * 100)}%)`,
                `${number(strategy.reference_probability * 100)}%`, `${number(strategy.simulation_interval[0])} a ${number(strategy.simulation_interval[1])} concursos`, pNumber(strategy.q_value)].forEach(text => row.append(node('td', text)));
            labBody.append(row); });
        labTable.append(node('caption', 'Ocorrência de perfis, não taxa de prêmios.'), labHead, labBody); labRegion.append(labTable); lab.append(labRegion); content.append(lab);
        const details = node('details'); details.append(node('summary', 'Intervalos sem aparecer'));
        details.append(node('p', 'Intervalos são contados em concursos consecutivos completos, não em dias. A probabilidade de continuar ausente não torna uma dezena mais propensa a sair.'));
        const region = node('div'); region.className = 'analysis-table-scroll'; region.tabIndex = 0;
        region.setAttribute('role', 'region'); region.setAttribute('aria-label', 'Intervalos por dezena');
        const table = node('table'); table.append(node('caption', 'Referência geométrica para sorteios independentes. Dados incompletos não recebem intervalo estimado.'));
        const head = node('thead'); const header = node('tr');
        ['Dezena', 'Concursos sem sair', 'Probabilidade de ausência por esse intervalo'].forEach(text => { const th = node('th', text); th.scope = 'col'; header.append(th); });
        head.append(header); const body = node('tbody');
        intervals.forEach(item => { const row = node('tr');
            [String(item.number).padStart(2, '0'), item.gap ?? 'Base incompleta', item.tail_probability === null ? 'Não estimada' : `${number(item.tail_probability * 100)}%`].forEach(text => row.append(node('td', text)));
            body.append(row); });
        table.append(head, body); region.append(table); details.append(region); content.append(details);
    } catch {
        if (pending === controller) { content.replaceChildren(); revision = null; status.textContent = 'Relatório indisponível. Reabra este painel para tentar novamente.'; }
    } finally { clearTimeout(timeout); if (pending === controller) pending = null; }
}

export function syncResearchReports(user, kind) {
    const next = user?.is_premium ? `${user.id}:${user.role}` : null;
    if (next !== identity || lottery !== kind) {
        pending?.abort(); pending = null; revision = null; content.replaceChildren(); status.textContent = '';
        if (next !== identity) panel.open = false;
    }
    identity = next; lottery = kind; panel.classList.toggle('hidden', !next);
    if (panel.open) load();
}
export function refreshResearchReports() { load(); }
panel.addEventListener('toggle', () => { if (panel.open) load(); else { pending?.abort(); pending = null; } });
document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
setInterval(() => { if (!document.hidden && panel.open) load(); }, 60000);
