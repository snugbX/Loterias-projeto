const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path'), os = require('node:os'), http = require('node:http');
let playwright;
try { playwright = require('playwright'); } catch { playwright = require(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')); }
async function main() {
    const server = spawn(process.env.PYTHON || 'python', [path.join(__dirname, 'preview_server.py'), '5115'], { windowsHide: true, stdio:'pipe' });
    let output=''; server.stdout.on('data',d=>output+=d); server.stderr.on('data',d=>output+=d);
    let browser;
    try {
        for(let n=0;;n++) {
            const ready=await new Promise(resolve=>{const r=http.get('http://127.0.0.1:5115/',res=>{res.resume();res.on('end',()=>resolve(res.statusCode===200));});r.on('error',()=>resolve(false));});
            if(ready) break; if(n>90||server.exitCode!==null)throw new Error(output);
            await new Promise(resolve=>setTimeout(resolve,300));
        }
        browser=await playwright.chromium.launch({headless:true,channel:'msedge'});
        const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
        const errors=[];page.on('pageerror',e=>errors.push(e.message));
        await page.goto('http://127.0.0.1:5115/');
        await page.evaluate(()=>{sessionStorage.setItem('snugbx-welcome-seen','1');localStorage.setItem('snugbx-draw-animation','off');});
        async function login(plan) {
            await page.evaluate(async plan=>{const r=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:`${plan}@example.com`,password:'PreviewTeste123!'})});if(!r.ok)throw new Error('Login failed');},plan);
            await page.reload();await page.waitForFunction(()=>!document.getElementById('app-shell').classList.contains('hidden'));
        }
        await login('premium');
        assert.equal(await page.locator('.lab-tool:visible').count(),7);
        assert.equal(await page.locator('#lab-stage > details[open]').count(),0);
        assert.equal(await page.locator('#num-games-input').count(),1);
        assert.equal(await page.locator('#gerar-jogos').count(),1);
        for(const name of ['flask-conical','scan-search','radar','shield-check','circle-help','history','sparkles','chart-no-axes-combined']) {
            assert.equal((await page.request.get(`http://127.0.0.1:5115/icons/lucide/${name}.svg`)).status(),200);
        }
        for(const [kind,width] of [['megasena',1440],['lotofacil',390],['quina',320],['diadesorte',390]]) {
            await page.locator(`button[data-lottery="${kind}"]`).click();
            await page.setViewportSize({width,height:1000});
            for(const dark of [false,true]) {
                if(await page.evaluate(()=>document.body.classList.contains('dark-theme'))!==dark)await page.locator('#theme-toggle').click();
                await page.locator('#generation-mode-section').evaluate(n=>n.scrollIntoView({block:'start'}));
                await page.screenshot({path:path.join(__dirname,`workbench-${kind}-${width}-${dark?'dark':'light'}.png`)});
                assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
                const clipped=await page.locator('#game-workbench').evaluate(root=>[...root.querySelectorAll('.lab-tool span')].filter(n=>n.getClientRects().length&&n.scrollWidth>n.clientWidth+1).map(n=>n.textContent));
                assert.deepEqual(clipped,[]);
            }
            await page.locator('[data-lab-panel="constrained-panel"]').click();
            await page.waitForFunction(()=>!document.getElementById('constrained-fields').disabled);
            await page.locator('#constrained-method').selectOption('uniform');
            await page.locator('#num-games-input').fill('2');
            assert.equal(await page.locator('#constrained-quantity').inputValue(),'2');
            const response=page.waitForResponse(r=>r.url().endsWith(`/generate_constrained/${kind}`)&&r.request().method()==='POST');
            await page.locator('#gerar-jogos').click();
            const result=await response;assert.equal(result.status(),200);assert.equal((await result.json()).games.length,2);
            await page.locator('#generated-games-modal-close-btn').click();
            await page.locator('[data-lab-panel="pattern-radar-panel"]').click();
            await page.waitForFunction(()=>document.getElementById('pattern-radar-panel').open);
            assert.equal(await page.locator('#lab-stage > details[open]').count(),1);
            assert.equal(await page.locator('#constrained-panel').isVisible(),false);
            assert.equal(await page.locator('#console-mode-name').innerText(),'Jogo normal');
            await page.locator('#pattern-radar-panel').evaluate(n=>n.scrollIntoView({block:'end'}));
            const buttonRect=await page.locator('#gerar-jogos').boundingBox();
            assert.ok(buttonRect.y>=0&&buttonRect.y+buttonRect.height<=1000,'Generate remains on screen inside a long tool');
            await page.locator('#pattern-radar-panel > summary').focus();await page.keyboard.press('Escape');
            assert.equal(await page.locator('#lab-stage > details[open]').count(),0);
            assert.equal(await page.locator('[data-lab-panel="pattern-radar-panel"]').evaluate(n=>n===document.activeElement),true);
        }
        await login('free');
        assert.equal(await page.locator('.lab-tool:visible').count(),2);
        assert.equal(await page.locator('[data-lab-panel="constrained-panel"]').isVisible(),false);
        assert.equal(await page.locator('#limpar-historico-btn').isVisible(),false);
        await page.locator('#num-games-input').fill('1');
        const normalResponse=page.waitForResponse(r=>r.url().includes('/gerar_jogos/megasena?')&&r.request().method()==='POST');
        await page.locator('#gerar-jogos').click();
        const normal=await normalResponse; assert.equal(normal.status(),200); assert.equal((await normal.json()).games.length,1);
        await page.locator('#generated-games-modal-close-btn').click();
        await page.locator('[data-lab-panel="user-assistance-panel"]').click();
        await page.waitForFunction(()=>document.getElementById('user-assistance-panel').open);
        assert.equal(await page.locator('#user-assistance-panel').isVisible(),true);
        assert.deepEqual(errors,[]);
        console.log('Workbench browser OK: icons, compact tools, one panel at a time, sticky generator, custom submission, all lotteries, themes/mobile, keyboard and free access.');
    } finally {await browser?.close();server.kill();await new Promise(resolve=>server.exitCode!==null?resolve():server.once('exit',resolve));}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
