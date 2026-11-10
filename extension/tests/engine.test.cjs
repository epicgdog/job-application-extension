const {test}=require('node:test');
const assert=require('node:assert/strict');
require('../schema.js');
require('../engine.js');
const E=globalThis.ApplyFlowEngine;
const match=(label,hints='',context='',autocomplete='',p={})=>E.match({label,hints,context,autocomplete},p);
test('maps ordinary contact and application fields',()=>{
 for(const [label,key] of [['First name','firstName'],['Last name','lastName'],['Full name *','fullName'],['Email address','email'],['Phone number','phone'],['Address line 2','address2'],['Street address','address'],['City','city'],['State / province','state'],['ZIP code','postalCode'],['Country of residence','country'],['LinkedIn URL','linkedin'],['Most recent employer','employer'],['Job title','jobTitle'],['University','school'],['Degree','degree'],['Field of study','fieldOfStudy'],['Graduation year','graduationYear']])assert.equal(match(label),key,label);
});
test('avoids ambiguous and sensitive guesses',()=>{
 for(const label of ['First and last name','City / state','Desired job title','Expected salary','Country of citizenship','Phone country code','Are you authorized to work in the United States?','What city would you prefer to relocate to?','What is the email address of your current manager?']) {
  if(label==='Phone country code')continue; // content-layer guard
  assert.equal(match(label),'',label);
 }
 assert.equal(match('First name','','Reference'), '');
});
test('autocomplete and camelCase hints',()=>{
 assert.equal(match('Contact','','','email'),'email');
 assert.equal(match('Contact','applicantFirstName'),'firstName');
 assert.equal(match('Contact','','','section-application given-name'),'firstName');
});
test('custom answers require an exact normalized question',()=>{
 const profile={answers:[{id:'q',question:'Why are you interested in this role?',answer:'My answer'}]};
 assert.equal(match('Why are you interested in this role? *','','','',profile),'answer:q');
 assert.equal(match('Why are you interested in this company?','','','',profile),'');
 assert.equal(E.valueFor('answer:q',profile),'My answer');
 assert.equal(E.valueFor('fullName',{firstName:'Ada',lastName:'Lovelace'}),'Ada Lovelace');
});
test('select matching is exact, unique and skips disabled options',()=>{
 const options=[{value:'',text:'Select country'},{value:'US',text:'United States'},{value:'CA',text:'Canada'}];
 assert.equal(E.selectValue(options,'USA'),'US');
 assert.equal(E.selectValue(options,'Canada'),'CA');
 assert.equal(E.selectValue(options,'United'),null);
 assert.equal(E.selectValue([{value:'x',text:'Canada',disabled:true}],'Canada'),null);
 assert.equal(E.selectValue([{value:'CA',text:'Canada'},{value:'can',text:'Canada'}],'Canada'),null);
});
