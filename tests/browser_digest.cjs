const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path'), os = require('node:os'), http = require('node:http');
let playwright;
try { playwright = require('playwright'); } catch { playwright = require(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')); }
const definitions = {
    megasena: {numbers:[2,15,18,23,47,56],max:60}, lotofacil:{numbers:Array.from({length:15},(_,i)=>i+1),max:25},
    quina:{numbers:[5,16,34,61,80],max:80}, diadesorte:{numbers:[1,5,7,12,18,24,31],max:31},
};
function fixture() {
    const digests={};
    for(const [kind,{numbers,max}] of Object.entries(definitions)) {
        const width=Math.ceil(max/5),ranges=[];
        for(let from=1;from<=max;from+=width) {const to=Math.min(max,from+width-1);ranges.push({from,to,count:numbers.filter(n=>n>=from&&n<=to).length});}
        const even=numbers.filter(n=>n%2===0).length;
        digests[kind]={status:'current',digest:{lottery_type:kind,contest:200,date:'24/11/2026',numbers,even,odd:numbers.length-even,
            sum:numbers.reduce((a,b)=>a+b,0),repeated_numbers:numbers.slice(0,2),consecutive_pairs:numbers.slice(1).filter((n,i)=>n===numbers[i]+1).length,
            ranges,month:kind==='diadesorte'?'Setembro':null,coverage:{total_draws:100,missing_contests:3,skipped_rows:1}}};
    }return {digests};
}
async function main() {
    const server=spawn(process.env.PYTHON||'python',[path.join(__dirname,'preview_server.py'),'5116'],{windowsHide:true,stdio:'pipe'});
    let output='';server.stdout.on('data',d=>output+=d);server.stderr.on('data',d=>output+=d);let browser;
    try {
        for(let n=0;;n++) {
            const ready=await new Promise(resolve=>{const r=http.get('http://127.0.0.1:5116/',res=>{res.resume();res.on('end',()=>resolve(res.statusCode===200));});r.on('error',()=>resolve(false));});
            if(ready)break;if(n>90||server.exitCode!==null)throw new Error(output);await new Promise(resolve=>setTimeout(resolve,300));
        }
        browser=await playwright.chromium.launch({headless:true,channel:'msedge'});
        const page=await browser.newPage({viewport:{width:1440,height:1100}});
        const errors=[];page.on('pageerror',e=>errors.push(e.message));
        let payload=fixture(),failed=false,reads=0;
        await page.route('**/draw_digest',route=>{reads++;return route.fulfill(failed?{status:503,json:{error:'Unavailable'}}:{json:payload});});
        await page.goto('http://127.0.0.1:5116/');
        await page.evaluate(async()=>{sessionStorage.setItem('snugbx-welcome-seen','1');await fetch('/auth/guest',{method:'POST'});});
        await page.reload();await page.waitForFunction(()=>!document.getElementById('app-shell').classList.contains('hidden'));
        await page.locator('#draw-digest-panel > summary').click();
        await page.waitForFunction(()=>document.querySelectorAll('.digest-page').length===4);
        assert.equal(await page.locator('.digest-page:visible').count(),1);
        assert.equal(await page.locator('.digest-page[hidden][inert]').count(),3);
        assert.equal(await page.locator('#digest-prev').isDisabled(),true);
        await page.waitForTimeout(500); // Let the existing app-entry scale animation finish.
        const originalHeight=await page.locator('#draw-digest-content').evaluate(n=>n.getBoundingClientRect().height);
        await page.locator('#digest-next').click();
        await page.waitForFunction(()=>!document.getElementById('digest-page-lotofacil').hidden);
        assert.equal(await page.locator('#digest-page-lotofacil').evaluate(n=>n===document.activeElement),true);
        assert.ok(await page.locator('#digest-page-lotofacil').evaluate(n=>n.getAnimations().length>0),'Page turn is animated');
        const newHeight=await page.locator('#draw-digest-content').evaluate(n=>n.getBoundingClientRect().height);
        assert.ok(Math.abs(newHeight-originalHeight)<2,`Pagination height stays stable: ${originalHeight} -> ${newHeight}; ${await page.locator('#draw-digest-content').getAttribute('style')}`);
        await page.locator('#digest-tab-lotofacil').focus();await page.keyboard.press('ArrowRight');
        assert.equal(await page.locator('#digest-tab-quina').getAttribute('aria-selected'),'true');
        await page.keyboard.press('End');assert.equal(await page.locator('#digest-tab-diadesorte').getAttribute('aria-selected'),'true');
        assert.equal(await page.locator('#digest-next').isDisabled(),true);
        assert.match(await page.locator('#digest-page-diadesorte .digest-month').innerText(),/Setembro/);
        const before=reads;await page.waitForTimeout(300);assert.equal(reads,before,'Pagination never refetches or auto-advances');
        for(const width of [1440,390,320]) {
            await page.setViewportSize({width,height:1100});
            for(const dark of [false,true]) {
                if(await page.evaluate(()=>document.body.classList.contains('dark-theme'))!==dark)await page.locator('#theme-toggle').click();
                for(const kind of Object.keys(definitions)) {
                    await page.locator(`#digest-tab-${kind}`).click();
                    await page.waitForTimeout(260);
                    const article=page.locator(`#digest-page-${kind}`);
                    assert.deepEqual(await article.locator('.digest-ball').allTextContents(),definitions[kind].numbers.map(n=>String(n).padStart(2,'0')));
                    assert.equal(await article.locator('.digest-month').count(),kind==='diadesorte'?1:0);
                    const sums=await article.locator('meter').evaluateAll(nodes=>nodes.reduce((sum,n)=>sum+n.value,0));assert.equal(sums,definitions[kind].numbers.length);
                    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
                    const clipped=await article.evaluate(root=>[...root.querySelectorAll('h3,h4,p,dt,dd,span,strong')].filter(n=>n.getClientRects().length&&n.scrollWidth>n.clientWidth+1).map(n=>n.textContent));
                    assert.deepEqual(clipped,[],`Text fits ${kind} ${width}`);
                    if((kind==='megasena'&&width===1440)||(kind==='diadesorte'&&width===390)||(kind==='lotofacil'&&width===320))await page.locator('#draw-digest-panel').screenshot({path:path.join(__dirname,`digest-${kind}-${width}-${dark?'dark':'light'}.png`)});
                }
            }
        }
        await page.emulateMedia({reducedMotion:'reduce'});await page.locator('#digest-tab-megasena').click();
        assert.equal(await page.locator('#digest-page-megasena').evaluate(n=>n.getAnimations().length),0);
        await page.locator('#increase-font').click();
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Enlarged text fits');
        await page.locator('#decrease-font').click();
        payload.digests.megasena={status:'pending'};await page.locator('#digest-refresh').click();
        await page.waitForFunction(()=>document.getElementById('digest-page-megasena').dataset.state==='pending');
        assert.equal(await page.locator('#digest-page-megasena .digest-ball').count(),0,'Stale numbers are not presented as current');
        payload=fixture();payload.digests.megasena.digest.even=99;await page.locator('#digest-refresh').click();
        await page.waitForFunction(()=>document.getElementById('draw-digest-content').getAttribute('aria-busy')==='false');
        assert.equal(await page.locator('#digest-page-megasena').getAttribute('data-state'),'pending','Inconsistent digest fails closed');
        payload=fixture();payload.digests.quina.digest.repeated_numbers=null;await page.locator('#digest-tab-quina').click();
        await page.locator('#digest-refresh').click();await page.waitForFunction(()=>document.querySelector('#digest-page-quina .digest-repeated')?.textContent.includes('não está disponível'));
        failed=true;await page.locator('#digest-refresh').click();await page.waitForFunction(()=>document.getElementById('draw-digest-status').textContent.includes('Não foi possível'));
        assert.equal(await page.locator('.digest-ball').count(),0);
        failed=false;await page.locator('#digest-refresh').click();await page.waitForFunction(()=>document.getElementById('digest-page-quina').dataset.state==='current');
        assert.equal(await page.locator('#digest-tab-quina').getAttribute('aria-selected'),'true','Refresh preserves the selected edition');
        payload=await (await page.request.get('http://127.0.0.1:5116/draw_digest')).json();
        const expected=Object.values(payload.digests).filter(result=>result.status==='current').length;
        const refreshed=page.waitForResponse(r=>r.url().endsWith('/draw_digest'));
        await page.locator('#digest-refresh').click();await refreshed;
        await page.waitForFunction(()=>document.getElementById('draw-digest-content').getAttribute('aria-busy')==='false');
        assert.equal(await page.locator('.digest-page[data-state="current"]').count(),expected,'Published report schema remains compatible with the new reader');
        assert.deepEqual(errors,[]);
        console.log('Digest browser OK: page turns, keyboard, stable layout, exact facts, all lotteries, month, themes/mobile, reduced motion, pending/invalid data, retry and guest access.');
    } finally {await browser?.close();server.kill();await new Promise(resolve=>server.exitCode!==null?resolve():server.once('exit',resolve));}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
