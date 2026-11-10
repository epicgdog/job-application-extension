# Qualification matching design and research

Reviewed November 10, 2026. This change replaces whole-posting word overlap with qualification-to-source evidence mapping. It does not estimate an employer's ATS score or verify candidate eligibility.

## Public product approaches

| Product | Published behavior | Principle used here |
| --- | --- | --- |
| [Jobscan](https://www.jobscan.co/jobscan-tutorial) | Prioritizes hard skills over soft skills and one-word keywords in its resume/job comparison. | Technical requirements carry more selection weight than generic transferable-skill matches. |
| [Teal](https://help.tealhq.com/en/articles/14435726-how-to-tailor-your-resume-for-a-specific-job) | Distinguishes terms included in the current resume, present only in the master, and absent from the source. | Show selected-entry evidence, omitted master evidence, and gaps separately, with exact source quotations. |
| [Textkernel](https://developer.textkernel.com/tx-platform/v10/search-match-v2/overview/) | Parses structured candidate/job fields, uses weighted conditions and semantic matching, and returns match explanations. | Extract criteria first, normalize narrow skill names, weight criteria explicitly, and preserve an evidence trail. |

These are documented product behaviors, not access to proprietary models, weighting formulas, or independent effectiveness studies. ApplyFlow's weights below are its own transparent design choices.

## Pipeline

1. Preserve HTML heading/list boundaries when reading the job. Handle cached descriptions with glued heading/list text.
2. Extract required/minimum/basic and preferred/desired/nice-to-have sections. Stop at unrelated sections. A fallback accepts only explicit required/preferred sentences; it never treats all posting text as qualifications.
3. Identify bounded skill names and phrases from a curated software-oriented vocabulary. Normalize narrow aliases and parent categories: PostgreSQL/Postgres are equivalent, and AWS is cloud evidence; AWS never implies Azure experience. Unknown criteria remain visible for review.
4. Build evidence from original source bullets, project technology lists, fixed skills/coursework, and explicitly requested prior-internship role history. Employer names, source IDs/hashes, arbitrary dates, job titles, and generic posting vocabulary are not scored as skills.
5. Search complete entries that fit the existing measured one-page layout. Required coverage is the first selection objective, preferred coverage the second. Each qualification saturates: duplicate mentions do not add coverage. Prefer coherent evidence within an entry over assembling unrelated fragments across entries. Ties favor less occupied space.
6. Return the original qualification and exact source quotations, including whether each source is included or omitted. Preserve every included bullet unchanged and keep the existing PDF verification.

Technical qualifications have weight 1.0. Qualifications containing only communication, collaboration, or problem-solving have weight 0.25. Direct skill evidence has strength 1.0, a narrow parent-category inference 0.8, a technology-list mention 0.65, a related transferable-skill clue 0.6, and a fixed skills-list mention 0.5. These strengths guide ranking, not a displayed eligibility percentage. The old per-entry ranking field remains for compatibility but selection uses saturated qualification coverage rather than additive word counts.

The evidence report separates direct evidence, partial/listed evidence, omitted evidence, no direct evidence, and manual-review conditions. Education, years, graduation, authorization, and similar constraints require review; recognized skills alone do not establish those conditions. Alternative language choices do not create gaps for every unchosen language. Domain-specific prior experience needs both the experience type and the domain.

## Limits and model decision

No LLM or external request is required for this correction. The local rules are conservative, software-oriented, and auditable, but are not general natural-language understanding. Complex conjunctions, unusual qualification headings, and skills outside the vocabulary can require manual review. The UI exposes the extracted criteria and evidence so those cases are visible.

An optional semantic pass would be useful for unfamiliar terminology, nuanced scope, and paraphrases. It should take extracted qualification text and source entry/bullet IDs, return structured evidence references plus uncertainty, and never return replacement resume prose. Provider/model selection and credentials would be required before enabling it. Job text must remain untrusted data, and a model's proposed quotations/IDs must be checked against the immutable source. No private resume data is sent to a model in this implementation.

## Regression checks

Tests cover the reported noisy-word list, required/preferred extraction, flattened HTML, inline bold skills, exclusion of benefits/company copy, OR alternatives, AND gaps, provider-specific gaps, unrelated metadata, coherent/domain evidence, duration/education review, unchanged quotations, cache versioning, and the installed extension's evidence UI. The user's saved posting is used only in a local private smoke test, not committed as a public fixture.
