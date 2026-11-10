const $ = id=>document.getElementById(id);
let profile = {}, fields = [], tabId, busy = false;
const status = (message,error=false) => { $('status').textContent=message; $('status').classList.toggle('error',error); };
function lock(value) { busy=value; for(const id of ['scan','fill','toggle']) $(id).disabled=value; }
const node = (tag,text,cls) => { const el=document.createElement(tag); if(text!==undefined) el.textContent=text; if(cls) el.className=cls; return el; };
$('profile').onclick=()=>chrome.runtime.openOptionsPage();
$('demo').onclick=()=>chrome.tabs.create({url:chrome.runtime.getURL('demo.html')});
async function inPage(action,args) {
  const result=await chrome.scripting.executeScript({target:{tabId},func:async(action,args)=>{
    if(!globalThis.ApplyFlowContent) throw new Error('Page reloaded. Scan again.');
    return globalThis.ApplyFlowContent[action](...args);
  },args:[action,args]});
  if (!result[0]?.result) throw new Error('Page reloaded. Scan again.');
  return result[0].result;
}
function render() {
  $('overwrite').disabled=false;
  $('fields').replaceChildren();
  const choices=[...ApplyFlowSchema.map(f=>({key:f.key,label:f.label})),...(profile.answers||[]).map(a=>({key:'answer:'+a.id,label:a.question}))]
    .filter(f=>ApplyFlowEngine.valueFor(f.key,profile).trim());
  fields.forEach(field=>{
    const row=node('div',undefined,'field');
    const top=node('div',undefined,'field-top');
    const check=node('input'); check.type='checkbox'; check.id='check-'+field.id; check.checked=!!field.key;
    const label=node('label',field.label); label.htmlFor=check.id; top.append(check,label);
    const select=node('select'); select.setAttribute('aria-label','Saved detail for '+field.label);
    const blank=node('option','Choose a saved detail…'); blank.value=''; select.append(blank);
    choices.forEach(choice=>{const opt=node('option',choice.label); opt.value=choice.key; select.append(opt);});
    select.value=field.key;
    const value=node('div',undefined,'value');
    const result=node('div',undefined,'result');
    function update() {
      field.key=select.value;
      field.value=ApplyFlowEngine.valueFor(field.key,profile);
      const noOption=field.options && ApplyFlowEngine.selectValue(field.options,field.value)===null;
      const existing=String(field.current).trim() && !(field.options?.find(o=>o.value===field.current)?.disabled);
      const skipExisting=existing && !$('overwrite').checked;
      check.disabled=!field.key || !field.value.trim() || noOption || !!skipExisting;
      if(check.disabled) check.checked=false;
      value.textContent=noOption ? 'No matching dropdown option. Edit your profile or choose it on the page.' :
        skipExisting ? 'Already filled — kept as is.' : field.value || 'No saved match. Choose a detail above, or fill this field yourself.';
      field.selected=check.checked && !check.disabled;
    }
    select.onchange=()=>{check.checked=true;update();}; check.onchange=update;
    field.update=update; field.check=check; field.result=result;
    update(); row.append(top,select,value,result); $('fields').append(row);
  });
  $('count').textContent=fields.length+' fields to review';
}
$('overwrite').onchange=()=>fields.forEach(f=>f.update());
$('toggle').onclick=()=>{
  const enable=!fields.some(f=>f.selected);
  fields.forEach(f=>{f.check.checked=enable&&!f.check.disabled;f.update();});
  $('toggle').textContent=enable?'Deselect all':'Select available';
};
$('scan').onclick=async()=>{
  lock(true); $('preview').hidden=true; status('Reading form fields…');
  try {
    profile=(await chrome.storage.local.get('profile')).profile||{};
    if (!ApplyFlowSchema.some(f=>ApplyFlowEngine.valueFor(f.key,profile).trim()) && !(profile.answers||[]).length) {
      status('Add your details in Edit profile first.'); return;
    }
    const [tab]=await chrome.tabs.query({active:true,currentWindow:true}); tabId=tab.id;
    // The bundled demo is an extension page: Chrome does not allow executeScript on it.
    if(tab.url?.startsWith(chrome.runtime.getURL(''))) {status('For the demo, use its built-in Test autofill button. On websites, scan from this popup.');return;}
    await chrome.scripting.executeScript({target:{tabId},files:['schema.js','engine.js','content.js']});
    const scanned=await inPage('scan',[profile]); fields=scanned.fields;
    render(); $('preview').hidden=!fields.length;
    status(fields.length?`Found ${fields.length} fields. Review matches below.${scanned.frames?' Embedded forms may need opening in their own tab.':''}`:
      'No supported visible fields found. Open the application form. Custom dropdowns and embedded forms may need manual entry.');
  } catch(error) { status('Could not scan this page. Open a regular website tab and try again. '+error.message,true); }
  finally {lock(false);}
};
$('fill').onclick=async()=>{
  const plan=fields.filter(f=>f.selected).map(({id,signature,current,value})=>({id,signature,current,value}));
  if(!plan.length) {status('Select at least one available field.');return;}
  lock(true); status('Filling selected fields…');
  try {
    const results=await inPage('fill',[plan,$('overwrite').checked]);
    results.forEach(r=>{const field=fields.find(f=>f.id===r.id); field.result.textContent=r.status;});
    status(`Filled ${results.filter(r=>r.status==='Filled').length} of ${plan.length} fields. Review the page. Scan again after moving to the next step.`);
    // A new scan is required before filling a second time, since page values have changed.
    $('preview').querySelectorAll('input,select,button').forEach(el=>el.disabled=true);
  } catch(error) {status(error.message,true);}
  finally {lock(false);$('fill').disabled=true;$('toggle').disabled=true;}
};
chrome.storage.local.get('profile').then(({profile:p})=>{
  if(p && Object.values(p).some(v=>typeof v==='string' && v.trim())) status('Profile ready. Open an application and scan its fields.');
});
