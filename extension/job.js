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
      return (doc.body.textContent||'').replace(/\s+/g,' ').trim().slice(0,40000);
    }
    const posting=jobs.length===1?jobs[0]:null;
    const descriptionEl=document.querySelector('[data-automation-id="jobPostingDescription"], [data-testid="job-description"], #job-description, #jobDescription, .job-description, .job__description, [itemprop="description"], #content .content, .posting-page .section-wrapper');
    const title=posting?.title || document.querySelector('[itemprop="title"], [data-automation-id="jobPostingHeader"], h1')?.textContent || '';
    const company=posting?.hiringOrganization?.name || document.querySelector('[itemprop="hiringOrganization"], [data-testid="company-name"], .company-name')?.textContent || '';
    const description=posting?plain(posting.description):descriptionEl?.innerText?.trim().slice(0,40000)||'';
    const url=new URL(location.href);url.hash='';
    ['utm_source','utm_medium','utm_campaign','utm_term','utm_content','gh_src','source'].forEach(k=>url.searchParams.delete(k));
    return {title:String(title).trim().slice(0,250),company:String(company).trim().slice(0,250),description,url:url.href,
      confident:!!posting && !!title && !!company && description.length>=80,
      note:jobs.length>1?'Several jobs found. Confirm the correct job below.':''};
  }
  globalThis.ApplyFlowJob={extract};
})();
