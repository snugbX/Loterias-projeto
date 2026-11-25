const el = id => document.getElementById(id);
const shelf = el('game-workbench');
const panels = [...el('lab-stage').querySelectorAll(':scope > details')];
const tools = [...shelf.querySelectorAll('[data-lab-panel]')];
const quantity = el('num-games-input');
const customQuantity = el('constrained-quantity');
const customMethod = el('constrained-method');
const customFields = el('constrained-fields');
let premium = false;
let busy = false;

function icon(name) {
    const span = document.createElement('span'); span.className = 'lab-icon';
    span.style.setProperty('--icon', `url('icons/lucide/${name}.svg')`); span.setAttribute('aria-hidden', 'true');
    return span;
}

// Move the original controls; there is still only one quantity and generation action.
const consoleBar = el('generation-console');
const quantityField = el('generation-quantity-field'); quantityField.className = 'console-quantity';
quantityField.querySelector('label').textContent = 'Quantidade';
const generate = el('gerar-jogos'); generate.className = 'console-generate';
const generateLabel = document.createElement('span'); generateLabel.id = 'generate-button-label'; generateLabel.textContent = 'Gerar Jogos';
generate.replaceChildren(icon('sparkles'), generateLabel); consoleBar.append(quantityField, generate);
for (const [id, name, label, title] of [
    ['visualizar-historico', 'history', 'Histórico', 'Abrir seus jogos, favoritos e conferências'],
    ['assistencia-btn', 'chart-no-axes-combined', 'Frequências', 'Consultar frequências de dezenas e meses'],
]) {
    const button = el(id); button.className = 'lab-tool'; button.title = title;
    const caption = document.createElement('span'); caption.textContent = label;
    button.replaceChildren(icon(name), caption);
    if (id === 'assistencia-btn') { button.setAttribute('data-premium', ''); button.classList.add('hidden'); }
    shelf.querySelector('.lab-shelf').insertBefore(button, tools.at(-1));
}

function customActive() {
    const panel = el('constrained-panel');
    return premium && panel.open && !panel.classList.contains('hidden');
}
function updateConsole() {
    const custom = customActive();
    const generating = el('constrained-form').getAttribute('aria-busy') === 'true';
    const name = custom ? (customMethod.value === 'uniform' ? 'Aleatório uniforme' : 'Minhas regras') : el('selected-generation-mode-label').textContent;
    el('console-mode-name').textContent = name || 'Jogo normal';
    generateLabel.textContent = custom ? 'Gerar meu lote' : 'Gerar Jogos';
    quantity.max = custom ? customQuantity.max || '20' : '100';
    if (custom) quantity.value = customQuantity.value;
    quantity.disabled = busy || generating || custom && customFields.disabled;
    generate.disabled = busy || generating || custom && customFields.disabled;
    shelf.querySelectorAll('.lab-tool').forEach(button => { button.disabled = busy || generating; });
}
function updateTools() {
    shelf.querySelector('.lab-shelf').classList.toggle('is-premium', premium);
    for (const button of shelf.querySelectorAll('[data-premium]')) button.classList.toggle('hidden', !premium);
    let activeName = '';
    for (const button of tools) {
        const panel = el(button.dataset.labPanel);
        const open = panel.open && !panel.classList.contains('hidden') && (!button.hasAttribute('data-premium') || premium);
        button.setAttribute('aria-expanded', String(open)); button.classList.toggle('is-active', open);
        if (open) activeName = button.textContent.trim();
    }
    el('workbench-active-name').textContent = activeName;
    updateConsole();
}
export function syncWorkbenchAccess(user) { premium = Boolean(user?.is_premium); updateTools(); }
export function setWorkbenchBusy(value) {
    busy = value; shelf.querySelectorAll('.lab-tool').forEach(button => { button.disabled = value; }); updateConsole();
}
export function submitWorkbenchGeneration() {
    if (!customActive()) return false;
    if (!busy && !customFields.disabled) el('constrained-form').requestSubmit();
    return true;
}
tools.forEach(button => button.addEventListener('click', () => {
    if (busy || button.disabled || button.classList.contains('hidden')) return;
    const panel = el(button.dataset.labPanel), open = !panel.open;
    panels.forEach(other => { if (other !== panel) other.open = false; }); panel.open = open; updateTools();
    if (open) {
        const heading = panel.querySelector(':scope > summary'); heading.focus({ preventScroll: true });
        const rect = heading.getBoundingClientRect();
        if (rect.bottom > innerHeight || rect.top < 0) panel.scrollIntoView({ block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    }
}));
panels.forEach(panel => {
    panel.addEventListener('toggle', () => {
        if (panel.open && !panel.classList.contains('hidden')) panels.forEach(other => { if (other !== panel) other.open = false; });
        if (!panel.open && panel.contains(document.activeElement) && !panels.some(other => other.open)) tools.find(button => button.dataset.labPanel === panel.id)?.focus();
        updateTools();
    });
    new MutationObserver(updateTools).observe(panel, { attributes: true, attributeFilter: ['class'] });
    panel.addEventListener('keydown', event => {
        if (event.key === 'Escape') { event.preventDefault(); panel.open = false; tools.find(button => button.dataset.labPanel === panel.id)?.focus(); }
    });
});
quantity.addEventListener('input', () => { if (customActive()) customQuantity.value = quantity.value; });
customQuantity.addEventListener('input', updateConsole); customMethod.addEventListener('change', updateConsole);
new MutationObserver(updateConsole).observe(customFields, { attributes: true, attributeFilter: ['disabled'] });
new MutationObserver(updateConsole).observe(el('constrained-form'), { attributes: true, attributeFilter: ['aria-busy'] });
new MutationObserver(updateConsole).observe(customQuantity, { attributes: true, attributeFilter: ['max'] });
new MutationObserver(updateConsole).observe(el('selected-generation-mode-label'), { childList: true, subtree: true });
if (typeof ResizeObserver === 'function') new ResizeObserver(() => {
    document.body.style.setProperty('--console-height', `${Math.ceil(consoleBar.getBoundingClientRect().height)}px`);
}).observe(consoleBar);
