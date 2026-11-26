const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const path = require('node:path'), os = require('node:os'), http = require('node:http');
let playwright;
try {playwright=require('playwright');} catch {playwright=require(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));}
async function main() {
    const server=spawn(process.env.PYTHON||'python',[path.join(__dirname,'preview_server.py'),'5119'],{windowsHide:true,stdio:'pipe'});
    let output='',browser; server.stdout.on('data',d=>output+=d);server.stderr.on('data',d=>output+=d);
    try {
        for(let n=0;;n++) {
            const ready=await new Promise(resolve=>{const r=http.get('http://127.0.0.1:5119/',res=>{res.resume();res.on('end',()=>resolve(res.statusCode===200));});r.on('error',()=>resolve(false));});
            if(ready)break;if(n>90||server.exitCode!==null)throw Error(output);await new Promise(r=>setTimeout(r,300));
        }
        browser=await playwright.chromium.launch({headless:true,channel:'msedge'});
        const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
        await page.addInitScript(()=>{Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.copied=text;}}});});
        const initial=page.waitForResponse(r=>r.url().endsWith('/auth/me'));
        await page.goto('http://127.0.0.1:5119/');await initial;
        await page.evaluate(async()=>{sessionStorage.setItem('snugbx-welcome-seen','1'); const r=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'premium@example.com',password:'PreviewTeste123!'})});if(!r.ok)throw Error('Test login failed');});
        await page.reload();await page.waitForFunction(()=>!document.getElementById('app-shell').classList.contains('hidden'));
        await page.locator('button.lottery-option[data-lottery="maismilionaria"]').click();
        assert.match(await page.locator('#selected-lottery-meta').innerText(),/2 trevos/);
        const latest=(await (await page.request.get('http://127.0.0.1:5119/latest_results')).json()).results.maismilionaria;
        await page.waitForFunction(()=>document.querySelector('.latest-result-card[data-lottery="maismilionaria"]')?.dataset.state==='available');
        await page.locator('[data-results-kind="maismilionaria"][data-results-action="digest"]').click();
        await page.waitForFunction(()=>document.querySelector('#digest-page-maismilionaria')?.dataset.state==='current');
        assert.match(await page.locator('#digest-page-maismilionaria .digest-month').innerText(),new RegExp(latest.extras['Trevo 1']));
        await page.locator('[data-lab-panel="game-analysis-panel"]').click();
        await page.locator('#analysis-numbers').fill(latest.numbers.join(' '));
        await page.locator('#analysis-trevos').fill(`${latest.extras['Trevo 1']} ${latest.extras['Trevo 2']}`);
        let request=page.waitForResponse(r=>r.url().includes('/analyze_games/maismilionaria'));
        await page.locator('#game-analysis-form button[type="submit"]').click();
        assert.equal((await request).status(),200);
        await page.waitForFunction(()=>!document.getElementById('analysis-result').hidden);
        assert.match(await page.locator('#analysis-result').innerText(),/238\.360\.500/);
        assert.match(await page.locator('#analysis-result').innerText(),/6 acertos \+ 2 trevos/);
        assert.equal(await page.locator('.analysis-month-field').isVisible(),false);
        for(const width of [1440,390,320]) {
            await page.setViewportSize({width,height:1100});
            for(const dark of [false,true]) {
                if(await page.evaluate(()=>document.body.classList.contains('dark-theme'))!==dark)await page.locator('#theme-toggle').click();
                assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`No page overflow ${width}`);
                assert.deepEqual(await page.locator('#game-analysis-form').evaluate(root=>[...root.querySelectorAll('label,input,button,p')].filter(n=>n.getClientRects().length&&n.scrollWidth>n.clientWidth+1).map(n=>n.textContent)),[],`Form fits ${width}`);
                await page.locator('#game-analysis-form').screenshot({path:path.join(__dirname,`mais-form-${width}-${dark?'dark':'light'}.png`)});
            }
        }
        for(let i=0;i<4;i++)await page.locator('#increase-font').click();
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Enlarged text fits');
        for(let i=0;i<4;i++)await page.locator('#decrease-font').click();
        await page.locator('#analysis-add-game').click();await page.locator('#analysis-numbers-2').fill(latest.numbers.join(' '));
        await page.locator('#analysis-trevos-2').fill('1 1');await page.locator('#game-analysis-form button[type="submit"]').click();
        assert.match(await page.locator('#analysis-feedback').innerText(),/dois trevos diferentes/);
        await page.locator('#analysis-trevos-2').fill('1 6');request=page.waitForResponse(r=>r.url().includes('/analyze_games/maismilionaria'));
        await page.locator('#game-analysis-form button[type="submit"]').click();assert.equal((await request).status(),200);
        await page.locator('[data-lab-panel="pattern-radar-panel"]').click();await page.waitForSelector('.radar-trevos table');
        assert.equal(await page.locator('.radar-trevos tbody tr').count(),15);
        assert.match(await page.locator('.radar-trevos').innerText(),/1 em 15/);
        await page.locator('[data-lab-panel="pattern-radar-panel"]').click();
        await page.locator('[data-lab-panel="constrained-panel"]').click();
        await page.waitForFunction(()=>!document.getElementById('constrained-fields').disabled);
        await page.locator('#constrained-method').selectOption('uniform');
        await page.locator('#constrained-quantity').fill('2');
        await page.locator('#constrained-trevos').fill('2 6');
        request=page.waitForResponse(r=>r.url().includes('/generate_constrained/maismilionaria'));
        await page.locator('#constrained-form button[type="submit"]').click();
        const customResponse=await request; assert.equal(customResponse.status(),200);
        const custom=await customResponse.json();
        assert.ok(custom.games.every(game=>JSON.stringify(game.slice(6))==='[2,6]'));
        assert.equal(custom.portfolio.jackpot_one_in,119180250);
        assert.equal(custom.portfolio.jackpot_probability,2/238360500);
        await page.waitForFunction(()=>document.getElementById('draw-experience').dataset.phase==='revealing');
        await page.locator('#draw-skip').click();await page.waitForFunction(()=>document.getElementById('draw-experience').dataset.phase==='complete');
        await page.locator('#generated-games-modal-close-btn').click();
        assert.match(await page.locator('#constrained-summary').innerText(),/119\.180\.250/);
        assert.match(await page.locator('#constrained-summary').innerText(),/1 par de trevos distinto/);
        await page.locator('#constrained-summary').screenshot({path:path.join(__dirname,'mais-custom-summary-320-dark.png')});
        await page.locator('[data-lab-panel="constrained-panel"]').click();
        await page.locator('#num-games-input').fill('2');
        request=page.waitForResponse(r=>r.url().includes('/gerar_jogos/maismilionaria'));
        await page.locator('#gerar-jogos').click();const generated=await (await request).json();
        assert.equal(generated.games.length,2);
        for(const game of generated.games){assert.equal(game.length,8);assert.equal(new Set(game.slice(0,6)).size,6);assert.equal(new Set(game.slice(6)).size,2);assert.ok(game.slice(6).every(n=>n>=1&&n<=6));}
        await page.waitForFunction(()=>document.querySelectorAll('#draw-preview .draw-month').length===2);
        assert.ok(await page.locator('#draw-canvas').evaluate(c=>c.getContext('2d').getImageData(0,0,c.width,c.height).data.some((v,i)=>i%4===3&&v>0)),'Canvas is nonblank');
        await page.locator('#draw-skip').click();await page.waitForFunction(()=>document.getElementById('draw-experience').dataset.phase==='complete');
        assert.equal(await page.locator('#jogos-gerados-modal-display .number-ball').count(),12);
        assert.equal(await page.locator('#jogos-gerados-modal-display .trevo-badge').count(),4);
        await page.locator('#copy-games-btn-modal').click();assert.match(await page.evaluate(()=>window.copied),/\| Trevos:/);
        await page.screenshot({path:path.join(__dirname,'mais-generated-320-dark.png')});
        const history=await (await page.request.get('http://127.0.0.1:5119/history_games/maismilionaria')).json();
        assert.ok(JSON.stringify(history).includes('not_effective'),'Saved games are never checked before effectuation');
        assert.deepEqual(errors,[]);
        console.log('+Milionaria browser: official data, trevos, consultation, comparison, validation, radar, actual generation, canvas, copy, private history and mobile themes passed.');
    } finally {await browser?.close();server.kill();await new Promise(resolve=>server.exitCode!==null?resolve():server.once('exit',resolve));}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
