# ApplyFlow

A Chrome/Edge extension that fills application forms from a saved profile and builds a one-page resume for the job you are viewing. The resume generator selects complete experience and project entries without rewriting their bullets.

## Features

- Review matched application fields before filling them, with manual match overrides and reusable saved answers.
- Detect jobs from structured `JobPosting` data, or enter the title, company, and description manually.
- Match required/preferred qualifications to exact source evidence and select complete entries that fit one page.
- Preserve every included bullet's wording and order; verify source hashes and PDF-extracted text.
- Preview and download PDFs, reuse cached results, regenerate versions, and browse history.
- Run locally without an account, or save privately using Supabase Auth, Postgres, and Storage.

The extension uses browser content scripts and DOM APIs. Python renders PDFs with ReportLab and checks them with pypdf and pdfplumber. Playwright is used only in development tests. No LLM or paid generation API is required.

## Quick start

Requirements: Python 3.10+, Chrome or Edge 120+, and Node.js 18+ if you want to run JavaScript tests.

```sh
git clone https://github.com/epicgdog/job-application-extension.git
cd job-application-extension
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python scripts/build.py
python -m server.app
```

Keep the API running. Open `chrome://extensions` (or `edge://extensions`), enable **Developer mode**, choose **Load unpacked**, and select the `extension/` folder. Pin ApplyFlow to the toolbar.

The default setup uses fictional examples, loopback-only storage, and an automatically generated local bearer token. It makes no Supabase uploads. `scripts/build.py` generates the ignored `extension/config.js` and sets network permissions for the configured API/Supabase hosts. Run it again and reload the extension whenever those settings change.

## Apply to a job

1. Open the employer's job posting and click ApplyFlow.
2. For a recognized single `JobPosting`, resume generation starts automatically. Otherwise, confirm the job title/company and paste its description. Descriptions require at least 80 characters and identifiable required/preferred qualifications or explicit requirement sentences.
3. Review the selected entries, choose **Preview & download**, and attach the PDF through the employer's upload control.
4. Use **Scan this page** to review and fill supported application fields. Existing field values are preserved unless you explicitly enable replacement.
5. Review the complete application and submit it yourself.

Applications without a job description may require copying the description from the original posting. A previous description is reused only for the same stored URL. **Regenerate** creates a new version; reopening the same unchanged job retrieves the cached artifact.

## Use your own profile and resume

The files in `examples/` are entirely fictional and safe for demonstrations/tests. Real profiles, source libraries, master PDFs, environment files, generated configuration, and local history are excluded from Git.

Create an ignored `private-data/` directory and place your data there. The profile format is shown in `examples/profile.json`; it can also be imported/exported through **Edit profile** in the extension. Set these paths in your local `.env`:

```dotenv
APPLYFLOW_PROFILE_PATH=./private-data/profile.json
APPLYFLOW_RESUME_LIBRARY_PATH=./private-data/resume-library.json
APPLYFLOW_MASTER_RESUME_PATH=./private-data/master.pdf
```

Use `examples/resume-library.json` as the source-library schema. Each entry has an ID, type, original metadata, and ordered bullets. Each bullet needs an ID, exact original `text`, and a SHA-256 hash of its UTF-8 text:

```python
import hashlib
bullet_hash = hashlib.sha256(original_text.encode('utf-8')).hexdigest()
```

Keep original punctuation and wording when building the library; PDF line wrapping may be represented as spaces. The optional master PDF's SHA-256 must match `source.sha256`. If there is no original PDF, point the master path to a nonexistent file. There is no automatic PDF-to-library importer in this release. The renderer supports 1–20 complete entries, one education block, and the contact/skills structure shown in the example.

Restart the API after changing source files. A changed library hash creates a new source version and invalidates cached resumes. Profile bootstrap fills extension storage only if no profile is already saved; use **Edit profile** to update an existing profile.

## Supabase setup

1. Create a Supabase project and run `supabase/001_initial.sql` once in its SQL Editor. It creates owner-scoped source/resume tables, private PDF buckets, and row-level policies.
2. Enable email authentication. Include `{{ .Token }}` in the **Magic Link** email template so users receive a code that can be entered in the extension.
3. Create your user in **Authentication → Users** and copy its UUID.
4. Configure `.env`:

```dotenv
APPLYFLOW_LOCAL_MODE=false
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_REPLACE_ME
APPLYFLOW_OWNER_USER_ID=YOUR_AUTH_USER_UUID
```

5. Run `python scripts/build.py`, restart the API, reload the extension, and sign in with your email code.

No service-role/admin key is used. The server verifies the Supabase identity on each cloud request and serves only the configured owner. Database/storage calls use that user's JWT, so RLS remains active. Source imports are immutable; generated PDFs use unique object paths and authenticated downloads. Keep the default bucket names consistent with the migration.

For remote deployment, use an HTTPS reverse proxy and a supervised server process. Configure the API URL, bind address/port, and allowed extension origin. The build prints the stable extension origin. Remote plain-HTTP API URLs are rejected. This is a personal backend rather than an open multiuser service.

Live email delivery, storage, and RLS must be checked against your configured project. A read-only cross-user check is available:

```sh
python scripts/check_supabase.py --help
```

It needs two test-user access tokens and an existing completed test resume. It verifies that the owner can read it, another user cannot read its metadata/source/PDF, and the public URL is inaccessible.

## Preservation and page layout

The ranker extracts required and preferred qualifications, then returns source entry IDs and evidence references, never replacement prose. The renderer keeps every bullet of each included entry and retains bullet order. It preserves contact details, education/coursework, and existing skills lines. It orders work experience chronologically and projects by relevance.

Selection searches combinations of complete entries using measured layout heights. The template uses a single US Letter page, 10 pt body text, 36 pt margins, embedded fonts, selectable text, and links. Generation fails if bullet hashes differ, PDF text is missing/changed/reordered/duplicated, content exceeds page bounds, or no useful complete entry fits. It never truncates bullets or shrinks them below those bounds.

Required qualification coverage takes priority over preferred coverage. Technical requirements outweigh generic transferable skills, repeated mentions do not accumulate credit, and employer names/IDs are excluded. The report shows original qualification text and exact source evidence, distinguishes included/omitted/listed evidence, and flags gaps or manual-review conditions. This is a conservative local rules model, not an ATS or eligibility score. No LLM key is needed. Read [the research and matching design](docs/matching-research.md) for sources, weights, and limitations. Review its choices for each job. Duplicate identical bullet text across selected entries is rejected by the current PDF integrity check; distinguish source entries or omit duplicates when preparing the library.

## History and failure recovery

Job metadata/description, library hash, and template version determine the cache key. Explicit regeneration creates a new immutable artifact. Editing job details hides a prior result until a new generation completes.

The backend continues submitted work when the popup closes. Reopen the popup/history to check its status. Completed local/cloud history is durable; unfinished jobs can fail on a server restart. Matching version changes invalidate the generation cache; older resumes remain in history and can be regenerated for a qualification report. Pending jobs older than ten minutes are marked failed when queried and can be regenerated.

Failed uploads are not reported as saved. When a completion response is lost, the worker checks metadata before deleting a PDF. If a network failure prevents determining the outcome, it leaves the object intact. This can leave an orphaned private object that needs inspection against its UUID history row before removal.

## Tests

```sh
python -m unittest discover -s tests -v
node --test extension/tests/engine.test.cjs tests/background.test.cjs
```

These tests use fictional data and temporary storage. They cover bullet preservation, page layout, relevance selection, tamper rejection, owner isolation, upload/commit failures, HTTP authentication/CORS, cache/version behavior, field matching, session refresh, and trusted extension messaging.

For the installed-extension test:

```sh
npm install --no-save playwright
npx playwright install chromium
node tests/extension-e2e.cjs
```

Set `PYTHON` if your test Python executable is not `python3`. The browser test uses an isolated profile and a synthetic job on a temporary local API. It emulates the active-tab query because its popup is navigated as a full browser tab; extension messaging, API access, PDF generation/preview/download, autofill, and history run normally. Configuration/manifest changes are restored afterward.

Additional real-DOM fill checks are in `extension/tests/browser.html`.

## Project layout

| Path | Purpose |
| --- | --- |
| `extension/` | Manifest V3 profile editor, autofill, job capture, resume UI, and background worker |
| `server/` | Authenticated HTTP API, ranking/PDF renderer, local/Supabase storage |
| `scripts/build.py` | Allowlisted browser config and host-permission generation |
| `scripts/check_supabase.py` | Read-only two-user cloud access check |
| `supabase/001_initial.sql` | Database tables, private buckets, and RLS policies |
| `examples/` | Fictional profile/source library |
| `tests/` | Python, background/session, and installed-extension tests |
| `.env.example` | Supported configuration variables |

## Limits

Standard text/email/phone/URL/number inputs, textareas, and native selects are supported. Custom ATS widgets, radio/checkbox questions, file uploads, closed shadow roots, embedded frames, and adding repeated history rows require manual handling. The profile holds one employment and one education entry; the source library holds the resume's complete entries. Production ATS compatibility is not guaranteed.

Local data and extension session/profile storage are not encrypted by this app. The API must remain running. The extension does not submit applications or automatically attach its generated PDF to employer forms.
