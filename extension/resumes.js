// Job and resume UI lives beside the existing autofill UI.
(async()=>{
  const el=id=>document.getElementById(id);
  const msg=async(op,data={})=>{
    const r=await chrome.runtime.sendMessage({type:'applyflow',op,...data});
    if(!r?.ok)throw new Error(r?.error||'Extension background unavailable. Reload the extension.');
    return r.data;
  };
  let job={url:'',title:'',company:'',description:''},currentId,jobIdForResult,authed=false,requestBusy=false,lastFailed=false,pollTimer;
  const say=(text,error=false)=>{el('resume-status').textContent=text;el('resume-status').classList.toggle('error',error);};
  function lock(value){requestBusy=value;for(const id of ['generate-resume','regenerate','detect-job'])el(id).disabled=value;}
  function readJob(){return {...job,title:el('job-title').value.trim(),company:el('job-company').value.trim(),description:el('job-description').value.trim()};}
  const identity=j=>JSON.stringify(j);
  function populate(){el('job-title').value=job.title;el('job-company').value=job.company;el('job-description').value=job.description;}
  function view(id){chrome.tabs.create({url:chrome.runtime.getURL('viewer.html')+'?id='+encodeURIComponent(id)});}
  function show(row){
    currentId=row.id;
    const complete=row.state==='complete';lastFailed=row.state==='failed';
    el('generate-resume').textContent=lastFailed?'Retry generation':'Generate resume';el('resume-result').hidden=!complete;
    if(complete){
      el('resume-entries').textContent=(row.result?.selected_entries||[]).map(e=>e.name).join(' · ');
      ApplyFlowQualifications.render(el('qualification-report'),row.result?.qualification_report);
      say(`One page verified. ${el('mode-label').dataset.local==='true'?'Saved locally on this computer.':'Saved privately in Supabase.'} Original bullets preserved.`);
      lock(false);loadHistory();
    }else if(row.state==='failed'){say(row.error||'Generation failed. Retry using Generate resume.',true);lock(false);}
    else{say({queued:'Queued…',generating:'Selecting complete entries and verifying the PDF…',uploading:'Saving your resume…'}[row.state]||row.state);lock(true);pollTimer=setTimeout(poll,1400);}
  }
  async function poll(){
    try{show(await msg('get',{id:currentId}));}
    catch(error){say(error.message+' Reopen this popup to resume checking.',true);lock(false);}
  }
  async function generate(force=false){
    if(requestBusy)return;
    job=readJob();
    if(!job.title||!job.company||job.description.length<80){say('Confirm a job title, company, and at least 80 characters of description.',true);el('job-details').open=true;return;}
    force=force||lastFailed;
    lock(true);clearTimeout(pollTimer);el('resume-result').hidden=true;say('Preparing your job-specific resume…');
    try {
      // Preserve a job snapshot for description-less application pages of the same URL.
      const stored=(await chrome.storage.local.get('afJobs')).afJobs||{};
      stored[job.url]={...job};
      const keys=Object.keys(stored);while(keys.length>30)delete stored[keys.shift()];
      await chrome.storage.local.set({afJobs:stored});
      const row=await msg('generate',{job,regenerationId:force?crypto.randomUUID():''});
      jobIdForResult=identity(job);show(row);
    }catch(error){say(error.message,true);lock(false);}
  }
  async function detect(auto=false){
    try{
      const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
      if(!/^https?:/.test(tab?.url||'')){say('Open a job posting in a website tab, then choose Read page.');return;}
      await chrome.scripting.executeScript({target:{tabId:tab.id},files:['job.js']});
      const results=await chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>ApplyFlowJob.extract()});
      const found=results[0]?.result;if(!found)throw new Error('Could not read this job.');
      const stored=(await chrome.storage.local.get('afJobs')).afJobs||{};
      const previous=stored[found.url];
      job={title:found.title,company:found.company,url:found.url,description:found.description};
      if(!job.description&&previous)job={...previous,...job,description:previous.description,company:job.company||previous.company,title:job.title||previous.title};
      populate();
      const valid=job.title&&job.company&&job.description.length>=80;
      if(!valid){el('job-details').open=true;say(found.note||'Confirm the title/company and add the job description to generate a resume.');}
      else if(auto&&(found.confident||previous))await generate();
      else say('Review the job details, then generate your resume.');
    }catch(error){say('Could not read the page. Paste the job details below. '+error.message,true);el('job-details').open=true;}
  }
  async function loadHistory(){
    try{
      const rows=await msg('history');el('history-list').replaceChildren();
      if(!rows.length)el('history-list').textContent='No resumes yet.';
      for(const row of rows){
        const item=document.createElement('div');item.className='history-row';
        const text=document.createElement('span');text.textContent=`${row.job.company} · ${row.job.title} — ${row.state}`;
        item.append(text);
        if(row.state==='complete'){const button=document.createElement('button');button.className='quiet';button.textContent='Open';button.onclick=()=>view(row.id);item.append(button);}
        else if(['queued','generating','uploading'].includes(row.state)){const button=document.createElement('button');button.className='quiet';button.textContent='Check';button.onclick=()=>{clearTimeout(pollTimer);show(row);};item.append(button);}
        else{const hint=document.createElement('small');hint.textContent=row.error||'';item.append(hint);}
        el('history-list').append(item);
      }
    }catch(error){el('history-list').textContent=error.message;}
  }
  async function setup(){
    const state=await msg('status');authed=state.signedIn;
    el('mode-label').dataset.local=String(state.localMode);
    el('mode-label').textContent=state.localMode?'Local mode · PDFs stay on this computer. Configure Supabase to enable cloud storage.':(authed?'Private Supabase storage · '+state.email:'Sign in to your private Supabase project.');
    el('auth-panel').hidden=authed;el('job-editor').hidden=!authed;el('sign-out').hidden=state.localMode||!authed;
    if(!authed){say('Sign in with an email code to get started.');return;}
    try{await msg('bootstrap');await detect(true);await loadHistory();}
    catch(error){say(error.message,true);}
  }
  el('send-code').onclick=async()=>{
    el('send-code').disabled=true;
    try{await msg('sendCode',{email:el('auth-email').value.trim()});say('Code sent. Check your email.');}
    catch(error){say(error.message,true);}finally{el('send-code').disabled=false;}
  };
  el('verify-code').onclick=async()=>{
    el('verify-code').disabled=true;
    try{await msg('verifyCode',{email:el('auth-email').value.trim(),code:el('auth-code').value.trim()});await setup();}
    catch(error){say(error.message,true);}finally{el('verify-code').disabled=false;}
  };
  el('sign-out').onclick=async()=>{clearTimeout(pollTimer);await msg('logout');el('resume-result').hidden=true;el('history-list').replaceChildren();await setup();};
  el('generate-resume').onclick=()=>generate(false);
  el('regenerate').onclick=()=>generate(true);
  el('detect-job').onclick=()=>detect(false);
  el('view-resume').onclick=()=>view(currentId);
  el('refresh-history').onclick=loadHistory;
  for(const id of ['job-title','job-company','job-description'])el(id).addEventListener('input',()=>{
    if(jobIdForResult&&jobIdForResult!==identity(readJob())){el('resume-result').hidden=true;say('Job details changed. Generate an updated resume.');}
  });
  try{await setup();}catch(error){say(error.message,true);}
})();
