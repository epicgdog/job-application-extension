"""Qualification extraction and auditable skill-to-source evidence.

This is a conservative local decision model, not an eligibility predictor. It
never ranks employer names, IDs, hashes, dates, or arbitrary posting vocabulary.
"""
from __future__ import annotations
import hashlib,re

VERSION='qualifications-1'
# Narrow names/phrases are deliberate. Unrecognized prose needs review instead
# of becoming a new skill merely because it occurs in both documents.
SKILLS={
 'Python':r'python', 'Java':r'java', 'JavaScript':r'javascript|(?<!\.)js',
 'TypeScript':r'typescript|ts', 'C++':r'c\+\+|cpp', 'C#':r'c\#|csharp',
 'C':r'c(?![+#])', 'Rust':r'rust', 'Go':r'golang|go programming',
 'LuaU':r'luau|lua', 'Roblox':r'roblox', 'SQL':r'sql', 'Swift':r'swift', 'Kotlin':r'kotlin',
 'Ruby':r'ruby', 'PHP':r'php', 'R':r'r programming|r language',
 'FastAPI':r'fastapi', 'Spring':r'spring(?:\s+boot|\s+security)?',
 'React':r'react(?:\.js|js)?', 'Next.js':r'next\.?js', 'Svelte':r'svelte',
 'Vue':r'vue(?:\.js|js)?', 'Angular':r'angular', 'Node.js':r'node\.?js',
 'Django':r'django', 'Flask':r'flask', '.NET':r'\.net|dotnet',
 'AWS':r'aws|amazon web services|ec2|amazon s3|aws bedrock',
 'Azure':r'azure', 'Google Cloud':r'gcp|google cloud',
 'Docker':r'docker', 'Kubernetes':r'kubernetes|k8s',
 'Jenkins':r'jenkins', 'GitHub Actions':r'github actions',
 'Git':r'git', 'Gerrit':r'gerrit', 'Linux':r'linux',
 'PostgreSQL':r'postgres(?:ql)?', 'SQLite':r'sqlite', 'MySQL':r'mysql',
 'MongoDB':r'mongodb', 'Redis':r'redis', 'Supabase':r'supabase',
 'APIs':r'apis?|rest(?:ful)?(?:\s+(?:apis?|endpoints?))?|web services',
 'Data pipelines':r'data pipelines?|ingestion pipelines?|etl|elt',
 'Database design':r'database design|schemas?|data model(?:ing|ling)?',
 'Databases':r'databases?', 'Cloud platforms':r'cloud(?:\s+(?:platforms?|infrastructure|services?|computing))?',
 'Web frameworks':r'web (?:application )?frameworks?',
 'Mobile frameworks':r'mobile (?:application )?frameworks?|react native|flutter',
 'Full-stack development':r'full[ -]?stack',
 'Version control':r'version control|source control',
 'CI/CD':r'ci\s*/\s*cd|continuous integration|continuous delivery|continuous deployment',
 'Testing':r'unit test(?:ed|ing|s)?|integration test(?:ed|ing|s)?|testing|tests?|test automation',
 'Debugging':r'debug(?:ging|ged)?|troubleshoot(?:ing|ed)?',
 'Data structures':r'data structures?|graphs?|trees?|hash tables?|linked lists?',
 'Algorithms':r'algorithms?|pathfinding|raycasting',
 'Software design':r'software design|design patterns?|object[ -]oriented|modular architecture',
 'Networking':r'networking|network protocols?|tcp|udp|http|mqtt|snmp|websockets?',
 'Distributed systems':r'distributed systems?|distributed computing|distributed services',
 'Embedded systems':r'embedded(?:\s+(?:systems?|software))?|microcontrollers?|firmware|jetson(?: orin nano)?',
 'Real-time operating systems':r'real[ -]time operating systems?|rtos',
 'Assembly debugging':r'assembly(?:[ -]level)?(?:\s+debugging)?',
 'Robotics':r'robotics|robots?|robot gestures|reachy',
 'Autonomy':r'autonom(?:y|ous systems?|ous agents?)',
 'Aerospace':r'aerospace|flight controllers?|flight software|avionics',
 'Machine learning':r'machine learning|\bml\b|deep learning|neural networks?|transcription models?|transcription accuracy|finetun(?:e|ed|ing)|fine[ -]tun(?:e|ed|ing)|object detection|sensor fusion',
 'LLMs':r'llms?|large language models?|gpt[ -]?4v?|gemini|whisper|bedrock',
 'PyTorch':r'pytorch', 'TensorFlow':r'tensorflow',
 'Statistics':r'statistics|statistical', 'Probability':r'probability',
 'Agile/Scrum':r'agile|scrum',
 'Communication':r'communication|written and (?:verbal|oral)|verbal and written',
 'Team collaboration':r'collaborat(?:e|ed|ion|ive)|cross[ -]functional|worked (?:with|alongside)|teamwork|team environment',
 'Problem solving':r'problem[ -]solving|analytical',
 'Internship experience':r'(?:prior |previous |summer )?internships?',
 'Research experience':r'research', 'Club experience':r'student clubs?|club/competition|club experience',
 'Competition experience':r'hackathons?|competitions?',
 'Programming languages':r'(?:modern )?programming languages?',
}
PATTERNS={name:re.compile(r'(?<![\w+#])(?:'+pattern+r')(?![\w+#])',re.I) for name,pattern in SKILLS.items()}
# Parent links express a narrow technical taxonomy, not equivalence between
# sibling products: AWS supports cloud evidence, never Azure/GCP experience.
PARENTS={
 'Programming languages':['Python','Java','JavaScript','TypeScript','C','C++','C#','Rust','Go','LuaU','SQL','Swift','Kotlin','Ruby','PHP','R'],
 'Cloud platforms':['AWS','Azure','Google Cloud'],
 'Databases':['PostgreSQL','SQLite','MySQL','MongoDB','Redis','Supabase'],
 'Web frameworks':['FastAPI','Spring','React','Next.js','Svelte','Vue','Angular','Node.js','Django','Flask','.NET'],
 'Version control':['Git','Gerrit'],
 'CI/CD':['Jenkins','GitHub Actions'],
 'Machine learning':['PyTorch','TensorFlow'],
}
HEADINGS={
 'required':r'required qualifications|minimum qualifications|basic qualifications|essential qualifications|required skills|minimum requirements|basic requirements|what you(?:\s+will|[’\x27]ll)? bring|what we(?:\s+are|[’\x27]re) looking for|what you(?:\s+will|[’\x27]ll)? need|must[ -]haves?',
 'preferred':r'preferred qualifications|preferred skills|preferred experience|desired qualifications|desired skills|nice[ -]to[ -]haves?|bonus points|bonus skills',
 'stop':r'job responsibilities|responsibilities|what you(?:\s+will|[’\x27]ll) do|about the role|about us|about the team|what we offer|our benefits|benefits|compensation|salary range|how to apply|application process|equal opportunity|#intern',
}
QUANTIFIED=re.compile(r'\b\d+(?:\s*\+|\s*[–-]\s*\d+)?\s*(?:years?|months?)\b|\bgpa\b|work authori[sz]ation|citizenship|security clearance|eligible|eligibility|graduat(?:e|ion)',re.I)
EDUCATION=re.compile(r'bachelor|master[’\x27]?s|ph\.?d|degree|currently (?:pursuing|enrolled)',re.I)

def _clean(text):return re.sub(r'\s+',' ',text).strip(' \t\r\n•*-:')

def extract_qualifications(description):
    text=str(description or '').replace('\r','\n')
    marks=[]
    for tier,pattern in HEADINGS.items():
        for match in re.finditer(pattern,text,re.I):
            if tier=='stop' and match.group(0).lower() in ('responsibilities','benefits','compensation'):
                prefix=text[:match.start()].rsplit('\n',1)[-1]
                glued=match.group(0)[0].isupper() and match.start()>0 and text[match.start()-1].isalnum()
                if prefix.strip() and not glued:continue
            marks.append((match.start(),match.end(),tier))
    for match in re.finditer(r'^\s*(?:qualifications|requirements|who you are|your background|about you)\s*:?\s*$',text,re.I|re.M):
        marks.append((match.start(),match.end(),'required'))
    marks.sort()
    sections=[]
    for i,(start,end,tier) in enumerate(marks):
        if tier=='stop':continue
        sections.append((tier,text[end:marks[i+1][0] if i+1<len(marks) else len(text)]))
    mode='sections'
    if not sections:
        # Only explicit requirement/preference sentences qualify as a fallback.
        # Responsibilities/company copy never become an implicit requirement set.
        mode='inline'
        for line in re.split(r'\n|(?<=[.!?])\s+(?=[A-Z])',text):
            if re.search(r'\b(preferred|desirable|nice to have)\b',line,re.I):sections.append(('preferred',line))
            elif re.search(r'\b(required|must have|must be|minimum qualifications)\b',line,re.I):sections.append(('required',line))
    found=[];seen={}
    starts=r'Currently|Proficiency|Solid foundation|Experience|Familiarity|Strong|Effective|Exposure|Hands-on|Coursework|Prior|Interest|Ability|Knowledge|Understanding|Bachelor|Master|Minimum|At least|Demonstrated|Excellent|Working knowledge|Fluency'
    for tier,body in sections:
        # Recover common list boundaries from previously flattened HTML, including
        # "...technical fieldProficiency..." in cached application snapshots.
        body=re.sub(r'(?<=[A-Za-z)])(?=(?:'+starts+r')\b)','\n',body)
        for line in re.split(r'\n+|[•●▪]|(?<!e\.g\.)(?<!i\.e\.)(?<=[.!?])\s+(?=[A-Z])',body):
            line=_clean(re.sub(r'^\s*\d+[.)]\s*','',line))
            if len(line)<8:continue
            if len(line)>1800:
                found.append({'tier':tier,'text':line[:1800],'truncated':True});continue
            key=line.casefold()
            if key in seen:
                if tier=='required':seen[key]['tier']='required'
                continue
            item={'tier':tier,'text':line};seen[key]=item;found.append(item)
    for item in found:
        skills=detect(item['text'],parents=False)
        # Drop broad names when the same qualification names concrete alternatives.
        for parent,children in PARENTS.items():
            if parent in skills and set(children)&set(skills) and not re.search(r'e\.g\.|such as|including',item['text'],re.I):skills.pop(parent)
        text=item['text']
        if 'Assembly debugging' in skills:
            skills.pop('Debugging',None);skills.pop('Problem solving',None)
        # Evidence provenance (coursework/projects/internships) is not an OR
        # alternative to the actual ability to write, test, and debug code.
        focus=re.split(r'\b(?:whether|through|via)\b',text,1,flags=re.I)[0]
        if len(focus)<len(text):
            for name in ['Internship experience','Research experience','Club experience','Competition experience']:
                if not PATTERNS[name].search(focus):skills.pop(name,None)
        item['skills']=list(skills)
        item['weight']=.25 if skills and set(skills)<={'Communication','Team collaboration','Problem solving'} else 1.0
        alternatives=bool(re.search(r'at least one|one of|\bor\b(?!\s+(?:equivalent|comparable|related))',focus,re.I))
        item['logic']='any' if alternatives and (not re.search(r'\band\b',focus,re.I) or re.search(r'at least one|one of',focus,re.I)) else 'all'
        types=set(skills)&{'Internship experience','Research experience','Club experience','Competition experience'}
        domains=set(skills)&{'Robotics','Autonomy','Aerospace'}
        item['context_groups']=[sorted(types),sorted(domains)] if types and domains else []
        item['review']=bool(QUANTIFIED.search(text) or EDUCATION.search(text) or item.get('truncated'))
        item['education']=bool(EDUCATION.search(text))
        item['id']='q-'+hashlib.sha256((item['tier']+'\0'+text).encode()).hexdigest()[:12]
    # Do not silently discard requirements from the reported list.
    if len(found)>60:raise ValueError('More than 60 qualifications found. Review the required/preferred sections before generating.')
    return found, mode if found else 'none'

def detect(text,parents=True):
    result={name:1.0 for name,pattern in PATTERNS.items() if pattern.search(text)}
    if parents:
        if re.search(r'technical writing|presentations?|documentation|workshops?',text,re.I):result.setdefault('Communication',.6)
        if re.search(r'debug(?:ging|ged)?|troubleshoot(?:ing|ed)?',text,re.I):result.setdefault('Problem solving',.6)
        for parent,children in PARENTS.items():
            if any(child in result for child in children):result.setdefault(parent,.8)
    return result

def evidence_for_library(lib):
    by_entry={}
    for entry in lib['entries']:
        evidence=[]
        for bullet in entry['bullets']:
            evidence.append({'entry_id':entry['id'],'entry_name':entry.get('name',entry.get('organization','')),
                'bullet_id':bullet['id'],'text':bullet['text'],'source':'bullet','skills':detect(bullet['text'])})
        if entry.get('technologies_display'):
            evidence.append({'entry_id':entry['id'],'entry_name':entry.get('name',''),'text':entry['technologies_display'],
                'source':'technologies','skills':{k:v*.65 for k,v in detect(entry['technologies_display']).items()}})
        # Only a named prior-internship requirement may use explicit role history.
        if re.search(r'\bintern\b|\binternship\b',entry.get('title',''),re.I):
            evidence.append({'entry_id':entry['id'],'entry_name':entry.get('organization',''),'text':entry['title']+' — '+entry.get('organization',''),
                'source':'role','skills':{'Internship experience':.65}})
        by_entry[entry['id']]=evidence
    fixed=[]
    for label,value in lib.get('skills',{}).items():fixed.append({'entry_id':None,'text':label+': '+value,'source':'skills','skills':{k:v*.5 for k,v in detect(value).items()}})
    for edu in lib.get('education',[]):
        text=' | '.join(edu.get(k,'') for k in ['school','degree_display','graduation_display'])
        fixed.append({'entry_id':None,'text':text,'source':'education','skills':{}})
        if edu.get('coursework_bullet'):
            b=edu['coursework_bullet'];fixed.append({'entry_id':None,'text':b['text'],'source':'coursework','skills':detect(b['text'])})
    return by_entry,fixed

def strengths(evidence):
    values={}
    for item in evidence:
        for skill,strength in item['skills'].items():values[skill]=max(values.get(skill,0),strength)
    return values

def coverage(q,values):
    if not q['skills']:return 0
    if q.get('context_groups'):
        return min(max(values.get(s,0) for s in group) for group in q['context_groups'])
    parts=[values.get(skill,0) for skill in q['skills']]
    return max(parts) if q['logic']=='any' else sum(parts)/len(parts)

def prepare(lib,job):
    qualifications,mode=extract_qualifications(job.get('description',''))
    if not qualifications:
        raise ValueError('No required or preferred qualifications detected. Paste those sections, including their headings, and try again.')
    by_entry,fixed=evidence_for_library(lib)
    rows=[]
    for entry in lib['entries']:
        evidence=by_entry[entry['id']];values=strengths(evidence)
        score=sum((3 if q['tier']=='required' else 1)*q['weight']*coverage(q,values) for q in qualifications)
        terms=sorted({skill for q in qualifications for skill in q['skills'] if values.get(skill,0)>0})
        rows.append({'id':entry['id'],'score':round(score,5),'matched_terms':terms,'strengths':values})
    return {'qualifications':qualifications,'mode':mode,'ranking':rows,'by_entry':by_entry,'fixed':fixed}

def objective(model,ids):
    # Saturate each qualification, preferring coherent evidence in an entry over
    # assembling unrelated fragments (e.g. tutoring algorithms + game keywords).
    rows=[r for r in model['ranking'] if r['id'] in ids]
    value=lambda q:q['weight']*max((coverage(q,r['strengths']) for r in rows),default=0)
    required=sum(value(q) for q in model['qualifications'] if q['tier']=='required')
    preferred=sum(value(q) for q in model['qualifications'] if q['tier']=='preferred')
    return round(required,5),round(preferred,5)

def report(model,selected_ids):
    all_evidence=[item for group in model['by_entry'].values() for item in group]+model['fixed']
    report={'version':VERSION,'extraction':model['mode'],'required':[],'preferred':[],
        'warnings':['Evidence mapping does not verify eligibility, seniority, years of experience, or proficiency.']}
    for q in model['qualifications']:
        found=[]
        for item in all_evidence:
            matches=[s for s in q['skills'] if s in item['skills']]
            if not matches and not (q['education'] and item['source']=='education'):continue
            found.append({k:v for k,v in item.items() if k!='skills'}|{'matched_skills':matches,'match_strengths':{s:item['skills'][s] for s in matches},'included':item['entry_id'] is None or item['entry_id'] in selected_ids})
        selected=[e for e in found if e['included']]
        skills={s for e in selected for s in e['matched_skills']}
        missing=[s for s in q['skills'] if s not in skills]
        if q['logic']=='any' and skills:missing=[]
        direct={s for e in selected if e['source'] in ('bullet','coursework') for s in e['matched_skills'] if e['match_strengths'].get(s,0)>=1.0}
        enough=bool(q['skills']) and (any(s in direct for s in q['skills']) if q['logic']=='any' else all(s in direct for s in q['skills']))
        if q.get('context_groups'):
            enough=all(any(s in direct for s in group) for group in q['context_groups'])
        if q['review']:status='review'
        elif enough:status='evidence'
        elif selected:status='partial'
        elif found:status='omitted'
        elif not q['skills']:status='review'
        else:status='not_evidenced'
        # Include one proof per distinct skill/source; keep all omitted evidence
        # available for the UI to explain master-vs-selected differences.
        found.sort(key=lambda e:(not e['included'],e['source']!='bullet',e.get('entry_id') or ''))
        report[q['tier']].append({'id':q['id'],'text':q['text'],'logic':q['logic'],'status':status,
            'recognized_skills':q['skills'],'missing_skills':missing,'evidence':found,
            'note':'Review dates, duration, education status, and any other conditions explicitly.' if q['review'] else
                   'Related source evidence; this does not establish every part of the qualification.' if status=='partial' else
                   'No recognized skill rule; review this qualification manually.' if not q['skills'] else ''})
    return report
