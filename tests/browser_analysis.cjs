const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
let playwright;
try { playwright = require('playwright'); }
catch {
    playwright = require(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
}

async function main() {
    const server = spawn(process.env.PYTHON || 'python', [path.join(__dirname, 'preview_server.py'), '5098'], { stdio: 'pipe', windowsHide: true });
    let serverOutput = '';
    server.stdout.on('data', data => { serverOutput += data; });
    server.stderr.on('data', data => { serverOutput += data; });
    let browser;
    try {
        for (let attempt = 0; ; attempt++) {
            const ready = await new Promise(resolve => {
                const request = http.get('http://127.0.0.1:5098/', response => {
                    response.resume();
                    response.on('end', () => resolve(response.statusCode === 200));
                });
                request.on('error', () => resolve(false));
            });
            if (ready) break;
            if (attempt > 60 || server.exitCode !== null) throw new Error(`Preview did not start: ${serverOutput}`);
            await new Promise(resolve => setTimeout(resolve, 500));
        }
        browser = await playwright.chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
        const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
        await page.clock.install();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto('http://127.0.0.1:5098/');
        await page.evaluate(() => {
            document.getElementById('welcome-screen').classList.add('hidden');
            sessionStorage.setItem('snugbx-welcome-seen', '1');
        });
        async function login(plan) {
            await page.evaluate(async plan => {
                const response = await fetch('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: `${plan}@example.com`, password: 'PreviewTeste123!' }) });
                if (!response.ok) throw new Error('Login failed');
            }, plan);
            await page.reload();
            await page.waitForFunction(() => !document.getElementById('app-shell').classList.contains('hidden'));
        }
        await login('premium');
        const section = page.locator('#game-analysis-form');
        await page.locator('#game-analysis-form').evaluate(form => { form.closest('details').open = true; });
        await page.locator('#analysis-numbers').fill('1 3 5 7 9 11');
        await section.locator('button[type="submit"]').click();
        await page.waitForFunction(() => document.getElementById('analysis-feedback').textContent === 'Consulta concluída.');
        assert.equal(await page.locator('.analysis-highlights dt').count(), 4);
        const suggested = await page.locator('.alternative-number').allTextContents();
        assert.equal(suggested.length, 6);
        assert.ok(suggested.some(n => Number(n) % 2 === 0));
        assert.ok(await page.locator('.alternative-affinities li').count() > 0);
        assert.match(await page.locator('.alternative-affinities').innerText(), /coocorrência acima da referência/);
        assert.match(await page.locator('.analysis-alternative').innerText(), /mesma chance|Mesma chance/);
        await page.evaluate(() => Object.defineProperty(navigator, 'clipboard', {
            configurable: true, value: { writeText: async text => { window.__copiedAlternative = text; } },
        }));
        await page.getByRole('button', { name: 'Copiar alternativa', exact: true }).click();
        assert.equal(await page.evaluate(() => window.__copiedAlternative), suggested.join(' '));
        assert.match(await page.locator('.alternative-action-status').innerText(), /copiada/);
        for (const width of [1440, 390]) {
            await page.setViewportSize({ width, height: 1000 });
            for (const dark of [false, true]) {
                if (await page.evaluate(() => document.body.classList.contains('dark-theme')) !== dark) {
                    await page.locator('#theme-toggle').click();
                }
                await page.locator('.analysis-alternative').screenshot({ path: path.join(__dirname, `alternative-${width}-${dark ? 'dark' : 'light'}.png`) });
                await page.locator('.analysis-highlights').screenshot({ path: path.join(__dirname, `highlights-${width}-${dark ? 'dark' : 'light'}.png`) });
                assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
            }
        }
        await page.setViewportSize({ width: 1440, height: 1000 });
        if (await page.evaluate(() => document.body.classList.contains('dark-theme'))) await page.locator('#theme-toggle').click();
        await page.getByRole('button', { name: 'Comparar com meu jogo', exact: true }).click();
        await page.waitForFunction(() => document.getElementById('analysis-feedback').textContent === 'Consulta concluída.');
        assert.equal(await page.locator('.analysis-entry').count(), 2);
        assert.equal(await page.locator('#analysis-numbers-2').inputValue(), suggested.join(' '));
        await page.locator('.analysis-game-detail').first().locator('summary').first().click();
        assert.equal(await page.locator('.analysis-game-detail').first().getByRole('button', { name: 'Comparar com meu jogo' }).isDisabled(), true);
        await page.locator('.analysis-entry').last().getByRole('button').click();
        await page.route('**/analyze_games/megasena', async route => {
            const response = await route.fetch();
            const payload = await response.json();
            payload.comparison.analyses[0].alternative.status = 'insufficient_synergy';
            payload.comparison.analyses[0].alternative.changes = [];
            payload.comparison.analyses[0].alternative.synergy.evidence = [];
            await route.fulfill({ response, json: payload });
        });
        await section.locator('button[type="submit"]').click();
        await page.waitForFunction(() => document.getElementById('analysis-feedback').textContent === 'Consulta concluída.');
        assert.match(await page.locator('.analysis-alternative').innerText(), /Sem alternativa com afinidade suficiente/);
        assert.equal(await page.getByRole('button', { name: 'Copiar alternativa', exact: true }).count(), 0);
        await page.unroute('**/analyze_games/megasena');
        await page.locator('#analysis-numbers').fill('1 2 3 4 5 6');
        await section.locator('button[type="submit"]').click();
        await page.waitForFunction(() => document.getElementById('analysis-feedback').textContent === 'Consulta concluída.');
        await page.locator('#analysis-result').getByText('O perfil do seu jogo', { exact: true }).waitFor();
        assert.match(await page.locator('#analysis-result').innerText(), /50\.063\.860/);
        await page.locator('#analysis-result').screenshot({ path: path.join(__dirname, 'analysis-desktop-light.png') });
        await page.locator('#analysis-add-game').click();
        await page.locator('#analysis-numbers-2').fill('10 20 30 40 50 60');
        await page.locator('#analysis-add-game').click();
        await page.locator('#analysis-numbers-3').fill('6 5 4 3 2 1');
        await section.locator('button[type="submit"]').click();
        await page.waitForFunction(() => document.getElementById('analysis-feedback').textContent === 'Consulta concluída.');
        assert.match(await page.locator('#analysis-result').innerText(), /Jogos repetidos: 1 e 3/);
        assert.match(await page.locator('#analysis-result').innerText(), /2 combinações numéricas diferentes/);
        await page.locator('.analysis-game-detail').first().locator('summary').first().click();
        await page.locator('.analysis-game-detail').first().getByText('Seu perfil no radar', { exact: true }).waitFor();
        await page.locator('.analysis-game-detail').first().locator('summary').first().click();
        await page.locator('#analysis-result').screenshot({ path: path.join(__dirname, 'comparison-desktop-light.png') });
        await page.locator('#pattern-radar-panel').evaluate(element => { element.open = true; });
        await page.locator('#radar-content').waitFor({ state: 'visible' });
        assert.match(await page.locator('#radar-content').innerText(), /transições analisadas/);
        assert.match(await page.locator('#radar-content').innerText(), /23,81%/);
        await page.locator('#radar-source').selectOption('3');
        await page.waitForFunction(() => document.getElementById('radar-content').textContent.includes('Depois de 3 pares e 3 ímpares'));
        await page.locator('#pattern-radar-panel').screenshot({ path: path.join(__dirname, 'radar-desktop-light.png') });
        const oldContest = await page.evaluate(async () => (await (await fetch('/pattern_radar/megasena')).json()).radar.latest.contest);
        await page.route('**/pattern_radar/megasena?*', async route => {
            const response = await route.fetch();
            const payload = await response.json();
            payload.radar.latest.contest = oldContest + 1;
            payload.radar.data_updated_at = new Date(Date.parse(payload.radar.data_updated_at) + 1000).toISOString();
            await route.fulfill({ response, json: payload });
        });
        await page.clock.fastForward(60_100);
        await page.waitForFunction(contest => document.getElementById('radar-latest').textContent.includes(contest.toLocaleString('pt-BR')), oldContest + 1);
        await page.unroute('**/pattern_radar/megasena?*');
        await page.locator('#theme-toggle').click();
        await page.locator('#game-analysis-form').evaluate(form => { form.closest('details').open = true; });
        await page.locator('#analysis-result').screenshot({ path: path.join(__dirname, 'analysis-desktop-dark.png') });
        await page.locator('#analysis-result').screenshot({ path: path.join(__dirname, 'comparison-desktop-dark.png') });
        await page.locator('#pattern-radar-panel').screenshot({ path: path.join(__dirname, 'radar-desktop-dark.png') });
        await page.setViewportSize({ width: 390, height: 844 });
        await page.locator('#analysis-result').scrollIntoViewIfNeeded();
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false, 'Mobile page overflows');
        await page.screenshot({ path: path.join(__dirname, 'analysis-mobile-dark.png') });
        await page.locator('#game-analysis-panel').screenshot({ path: path.join(__dirname, 'comparison-mobile-dark.png') });
        assert.equal(await page.locator('.comparison-overview [role="region"]').evaluate(element => element.scrollWidth > element.clientWidth), true);
        await page.locator('#pattern-radar-panel').screenshot({ path: path.join(__dirname, 'radar-mobile-dark.png') });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false, 'Radar overflows mobile page');
        assert.equal(await page.locator('.radar-table-scroll').evaluate(element => element.scrollWidth > element.clientWidth), true);
        await page.locator('button[data-lottery="diadesorte"]').click();
        assert.equal(await page.locator('#analysis-result').isVisible(), false, 'Lottery change must clear previous result');
        await page.locator('#analysis-numbers').fill('01, 02, 03, 04, 05, 06, 07');
        await page.locator('#analysis-month').selectOption('1');
        await section.locator('button[type="submit"]').click();
        await page.waitForFunction(() => document.getElementById('analysis-feedback').textContent === 'Consulta concluída.');
        assert.match(await page.locator('#analysis-result').innerText(), /Mês da Sorte: Janeiro/);
        await page.locator('#analysis-add-game').click();
        await page.locator('#analysis-numbers-2').fill('01 02 03 04 05 06 07');
        await page.locator('#analysis-month-2').selectOption('2');
        await section.locator('button[type="submit"]').click();
        await page.waitForFunction(() => document.getElementById('analysis-feedback').textContent === 'Consulta concluída.');
        assert.match(await page.locator('#analysis-result').innerText(), /2 meses diferentes cobertos/);
        assert.match(await page.locator('#analysis-result').innerText(), /1 combinação numérica diferente/);
        await page.locator('.comparison-overlap > summary').click();
        assert.match(await page.locator('.comparison-overlap').innerText(), /Mesmas dezenas, meses diferentes/);
        await page.locator('.analysis-entry').nth(1).getByRole('button', { name: 'Remover jogo 2' }).click();
        assert.equal(await page.locator('#analysis-result').isVisible(), false);
        assert.equal(await page.locator('.analysis-entry').count(), 1);
        for (let count = 1; count < 10; count++) await page.locator('#analysis-add-game').click();
        assert.equal(await page.locator('#analysis-add-game').isDisabled(), true);
        assert.equal(await page.locator('.analysis-entry').count(), 10);
        for (let count = 10; count > 1; count--) await page.locator('.analysis-entry').last().getByRole('button').click();
        await page.locator('#analysis-numbers').fill('1 1 2 3 4 5 6');
        await section.locator('button[type="submit"]').click();
        await page.waitForFunction(() => document.getElementById('analysis-numbers').getAttribute('aria-invalid') === 'true');
        await login('free');
        assert.equal(await page.locator('#game-analysis-form').isVisible(), false, 'Free user sees premium consultation');
        assert.equal(await page.locator('#pattern-radar-panel').isVisible(), false, 'Free user sees radar');
        assert.equal(await page.evaluate(async () => (await fetch('/pattern_radar/megasena')).status), 403);
        const denied = await page.evaluate(async () => (await fetch('/analyze_game/megasena', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ numbers: [1, 2, 3, 4, 5, 6] }) })).status);
        assert.equal(denied, 403);
        assert.equal(await page.evaluate(async () => (await fetch('/analyze_games/megasena', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ games: [{ numbers: [1, 2, 3, 4, 5, 6] }] }) })).status), 403);
        assert.deepEqual(errors, []);
        console.log('Browser OK: highlights, minimal alternative, copy, compare alternative, duplicates, batch, radar, months, automatic refresh, light/dark, mobile and premium access control.');
    } finally {
        await browser?.close();
        server.kill();
        await new Promise(resolve => server.exitCode !== null ? resolve() : server.once('exit', resolve));
    }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
