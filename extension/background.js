importScripts('config.js');
const config=ApplyFlowConfig;
const restrict=()=>chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'});
chrome.runtime.onInstalled.addListener(restrict);chrome.runtime.onStartup.addListener(restrict);restrict();
let refreshPromise;
async function request(url,options={}) {
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),40000);
  try {
    const response=await fetch(url,{...options,signal:controller.signal,cache:'no-store'});
    if(!response.ok) {
      let info={};try{info=await response.json();}catch{}
      throw new Error(info.error_description||info.msg||info.message||info.error||`Request failed (${response.status})`);
    }
    return response;
  } catch(error) {
    if(error.name==='AbortError')throw new Error('Request timed out. Reopen the popup to check history before retrying.');
    if(error instanceof TypeError)throw new Error('Cannot reach the resume service. Start the server and check your configuration.');
    throw error;
  } finally {clearTimeout(timer);}
}
async function authCall(path,body,token) {
  return (await request(config.supabaseUrl+'/auth/v1/'+path,{method:'POST',headers:{apikey:config.supabaseKey,'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},body:JSON.stringify(body)})).json();
}
async function persistSession(s) {
  if(!s.access_token||!s.refresh_token)throw new Error('Sign-in did not return a session. Check the email OTP template.');
  await chrome.storage.local.set({afSession:{access_token:s.access_token,refresh_token:s.refresh_token,expires_at:s.expires_at||Math.floor(Date.now()/1000)+(s.expires_in||3600),email:s.user?.email||''}});
  return s.access_token;
}
async function token() {
  if(config.localMode)return config.localToken;
  const {afSession:s}=await chrome.storage.local.get('afSession');
  if(!s)throw new Error('Sign in to save resumes in Supabase.');
  if(s.expires_at*1000>Date.now()+60000)return s.access_token;
  if(!refreshPromise)refreshPromise=authCall('token?grant_type=refresh_token',{refresh_token:s.refresh_token}).then(persistSession).catch(async()=>{await chrome.storage.local.remove('afSession');throw new Error('Sign-in expired. Enter a new email code.');}).finally(()=>{refreshPromise=null;});
  return refreshPromise;
}
async function api(path,method='GET',body) {
  const response=await request(config.api+path,{method,headers:{Authorization:'Bearer '+await token(),...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
  return path.endsWith('/pdf')?response.arrayBuffer():response.json();
}
async function run(message) {
  switch(message.op) {
    case 'status': {
      const {afSession:s}=await chrome.storage.local.get('afSession');
      return {localMode:config.localMode,signedIn:config.localMode||!!s,email:s?.email||''};
    }
    case 'sendCode':
      if(config.localMode)throw new Error('Email sign-in is only used in Supabase mode.');
      if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(message.email))throw new Error('Enter a valid email.');
      await authCall('otp',{email:message.email,create_user:true});return {sent:true};
    case 'verifyCode':
      await persistSession(await authCall('verify',{email:message.email,token:message.code,type:'email'}));
      return {signedIn:true};
    case 'logout': {
      const {afSession:s}=await chrome.storage.local.get('afSession');
      if(s)try{await request(config.supabaseUrl+'/auth/v1/logout',{method:'POST',headers:{apikey:config.supabaseKey,Authorization:'Bearer '+s.access_token}});}catch{}
      await chrome.storage.local.remove(['afSession','afLastResume']);return {signedIn:false};
    }
    case 'bootstrap': {
      const data=await api('/bootstrap');
      const {profile}=await chrome.storage.local.get('profile');
      if(!profile||!Object.keys(profile).length)await chrome.storage.local.set({profile:data.profile});
      return {mode:data.mode,entryCount:data.entry_count};
    }
    case 'generate': {
      const row=await api('/resumes','POST',{job:message.job,regeneration_id:message.regenerationId||''});
      await chrome.storage.local.set({afLastResume:row.id});return row;
    }
    case 'get':return api('/resumes/'+encodeURIComponent(message.id));
    case 'history':return api('/resumes');
    case 'pdf': {
      const data=new Uint8Array(await api('/resumes/'+encodeURIComponent(message.id)+'/pdf'));
      let binary='';for(const b of data)binary+=String.fromCharCode(b);
      return {base64:btoa(binary)};
    }
    default:throw new Error('Unknown extension operation.');
  }
}
chrome.runtime.onMessage.addListener((message,sender,respond)=>{
  // Content scripts and websites cannot request sessions, profiles, or private PDFs.
  if(message?.type!=='applyflow' || sender.id!==chrome.runtime.id || !sender.url?.startsWith(chrome.runtime.getURL('')))return;
  run(message).then(data=>respond({ok:true,data})).catch(error=>respond({ok:false,error:error.message}));
  return true;
});
