const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path');
const os = require('node:os');
const fs = require('node:fs');
const http = require('node:http');
let playwright;
try { playwright = require('playwright'); }
catch { playwright = require(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')); }

function fixture(unavailable = false, today = '2026-11-17') {
    const lotteries = ['lotofacil', 'quina', 'megasena', 'diadesorte'];
    const names = ['Lotofácil', 'Quina', 'Mega-Sena', 'Dia de Sorte'];
    return { today, checked_at: '2026-11-17T23:59:00-03:00', status: unavailable ? 'unavailable' : 'current',
        days: ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'].map((label, i) => ({
            label, date: `2026-11-${16 + i}`, today: `2026-11-${16 + i}` === today,
            available: !unavailable, confirmed: !unavailable,
            draws: i === 4 || i === 5 || unavailable ? [] : lotteries.map((lottery, j) => ({ lottery, name: names[j], contest: 3000 + j })),
        })),
        tips: [{ title: 'Seu limite vem primeiro', text: 'Defina um valor de lazer antes de jogar. Não use dinheiro de contas nem aumente apostas para recuperar perdas.' },
            { title: 'Histórico não é previsão', text: 'Cada novo sorteio é independente. Estratégias não garantem prêmio.' }],
    };
}

async function main() {
    const server = spawn(process.env.PYTHON || 'python', [path.join(__dirname, 'preview_server.py'), '5107'], { stdio: 'pipe', windowsHide: true });
    let output = '';
    server.stdout.on('data', data => { output += data; });
    server.stderr.on('data', data => { output += data; });
    let browser;
    try {
        for (let n = 0; ; n++) {
            const ready = await new Promise(resolve => {
                const request = http.get('http://127.0.0.1:5107/', response => {
                    response.resume();
                    response.on('end', () => resolve(response.statusCode === 200));
                });
                request.on('error', () => resolve(false));
            });
            if (ready) break;
            if (n > 60 || server.exitCode !== null) throw new Error(output);
            await new Promise(resolve => setTimeout(resolve, 300));
        }
        browser = await playwright.chromium.launch({ headless: true, channel: 'msedge' });
        const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
        await page.clock.install({ time: new Date('2026-11-18T02:59:30Z') });
        let unavailable = false;
        let today = '2026-11-17';
        let requests = 0;
        await page.route('**/draw_calendar', route => {
            requests++;
            return route.fulfill({ json: fixture(unavailable, today) });
        });
        const errors = [];
        page.on('pageerror', e => errors.push(e.message));
        await page.goto('http://127.0.0.1:5107/');
        await page.evaluate(() => {
            sessionStorage.setItem('snugbx-welcome-seen', '1');
            document.getElementById('welcome-screen').classList.add('hidden');
        });
        // Public calendar must stay hidden until login/guest access, like the rest of the app.
        assert.equal(await page.locator('.draw-calendar-panel').isVisible(), false);
        await page.evaluate(async () => {
            const r = await fetch('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: 'free@example.com', password: 'PreviewTeste123!' }) });
            if (!r.ok) throw new Error('Login failed');
        });
        await page.reload();
        await page.waitForFunction(() => document.querySelectorAll('.draw-calendar-day').length === 7);
        await page.locator('.draw-calendar-panel').waitFor({ state: 'visible' });
        assert.match(await page.locator('.draw-calendar-day').last().innerText(), /Mega-Sena/);
        assert.match(await page.locator('.draw-calendar-day').nth(4).innerText(), /Sem sorteios previstos/);
        assert.match(await page.locator('#daily-tips-content').innerText(), /Não use dinheiro/);
        assert.equal(await page.locator('[aria-current="date"]').count(), 1);
        const directory = path.join(__dirname, '../tmp/calendar-qa');
        fs.mkdirSync(directory, { recursive: true });
        for (const width of [1440, 390, 320]) {
            await page.setViewportSize({ width, height: 1000 });
            for (const dark of [false, true]) {
                await page.evaluate(dark => document.body.classList.toggle('dark-theme', dark), dark);
                await page.locator('.draw-calendar-panel').screenshot({ path: path.join(directory, `calendar-${width}-${dark ? 'dark' : 'light'}.png`) });
                const overflow = await page.evaluate(() => [...document.querySelectorAll('body *')]
                    .filter(el => el.getBoundingClientRect().width && el.getBoundingClientRect().right > innerWidth + 1)
                    .slice(0, 12).map(el => [el.id || el.className, Math.round(el.getBoundingClientRect().width)]));
                assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `Overflow at ${width}: ${JSON.stringify(overflow)}`);
                const clipped = await page.locator('.draw-calendar-panel').evaluate(panel => [...panel.querySelectorAll('p,h2,h3,span,button,a')]
                    .filter(el => !el.classList.contains('calendar-screen-reader') && el.scrollWidth > el.clientWidth + 1).map(el => el.textContent));
                assert.deepEqual(clipped, [], `Clipped text at ${width}`);
            }
        }
        await page.setViewportSize({ width: 1440, height: 1000 });
        const before = requests;
        today = '2026-11-18';
        await page.clock.fastForward(61_000);
        await page.waitForFunction(() => document.getElementById('daily-tips-date').textContent === '18/11');
        assert.ok(requests > before, 'Calendar did not refresh after Brazilian midnight');
        unavailable = true;
        await page.getByRole('button', { name: 'Consultar atualização do calendário' }).click();
        await page.waitForFunction(() => document.getElementById('draw-calendar-status').textContent.includes('não confirmada'));
        assert.equal(await page.getByText('A confirmar', { exact: true }).count(), 7);
        assert.deepEqual(errors, []);
        console.log('Calendar OK: Sunday, holiday, free access, login gate, refresh, Brazil midnight, unavailable source, 320/390/1440px light/dark.');
    } finally {
        await browser?.close();
        server.kill();
        await new Promise(resolve => server.exitCode !== null ? resolve() : server.once('exit', resolve));
    }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
