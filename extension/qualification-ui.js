(() => {
  const make=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
  function render(container,report){
    container.replaceChildren();
    if(!report){container.append(make('p','This resume used the older matcher. Regenerate it to see qualification evidence.','muted'));return;}
    for(const tier of ['required','preferred']){
      const qualifications=report[tier]||[];
      if(!qualifications.length)continue;
      container.append(make('h3',tier==='required'?'Required qualifications':'Preferred qualifications'));
      for(const q of qualifications){
        const details=make('details',undefined,'qualification');
        const summary=make('summary');
        const labels={evidence:'Source evidence found',partial:'Partial / listed evidence',not_evidenced:'No direct source evidence',omitted:'Evidence in omitted entries',review:'Needs review'};
        summary.append(make('span',labels[q.status]||'Needs review','qualification-status '+q.status),make('span',q.text,'qualification-text'));
        details.append(summary);
        if(q.note)details.append(make('p',q.note,'muted'));
        if(q.recognized_skills?.length)details.append(make('p','Skills examined: '+q.recognized_skills.join(', '),'muted'));
        if(q.missing_skills?.length)details.append(make('p','Not evidenced in this resume: '+q.missing_skills.join(', '),'qualification-gap'));
        for(const e of (q.evidence||[]).slice(0,6)){
          const proof=make('div',undefined,'qualification-proof');
          const source=e.source==='bullet'?'Original bullet':e.source==='technologies'?'Technology list':e.source==='skills'?'Skills section':e.source==='education'?'Education':e.source==='coursework'?'Coursework':'Role history';
          const location=e.entry_id?(e.included?'Selected entry':'Master entry left out'):'Included fixed section';
          proof.append(make('small',source+' · '+location+(e.entry_name?' · '+e.entry_name:'')),make('blockquote',e.text));
          details.append(proof);
        }
        if(!(q.evidence||[]).length)details.append(make('p','No direct evidence was found in the source library.','muted'));
        if((q.evidence||[]).length>6)details.append(make('p','Additional source evidence is saved with this resume.','muted'));
        container.append(details);
      }
    }
    container.append(make('p','Evidence mapping is not an eligibility check. Review proficiency, years, dates, and any other conditions.','muted'));
  }
  globalThis.ApplyFlowQualifications={render};
})();
