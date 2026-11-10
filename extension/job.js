(() => {
  function extract() {
    const jobs=[];
    function walk(value,depth=0) {
      if(!value || depth>12)return;
      if(Array.isArray(value)){value.slice(0,100).forEach(v=>walk(v,depth+1));return;}
      if(typeof value!=='object')return;
      if([].concat(value['@type']||[]).some(t=>t==='JobPosting' || t==='https://schema.org/JobPosting'))jobs.push(value);
      if(value['@graph'])walk(value['@graph'],depth+1);
      if(value.mainEntity)walk(value.mainEntity,depth+1);
    }
    document.querySelectorAll('script[type="application/ld+json"]').forEach(s=>{
      if(s.textContent.length>1000000)return;
      try{walk(JSON.parse(s.textContent));}catch{}
    });
    function plain(html) {
      const doc=new DOMParser().parseFromString(String(html||''),'text/html');
      doc.querySelectorAll('script,style,noscript').forEach(el=>el.remove());
      // Keep section headings/list items separate, including "<b>Required
      // Qualifications</b><ul>...". textContent previously glued them together.
      doc.querySelectorAll('br').forEach(el=>el.replaceWith(doc.createTextNode('\n')));
      doc.querySelectorAll('p,div,section,h1,h2,h3,h4,h5,h6,li,ul,ol').forEach(el=>{
        el.before(doc.createTextNode('\n'));el.after(doc.createTextNode('\n'));
      });
      doc.querySelectorAll('strong,b').forEach(el=>{
        if(/^(required|preferred|minimum|basic|essential|desired) (qualifications|requirements|skills)$/i.test(el.textContent.trim())){el.before(doc.createTextNode('\n'));el.after(doc.createTextNode('\n'));}
      });
      return (doc.body.textContent||'').split('\n').map(line=>line.replace(/[ \t]+/g,' ').trim()).filter(Boolean).join('\n').slice(0,40000);
    }
    const posting=jobs.length===1?jobs[0]:null;
    const descriptionEl=document.querySelector('[data-automation-id="jobPostingDescription"], [data-testid="job-description"], #job-description, #jobDescription, .job-description, .job__description, [itemprop="description"], #content .content, .posting-page .section-wrapper');
    const title=posting?.title || document.querySelector('[itemprop="title"], [data-automation-id="jobPostingHeader"], h1')?.textContent || '';
    const orgName=posting?.hiringOrganization?.name || '';
    const validOrg=!/^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(orgName) ? orgName : '';
    const company=validOrg || document.querySelector('[itemprop="hiringOrganization"], [data-testid="company-name"], .company-name')?.textContent || '';
    const description=posting?plain(posting.description):descriptionEl?.innerText?.trim().slice(0,40000)||'';
    const url=new URL(location.href);url.hash='';
    ['utm_source','utm_medium','utm_campaign','utm_term','utm_content','gh_src','source'].forEach(k=>url.searchParams.delete(k));
    return {title:String(title).trim().slice(0,250),company:String(company).trim().slice(0,250),description,url:url.href,
      confident:!!posting && !!title && !!company && description.length>=80,
      note:jobs.length>1?'Several jobs found. Confirm the correct job below.':''};
  }
  globalThis.ApplyFlowJob={extract};
})();
