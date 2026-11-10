import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.matching import extract_qualifications,prepare,objective,report,detect
from server.resume import digest,generate
LIB=json.loads((ROOT/'examples/resume-library.json').read_text())

def job(description):return {'title':'Software Intern','company':'Fixture','description':description}

def qualification(text):return job('Required Qualifications\n'+text)

class QualificationExtractionTests(unittest.TestCase):
    def test_extracts_required_preferred_and_excludes_other_sections(self):
        text='About Us\nOur service status is standard over summer.\nRequired Qualifications\nExperience with Python and SQL.\nPreferred Qualifications\nExperience with Docker.\nBenefits\nJava and Rust branded hoodies.'
        found,mode=extract_qualifications(text)
        self.assertEqual(mode,'sections');self.assertEqual([q['tier'] for q in found],['required','preferred'])
        self.assertEqual(found[0]['skills'],['Python','SQL']);self.assertEqual(found[1]['skills'],['Docker'])
    def test_recovers_glued_cached_headings_and_list_items(self):
        found,_=extract_qualifications("About the RoleSummer intern activities.Required QualificationsProficiency in PythonExperience with SQLFamiliarity with GitPreferred QualificationsExposure to DockerHands-on experience with AWS#intern Standard summer benefits")
        self.assertEqual(len([q for q in found if q['tier']=='required']),3)
        self.assertEqual(len([q for q in found if q['tier']=='preferred']),2)
        self.assertNotIn('standard',str(found).lower())
    def test_deduplicates_qualification_and_prefers_required_tier(self):
        found,_=extract_qualifications('Preferred Qualifications\nExperience with Python.\nRequired Qualifications\nExperience with Python.')
        self.assertEqual(len(found),1);self.assertEqual(found[0]['tier'],'required')
    def test_no_heading_does_not_fall_back_to_generic_overlap(self):
        with self.assertRaisesRegex(ValueError,'No required or preferred'):prepare(LIB,job('Our intern job is over summer and provides standard service status via user-facing tools.'))
    def test_explicit_inline_requirement_is_allowed(self):
        found,mode=extract_qualifications('We offer summer events. Python proficiency is required. Docker experience is preferred.')
        self.assertEqual(mode,'inline');self.assertEqual(len(found),2)
    def test_common_words_and_punctuation_are_not_skills(self):
        self.assertEqual(detect('intern into job over service status user-facing via all end. standard summer'),{})
    def test_c_cpp_csharp_and_java_javascript_are_distinct(self):
        values=detect('C++ C# JavaScript')
        self.assertIn('C++',values);self.assertIn('C#',values);self.assertIn('JavaScript',values)
        self.assertNotIn('C',values);self.assertNotIn('Java',values)

    def test_benefits_word_inside_a_requirement_is_not_a_heading(self):
        found,_=extract_qualifications('Required Qualifications\nExperience administering benefits databases.\nPreferred Qualifications\nExperience with Python.')
        self.assertEqual(found[0]['skills'],['Databases'])
    def test_framework_suffix_is_not_a_language_alias(self):
        self.assertNotIn('JavaScript',detect('Next.js'))
        self.assertIn('JavaScript',detect('JS and JavaScript'))

class EvidenceTests(unittest.TestCase):
    def test_metadata_and_employer_names_are_not_evidence(self):
        lib=copy.deepcopy(LIB);e=lib['entries'][0];lib['entries']=[e]
        e['title']='Python Developer';e['organization']='Python Company';e['id']='Python'
        for b in e['bullets']:b['text']='Maintained the standard service status through summer.';b['sha256']=digest(b['text'])
        model=prepare(lib,qualification('Proficiency in Python is required.'))
        self.assertEqual(model['ranking'][0]['score'],0)
    def test_evidence_quotes_are_exact_original_source_text(self):
        model=prepare(LIB,qualification('Experience using Python and PostgreSQL.'))
        result=report(model,{'entry-01'})['required'][0]
        bullets={b['id']:b['text'] for e in LIB['entries'] for b in e['bullets']}
        for e in result['evidence']:
            if e['source']=='bullet':self.assertEqual(e['text'],bullets[e['bullet_id']])
        self.assertTrue(any(e['included'] and e.get('entry_id')=='entry-01' for e in result['evidence']))
    def test_missing_provider_is_not_inferred_from_other_cloud(self):
        model=prepare(LIB,qualification('Experience with Azure.'))
        row=report(model,{'entry-01','entry-03'})['required'][0]
        self.assertEqual(row['status'],'not_evidenced');self.assertEqual(row['missing_skills'],['Azure'])
    def test_alternative_languages_do_not_create_false_gaps(self):
        model=prepare(LIB,qualification('Proficiency in at least one of Python, Java, or C++.'))
        row=report(model,{'entry-01'})['required'][0]
        self.assertEqual(row['logic'],'any');self.assertEqual(row['missing_skills'],[]);self.assertEqual(row['status'],'evidence')
    def test_missing_and_term_is_partial_not_complete(self):
        model=prepare(LIB,qualification('Experience with Python and PyTorch.'))
        row=report(model,{'entry-01'})['required'][0]
        self.assertEqual(row['status'],'partial');self.assertIn('PyTorch',row['missing_skills'])
    def test_education_and_duration_require_manual_review(self):
        for text in ["Currently pursuing a Bachelor's degree in Computer Science.",'At least 5 years of Python experience.']:
            model=prepare(LIB,qualification(text));row=report(model,{'entry-01'})['required'][0]
            self.assertEqual(row['status'],'review')
    def test_unrecognized_qualification_stays_visible_for_review(self):
        model=prepare(LIB,qualification('A valid XYZ specialist certification.'))
        row=report(model,set())['required'][0]
        self.assertEqual(row['status'],'review');self.assertEqual(row['recognized_skills'],[])
    def test_coverage_saturates_and_rewards_diversity(self):
        model=prepare(LIB,qualification('Experience with Python.\nExperience with React.'))
        python_only={'entry-01','entry-03'};diverse={'entry-01','entry-02'}
        self.assertGreater(objective(model,diverse),objective(model,python_only))
        self.assertEqual(objective(model,{'entry-01'}),objective(model,{'entry-01','entry-03'}))
    def test_required_coverage_dominates_preferred(self):
        model=prepare(LIB,job('Required Qualifications\nExperience with React.\nPreferred Qualifications\nExperience with Python, SQL, Docker, AWS, and Jenkins.'))
        self.assertGreater(objective(model,{'entry-02'}),objective(model,{'entry-01','entry-03'}))
    def test_omitted_master_evidence_is_distinguished(self):
        model=prepare(LIB,qualification('Experience using Roblox LuaU.'))
        row=report(model,{'entry-01'})['required'][0]
        self.assertEqual(row['status'],'omitted');self.assertTrue(all(not e['included'] for e in row['evidence']))
    def test_examples_do_not_exclude_the_broader_skill(self):
        model=prepare(LIB,qualification('Experience with cloud platforms, such as AWS.'))
        self.assertIn('Cloud platforms',model['qualifications'][0]['skills'])
    def test_embedded_requirement_does_not_reward_generic_debugging(self):
        model=prepare(LIB,qualification('Hands-on experience with embedded systems, RTOS, or assembly-level debugging.'))
        row=next(r for r in model['ranking'] if r['id']=='entry-06')
        self.assertEqual(row['score'],0)
    def test_domain_experience_needs_domain_and_experience_type(self):
        model=prepare(LIB,qualification('Prior internship, research, or competition experience in robotics or aerospace.'))
        row=next(r for r in model['ranking'] if r['id']=='entry-03')
        self.assertEqual(row['score'],0)
    def test_related_soft_skill_evidence_is_not_direct_proof(self):
        model=prepare(LIB,qualification('Effective communication skills.'))
        q=report(model,{'entry-05'})['required'][0]
        self.assertIn(q['status'],['partial','not_evidenced'])

    def test_generation_returns_versioned_qualification_report(self):
        data,result=generate(LIB,job('Required Qualifications\nExperience building Python FastAPI APIs with PostgreSQL.\nPreferred Qualifications\nExperience with AWS and Docker.'))
        self.assertTrue(data.startswith(b'%PDF'));self.assertEqual(result['matching_version'],'qualifications-1')
        self.assertTrue(result['qualification_report']['required'])
        for row in result['ranking']:
            self.assertNotIn('intern',row['matched_terms']);self.assertNotIn('standard',row['matched_terms'])

if __name__=='__main__':unittest.main()
