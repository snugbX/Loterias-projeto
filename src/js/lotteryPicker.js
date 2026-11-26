import {lotteryDetails} from './dom.js';

const grid = document.getElementById('lottery-option-grid');
const native = document.getElementById('lottery-select');
const search = document.getElementById('lottery-search');
const clear = document.getElementById('lottery-clear-search');
const status = document.getElementById('lottery-picker-status');
const previous = document.getElementById('lottery-scroll-prev');
const next = document.getElementById('lottery-scroll-next');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const buttons = () => [...grid.querySelectorAll('.lottery-option')];
const normalize = text => text.normalize('NFD').replace(/\p{M}/gu, '').replace(/[^a-z0-9]/gi, '').toLowerCase();

function scrollState() {
    previous.disabled = grid.scrollLeft <= 2;
    next.disabled = grid.scrollLeft + grid.clientWidth >= grid.scrollWidth - 2;
}

export function syncLotteryPicker() {
    const visible = buttons().filter(button => !button.hidden);
    const selected = visible.find(button => button.getAttribute('aria-checked') === 'true') || visible[0];
    buttons().forEach(button => {button.tabIndex = button === selected ? 0 : -1;});
    const message = visible.length ? `${visible.length} ${visible.length === 1 ? 'modalidade disponível' : 'modalidades disponíveis'}` : 'Nenhuma loteria encontrada.';
    if (status.textContent !== message) status.textContent = message;
    scrollState();
}

export function revealLotteryOption(kind) {
    const button = buttons().find(button => button.dataset.lottery === kind && !button.hidden);
    if (!button) return;
    const viewport = grid.getBoundingClientRect(), rect = button.getBoundingClientRect();
    const left = rect.left < viewport.left + 6 ? rect.left - viewport.left - 6 : rect.right > viewport.right - 6 ? rect.right - viewport.right + 6 : 0;
    if (left) grid.scrollBy({left, behavior: reduced.matches ? 'auto' : 'smooth'});
}

export function initLotteryPicker() {
    const selected = native.value;
    native.replaceChildren(); grid.replaceChildren();
    for (const [kind, detail] of Object.entries(lotteryDetails)) {
        const option = document.createElement('option'); option.value = kind; option.textContent = detail.name; native.append(option);
        const button = document.createElement('button'); button.type = 'button'; button.className = 'lottery-option'; button.dataset.lottery = kind;
        button.setAttribute('role', 'radio'); button.setAttribute('aria-checked', 'false'); button.tabIndex = -1;
        const top = document.createElement('span'); top.className = 'lottery-option-topline';
        const icon = document.createElement('span'); icon.className = 'lab-icon'; icon.style.setProperty('--icon', "url('icons/lucide/ticket.svg')"); icon.setAttribute('aria-hidden', 'true');
        const kicker = document.createElement('span'); kicker.className = 'lottery-option-kicker'; kicker.textContent = 'APOSTA SIMPLES';
        const check = document.createElement('span'); check.className = 'lottery-option-check'; check.setAttribute('aria-hidden', 'true');
        top.append(icon, kicker, check);
        const name = document.createElement('span'); name.className = 'lottery-option-name'; name.textContent = detail.name;
        const meta = document.createElement('span'); meta.className = 'lottery-option-meta'; meta.textContent = detail.summary;
        button.append(top, name, meta); grid.append(button);
    }
    if (lotteryDetails[selected]) native.value = selected;
    search.addEventListener('input', () => {
        const query = normalize(search.value);
        buttons().forEach(button => {button.hidden = !normalize(button.textContent).includes(query);});
        clear.classList.toggle('hidden', !search.value);
        grid.scrollTo({left: 0, behavior: 'auto'}); syncLotteryPicker();
    });
    clear.addEventListener('click', () => {search.value = ''; search.dispatchEvent(new Event('input')); search.focus();});
    grid.addEventListener('scroll', scrollState, {passive: true});
    previous.addEventListener('click', () => grid.scrollBy({left: -Math.max(200, grid.clientWidth * .75), behavior: reduced.matches ? 'auto' : 'smooth'}));
    next.addEventListener('click', () => grid.scrollBy({left: Math.max(200, grid.clientWidth * .75), behavior: reduced.matches ? 'auto' : 'smooth'}));
    new ResizeObserver(scrollState).observe(grid);
    syncLotteryPicker();
}
