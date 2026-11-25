const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const path = require('node:path'), os = require('node:os'), http = require('node:http');
let playwright;
try {playwright=require('playwright');} catch {playwright=require(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));}
async function main() {
    const server=spawn(process.env.PYTHON||'python',[path.join(__dirname,'preview_server.py'),'5118'],{windowsHide:true,stdio:'pipe'});
    let output='',browser;server.stdout.on('data',d=>output+=d);server.stderr.on('data',d=>output+=d);
    try {
        for(let n=0;;n++) {
            const ready=await new Promise(resolve=>{const r=http.get('http://127.0.0.1:5118/',res=>{res.resume();res.on('end',()=>resolve(res.statusCode===200));});r.on('error',()=>resolve(false));});
            if(ready)break;if(n>90||server.exitCode!==null)throw Error(output);await new Promise(r=>setTimeout(r,300));
        }
        browser=await playwright.chromium.launch({headless:true,channel:'msedge'});
        const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
        let role='guest';
        await page.route('**/auth/me',async route=>{
            if(!['admin','long'].includes(role))return route.continue();
            const response=await route.fetch(),data=await response.json();
            if(data.user&&role==='admin')data.user={...data.user,is_admin:true,is_premium:true};
            if(data.user&&role==='long')data.user={...data.user,name:'NomeMuitoLongoSemEspaçosParaTestarAcessibilidade',email:'email.bastante.longo.para.conferir.o.cabecalho@example.com'};
            return route.fulfill({response,json:data});
        });
        const initialSession=page.waitForResponse(r=>r.url().endsWith('/auth/me'));
        await page.goto('http://127.0.0.1:5118/');await initialSession;
        await page.evaluate(()=>sessionStorage.setItem('snugbx-welcome-seen','1'));
        for(role of ['guest','free','premium','admin','long']) {
            await page.evaluate(async role=>{
                const response=role==='guest'?await fetch('/auth/guest',{method:'POST'}):await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:`${role==='free'?'free':'premium'}@example.com`,password:'PreviewTeste123!'})});
                if(!response.ok)throw Error(`Test login ${role}: ${response.status}`);
            },role);
            await page.reload();
            try { await page.waitForFunction(()=>!document.getElementById('app-shell').classList.contains('hidden')); }
            catch(error) { throw Error(`Account state ${role}: ${errors.join('; ')}; ${error.message}`); }
            assert.equal(await page.locator('#admin-users-btn').isVisible(),role==='admin');
            assert.equal(await page.locator('#nav-login-btn').isVisible(),role==='guest');
            assert.equal(await page.locator('#logout-btn').isVisible(),role!=='guest');
            assert.equal(await page.locator('#premium-pix-btn').isVisible(),role!=='guest');
            assert.equal(await page.locator('#account-usage-meter').isVisible(),['guest','free'].includes(role));
            if(role==='premium')assert.match(await page.locator('#account-usage-detail').innerText(),/sem limite/);
            for(const width of [1440,1000,768,390,320]) {
                await page.setViewportSize({width,height:1000});
                for(const dark of [false,true]) {
                    if(await page.evaluate(()=>document.body.classList.contains('dark-theme'))!==dark)await page.locator('#theme-toggle').click();
                    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${role} ${width} page overflow`);
                    assert.deepEqual(await page.locator('#top-nav').evaluate(root=>[...root.querySelectorAll('strong,span,button')].filter(n=>n.getClientRects().length&&n.scrollWidth>n.clientWidth+1).map(n=>n.textContent)),[],`${role} ${width} clipped text`);
                    if(['premium','guest','admin'].includes(role)&&[1440,390,320].includes(width))await page.locator('#top-nav').screenshot({path:path.join(__dirname,`account-${role}-${width}-${dark?'dark':'light'}.png`)});
                }
            }
            for(let i=0;i<4;i++)await page.locator('#increase-font').click();
            assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Enlarged header fits');
            for(let i=0;i<4;i++)await page.locator('#decrease-font').click();
        }
        role='premium';await page.reload();await page.waitForFunction(()=>!document.getElementById('app-shell').classList.contains('hidden'));
        await page.locator('#premium-pix-btn').click();await page.waitForFunction(()=>!document.getElementById('billing-pix-panel').classList.contains('hidden'));
        await page.locator('#logout-btn').click();await page.waitForFunction(()=>!document.getElementById('auth-gate').classList.contains('hidden'));
        await page.evaluate(()=>fetch('/auth/guest',{method:'POST'}));await page.reload();await page.waitForFunction(()=>!document.getElementById('app-shell').classList.contains('hidden'));
        await page.locator('#nav-login-btn').click();await page.waitForFunction(()=>!document.getElementById('auth-gate').classList.contains('hidden'));
        assert.deepEqual(errors,[]);
        console.log('Account bar: guest/free/premium/admin, long identities, themes, mobile, enlarged text, Pix, sign out and guest sign in passed.');
    } finally {await browser?.close();server.kill();await new Promise(resolve=>server.exitCode!==null?resolve():server.once('exit',resolve));}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
