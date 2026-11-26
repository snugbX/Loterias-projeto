const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const path = require('node:path'), os = require('node:os'), http = require('node:http');
let playwright;
try {playwright=require('playwright');} catch {playwright=require(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));}
async function main() {
    const server=spawn(process.env.PYTHON||'python',[path.join(__dirname,'preview_server.py'),'5120'],{windowsHide:true,stdio:'pipe'});
    let output='',browser;server.stdout.on('data',d=>output+=d);server.stderr.on('data',d=>output+=d);
    try {
        for(let n=0;;n++) {
            const ready=await new Promise(resolve=>{const r=http.get('http://127.0.0.1:5120/',res=>{res.resume();res.on('end',()=>resolve(res.statusCode===200));});r.on('error',()=>resolve(false));});
            if(ready)break;if(n>90||server.exitCode!==null)throw Error(output);await new Promise(r=>setTimeout(r,300));
        }
        browser=await playwright.chromium.launch({headless:true,channel:'msedge'});
        const page=await browser.newPage({viewport:{width:1440,height:1100},reducedMotion:'reduce'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
        const initial=page.waitForResponse(r=>r.url().endsWith('/auth/me'));
        await page.goto('http://127.0.0.1:5120/');await initial;
        await page.evaluate(async()=>{sessionStorage.setItem('snugbx-welcome-seen','1');await fetch('/auth/guest',{method:'POST'});});
        await page.reload();await page.waitForFunction(()=>!document.getElementById('app-shell').classList.contains('hidden'));
        await page.waitForTimeout(500);
        const picker=page.locator('.lottery-picker'),grid=page.locator('#lottery-option-grid');
        assert.equal(await page.locator('.lottery-option').count(),5);
        assert.equal(await page.locator('#lottery-select').inputValue(),'megasena');
        assert.equal(await page.locator('.lottery-option-balls').count(),0,'No invented draw numbers in the selector');
        const kinds=['megasena','lotofacil','quina','diadesorte','maismilionaria'];
        for(const width of [1440,768,390,320]) {
            await page.setViewportSize({width,height:1100});
            for(const dark of [false,true]) {
                if(await page.evaluate(()=>document.body.classList.contains('dark-theme'))!==dark)await page.locator('#theme-toggle').click();
                const height=await grid.evaluate(n=>n.offsetHeight);
                for(const kind of kinds) {
                    await page.locator(`.lottery-option[data-lottery="${kind}"]`).click();
                    assert.equal(await page.locator('#lottery-select').inputValue(),kind);
                    assert.equal(await page.locator('.lottery-option[aria-checked="true"]').count(),1);
                    assert.equal(await page.locator('.lottery-option[tabindex="0"]').count(),1);
                    const bounds=await page.locator(`.lottery-option[data-lottery="${kind}"]`).evaluate(n=>{const r=n.getBoundingClientRect(),v=n.parentElement.getBoundingClientRect();return r.left>=v.left-1&&r.right<=v.right+1;});
                    assert.ok(bounds,`Selected ticket is visible ${kind} ${width}`);
                    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
                    assert.deepEqual(await picker.evaluate(root=>[...root.querySelectorAll('span,strong,input,button,p')].filter(n=>n.getClientRects().length&&n.scrollWidth>n.clientWidth+1).map(n=>n.textContent)),[],`Labels fit ${kind} ${width}`);
                }
                const afterHeight=await grid.evaluate(n=>n.offsetHeight);
                await picker.screenshot({path:path.join(__dirname,`picker-${width}-${dark?'dark':'light'}.png`)});
                assert.ok(Math.abs(afterHeight-height)<2,`Selection never expands the rail: ${height} -> ${afterHeight}; width=${width}; ${JSON.stringify(await grid.evaluate(n=>[...n.children].map(b=>({kind:b.dataset.lottery,height:b.getBoundingClientRect().height,font:getComputedStyle(b).fontSize}))))}`);
                await picker.screenshot({path:path.join(__dirname,`picker-${width}-${dark?'dark':'light'}.png`)});
            }
        }
        const selected=await page.locator('#lottery-select').inputValue();
        await page.locator('#lottery-search').fill('lotofacil');
        assert.equal(await page.locator('.lottery-option:visible').count(),1);
        assert.equal(await page.locator('#lottery-select').inputValue(),selected,'Filtering alone never changes the chosen lottery');
        assert.match(await page.locator('#lottery-picker-status').innerText(),/1 modalidade/);
        await page.keyboard.press('Tab');
        await page.locator('.lottery-option:visible').focus();await page.keyboard.press('Enter');
        assert.equal(await page.locator('#lottery-select').inputValue(),'lotofacil');
        await page.locator('#lottery-search').fill('trevos');assert.equal(await page.locator('.lottery-option:visible').count(),1);
        await page.locator('#lottery-search').fill('inexistente');assert.equal(await page.locator('.lottery-option:visible').count(),0);
        assert.match(await page.locator('#lottery-picker-status').innerText(),/Nenhuma loteria/);
        await page.locator('#lottery-clear-search').click();assert.equal(await page.locator('.lottery-option:visible').count(),5);
        await page.locator('.lottery-option[data-lottery="lotofacil"]').focus();await page.keyboard.press('End');
        assert.equal(await page.locator('#lottery-select').inputValue(),'maismilionaria');
        await page.keyboard.press('ArrowRight');assert.equal(await page.locator('#lottery-select').inputValue(),'megasena');
        const before=await grid.evaluate(n=>n.scrollLeft);await page.locator('#lottery-scroll-next').click();
        await page.waitForFunction(before=>document.getElementById('lottery-option-grid').scrollLeft>before,before);
        assert.equal(await page.locator('#lottery-select').inputValue(),'megasena','Browsing arrows do not select another lottery');
        for(let i=0;i<8;i++)await page.locator('#increase-font').click();
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Maximum font size fits');
        assert.deepEqual(await picker.evaluate(root=>[...root.querySelectorAll('span,strong,input,button,p')].filter(n=>n.getClientRects().length&&n.scrollWidth>n.clientWidth+1).map(n=>n.textContent)),[],'Enlarged text fits the tickets');
        await picker.screenshot({path:path.join(__dirname,'picker-320-enlarged.png')});
        assert.deepEqual(errors,[]);
        console.log('Lottery picker: all modalities, responsive rail, themes, search/accent folding, no-result recovery, keyboard, single selection, scroll controls and maximum text size passed.');
    } finally {await browser?.close();server.kill();await new Promise(resolve=>server.exitCode!==null?resolve():server.once('exit',resolve));}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
