document.querySelector('form').addEventListener('submit',e=>e.preventDefault());
document.getElementById('edit').onclick=()=>chrome.runtime.openOptionsPage();
document.getElementById('test').onclick=async()=>{
  const status=document.getElementById('status');
  try {
    const {profile={}}=await chrome.storage.local.get('profile');
    const {fields}=ApplyFlowContent.scan(profile);
    const plan=fields.filter(f=>f.key&&ApplyFlowEngine.valueFor(f.key,profile).trim()).map(f=>({...f,value:ApplyFlowEngine.valueFor(f.key,profile)}));
    if(!plan.length){status.textContent='Save some profile details first using Edit profile.';return;}
    const results=await ApplyFlowContent.fill(plan,false);
    status.textContent=`Filled ${results.filter(r=>r.status==='Filled').length} fields. Review your details below. Existing values were kept.`;
  }catch(error){status.textContent=error.message;}
};
