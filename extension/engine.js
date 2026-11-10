(() => {
  const normalize = value => String(value || '').replace(/([a-z])([A-Z])/g, '$1 $2').toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ').trim().replace(/\s+/g, ' ');
  const rules = [
    ['firstName', /\b(first name|given name|forename)\b/],
    ['lastName', /\b(last name|family name|surname)\b/],
    ['fullName', /^(full name|legal name|your name|name)( required)?$/],
    ['email', /\b(e mail|email)\b/],
    ['phone', /\b(phone|telephone|mobile|cell number)\b/],
    ['address2', /\b(address (line )?2|apartment|suite|unit number)\b/],
    ['address', /\b(street address|address line 1|address 1|mailing address)\b|^address$/],
    ['city', /\b(city|town)\b/],
    ['state', /\b(state|province|region)\b/],
    ['postalCode', /\b(zip|zip code|postal code|postcode)\b/],
    ['country', /\bcountry( of residence)?\b/],
    ['linkedin', /\blinked ?in\b/],
    ['github', /\bgithub\b/],
    ['website', /\b(website|portfolio|personal site)\b/],
    ['employer', /\b(employer|company name|current company|most recent company)\b/],
    ['jobTitle', /\b(job title|position title|current title|most recent title)\b/],
    ['school', /\b(school|university|college|institution)\b/],
    ['degree', /\b(degree|qualification)\b/],
    ['fieldOfStudy', /\b(major|field of study|discipline)\b/],
    ['graduationYear', /\b(graduation year|year of graduation)\b/],
    ['summary', /\b(professional summary|professional bio)\b/]
  ];
  function match(meta, profile) {
    const label = normalize(meta.label);
    const hints = normalize(meta.hints);
    const context = normalize(meta.context);
    if (/\b(reference|referee|emergency contact|recruiter|manager|supervisor)\b/.test(label+' '+context)) return '';
    const custom = (profile.answers || []).find(a => normalize(a.question) === label && String(a.answer || '').trim());
    if (custom) return 'answer:' + custom.id;
    // Long questions need an explicit saved answer, not a keyword guess.
    if (/\bfirst (and|&) last name\b/.test(label)) return '';
    if (label.split(' ').length > 9 || /\b(password|search|salary|citizenship|birth|ssn|social security|credit card|bank|authorization|authorised|authorized|sponsor|disability|gender|ethnicity|race|veteran|relocat|consent|agree|signature|desired|preferred|expected|minimum)\w*\b/.test(label+' '+hints)) return '';
    const ac = String(meta.autocomplete || '').split(' ').pop();
    const acField = ApplyFlowSchema.find(f => f.autocomplete && f.autocomplete === ac);
    if (acField) return acField.key;
    const matches = text => rules.filter(([,rule]) => rule.test(text)).map(([key])=>key);
    const direct = matches(label);
    if (direct.length === 1) return direct[0];
    if (direct.length > 1) return ''; // e.g. combined city/state, or first and last name.
    const indirect = matches(hints);
    return indirect.length === 1 ? indirect[0] : '';
  }
  function valueFor(key, profile) {
    if (key.startsWith('answer:')) return String((profile.answers || []).find(a => a.id === key.slice(7))?.answer || '');
    if (key === 'fullName') return profile.fullName || [profile.firstName,profile.lastName].filter(Boolean).join(' ');
    return String(profile[key] || '');
  }
  function selectValue(options, value) {
    const target = normalize(value);
    if (!target) return null;
    const aliases = {us:['united states','united states of america','usa'], uk:['united kingdom','great britain'],
      yes:['true'], no:['false']};
    const equivalent = (a,b) => a === b || Object.entries(aliases).some(([key,values]) => [key,...values].includes(a) && [key,...values].includes(b));
    const matches = options.filter(o => !o.disabled && o.value !== '' &&
      (equivalent(normalize(o.value),target) || equivalent(normalize(o.text),target)));
    return matches.length === 1 ? matches[0].value : null;
  }
  globalThis.ApplyFlowEngine = {normalize,match,valueFor,selectValue};
})();
