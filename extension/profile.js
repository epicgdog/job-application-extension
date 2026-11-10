const $=id=>document.getElementById(id);
const node=(tag,text)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;};
const inputs=new Map(); let answers=[];
for(const group of [...new Set(ApplyFlowSchema.map(f=>f.group))]) {
  const section=node('section');section.className='card';section.id=group.toLowerCase();
  section.append(node('h2',group));
  if(group==='Experience'||group==='Education') {const p=node('p','Save one entry here. For applications with several entries, choose the matching fields manually in the preview.');p.className='muted';section.append(p);}
  const grid=node('div');grid.className='grid';
  for(const field of ApplyFlowSchema.filter(f=>f.group===group)) {
    const label=node('label',field.label);
    const input=node(field.key==='summary'?'textarea':'input');input.id=field.key;
    input.name=field.key;
    if(input.tagName==='INPUT')input.type=field.key==='email'?'email':['linkedin','github','website'].includes(field.key)?'url':'text';
    input.autocomplete=field.autocomplete||'off';
    label.append(input);grid.append(label);inputs.set(field.key,input);
  }
  section.append(grid);$('sections').append(section);
  const link=node('a',group);link.href='#'+section.id;$('nav').append(link);
}
const answerLink=node('a','Saved answers');answerLink.href='#answers';$('nav').append(answerLink);
function renderAnswers() {
  $('answer-list').replaceChildren();
  for(const a of answers) {
    const row=node('div');row.className='answer';
    const toolbar=node('div');toolbar.className='toolbar';toolbar.append(node('strong','Answer '+(answers.indexOf(a)+1)));
    const remove=node('button','Remove');remove.type='button';remove.className='quiet';
    remove.onclick=()=>{answers=answers.filter(item=>item!==a);renderAnswers();dirty();};toolbar.append(remove);
    const q=node('label','Question as shown on the form');const qi=node('input');qi.value=a.question;qi.maxLength=250;
    qi.oninput=()=>{a.question=qi.value;dirty();};q.append(qi);
    const label=node('label','Your answer');label.style.marginTop='12px';const ai=node('textarea');ai.value=a.answer;ai.maxLength=10000;
    ai.oninput=()=>{a.answer=ai.value;dirty();};label.append(ai);
    row.append(toolbar,q,label);$('answer-list').append(row);
  }
}
function dirty(){$('status').textContent='Unsaved changes';}
$('form').addEventListener('input',dirty);
function load(profile) {
  for(const [key,input] of inputs)input.value=String(profile[key]||'');
  answers=(profile.answers||[]).map(a=>({...a}));renderAnswers();
}
function read() {
  return {...Object.fromEntries([...inputs].map(([key,input])=>[key,input.value.trim()])),
    answers:answers.filter(a=>a.question.trim()&&a.answer.trim()).map(a=>({id:a.id,question:a.question.trim(),answer:a.answer.trim()}))};
}
$('add-answer').onclick=()=>{answers.push({id:crypto.randomUUID(),question:'',answer:''});renderAnswers();dirty();};
$('form').onsubmit=async(event)=>{
  event.preventDefault();
  try {await chrome.storage.local.set({profile:read()});$('status').textContent='Saved. You’re ready to fill applications.';}
  catch(error){$('status').textContent='Could not save: '+error.message;}
};
$('export').onclick=()=>{
  const data=JSON.stringify({format:'applyflow',version:1,profile:read()},null,2);
  const url=URL.createObjectURL(new Blob([data],{type:'application/json'}));
  const a=node('a');a.href=url;a.download='applyflow-profile.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  $('data-status').textContent='Exported current profile. This file contains your personal information.';
};
$('import').onclick=()=>$('file').click();
$('file').onchange=async()=>{
  try {
    const file=$('file').files[0];if(!file)return;if(file.size>500000)throw new Error('Profile file is too large.');
    const data=JSON.parse(await file.text());
    if(data.format!=='applyflow'||data.version!==1||!data.profile||typeof data.profile!=='object')throw new Error('Choose an ApplyFlow profile export.');
    const p={};for(const field of ApplyFlowSchema)if(typeof data.profile[field.key]==='string')p[field.key]=data.profile[field.key].slice(0,10000);
    p.answers=(Array.isArray(data.profile.answers)?data.profile.answers:[]).slice(0,100).filter(a=>a&&typeof a.question==='string'&&typeof a.answer==='string')
      .map(a=>({id:crypto.randomUUID(),question:a.question.slice(0,250),answer:a.answer.slice(0,10000)}));
    load(p);dirty();$('data-status').textContent='Imported into the editor. Review and click Save profile.';
  }catch(error){$('data-status').textContent=error.message;}
  $('file').value='';
};
$('delete').onclick=async()=>{
  if(!confirm('Delete your saved profile from this browser?'))return;
  try {await chrome.storage.local.remove('profile');load({});$('status').textContent='Saved profile deleted.';$('data-status').textContent='Your stored details have been removed.';}
  catch(error){$('data-status').textContent='Could not delete: '+error.message;}
};
chrome.storage.local.get('profile').then(({profile})=>load(profile||{})).catch(error=>{$('status').textContent=error.message;});
