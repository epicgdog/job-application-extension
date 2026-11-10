(() => {
  if (globalThis.ApplyFlowContent) return;
  let sequence = 0;
  const ids = new WeakMap();
  const elements = new Map();
  function roots(root = document) {
    const result = [root];
    for (const el of root.querySelectorAll('*')) if (el.shadowRoot) result.push(...roots(el.shadowRoot));
    return result;
  }
  function meta(el) {
    const root = el.getRootNode();
    const labelled = (el.getAttribute('aria-labelledby') || '').split(/\s+/)
      .map(id => root.getElementById?.(id)?.textContent || '').join(' ').trim();
    const labelText = label => {
      const clone = label.cloneNode(true);
      clone.querySelectorAll('input,textarea,select,button').forEach(child=>child.remove());
      return clone.textContent;
    };
    const label = labelled || el.getAttribute('aria-label') || Array.from(el.labels || []).map(labelText).join(' ').trim() || el.placeholder || el.name || el.id || 'Unlabelled field';
    const group = el.closest('fieldset');
    return {label:label.trim().slice(0,250), hints:[el.name,el.id,el.placeholder].filter(Boolean).join(' '),
      context:group?.querySelector('legend')?.textContent || '', autocomplete:el.autocomplete || ''};
  }
  function supported(el) {
    return el.matches('textarea,select,input:not([type]),input[type="text"],input[type="email"],input[type="tel"],input[type="url"],input[type="number"]')
      && !el.disabled && !el.readOnly && !el.matches('[role="combobox"], [aria-autocomplete]')
      && !el.closest('[inert]') && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
  }
  const signature = el => JSON.stringify({...meta(el),tag:el.tagName,type:el.type});
  function scan(profile) {
    elements.clear();
    const fields = [];
    for (const root of roots()) for (const el of root.querySelectorAll('input,textarea,select')) {
      if (!supported(el)) continue;
      if (!ids.has(el)) ids.set(el, String(++sequence));
      const id = ids.get(el);
      const data = meta(el);
      let key = ApplyFlowEngine.match(data,profile);
      // Don't infer a country from a country-code field.
      if (/\b(country code|dial code|dialing code)\b/.test(ApplyFlowEngine.normalize(data.label))) key = '';
      const field = {id,label:data.label,key,current:el.value,signature:signature(el),
        options:el.tagName === 'SELECT' ? Array.from(el.options).map(o=>({value:o.value,text:o.text,disabled:o.disabled || o.parentElement.disabled})) : null};
      fields.push(field);
      elements.set(id,el);
    }
    // Multiple education/employment entries need a deliberate field-by-field choice.
    for (const key of ['school','degree','fieldOfStudy','graduationYear','employer','jobTitle']) {
      const group = fields.filter(f=>f.key===key);
      if (group.length > 1) group.forEach(f=>{ f.key=''; });
    }
    return {fields,frames:document.querySelectorAll('iframe').length};
  }
  async function fill(plan, overwrite) {
    const results = [];
    for (const item of plan) {
      const el = elements.get(item.id);
      let status;
      if (!el?.isConnected || !supported(el) || signature(el) !== item.signature) status = 'Page changed — scan again';
      else if (el.value !== item.current) status = 'Changed since preview — skipped';
      else if (!overwrite && String(el.value).trim() && !(el.tagName==='SELECT' && el.selectedOptions[0]?.disabled)) status = 'Already has a value — skipped';
      else {
        let value = String(item.value);
        if (el.tagName === 'SELECT') value = ApplyFlowEngine.selectValue(Array.from(el.options).map(o=>({value:o.value,text:o.text,disabled:o.disabled || o.parentElement.disabled})),value);
        if (value === null) status = 'No exact dropdown option — choose manually';
        else {
          const proto = el.tagName === 'SELECT' ? HTMLSelectElement.prototype : el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
          Object.getOwnPropertyDescriptor(proto,'value').set.call(el,value);
          el.dispatchEvent(new Event('input',{bubbles:true,composed:true}));
          el.dispatchEvent(new Event('change',{bubbles:true,composed:true}));
          el.dispatchEvent(new Event('blur',{bubbles:true,composed:true}));
          await new Promise(resolve=>setTimeout(resolve,45));
          status = el.value === value ? 'Filled' : 'Website rejected value — fill manually';
        }
      }
      results.push({id:item.id,status});
    }
    return results;
  }
  globalThis.ApplyFlowContent = {scan,fill};
})();
