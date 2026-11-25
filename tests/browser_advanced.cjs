const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
let playwright;
try { playwright = require('playwright'); }
catch { playwright = require(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')); }

async function main() {
    const server = spawn(process.env.PYTHON || 'python', [path.join(__dirname, 'preview_server.py'), '5112'], { windowsHide: true, stdio: 'pipe' });
    let output = ''; server.stdout.on('data', d => { output += d; }); server.stderr.on('data', d => { output += d; });
    let browser;
    try {
        for (let n = 0; ; n++) {
            const ready = await new Promise(resolve => {
                const request = http.get('http://127.0.0.1:5112/', response => { response.resume(); response.on('end', () => resolve(response.statusCode === 200)); });
                request.on('error', () => resolve(false));
            });
            if (ready) break;
            if (n > 90 || server.exitCode !== null) throw new Error(output);
            await new Promise(resolve => setTimeout(resolve, 300));
        }
        browser = await playwright.chromium.launch({ headless: true, channel: 'msedge' });
        const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
        const errors = []; page.on('pageerror', e => errors.push(e.message));
        await page.goto('http://127.0.0.1:5112/');
        await page.evaluate(() => sessionStorage.setItem('snugbx-welcome-seen', '1'));
        async function login(plan) {
            await page.evaluate(async plan => {
                const r = await fetch('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: `${plan}@example.com`, password: 'PreviewTeste123!' }) });
                if (!r.ok) throw new Error('Login failed');
            }, plan);
            await page.reload();
            await page.waitForFunction(() => !document.getElementById('app-shell').classList.contains('hidden'));
        }
        await login('premium');
        await page.locator('#generation-mode-toggle').click();
        await page.waitForFunction(() => document.querySelectorAll('[data-generation-mode]').length === 11);
        for (const width of [1440, 390, 320]) {
            await page.setViewportSize({ width, height: 1000 });
            for (const dark of [false, true]) {
                if (await page.evaluate(() => document.body.classList.contains('dark-theme')) !== dark) await page.locator('#theme-toggle').click();
                await page.locator('#generation-mode-section').screenshot({ path: path.join(__dirname, `strategies-${width}-${dark ? 'dark' : 'light'}.png`) });
                assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `Strategy overflow at ${width}`);
                const clipped = await page.locator('#generation-mode-section').evaluate(panel => [...panel.querySelectorAll('strong,span,button')]
                    .filter(el => el.getClientRects().length && el.scrollWidth > el.clientWidth + 1).map(el => el.textContent));
                assert.deepEqual(clipped, [], `Clipped strategy labels at ${width}`);
            }
        }
        await page.setViewportSize({ width: 1440, height: 1000 });
        await page.locator('[data-generation-mode="balanced_parity"]').click();
        assert.match(await page.locator('#selected-generation-mode-label').innerText(), /Pares e ímpares/);
        await page.locator('#generation-mode-toggle').click();
        await page.locator('[data-generation-mode="never_prize"]').click();
        assert.match(await page.locator('#selected-generation-mode-label').innerText(), /Filtro histórico forte/);
        await page.locator('#generation-mode-toggle').click();
        await page.locator('[data-generation-mode="normal"]').focus();
        await page.keyboard.press('ArrowRight');
        assert.equal(await page.locator('[data-generation-mode="balanced_never_prize"]').getAttribute('aria-checked'), 'true');
        await page.keyboard.press('ArrowLeft');
        await page.locator('[data-strategy-tool="uniform"]').click();
        await page.waitForFunction(() => !document.getElementById('constrained-fields').disabled);
        assert.equal(await page.locator('#constrained-method').inputValue(), 'uniform');
        assert.equal(await page.locator('#constrained-rules').isVisible(), false);
        await page.locator('#generation-mode-toggle').click();
        await page.locator('[data-strategy-tool="constraints"]').click();
        assert.equal(await page.locator('#constrained-method').inputValue(), 'constraints');
        assert.equal(await page.locator('#constrained-rules').isVisible(), true);
        await page.locator('#research-report-panel').evaluate(p => { p.open = true; });
        await page.waitForFunction(() => document.getElementById('research-report-status').textContent.includes('Relatório gerado'));
        assert.match(await page.locator('#research-report-content').innerText(), /falsas descobertas/);
        await page.locator('#research-report-content').getByText('Laboratório de estratégias', { exact: true }).click();
        assert.equal(await page.locator('#research-report-content table').first().locator('tbody tr').count(), 6);
        assert.match(await page.locator('#research-report-content').innerText(), /Não é taxa de prêmios/);
        await page.locator('#draw-digest-panel').evaluate(p => { p.open = true; });
        await page.waitForFunction(() => document.querySelectorAll('#draw-digest-content article').length === 4);
        await page.locator('#constrained-panel').evaluate(p => { p.open = true; });
        await page.waitForFunction(() => !document.getElementById('constrained-fields').disabled);
        await page.locator('#constrained-quantity').fill('3');
        await page.locator('#constrained-fixed').fill('2 15');
        await page.locator('#constrained-excluded').fill('60');
        await page.locator('#constrained-parity').selectOption('3');
        await page.locator('#constrained-overlap').fill('3');
        await page.locator('#constrained-min-sum').fill('100');
        await page.locator('#constrained-max-sum').fill('200');
        const result = page.waitForResponse(r => r.url().endsWith('/generate_constrained/megasena') && r.request().method() === 'POST');
        await page.locator('#constrained-form button[type="submit"]').click();
        const response = await result; assert.equal(response.status(), 200); const batch = await response.json();
        assert.equal(batch.games.length, 3);
        batch.games.forEach(game => { assert.ok(game.includes(2) && game.includes(15) && !game.includes(60)); assert.equal(game.filter(n => n % 2 === 0).length, 3); });
        assert.ok(batch.portfolio.max_overlap <= 3);
        await page.locator('#generated-games-modal-close-btn').click();
        await page.getByRole('button', { name: 'Consultar e comparar este lote' }).click();
        await page.waitForFunction(() => document.getElementById('analysis-feedback').textContent === 'Consulta concluída.');
        assert.equal(await page.locator('.analysis-game-detail').count(), 3);
        await page.locator('#constrained-panel').evaluate(p => { p.open = true; });
        for (const width of [1440, 390, 320]) {
            await page.setViewportSize({ width, height: 1000 });
            for (const dark of [false, true]) {
                if (await page.evaluate(() => document.body.classList.contains('dark-theme')) !== dark) await page.locator('#theme-toggle').click();
                await page.locator('#constrained-panel').screenshot({ path: path.join(__dirname, `constrained-${width}-${dark ? 'dark' : 'light'}.png`) });
                assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `Page overflow at ${width}`);
                const clipped = await page.locator('#constrained-panel').evaluate(panel => [...panel.querySelectorAll('p,label,summary,button')]
                    .filter(el => el.getClientRects().length && el.scrollWidth > el.clientWidth + 1).map(el => el.textContent));
                assert.deepEqual(clipped, [], `Clipped controls at ${width}`);
            }
        }
        await page.locator('#research-report-panel').evaluate(p => { p.open = true; });
        await page.locator('#research-report-panel').screenshot({ path: path.join(__dirname, 'research-mobile-dark.png') });
        await page.locator('#draw-digest-panel').screenshot({ path: path.join(__dirname, 'digest-mobile-dark.png') });
        await page.locator('#increase-font').click();
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'Enlarged text overflows');
        await page.locator('#decrease-font').click();
        await page.setViewportSize({ width: 1440, height: 1000 });
        // Incompatible numeric filters must not accidentally constrain the uniform mode.
        await page.locator('#constrained-panel').evaluate(p => { p.open = true; });
        await page.locator('#constrained-min-sum').fill('9999');
        await page.locator('#constrained-method').selectOption('uniform');
        const uniformResponse = page.waitForResponse(r => r.url().endsWith('/generate_constrained/megasena') && r.request().method() === 'POST');
        await page.locator('#constrained-form button[type="submit"]').click();
        const uniform = await uniformResponse; assert.equal(uniform.status(), 200);
        assert.deepEqual(Object.keys(uniform.request().postDataJSON()).sort(), ['method', 'num_games']);
        await page.locator('#generated-games-modal-close-btn').click();
        await page.locator('button[data-lottery="diadesorte"]').click();
        await page.waitForFunction(() => !document.getElementById('constrained-fields').disabled && document.getElementById('constrained-month').options.length === 13);
        await page.locator('#constrained-quantity').fill('2');
        await page.locator('#constrained-month').selectOption('6');
        const monthResponse = page.waitForResponse(r => r.url().endsWith('/generate_constrained/diadesorte') && r.request().method() === 'POST');
        await page.locator('#constrained-form button[type="submit"]').click();
        const monthBatch = await (await monthResponse).json();
        assert.ok(monthBatch.games.every(game => game.length === 8 && game[7] === 'Junho'));
        await page.locator('#generated-games-modal-close-btn').click();
        await page.route('**/statistical_report/diadesorte', route => route.fulfill({ json: { status: 'pending', message: 'A base mudou; aguardando relatório.' } }));
        await page.locator('#research-report-panel').evaluate(p => { p.open = false; });
        await page.locator('#research-report-panel').evaluate(p => { p.open = true; });
        await page.waitForFunction(() => document.getElementById('research-report-status').textContent.includes('A base mudou'));
        assert.equal(await page.locator('#research-report-content').innerText(), '');
        await login('free');
        assert.equal(await page.locator('#constrained-panel').isVisible(), false);
        assert.equal(await page.locator('#research-report-panel').isVisible(), false);
        assert.equal(await page.locator('#generation-mode-toggle').isVisible(), false);
        assert.equal(await page.locator('#generation-mode-tools').isVisible(), false);
        assert.equal(await page.evaluate(async () => (await fetch('/generation_rules/megasena')).status), 403);
        assert.equal(await page.evaluate(async () => (await fetch('/generate_constrained/megasena', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })).status), 403);
        assert.equal(await page.evaluate(async () => (await fetch('/draw_digest')).status), 200);
        assert.deepEqual(errors, []);
        console.log('Advanced browser OK: audits, freshness, digest, constraints, uniform generation, private saving, batch comparison, month, 320/390/1440px themes and premium protection.');
    } finally {
        await browser?.close(); server.kill();
        await new Promise(resolve => server.exitCode !== null ? resolve() : server.once('exit', resolve));
    }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
