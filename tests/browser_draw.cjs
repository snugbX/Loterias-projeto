const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
let playwright;
try { playwright = require('playwright'); }
catch { playwright = require(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')); }

async function main() {
    const server = spawn(process.env.PYTHON || 'python', [path.join(__dirname, 'preview_server.py'), '5113'], { windowsHide: true, stdio: 'pipe' });
    let output = ''; server.stdout.on('data', d => { output += d; }); server.stderr.on('data', d => { output += d; });
    let browser;
    try {
        for (let n = 0; ; n++) {
            const ready = await new Promise(resolve => {
                const request = http.get('http://127.0.0.1:5113/', response => { response.resume(); response.on('end', () => resolve(response.statusCode === 200)); });
                request.on('error', () => resolve(false));
            });
            if (ready) break;
            if (n > 90 || server.exitCode !== null) throw new Error(output);
            await new Promise(resolve => setTimeout(resolve, 300));
        }
        browser = await playwright.chromium.launch({ headless: true, channel: 'msedge' });
        const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
        const errors = []; page.on('pageerror', e => errors.push(e.message));
        await page.goto('http://127.0.0.1:5113/');
        await page.evaluate(async () => {
            sessionStorage.setItem('snugbx-welcome-seen', '1');
            const response = await fetch('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: 'premium@example.com', password: 'PreviewTeste123!' }) });
            if (!response.ok) throw new Error('Login failed');
        });
        await page.reload();
        const fixtures = { megasena: [2, 15, 18, 23, 47, 55], lotofacil: Array.from({ length: 15 }, (_, i) => i + 1), quina: [1, 17, 39, 62, 80], diadesorte: [1, 5, 9, 14, 21, 28, 31, 'Setembro'] };
        let requests = 0, batchSize = 1, failure = false, delay = 1500;
        await page.route('**/gerar_jogos/*', async route => {
            requests++;
            const kind = route.request().url().split('/').at(-1).split('?')[0];
            if (delay) await new Promise(resolve => setTimeout(resolve, delay));
            return route.fulfill(failure ? { status: 422, json: { error: 'Falha de teste' } } : { json: { games: Array.from({ length: batchSize }, () => fixtures[kind]) } });
        });
        const close = page.locator('#generated-games-modal-close-btn');
        // The application uses the same control for all lotteries and account plans.
        const buttonId = await page.evaluate(() => [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Gerar Jogos')?.id);
        assert.ok(buttonId, 'Generation button exists');
        const trigger = page.locator(`#${buttonId}`);
        const picture = () => page.locator('#draw-canvas').evaluate(c => c.toDataURL());
        const finished = () => page.waitForFunction(() => !document.getElementById('generated-games-modal-overlay').classList.contains('hidden') && document.getElementById('draw-experience').classList.contains('is-complete'));
        for (const [kind, width, dark] of [['megasena', 1440, false], ['lotofacil', 390, true], ['quina', 320, false], ['diadesorte', 390, true]]) {
            await page.setViewportSize({ width, height: 1000 });
            if (await page.evaluate(() => document.body.classList.contains('dark-theme')) !== dark) await page.locator('#theme-toggle').click();
            await page.locator(`.lottery-option[data-lottery="${kind}"]`).click();
            await trigger.click();
            await page.waitForFunction(() => document.getElementById('draw-experience').dataset.phase === 'preparing');
            const loadingPicture = await picture(); await page.waitForTimeout(180);
            assert.notEqual(await picture(), loadingPicture, 'Preparation character moves during the real request');
            await page.locator('#draw-pause').click();
            const loadingPaused = await picture(); await page.waitForTimeout(80);
            assert.equal(await picture(), loadingPaused, 'Preparation can be paused without stopping the request');
            assert.match(await page.locator('#draw-status').innerText(), /geração continua no servidor/);
            await page.locator('#draw-pause').click();
            assert.equal(await page.locator('#draw-experience').getAttribute('data-charm'), { megasena: 'clover', lotofacil: 'ladybird', quina: 'horseshoe', diadesorte: 'lucky-cat' }[kind]);
            await page.locator('#generated-games-modal-overlay .modal-content').screenshot({ path: path.join(__dirname, `preparing-${kind}-${width}.png`) });
            await page.waitForFunction(() => document.querySelectorAll('.draw-slot.is-revealed').length > 0);
            const before = await picture();
            await page.waitForTimeout(100);
            assert.notEqual(await picture(), before, 'Canvas moves');
            await page.locator('#draw-pause').click();
            const paused = await picture();
            await page.waitForTimeout(140);
            assert.equal(await picture(), paused, 'Paused canvas is static');
            const hostFace = await page.locator('#draw-canvas').evaluate(c => {
                const pixel = c.getContext('2d').getImageData(Math.round(c.width * 77 / 720), Math.round(c.height * 140 / 350), 1, 1).data;
                return [...pixel];
            });
            assert.deepEqual(hostFace, [240, 198, 163, 255], 'Character remains fully visible during number reveal');
            assert.ok(await page.locator('#draw-canvas').evaluate(c => c.getContext('2d').getImageData(0, 0, c.width, c.height).data.some((v, i) => i % 4 === 3 && v > 0)), 'Canvas is nonblank');
            assert.equal(await page.locator('.draw-slot').count(), kind === 'lotofacil' ? 15 : kind === 'quina' ? 5 : kind === 'diadesorte' ? 7 : 6);
            assert.equal(await page.locator('.draw-month').count(), kind === 'diadesorte' ? 1 : 0);
            await page.locator('#generated-games-modal-overlay .modal-content').screenshot({ path: path.join(__dirname, `draw-${kind}-${width}.png`) });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'No page overflow');
            const clipped = await page.locator('#draw-experience').evaluate(root => [...root.querySelectorAll('p,h4,button,label,span')].filter(el => el.getClientRects().length && el.scrollWidth > el.clientWidth + 1).map(el => el.textContent));
            assert.deepEqual(clipped, [], 'All text fits');
            await page.locator('#draw-skip').click(); await finished();
            assert.ok(await page.locator('#generated-games-modal-overlay .modal-content').evaluate(node => node.getAnimations().length > 0), 'Result transition animates the existing panel');
            await page.waitForTimeout(350);
            assert.equal(await page.locator('#draw-experience').getAttribute('data-phase'), 'complete');
            assert.equal(await page.locator('#draw-canvas').isVisible(), true, 'Compact character and globe stay beside results');
            assert.ok(await page.locator('#draw-canvas').evaluate(c => c.getBoundingClientRect().width <= 250));
            await page.locator('#generated-games-modal-overlay .modal-content').screenshot({ path: path.join(__dirname, `complete-${kind}-${width}.png`) });
            const numbers = await page.locator('#jogos-gerados-modal-display .number-ball').allTextContents();
            assert.deepEqual(numbers, fixtures[kind].filter(n => typeof n === 'number').map(n => String(n).padStart(2, '0')));
            if (kind === 'diadesorte') assert.match(await page.locator('#jogos-gerados-modal-display').innerText(), /Setembro/);
            const count = requests;
            await page.locator('#draw-replay').click();
            await page.locator('#draw-skip').click();
            assert.equal(requests, count, 'Replay never requests or saves another game');
            await page.keyboard.press('Escape'); assert.equal(await close.isVisible(), false);
        }
        await page.setViewportSize({ width: 1440, height: 1000 });
        delay = 800;
        await trigger.click();
        await page.waitForFunction(() => document.getElementById('draw-experience').dataset.phase === 'preparing');
        await close.click(); await page.waitForTimeout(1100);
        assert.equal(await close.isVisible(), false, 'A dismissed preparation never reopens after the response');
        delay = 0;
        const singleStarted = Date.now();
        await trigger.click();
        await page.waitForFunction(() => document.getElementById('draw-experience').dataset.phase === 'revealing');
        assert.equal(await page.locator('#draw-experience').getAttribute('data-minimum-ms'), '5000');
        await finished();
        assert.ok(Date.now() - singleStarted >= 5000, 'Fast generation preserves the minimum visual time');
        await close.click();
        batchSize = 100;
        const batchStarted = Date.now();
        await trigger.click();
        await page.waitForFunction(() => document.querySelectorAll('#draw-batch-progress li').length === 3);
        await page.waitForFunction(() => document.getElementById('draw-experience').dataset.previewGame === '2');
        assert.match(await page.locator('#draw-batch-summary').innerText(), /3 dos 100/);
        await page.waitForFunction(() => document.getElementById('draw-experience').dataset.previewGame === '3');
        await finished();
        assert.ok(Date.now() - batchStarted >= 6500, 'Batch has a bounded minimum presentation, not one delay per game');
        assert.equal(await page.locator('#jogos-gerados-modal-display > div').count(), 100, 'All games remain available');
        assert.equal(await page.locator('.draw-game-title').count(), 100, 'Every game has its own number');
        await page.waitForTimeout(350);
        await page.locator('#generated-games-modal-overlay .modal-content').screenshot({ path: path.join(__dirname, 'complete-batch-1440.png') });
        await page.setViewportSize({ width: 320, height: 1000 });
        // Exercise the preference callback without clicking outside the modal.
        await page.locator('#increase-font').evaluate(button => button.click());
        assert.equal(await page.locator('.draw-game-title').count(), 100, 'Numbered batch survives font enlargement');
        const batchOverflow = await page.locator('#generated-games-modal-overlay .modal-content').evaluate(node => node.scrollWidth > node.clientWidth + 1);
        assert.equal(batchOverflow, false, 'Batch fits the narrow modal with enlarged text');
        await page.locator('#generated-games-modal-overlay .modal-content').screenshot({ path: path.join(__dirname, 'complete-batch-320.png') });
        await page.locator('#decrease-font').evaluate(button => button.click());
        await page.setViewportSize({ width: 1440, height: 1000 });
        assert.equal(await page.locator('#draw-replay').isVisible(), true);
        await page.locator('#copy-games-btn-modal').focus(); await page.keyboard.press('Tab');
        assert.equal(await close.evaluate(el => el === document.activeElement), true, 'Focus stays in modal');
        await close.click();
        batchSize = 1;
        await page.emulateMedia({ reducedMotion: 'reduce' });
        await trigger.click(); await finished();
        assert.equal(await page.locator('#draw-canvas').isVisible(), true, 'Reduced motion keeps a static illustration');
        const still = await picture(); await page.waitForTimeout(100); assert.equal(await picture(), still);
        assert.equal(await page.locator('#draw-replay').isVisible(), false);
        assert.equal(await page.locator('#draw-motion-note').isVisible(), true);
        await close.click();
        await page.emulateMedia({ reducedMotion: 'no-preference' });
        await trigger.click(); await page.locator('#draw-enabled').uncheck(); await finished();
        assert.equal(await page.evaluate(() => localStorage.getItem('snugbx-draw-animation')), 'off');
        await close.click();
        await trigger.click(); await finished();
        assert.equal(await page.locator('#draw-canvas').isVisible(), true);
        await close.click();
        await page.reload();
        await trigger.click(); await finished();
        assert.equal(await page.locator('#draw-enabled').isChecked(), false, 'Preference survives a reload');
        await close.click();
        await page.evaluate(() => localStorage.setItem('snugbx-draw-animation', 'on'));
        await page.addInitScript(() => {
            const original = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function (...args) {
                if (this.id === 'draw-canvas') throw new Error('Canvas unavailable');
                return original.apply(this, args);
            };
        });
        await page.reload();
        await trigger.click(); await finished();
        assert.equal(await page.locator('#draw-enabled').isChecked(), true);
        assert.equal(await page.locator('#draw-canvas').isVisible(), false, 'No Canvas falls back to results');
        assert.ok(await page.locator('#jogos-gerados-modal-display .number-ball').count() > 0);
        await close.click();
        failure = true;
        await trigger.click();
        await page.waitForTimeout(300);
        assert.equal(await close.isVisible(), false, 'Errors never start a fake reveal');
        assert.deepEqual(errors, []);
        console.log('Draw browser OK: all lotteries, exact results, moving/nonblank canvas, pause/skip/replay, themes/mobile, 100 games, reduced motion, preference, keyboard and errors.');
    } finally {
        await browser?.close(); server.kill();
        await new Promise(resolve => server.exitCode !== null ? resolve() : server.once('exit', resolve));
    }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
