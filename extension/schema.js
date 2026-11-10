(() => {
  const fields = [
    ['Contact', 'firstName', 'First name', 'given-name'],
    ['Contact', 'lastName', 'Last name', 'family-name'],
    ['Contact', 'fullName', 'Full name', 'name'],
    ['Contact', 'email', 'Email', 'email'],
    ['Contact', 'phone', 'Phone', 'tel'],
    ['Location', 'address', 'Street address', 'address-line1'],
    ['Location', 'address2', 'Apartment / address line 2', 'address-line2'],
    ['Location', 'city', 'City', 'address-level2'],
    ['Location', 'state', 'State / province', 'address-level1'],
    ['Location', 'postalCode', 'ZIP / postal code', 'postal-code'],
    ['Location', 'country', 'Country', 'country-name'],
    ['Links', 'linkedin', 'LinkedIn URL', ''],
    ['Links', 'github', 'GitHub URL', ''],
    ['Links', 'website', 'Website / portfolio', ''],
    ['Experience', 'employer', 'Most recent employer', 'organization'],
    ['Experience', 'jobTitle', 'Most recent job title', 'organization-title'],
    ['Education', 'school', 'School / university', ''],
    ['Education', 'degree', 'Degree', ''],
    ['Education', 'fieldOfStudy', 'Major / field of study', ''],
    ['Education', 'graduationYear', 'Graduation year', ''],
    ['Application', 'summary', 'Professional summary', '']
  ].map(([group,key,label,autocomplete]) => ({group,key,label,autocomplete}));
  globalThis.ApplyFlowSchema = fields;
})();
