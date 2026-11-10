const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../extension/background.js'),'utf8');
function harness(session){
 const data=session?{afSession:session}:{};const requests=[];let listener,refreshes=0;
 const context={ApplyFlowConfig:{localMode:false,api:'https://api.example.test',supabaseUrl:'https://project.supabase.co',supabaseKey:'sb_publishable_fixture'},importScripts(){},AbortController,setTimeout,clearTimeout,Uint8Array,btoa:s=>Buffer.from(s,'binary').toString('base64'),chrome:{storage:{local:{setAccessLevel:async()=>{},get:async key=>({[key]:data[key]}),set:async values=>Object.assign(data,values),remove:async keys=>[].concat(keys).forEach(k=>delete data[k])}},runtime:{id:'fixture',getURL:p=>'chrome-extension://fixture/'+p,onInstalled:{addListener(){}},onStartup:{addListener(){}},onMessage:{addListener(fn){listener=fn;}}}},fetch:async(url,options)=>{
  requests.push({url,options});let result={};
  if(url.includes('token?grant_type=refresh_token')){refreshes++;await new Promise(r=>setTimeout(r,10));result={access_token:'new-access',refresh_token:'new-refresh',expires_in:3600,user:{email:'fixture@example.com'}};}
  else if(url.endsWith('/verify'))result={access_token:'verified-access',refresh_token:'verified-refresh',expires_in:3600,user:{email:'fixture@example.com'}};
  else if(url.endsWith('/resumes'))result=[];
  return {ok:true,json:async()=>result};
 }};
 vm.runInNewContext(source,context);
 function invoke(op,payload={},sender={id:'fixture',url:'chrome-extension://fixture/popup.html'}) {
  return new Promise(resolve=>{const keep=listener({type:'applyflow',op,...payload},sender,resolve);if(!keep)resolve(undefined);});
 }
 return {data,requests,invoke,get refreshes(){return refreshes;}};
}
test('content scripts cannot request authenticated operations',async()=>{
 const h=harness();assert.equal(await h.invoke('history',{}, {id:'fixture',url:'https://employer.example/apply'}),undefined);assert.equal(h.requests.length,0);
});
test('OTP sign-in stores session without exposing tokens in response',async()=>{
 const h=harness();const r=await h.invoke('verifyCode',{email:'fixture@example.com',code:'123456'});
 assert.equal(r.ok,true);assert.equal(r.data.signedIn,true);assert.equal(h.data.afSession.access_token,'verified-access');assert.ok(!JSON.stringify(r).includes('verified-access'));
});
test('expired concurrent requests share one refresh and use the new token',async()=>{
 const h=harness({access_token:'old',refresh_token:'refresh',expires_at:1,email:'fixture@example.com'});
 const responses=await Promise.all([h.invoke('history'),h.invoke('history')]);
 assert.ok(responses.every(r=>r.ok));assert.equal(h.refreshes,1);
 assert.ok(h.requests.filter(r=>r.url.endsWith('/resumes')).every(r=>r.options.headers.Authorization==='Bearer new-access'));
});
test('signed-out cloud requests fail before contacting private API',async()=>{
 const h=harness();const r=await h.invoke('history');assert.equal(r.ok,false);assert.match(r.error,/Sign in/);assert.equal(h.requests.length,0);
});
test('logout removes saved session',async()=>{
 const h=harness({access_token:'session',refresh_token:'refresh',expires_at:9999999999});
 await h.invoke('logout');assert.equal(h.data.afSession,undefined);
});
