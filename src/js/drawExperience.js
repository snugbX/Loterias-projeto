import { lotteryColors } from './dom.js';
import { formatLotteryName } from './render.js';

// TEMPO MÍNIMO VISUAL: altere aqui (milissegundos). Não atrasa a API nem impede pular.
const MIN_PRESENTATION_MS = 5000;
const MIN_BATCH_PRESENTATION_MS = 6500;
const MIX_MS = 900;
const MAX_PREVIEW_GAMES = 3;
const FORMATS = {
    megasena: { count: 6, maximum: 60, label: '6 dezenas · 01 a 60' },
    lotofacil: { count: 15, maximum: 25, label: '15 dezenas · 01 a 25' },
    quina: { count: 5, maximum: 80, label: '5 dezenas · 01 a 80' },
    diadesorte: { count: 7, maximum: 31, label: '7 dezenas + Mês da Sorte' },
};
const el = id => document.getElementById(id);
const root = el('draw-experience');
const overlay = el('generated-games-modal-overlay');
const canvas = el('draw-canvas');
let ctx = null;
try { ctx = canvas.getContext('2d'); } catch { /* Results must work when Canvas is blocked. */ }
let renderingAvailable = Boolean(ctx);
const preview = el('draw-preview');
const status = el('draw-status');
const enabled = el('draw-enabled');
const pause = el('draw-pause');
const skip = el('draw-skip');
const replay = el('draw-replay');
const results = el('jogos-gerados-modal-display');
const batchSummary = el('draw-batch-summary');
const batchProgress = el('draw-batch-progress');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
let frame = 0;
let elapsed = 0;
let previous = null;
let active = false;
let paused = false;
let snapshot = null;
let revealed = -1;
let previewIndex = 0;
let returnFocus = null;
let scene = null;
let preparing = false;
let preparation = null;
let settlement = 0;
let transitions = [];
const content = overlay.querySelector('.modal-content');
try { enabled.checked = localStorage.getItem('snugbx-draw-animation') !== 'off'; } catch { /* Storage can be unavailable in private mode. */ }

function stopFrame() { cancelAnimationFrame(frame); frame = 0; previous = null; }
function canAnimate() { return renderingAvailable && enabled.checked && !reduced.matches; }

function cancelSettlement() {
    settlement++;
    transitions.forEach(animation => animation.cancel()); transitions = [];
}

function finish(announce = true) {
    cancelSettlement();
    stopFrame(); active = false; paused = false;
    const focused = document.activeElement === pause || document.activeElement === skip;
    const reveal = () => {
        pause.hidden = true; skip.hidden = true; replay.hidden = !canAnimate();
        pause.disabled = false; skip.disabled = false; pause.textContent = 'Pausar';
        root.classList.add('is-complete'); results.hidden = false;
        root.classList.toggle('has-illustration', renderingAvailable);
        batchProgress.hidden = true;
        if (snapshot?.games.length > 1) batchSummary.textContent = `${snapshot.games.length} jogos · lote completo`;
        try { paint(elapsed / 1000, 1); } catch { renderingAvailable = false; root.classList.remove('has-illustration'); }
        root.dataset.phase = 'complete';
        if (snapshot && announce) status.textContent = `${snapshot.games.length === 1 ? 'Seu jogo está pronto' : `Seus ${snapshot.games.length} jogos estão prontos`}. Confira as dezenas abaixo.`;
        if (focused) (replay.hidden ? enabled : replay).focus();
    };
    if (announce && snapshot && canAnimate() && !overlay.classList.contains('hidden') && typeof content.animate === 'function') {
        root.dataset.phase = 'settling'; pause.disabled = true; skip.disabled = true;
        const version = settlement;
        const fades = [...root.querySelectorAll('.draw-scene, .draw-preview')].map(node => node.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 160, fill: 'forwards' }));
        transitions.push(...fades);
        Promise.all(fades.map(animation => animation.finished)).then(() => {
            if (version !== settlement) return;
            const height = content.getBoundingClientRect().height;
            reveal();
            fades.forEach(animation => animation.cancel());
            const nextHeight = content.getBoundingClientRect().height;
            transitions.push(content.animate([{ height: `${height}px`, overflow: 'hidden' }, { height: `${nextHeight}px`, overflow: 'hidden' }], { duration: 320, easing: 'cubic-bezier(.2,.7,.2,1)' }),
                results.animate([{ opacity: 0, transform: 'translateY(5px)' }, { opacity: 1, transform: 'none' }], { duration: 300, easing: 'ease-out' }));
            if (renderingAvailable) transitions.push(root.querySelector('.draw-scene').animate([{ opacity: 0 }, { opacity: 1 }], { duration: 300 }));
        }).catch(() => {});
    } else reveal();
}

function updatePreference() {
    el('draw-motion-note').hidden = !reduced.matches;
    replay.hidden = active || !snapshot || !canAnimate();
    if (!canAnimate() && preparing) {
        stopFrame(); active = false; pause.hidden = true; skip.hidden = true;
        try { paint(0, 0); } catch { renderingAvailable = false; }
    } else if (!canAnimate() && (active || transitions.length)) finish();
}

function charm(kind, x, y, color) {
    ctx.save(); ctx.translate(x, y); ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 4;
    if (kind === 'megasena') {
        for (const [dx, dy] of [[-7,-7],[7,-7],[-7,7],[7,7]]) { ctx.beginPath(); ctx.arc(dx,dy,8,0,Math.PI*2); ctx.fill(); }
        ctx.beginPath(); ctx.moveTo(0,6); ctx.quadraticCurveTo(4,18,-4,22); ctx.stroke();
    } else if (kind === 'quina') {
        ctx.beginPath(); ctx.moveTo(-12,-14); ctx.lineTo(-12,4); ctx.bezierCurveTo(-12,23,12,23,12,4); ctx.lineTo(12,-14); ctx.stroke();
        for (const dx of [-12,12]) for (const dy of [-9,1,10]) { ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(dx,dy,1.5,0,Math.PI*2); ctx.fill(); }
    } else if (kind === 'lotofacil') {
        ctx.beginPath(); ctx.ellipse(0,3,14,17,0,0,Math.PI*2); ctx.fill();
        ctx.fillStyle = '#24353b'; ctx.beginPath(); ctx.arc(0,-12,8,0,Math.PI*2); ctx.fill();
        ctx.beginPath(); ctx.moveTo(0,-6); ctx.lineTo(0,19); ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke();
        for (const [dx,dy] of [[-7,0],[7,0],[-7,10],[7,10]]) { ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(dx,dy,2.5,0,Math.PI*2); ctx.fill(); }
    } else {
        ctx.beginPath(); ctx.moveTo(-14,-4); ctx.lineTo(-12,-19); ctx.lineTo(-2,-10); ctx.lineTo(7,-11); ctx.lineTo(15,-19); ctx.lineTo(16,-2); ctx.closePath(); ctx.fill();
        ctx.beginPath(); ctx.ellipse(1,3,16,14,0,0,Math.PI*2); ctx.fill();
        ctx.fillStyle = '#fff'; for (const dx of [-5,7]) { ctx.beginPath(); ctx.arc(dx,1,2,0,Math.PI*2); ctx.fill(); }
        ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(0,7); ctx.lineTo(4,7); ctx.stroke();
    }
    ctx.restore();
}

function host(time, colors, ink) {
    const cycle = (time / 1.6) % 1;
    const lift = preparing ? Math.min(1, cycle / .38) : .85 + Math.sin(time * 3) * .05;
    const wristX = 115 + 26 * lift, wristY = 251 - 133 * lift;
    ctx.save();
    ctx.strokeStyle = ink; ctx.lineWidth = 13; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(59,264); ctx.lineTo(54,300); ctx.moveTo(93,264); ctx.lineTo(101,300); ctx.stroke();
    ctx.fillStyle = colors.ball; ctx.beginPath(); ctx.roundRect(39,181,76,88,18); ctx.fill();
    ctx.strokeStyle = colors.ball; ctx.lineWidth = 15;
    ctx.beginPath(); ctx.moveTo(106,196); ctx.lineTo(133,194 - lift*32); ctx.lineTo(wristX,wristY); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(43,197); ctx.lineTo(27,225); ctx.lineTo(51,242); ctx.stroke();
    ctx.fillStyle = '#f0c6a3'; ctx.beginPath(); ctx.arc(77,148,31,0,Math.PI*2); ctx.fill();
    ctx.fillStyle = ink; ctx.beginPath(); ctx.ellipse(76,130,34,17,-.1,Math.PI,Math.PI*2); ctx.fill();
    ctx.fillStyle = '#24353b'; for (const x of [67,88]) { ctx.beginPath(); ctx.arc(x,148,3,0,Math.PI*2); ctx.fill(); }
    ctx.strokeStyle = '#69452f'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(78,153,10,.2,Math.PI-.2); ctx.stroke();
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.roundRect(52,201,50,49,10); ctx.fill();
    charm(scene.lotteryType,77,224,colors.ball);
    ctx.fillStyle = '#f0c6a3'; ctx.beginPath(); ctx.arc(wristX,wristY,9,0,Math.PI*2); ctx.fill();
    ctx.strokeStyle = ink; ctx.lineWidth = 3; ctx.strokeRect(14,260,112,28);
    for (let i=0;i<4;i++) ball(30+i*25,258,13,String((i*7)%scene.format.maximum+1).padStart(2,'0'),colors.ball);
    if (preparing && cycle < .38) ball(wristX,wristY-13,14,String((Math.floor(time/1.6)*7)%scene.format.maximum+1).padStart(2,'0'),colors.ball);
    else if (preparing && cycle < .86) {
        const t=(cycle-.38)/.48;
        ball((1-t)**2*141+2*(1-t)*t*220+t*t*282,(1-t)**2*105+2*(1-t)*t*(-10)+t*t*75,14,String((Math.floor(time/1.6)*7)%scene.format.maximum+1).padStart(2,'0'),colors.ball);
    }
    ctx.restore();
}

function ball(x, y, radius, label, color) {
    const shade = ctx.createRadialGradient(x - radius * .3, y - radius * .4, 1, x, y, radius);
    shade.addColorStop(0, '#ffffff'); shade.addColorStop(.22, '#f1f5f9'); shade.addColorStop(1, '#b9c5cb');
    ctx.beginPath(); ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fillStyle = shade; ctx.fill();
    ctx.beginPath(); ctx.arc(x, y, radius * .7, 0, Math.PI * 2);
    ctx.fillStyle = color; ctx.fill();
    ctx.fillStyle = '#ffffff'; ctx.font = `700 ${radius * .68}px system-ui`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(label, x, y + 1);
}

// Ilustração 2D: trajetórias decorativas, não um motor físico de sorteio.
function paint(time, progress) {
    if (!ctx || !scene) return;
    const dark = document.body.classList.contains('dark-theme');
    const ink = dark ? '#dce8ed' : '#314b52';
    const line = dark ? '#708b95' : '#98acb1';
    const { format, colors, first } = scene;
    const width = Math.round((canvas.clientWidth || 720) * Math.min(devicePixelRatio || 1, 2));
    const scale = width / 720;
    if (canvas.width !== width) { canvas.width = width; canvas.height = Math.round(350 * scale); }
    ctx.setTransform(scale, 0, 0, scale, 0, 0); ctx.clearRect(0, 0, 720, 350);
    const x = 282, y = 152, radius = 120;
    ctx.strokeStyle = line; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(177, 305); ctx.lineTo(221, 245); ctx.moveTo(387, 305); ctx.lineTo(343, 245); ctx.stroke();
    ctx.fillStyle = ink; ctx.beginPath(); ctx.roundRect(164, 301, 236, 12, 6); ctx.fill();
    ctx.save(); ctx.beginPath(); ctx.arc(x, y, radius - 5, 0, Math.PI * 2); ctx.clip();
    ctx.fillStyle = dark ? '#1a3037' : '#eaf3f2'; ctx.fillRect(x-radius,y-radius,radius*2,radius*2);
    for (let i = 0; i < 22; i++) {
        const angle = i * 2.399 + time * (.65 + (i % 3) * .09);
        const distance = 25 + (i % 6) * 14;
        ball(x + Math.cos(angle) * distance, y + Math.sin(angle * 1.3 + i) * distance * .82,
            16, String((i * 7) % format.maximum + 1).padStart(2, '0'), colors.ball);
    }
    ctx.strokeStyle = line; ctx.globalAlpha = .6; ctx.lineWidth = 1.5;
    for (let i = 0; i < 4; i++) {
        ctx.beginPath(); ctx.ellipse(x, y, Math.max(8, Math.abs(Math.cos(time * .55 + i * Math.PI / 4)) * radius), radius, 0, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.beginPath(); ctx.ellipse(x, y, radius, 39, -.22, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
    ctx.strokeStyle = ink; ctx.lineWidth = 5; ctx.beginPath(); ctx.arc(x,y,radius,0,Math.PI*2); ctx.stroke();
    ctx.strokeStyle = line; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(x,y,radius + 8,0,Math.PI*2); ctx.stroke();
    ctx.fillStyle = ink; ctx.beginPath(); ctx.roundRect(386, 190, 26, 23, 5); ctx.fill();
    ctx.strokeStyle = ink; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(408, 210); ctx.lineTo(444, 256); ctx.lineTo(575, 256); ctx.stroke();
    const step = progress * first.length;
    if (progress > 0 && progress < 1) {
        const local = step % 1, index = Math.min(first.length - 1, Math.floor(step));
        const travel = 1 - (1 - local) ** 3;
        const value = first[index];
        ball(410 + travel * 127, 208 + travel * 27 - Math.sin(local * Math.PI) * 25, 25,
            typeof value === 'number' ? String(value).padStart(2, '0') : 'MÊS', colors.ball);
    }
    ctx.fillStyle = ink; ctx.font = '700 13px system-ui'; ctx.textAlign = 'center';
    ctx.fillText('SEU JOGO', 510, 285);
    ctx.fillStyle = colors.ball; ctx.fillRect(479, 299, 64 * progress, 5);
    host(time,colors,ink);
}

function renderPreview(count) {
    if (count === revealed) return;
    revealed = count;
    [...preview.children].forEach((slot, index) => {
        const value = scene.first[index];
        slot.classList.toggle('is-revealed', index < count);
        slot.textContent = index < count ? (typeof value === 'number' ? String(value).padStart(2, '0') : value) : (index < scene.format.count ? '·' : 'Mês');
    });
    const prefix = snapshot?.games.length > 1 ? `Jogo ${String(previewIndex + 1).padStart(2, '0')}` : 'Seu jogo';
    if (count > 0) status.textContent = count <= scene.format.count
        ? `${prefix}: ${count} de ${scene.format.count} dezenas reveladas.`
        : `${prefix} · Mês da Sorte: ${scene.first.at(-1)}.`;
}

export function refreshDrawResultLabels() {
    const games = snapshot?.games;
    if (!games) return;
    results.classList.toggle('draw-results-batch', games.length > 1);
    [...results.children].forEach((row, index) => {
        row.querySelector('.draw-game-title')?.remove();
        if (games.length < 2) return;
        row.setAttribute('aria-label', `Jogo ${index + 1}`);
        const title = document.createElement('strong'); title.className = 'draw-game-title';
        title.textContent = `Jogo ${String(index + 1).padStart(2, '0')}`; row.prepend(title);
    });
}

function configureBatch() {
    const games = snapshot.games;
    refreshDrawResultLabels();
    batchSummary.hidden = games.length < 2; batchProgress.hidden = games.length < 2;
    batchProgress.replaceChildren();
    if (games.length < 2) return;
    const count = Math.min(MAX_PREVIEW_GAMES, games.length);
    batchSummary.textContent = games.length > count ? `Prévia de ${count} dos ${games.length} jogos` : `${games.length} jogos · revelação em sequência`;
    for (let index = 0; index < count; index++) {
        const step = document.createElement('li'); step.textContent = `Jogo ${String(index + 1).padStart(2, '0')}`;
        batchProgress.append(step);
    }
}

function setPreviewGame(index) {
    if (index !== previewIndex) { previewIndex = index; scene.first = snapshot.games[index]; revealed = -1; }
    root.dataset.previewGame = String(index + 1);
    [...batchProgress.children].forEach((step, number) => {
        step.classList.toggle('is-current', number === index); step.classList.toggle('is-done', number < index);
        if (number === index) step.setAttribute('aria-current', 'step'); else step.removeAttribute('aria-current');
    });
}

function tick(now) {
    frame = 0;
    if (!active || paused || document.hidden) return;
    if (previous !== null) elapsed += Math.min(now - previous, 80);
    previous = now;
    const duration = snapshot?.games.length > 1 ? MIN_BATCH_PRESENTATION_MS : MIN_PRESENTATION_MS;
    const totalProgress = preparing ? 0 : Math.min(1, Math.max(0, (elapsed - MIX_MS) / (duration - MIX_MS)));
    const count = preparing ? 1 : Math.min(MAX_PREVIEW_GAMES, snapshot.games.length);
    const position = totalProgress * count;
    if (!preparing) setPreviewGame(Math.min(count - 1, Math.floor(position)));
    const progress = preparing ? 0 : Math.min(1, (totalProgress === 1 ? 1 : position % 1) / .85);
    try {
        paint(elapsed / 1000, progress);
        if (!preparing) renderPreview(Math.floor(progress * scene.first.length));
    } catch {
        renderingAvailable = false;
        if (preparing) { stopFrame(); active = false; pause.hidden = true; skip.hidden = true; root.classList.add('is-waiting-quiet'); }
        else finish();
        return;
    }
    if (!preparing && totalProgress === 1) { finish(); return; }
    frame = requestAnimationFrame(tick);
}

function start(previousHeight = null) {
    cancelSettlement(); preparing = false; root.classList.remove('is-preparing', 'is-waiting-quiet');
    stopFrame(); elapsed = 0; revealed = -1; paused = false;
    previewIndex = 0; scene.first = snapshot.games[0];
    root.classList.remove('is-complete');
    root.dataset.phase = 'revealing';
    root.dataset.minimumMs = String(snapshot.games.length > 1 ? MIN_BATCH_PRESENTATION_MS : MIN_PRESENTATION_MS);
    configureBatch(); setPreviewGame(0);
    preview.replaceChildren();
    scene.first.forEach((value, index) => {
        const slot = document.createElement('span'); slot.className = index < scene.format.count ? 'draw-slot' : 'draw-month'; preview.append(slot);
    });
    renderPreview(0);
    if (!canAnimate()) { finish(); return; }
    active = true; results.hidden = true;
    pause.hidden = false; skip.hidden = false; replay.hidden = true; pause.textContent = 'Pausar';
    skip.textContent = 'Ver jogos agora';
    status.textContent = snapshot.games.length > 1 ? 'Lote gerado. Começando a revelação dos jogos...' : 'Jogo gerado. Começando a revelação...';
    try { paint(0, 0); } catch { renderingAvailable = false; finish(); return; }
    if (previousHeight !== null && typeof content.animate === 'function') {
        transitions.push(content.animate([{ height: `${previousHeight}px`, overflow: 'hidden' }, { height: `${content.getBoundingClientRect().height}px`, overflow: 'hidden' }], { duration: 320, easing: 'ease-out' }));
    }
    if (!document.hidden) frame = requestAnimationFrame(tick);
}

function configureScene(lotteryType, first = []) {
    const format = FORMATS[lotteryType];
    scene = { format, colors: lotteryColors[lotteryType], first, lotteryType };
    const colors = scene.colors;
    root.hidden = false; root.dataset.lottery = lotteryType;
    root.style.setProperty('--draw-ball', colors.ball);
    root.style.setProperty('--draw-ink', document.body.classList.contains('dark-theme') ? colors.readableDark : colors.readable);
    root.style.setProperty('--draw-soft', document.body.classList.contains('dark-theme') ? colors.softBgDark : colors.softBg);
    el('draw-lottery-name').textContent = formatLotteryName(lotteryType);
    el('draw-format').textContent = format.label;
    const charms = { megasena: 'TREVO DE QUATRO FOLHAS', lotofacil: 'JOANINHA', quina: 'FERRADURA', diadesorte: 'GATO DA SORTE' };
    root.dataset.charm = lotteryType === 'megasena' ? 'clover' : lotteryType === 'lotofacil' ? 'ladybird' : lotteryType === 'quina' ? 'horseshoe' : 'lucky-cat';
    root.querySelector('.draw-scene-label').textContent = preparing ? `SNUGBX · ${charms[lotteryType]}` : 'SNUGBX · ESTÚDIO DE PALPITES';
}

export function beginDrawPreparation(lotteryType) {
    finish(false); preparing = true; snapshot = null; elapsed = 0; paused = false;
    preparation = { dismissed: false };
    configureScene(lotteryType);
    returnFocus = document.activeElement;
    root.classList.remove('is-complete', 'is-waiting-quiet'); root.classList.add('is-preparing');
    root.dataset.phase = 'preparing';
    preview.replaceChildren(); results.hidden = true;
    batchSummary.hidden = true; batchProgress.hidden = true;
    el('copy-games-btn-modal').classList.add('hidden');
    status.textContent = 'Preparando seu jogo. Aguardando a resposta da geração...';
    el('generated-games-modal-title').textContent = 'Preparando seus jogos';
    overlay.classList.remove('hidden'); overlay.setAttribute('aria-hidden','false');
    replay.hidden = true; pause.hidden = !canAnimate(); skip.hidden = !canAnimate();
    pause.textContent = 'Pausar'; skip.textContent = 'Ocultar animação';
    el('draw-motion-note').hidden = !reduced.matches;
    active = canAnimate();
    try { paint(0,0); } catch { renderingAvailable = false; active = false; pause.hidden = true; skip.hidden = true; }
    if (!renderingAvailable) root.classList.add('is-waiting-quiet');
    if (active && !document.hidden) frame = requestAnimationFrame(tick);
    el('generated-games-modal-close-btn').focus();
    return preparation;
}

export function cancelDrawPreparation(ticket) {
    if (ticket !== preparation) return;
    preparing = false; preparation = null; finish(false);
    overlay.classList.add('hidden'); overlay.setAttribute('aria-hidden','true');
}

export function presentDrawExperience(games, lotteryType, ticket) {
    if (ticket?.dismissed) return false;
    const previousHeight = preparing ? content.getBoundingClientRect().height : null;
    cancelSettlement(); stopFrame(); active = false; paused = false;
    preparation = null; preparing = false;
    const format = FORMATS[lotteryType];
    if (!format || !games?.length) { root.hidden = true; return false; }
    snapshot = { games, lotteryType };
    configureScene(lotteryType, games[0]);
    el('generated-games-modal-title').textContent = 'Seus Jogos Gerados';
    updatePreference(); start(previousHeight);
    return true;
}

pause.addEventListener('click', () => {
    paused = !paused; stopFrame(); pause.textContent = paused ? 'Continuar' : 'Pausar';
    status.textContent = paused
        ? (preparing ? 'Preparação pausada. A geração continua no servidor.' : 'Apresentação pausada. Seus jogos já estão gerados.')
        : (preparing ? 'Preparando seu jogo. Aguardando a resposta da geração...' : 'Continuando a revelação dos jogos...');
    if (!paused && active && !document.hidden) frame = requestAnimationFrame(tick);
});
skip.addEventListener('click', () => {
    if (preparing) { stopFrame(); active = false; root.classList.add('is-waiting-quiet'); pause.hidden = true; skip.hidden = true; enabled.focus(); }
    else finish();
});
replay.addEventListener('click', () => { start(); if (active) pause.focus(); });
enabled.addEventListener('change', () => {
    try { localStorage.setItem('snugbx-draw-animation', enabled.checked ? 'on' : 'off'); } catch { /* Preference stays valid for this session. */ }
    updatePreference();
});
reduced.addEventListener('change', updatePreference);
document.addEventListener('visibilitychange', () => {
    stopFrame();
    if (active && !paused && !document.hidden) frame = requestAnimationFrame(tick);
});
new MutationObserver(() => {
    if (overlay.classList.contains('hidden')) {
        if (preparation) preparation.dismissed = true;
        preparing = false; finish(false);
    }
}).observe(overlay, { attributes: true, attributeFilter: ['class'] });
overlay.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
        event.preventDefault(); el('generated-games-modal-close-btn').click();
        if (returnFocus?.isConnected && !returnFocus.disabled) returnFocus.focus();
    }
    if (event.key !== 'Tab') return;
    const controls = [...overlay.querySelectorAll('button,input,[href],[tabindex="0"]')].filter(node => !node.disabled && node.getClientRects().length);
    const first = controls[0], last = controls.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});
