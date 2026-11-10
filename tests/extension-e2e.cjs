// Development test only. The extension/runtime does not depend on Playwright.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {spawn,spawnSync}=require('node:child_process');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),ext=path.join(root,'extension');
const python=process.env.PYTHON||'python3';
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'applyflow-e2e-'));
const port=18746,base=`http://127.0.0.1:${port}`;
const environment={...process.env,APPLYFLOW_PROFILE_PATH:'examples/profile.json',APPLYFLOW_RESUME_LIBRARY_PATH:'examples/resume-library.json',APPLYFLOW_MASTER_RESUME_PATH:path.join(temp,'no-original.pdf'),APPLYFLOW_LOCAL_MODE:'true',APPLYFLOW_API_BASE_URL:base,APPLYFLOW_API_PORT:String(port),APPLYFLOW_DATA_DIR:path.join(temp,'data')};
const configPath=path.join(ext,'config.js');const originalConfig=fs.existsSync(configPath)?fs.readFileSync(configPath):null;const originalManifest=fs.readFileSync(path.join(ext,'manifest.json'));
let server,context;let stderr='';
const tests=[];
function check(condition,message){assert.ok(condition,message);tests.push(message);}
(async()=>{
 try{
  const build=spawnSync(python,['scripts/build.py'],{cwd:root,env:environment,encoding:'utf8'});if(build.status!==0)throw new Error(build.stderr);
  server=spawn(python,['tests/serve_fixture.py'],{cwd:root,env:environment,stdio:['ignore','pipe','pipe']});server.stderr.on('data',chunk=>stderr+=chunk);
  for(let i=0;i<80;i++){try{if((await fetch(base+'/health')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
  context=await chromium.launchPersistentContext(path.join(temp,'browser'),{channel:'chromium',headless:true,args:[`--disable-extensions-except=${ext}`,`--load-extension=${ext}`]});
  const worker=context.serviceWorkers()[0]||await context.waitForEvent('serviceworker');
  const id=new URL(worker.url()).hostname;
  check(!!id,'Extension service worker loaded');
  const fixture=await context.newPage();await fixture.goto(base+'/fixture');
  const fixtureTab=await worker.evaluate(async url=>(await chrome.tabs.query({})).find(t=>t.url===url),base+'/fixture');
  const popup=await context.newPage();
  // A real action popup does not replace the active job tab. Navigating a popup
  // HTML page in a test does, so emulate only that browser-tab lookup.
  await popup.addInitScript(tab=>{const query=chrome.tabs.query.bind(chrome.tabs);chrome.tabs.query=options=>options.active?Promise.resolve([tab]):query(options);},fixtureTab);
  const errors=[];popup.on('pageerror',e=>errors.push(e.message));
  await popup.goto(`chrome-extension://${id}/popup.html`);
  await popup.waitForFunction(()=>document.getElementById('resume-status')?.textContent.includes('One page verified'),{timeout:30000});
  check((await popup.locator('#resume-status').innerText()).includes('Saved locally'),'Activation detects job and generates a verified resume');
  check(await popup.locator('#job-title').inputValue()==='Backend Engineer','Reads JobPosting structured title');
  check(await popup.locator('#job-company').inputValue()==='Fixture Company','Reads structured company');
  check((await popup.locator('#job-description').inputValue()).includes('Qualifications\n'),'Preserves qualification heading/list boundaries');
  check((await popup.locator('#job-description').inputValue()).includes('Experience building Python FastAPI'),'Keeps inline bold skill names inside their qualification');
  check(await popup.locator('#qualification-report h3').allTextContents().then(t=>t.includes('Required qualifications')&&t.includes('Preferred qualifications')),'Shows separate required and preferred evidence reports');
  check(!(await popup.locator('#resume-result').innerText()).includes('Matched:'),'Removes generic word-overlap display');
  await popup.locator('.qualification').first().evaluate(el=>el.open=true);
  check(await popup.locator('.qualification-proof blockquote').count()>0,'Shows exact original source evidence for qualifications');
  const profile=await worker.evaluate(async()=>(await chrome.storage.local.get('profile')).profile);
  check(profile.firstName==='Alex','Bootstraps example autofill profile');
  await popup.locator('#scan').click();await popup.waitForFunction(()=>document.querySelector('#count').textContent.includes('4 fields'));
  await popup.locator('#fill').click();await popup.waitForFunction(()=>document.querySelector('#status').textContent.includes('Filled 4 of 4'));
  check(await fixture.locator('#first').inputValue()==='Alex','Autofill works alongside resume generation');
  check(await fixture.locator('#school').inputValue()==='Example University','Education profile is available');
  const lastId=await worker.evaluate(async()=>(await chrome.storage.local.get('afLastResume')).afLastResume);
  const viewerPromise=context.waitForEvent('page');await popup.locator('#view-resume').click();const viewer=await viewerPromise;
  await viewer.waitForFunction(()=>!document.getElementById('download').disabled);
  check((await viewer.locator('#title').innerText()).includes('Fixture Company'),'Private PDF preview loads');
  check((await viewer.locator('#pdf').getAttribute('src')).startsWith('blob:'),'PDF bytes are loaded through authenticated background');
  const downloadPromise=viewer.waitForEvent('download');await viewer.locator('#download').click();const download=await downloadPromise;
  check(download.suggestedFilename().endsWith('-resume.pdf'),'PDF download is offered with a friendly name');
  await popup.locator('#generate-resume').click();await popup.waitForFunction(()=>document.getElementById('resume-status').textContent.includes('One page verified'));
  const cachedId=await worker.evaluate(async()=>(await chrome.storage.local.get('afLastResume')).afLastResume);
  check(cachedId===lastId,'Repeated job activation reuses the existing artifact');
  await popup.locator('#regenerate').click();await popup.waitForFunction(()=>document.getElementById('resume-status').textContent.includes('One page verified'));
  const newId=await worker.evaluate(async()=>(await chrome.storage.local.get('afLastResume')).afLastResume);
  check(newId!==lastId,'Explicit regeneration creates a new version');
  await popup.locator('#resume-history').evaluate(el=>el.open=true);await popup.locator('#refresh-history').click();
  await popup.waitForFunction(()=>document.querySelectorAll('.history-row').length>=2);
  check(await popup.locator('.history-row').count()===2,'History contains both versions');
  const options=await context.newPage();await options.goto(`chrome-extension://${id}/profile.html`);
  await options.waitForFunction(()=>document.getElementById('firstName').value==='Alex');
  await options.locator('#phone').fill('202-555-0100');await options.locator('button[type=submit]').click();
  check((await options.locator('#status').innerText()).startsWith('Saved.'),'Profile editor still saves');
  check(errors.length===0,'Popup has no uncaught JavaScript errors');
  if(process.env.SCREENSHOT)await popup.screenshot({path:process.env.SCREENSHOT,fullPage:true});
  console.log(JSON.stringify({passed:tests.length,tests},null,2));
 }finally{
  if(context)await context.close();if(server)server.kill();
  if(originalConfig)fs.writeFileSync(configPath,originalConfig);else fs.rmSync(configPath,{force:true});fs.writeFileSync(path.join(ext,'manifest.json'),originalManifest);
  fs.rmSync(temp,{recursive:true,force:true});
 }
})().catch(e=>{console.error(e);if(stderr)console.error(stderr);process.exitCode=1;});
