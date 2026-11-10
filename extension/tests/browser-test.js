(async()=>{
 const assertions=[];
 function ok(condition,message){assertions.push({pass:!!condition,message});if(!condition)throw new Error(message);}
 const $=id=>document.getElementById(id);
 const shadow=$('shadow').attachShadow({mode:'open'});shadow.innerHTML='<label>GitHub URL<input id="github" type="url"></label>';
 const profile={firstName:'Ada',lastName:'Lovelace',email:'new@example.com',country:'USA',summary:'Mathematician',city:'London',postalCode:'12345',school:'University',github:'https://github.com/ada',answers:[{id:'why',question:'Why are you interested in this role?',answer:'I like the work.'}]};
 try{
  let {fields}=ApplyFlowContent.scan(profile);
  const fieldFor=id=>fields.find(f=>f.id && f.label=== (id==='first'?'First name':id));
  ok(fields.length===13,'Scans only supported visible editable controls, including open shadow DOM');
  ok(!fields.some(f=>f.label==='Password'),'Skips passwords');
  ok(fields.find(f=>f.label==='Phone country code').key==='','Does not confuse country dialing codes');
  ok(fields.filter(f=>f.label==='School').every(f=>!f.key),'Duplicate education fields require manual mapping');
  ok(fields.filter(f=>f.label==='First name').filter(f=>f.key).length===1,'Reference name is not mapped to applicant');
  let events=0;$('first').addEventListener('input',()=>events++);
  // Own value setter mimics the tracking wrapper used by controlled UI frameworks.
  let tracked=0;Object.defineProperty($('last'),'value',{configurable:true,get(){return Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').get.call(this);},set(v){tracked++;Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(this,v);}});
  let plan=fields.filter(f=>f.key&&ApplyFlowEngine.valueFor(f.key,profile)).map(f=>({...f,value:ApplyFlowEngine.valueFor(f.key,profile)}));
  $('city').value='User changed this';
  $('zip').setAttribute('aria-label','Different question');
  let results=await ApplyFlowContent.fill(plan,false);
  ok($('first').value==='Ada'&&$('last').value==='Lovelace','Fills contact details');
  ok(events===1&&tracked===0,'Uses native value setter and dispatches input event');
  ok($('email').value==='existing@example.com','Preserves existing values');
  ok($('country').value==='US','Matches dropdown country alias');
  ok($('summary').value==='Mathematician','Fills textarea');
  ok($('why').value==='I like the work.','Fills exact saved-answer question');
  ok(shadow.getElementById('github').value===profile.github,'Fills shadow DOM field');
  ok($('city').value==='User changed this','Preserves changes made after preview');
  ok($('zip').value==='','Skips fields whose label changed after preview');
  ok(results.some(r=>r.status.includes('Page changed')),'Reports changed-page skip');
  ok($('ref').value===''&&$('school1').value===''&&$('school2').value==='','Leaves ambiguous and reference fields alone');
  fields=ApplyFlowContent.scan(profile).fields;
  plan=fields.filter(f=>f.key==='email').map(f=>({...f,value:profile.email}));
  await ApplyFlowContent.fill(plan,true);
  ok($('email').value==='new@example.com','Overwrites only with explicit overwrite setting');
  $('first').remove();
  const stale=await ApplyFlowContent.fill([{id:'not-existing',signature:'x',value:'x',current:''}],false);
  ok(stale[0].status.includes('Page changed'),'Detached field is skipped safely');
  $('output').textContent=JSON.stringify({passed:assertions.length,assertions},null,2);
  document.documentElement.dataset.testStatus='PASS';
 }catch(error){$('output').textContent=JSON.stringify({error:error.message,assertions},null,2);document.documentElement.dataset.testStatus='FAIL';}
})();
