const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path'), os = require('node:os'), http = require('node:http');
let playwright;
try { playwright = require('playwright'); } catch { playwright = require(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')); }
const numbers = {megasena:[2,15,18,23,47,56],lotofacil:Array.from({length:15},(_,i)=>i+1),quina:[5,16,34,61,80],diadesorte:[1,5,7,12,18,24,31]};
const names = {megasena:'Mega Sena',lotofacil:'Lotofácil',quina:'Quina',diadesorte:'Dia de Sorte'};
function fixture() { return Object.fromEntries(Object.entries(numbers).map(([kind,values])=>[kind,{name:names[kind],contest:200,date:'24/11/2026',numbers:values,extras:kind==='diadesorte'?{'Mês da Sorte':'Setembro'}:null}])); }
async function main() {
    const server=spawn(process.env.PYTHON||'python',[path.join(__dirname,'preview_server.py'),'5117'],{windowsHide:true,stdio:'pipe'});
    let output='',browser;server.stdout.on('data',d=>output+=d);server.stderr.on('data',d=>output+=d);
    try {
        for(let n=0;;n++) {
            const ready=await new Promise(resolve=>{const r=http.get('http://127.0.0.1:5117/',res=>{res.resume();res.on('end',()=>resolve(res.statusCode===200));});r.on('error',()=>resolve(false));});
            if(ready)break;if(n>90||server.exitCode!==null)throw new Error(output);await new Promise(resolve=>setTimeout(resolve,300));
        }
        browser=await playwright.chromium.launch({headless:true,channel:'msedge'});
        const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
        page.on('pageerror',e=>errors.push(e.message));
        await page.addInitScript(()=>{Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{if(window.failCopy)throw Error('Denied');window.copiedResult=text;}}});});
        let results=fixture(),failed=false,reads=0,mismatch=false;
        await page.route('**/latest_results',r=>{reads++;return r.fulfill(failed?{status:503,json:{error:'Unavailable'}}:{json:{results}});});
        await page.route('**/data_status',r=>r.fulfill({json:{status:Object.fromEntries(Object.keys(numbers).map(kind=>[kind,{file_exists:true,contest:mismatch?201:200,modified_at:'2026-11-25T10:00:00'}]))}}));
        await page.goto('http://127.0.0.1:5117/');
        await page.evaluate(async()=>{sessionStorage.setItem('snugbx-welcome-seen','1');await fetch('/auth/guest',{method:'POST'});});
        await page.reload();await page.waitForFunction(()=>!document.getElementById('app-shell').classList.contains('hidden'));
        await page.waitForFunction(()=>document.querySelectorAll('.latest-result-ball').length===33);
        await page.waitForTimeout(500);
        assert.equal(await page.locator('.latest-result-card').count(),4);
        assert.equal(await page.locator('#update-data-btn').isVisible(),false,'Guest cannot update source data');
        for(const [kind,values] of Object.entries(numbers)) {
            const card=page.locator(`.latest-result-card[data-lottery="${kind}"]`);
            assert.deepEqual(await card.locator('.latest-result-ball').allTextContents(),values.map(n=>String(n).padStart(2,'0')));
            assert.equal(await card.locator('time').getAttribute('datetime'),'2026-11-24');
            assert.equal(await card.locator('.result-lucky-month').count(),kind==='diadesorte'?1:0);
        }
        for(const width of [1440,390,320]) {
            await page.setViewportSize({width,height:1100});
            for(const dark of [false,true]) {
                if(await page.evaluate(()=>document.body.classList.contains('dark-theme'))!==dark)await page.locator('#theme-toggle').click();
                assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
                const clipped=await page.locator('#latest-results-grid').evaluate(root=>[...root.querySelectorAll('h3,span,strong,time,button')].filter(n=>n.getClientRects().length&&n.scrollWidth>n.clientWidth+1).map(n=>n.textContent));
                assert.deepEqual(clipped,[],`No clipped text at ${width}, dark=${dark}`);
                await page.locator('#latest-results-section').screenshot({path:path.join(__dirname,`results-${width}-${dark?'dark':'light'}.png`)});
            }
        }
        for(let i=0;i<4;i++)await page.locator('#increase-font').click();
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Enlarged text fits');
        assert.deepEqual(await page.locator('#latest-results-grid').evaluate(root=>[...root.querySelectorAll('h3,span,strong,time,button')].filter(n=>n.getClientRects().length&&n.scrollWidth>n.clientWidth+1).map(n=>n.textContent)),[],'Enlarged card text is not clipped');
        for(let i=0;i<4;i++)await page.locator('#decrease-font').click();
        await page.locator('[data-results-kind="diadesorte"][data-results-action="copy"]').click();
        assert.match(await page.evaluate(()=>window.copiedResult),/Mês da Sorte: Setembro/);
        await page.evaluate(()=>window.failCopy=true);await page.locator('[data-results-kind="quina"][data-results-action="copy"]').click();
        assert.match(await page.locator('#results-action-feedback').innerText(),/Não foi possível copiar/);
        await page.locator('[data-results-kind="diadesorte"][data-results-action="digest"]').click();
        await page.waitForFunction(()=>document.getElementById('digest-tab-diadesorte').getAttribute('aria-selected')==='true');
        assert.equal(await page.locator('#draw-digest-panel').getAttribute('open'),'');
        const before=reads;mismatch=true;await page.locator('#results-reload').click();
        await page.waitForFunction(()=>document.querySelectorAll('.result-state-note').length===4);assert.ok(reads>before);
        mismatch=false;results.megasena.numbers=[1,1,1,1,1,1];await page.locator('#results-reload').click();
        await page.waitForFunction(()=>document.querySelector('.latest-result-card[data-lottery="megasena"]')?.dataset.state==='unavailable');
        assert.equal(await page.locator('.latest-result-card[data-lottery="megasena"] .latest-result-ball').count(),0);
        failed=true;await page.locator('#results-reload').click();
        await page.waitForFunction(()=>document.querySelectorAll('.result-unavailable').length===4);
        assert.equal(await page.locator('.latest-result-ball').count(),0,'Failed read never retains apparently current numbers');
        failed=false;results=fixture();await page.locator('#results-reload').click();
        await page.waitForFunction(()=>document.querySelectorAll('.latest-result-ball').length===33);
        assert.deepEqual(errors,[]);
        console.log('Results board: all lotteries, themes, mobile, enlarged text, safe copy, digest link, mismatch, invalid data and retry passed.');
    } finally {await browser?.close();server.kill();await new Promise(resolve=>server.exitCode!==null?resolve():server.once('exit',resolve));}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
