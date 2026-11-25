const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path'), os = require('node:os'), http = require('node:http');
let playwright;
try { playwright = require('playwright'); } catch { playwright = require(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')); }
async function main() {
    const server = spawn(process.env.PYTHON || 'python', [path.join(__dirname, 'preview_server.py'), '5114', '--history'], { windowsHide: true, stdio:'pipe' });
    let output=''; server.stdout.on('data', d=>output+=d); server.stderr.on('data',d=>output+=d);
    let browser;
    try {
        for(let n=0;;n++) {
            const ready=await new Promise(resolve=>{const r=http.get('http://127.0.0.1:5114/',res=>{res.resume();res.on('end',()=>resolve(res.statusCode===200));});r.on('error',()=>resolve(false));});
            if(ready)break;
            if(n>90||server.exitCode!==null)throw new Error(output);
            await new Promise(resolve=>setTimeout(resolve,300));
        }
        browser=await playwright.chromium.launch({headless:true,channel:'msedge'});
        const page=await browser.newPage({viewport:{width:1440,height:1000}});
        await page.clock.install();
        const errors=[];page.on('pageerror',e=>errors.push(e.message));
        await page.goto('http://127.0.0.1:5114/');
        await page.evaluate(()=>sessionStorage.setItem('snugbx-welcome-seen','1'));
        async function login(plan) {
            await page.evaluate(async plan=>{const r=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:`${plan}@example.com`,password:'PreviewTeste123!'})});if(!r.ok)throw new Error('Login failed');},plan);
            await page.reload();await page.waitForFunction(()=>!document.getElementById('app-shell').classList.contains('hidden'));
        }
        await login('premium');
        let reads=0;page.on('request',r=>{if(r.url().includes('/history_games/'))reads++;});
        await page.locator('#visualizar-historico').click();
        await page.waitForFunction(()=>document.querySelectorAll('.history-game').length===20);
        assert.match(await page.locator('#history-summary').innerText(),/0 efetivados/);
        assert.equal(await page.locator('.history-game[data-status="prize"]').count(),0,'Winning generated combinations are not checked until marked effective');
        await page.locator('.history-favorite').first().click();
        await page.waitForFunction(()=>document.querySelector('.history-favorite').getAttribute('aria-pressed')==='true');
        await page.locator('#history-filter-panel summary').click();
        await page.locator('#history-filters [name="favorite"]').check();await page.locator('#history-filters button[type="submit"]').click();
        await page.waitForFunction(()=>document.querySelectorAll('.history-game').length===1);
        const contest=await page.evaluate(async()=> (await (await fetch('/history_games/megasena')).json()).source.latest_contest);
        const effective=page.locator('.history-effective-form').first();
        await effective.locator('input[type="checkbox"]').check();await effective.locator('input[type="number"]').fill(String(contest));
        await effective.locator('button[type="submit"]').click();
        await page.waitForFunction(()=>document.querySelector('.history-game').dataset.status==='prize');
        const before=reads; await page.locator('#history-modal-close-btn').focus();
        const automatic = page.waitForResponse(r=>r.url().includes('/history_games/'));
        await page.clock.fastForward(61000); await automatic;
        assert.ok(reads>before,'Automatic refresh runs while the panel is visible');
        await page.locator('#history-reset').click();await page.waitForFunction(()=>document.querySelectorAll('.history-game').length===20);
        await page.locator('#history-next').click();await page.waitForFunction(()=>document.querySelectorAll('.history-game').length===2);
        await page.locator('#history-prev').click();await page.waitForFunction(()=>document.querySelectorAll('.history-game').length===20);
        await page.locator('#history-filter-panel summary').click();
        for(const [kind,width,dark] of [['megasena',1440,false],['lotofacil',390,true],['quina',320,false],['diadesorte',390,true]]) {
            await page.locator('#history-modal-close-btn').click();
            await page.setViewportSize({width,height:1000});
            if(await page.evaluate(()=>document.body.classList.contains('dark-theme'))!==dark)await page.locator('#theme-toggle').click();
            await page.locator(`button[data-lottery="${kind}"]`).click();await page.locator('#visualizar-historico').click();
            await page.waitForFunction(()=>document.querySelectorAll('.history-game').length===20);
            await page.locator('#history-modal-overlay .modal-content').screenshot({path:path.join(__dirname,`history-${kind}-${width}.png`)});
            assert.equal(await page.locator('#history-modal-overlay .modal-content').evaluate(n=>n.scrollWidth>n.clientWidth+1),false,'No horizontal overflow');
        }
        page.once('dialog',d=>d.accept());await page.locator('.history-effective-form button[type="button"]').first().click();
        await page.waitForFunction(()=>document.getElementById('history-summary').textContent.startsWith('21 jogos'));
        page.once('dialog',d=>d.accept());await page.locator('#history-clear-own').click();
        await page.waitForFunction(()=>document.getElementById('history-summary').textContent.startsWith('0 jogos'));
        await page.locator('#history-modal-close-btn').click();await login('free');
        await page.locator('#visualizar-historico').click();await page.waitForFunction(()=>document.getElementById('history-summary').textContent.startsWith('0 jogos'));
        assert.deepEqual(errors,[]);
        console.log('History browser OK: effective-only checking, favorites, filters, paging, owner isolation, deletion, auto refresh and all lotteries/themes/mobile.');
    } finally {await browser?.close();server.kill();await new Promise(resolve=>server.exitCode!==null?resolve():server.once('exit',resolve));}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
