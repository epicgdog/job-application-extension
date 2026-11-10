"""Deterministic whole-entry ranking and a measured, immutable-text PDF renderer."""
from __future__ import annotations
import hashlib, io, json, re
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab import __file__ as reportlab_file
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.pdfgen.canvas import Canvas
from pypdf import PdfReader
import pdfplumber

from .matching import prepare, objective, report, VERSION as MATCHING_VERSION

VERSION = '3'
PAGE_W, PAGE_H, MARGIN = 612, 792, 36
WIDTH, HEIGHT = PAGE_W - 2*MARGIN, PAGE_H - 2*MARGIN
FONT_DIR = Path(reportlab_file).parent/'fonts'
for name, filename in [('AF','Vera.ttf'),('AF-Bold','VeraBd.ttf'),('AF-Italic','VeraIt.ttf')]:
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, str(FONT_DIR/filename)))
pdfmetrics.registerFontFamily('AF', normal='AF', bold='AF-Bold', italic='AF-Italic', boldItalic='AF-Bold')
S = {
 'body': ParagraphStyle('body',fontName='AF',fontSize=10,leading=12),
 'bullet': ParagraphStyle('bullet',fontName='AF',fontSize=10,leading=12,leftIndent=10,firstLineIndent=0,bulletIndent=0,bulletFontName='AF',bulletFontSize=10),
 'small': ParagraphStyle('small',fontName='AF',fontSize=9,leading=11,alignment=TA_CENTER),
 'name': ParagraphStyle('name',fontName='AF-Bold',fontSize=19,leading=23,alignment=TA_CENTER),
 'heading': ParagraphStyle('heading',fontName='AF-Bold',fontSize=10,leading=13),
 'right': ParagraphStyle('right',fontName='AF',fontSize=9,leading=12,alignment=2),
}

def digest(value):
    return hashlib.sha256(value.encode() if isinstance(value,str) else value).hexdigest()

def library_hash(library):
    return digest(json.dumps(library,sort_keys=True,ensure_ascii=False,separators=(',',':')))

def validate_library(lib):
    if lib.get('format') != 'applyflow-resume-library' or lib.get('version') != 1:
        raise ValueError('Unsupported source library.')
    if not 1 <= len(lib.get('entries',[])) <= 20:
        raise ValueError('Library needs 1–20 complete entries.')
    ids=set()
    bullets=[]
    for entry in lib['entries']:
        if entry['id'] in ids: raise ValueError('Duplicate entry ID.')
        ids.add(entry['id'])
        if entry.get('kind') not in ('experience','project') or not entry.get('bullets'):
            raise ValueError('Every entry needs a type and original bullets.')
        for bullet in entry['bullets']:
            if bullet['id'] in ids: raise ValueError('Duplicate bullet ID.')
            ids.add(bullet['id']); bullets.append(bullet)
    for edu in lib.get('education',[]):
        if edu.get('coursework_bullet'): bullets.append(edu['coursework_bullet'])
    for bullet in bullets:
        if not isinstance(bullet['text'],str) or len(bullet['text']) > 10000 or digest(bullet['text']) != bullet['sha256']:
            raise ValueError('Source bullet hash mismatch. No resume was generated.')
    return lib

def p(text,style='body',markup=False,bullet=False):
    return Paragraph(text if markup else escape(str(text)),S[style],bulletText='•' if bullet else None)

def link(url,label=None):
    if not re.match(r'^https?://',url): return escape(label or url)
    return '<link href="'+escape(url,{'"':'&quot;'})+'">'+escape(label or url.replace('https://','').rstrip('/'))+'</link>'

def section(title):
    return [Spacer(1,8),p(title.upper(),'heading'),HRFlowable(width='100%',thickness=.5,color='#333333'),Spacer(1,4)]

def fixed(lib):
    c=lib['contact']; edu=lib['education'][0]
    parts=[p(c['fullName'],'name'),Spacer(1,4),
        p(escape(c['phone'])+' | '+escape(c['email'])+' | '+link(c['website']),'small',True),
        p(link(c['linkedin'])+' | '+link(c['github']),'small',True)]
    parts+=section('Education')
    parts.append(row('<b>'+escape(edu['school'])+'</b>', 'Expected '+edu['graduation_display']))
    parts.append(p(edu['degree_display']+' | GPA: '+edu['gpa_display']))
    if edu.get('coursework_bullet'): parts.append(p(edu['coursework_bullet']['text'],'bullet',bullet=True))
    parts+=section('Technical skills')
    for label,value in lib['skills'].items():parts.append(p('<b>'+escape(label)+':</b> '+escape(value),markup=True))
    return parts

def row(left,right):
    t=Table([[p(left,markup=True),p(right,'right')]],colWidths=[WIDTH*.66,WIDTH*.34])
    t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    return t

def block(entry):
    if entry['kind']=='experience':
        result=[row('<b>'+escape(entry['title'])+'</b>',entry['dates_display']),
                row('<i>'+escape(entry['organization'])+'</i>',entry['location'])]
    else:
        title=link(entry.get('url',''),entry['name'])
        result=[p('<b>'+title+'</b>',markup=True),p(entry['technologies_display'])]
    result += [p(b['text'],'bullet',bullet=True) for b in entry['bullets']]
    return result+[Spacer(1,5)]

def height(parts):
    return sum(item.wrap(WIDTH,10000)[1] for item in parts)

def rank(lib,job):
    return prepare(lib,job)['ranking']

def ordered(lib,ids,scores):
    selected=[e for e in lib['entries'] if e['id'] in ids]
    exp=[e for e in selected if e['kind']=='experience']
    def end_date(e):
        months={'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}
        dates=re.findall(r'([A-Za-z]+)\.?\s+(\d{4})',e['dates_display'])
        if not dates:return (0,0)
        month,year=dates[-1];return int(year),months.get(month[:3].lower(),0)
    exp.sort(key=end_date,reverse=True)
    projects=sorted([e for e in selected if e['kind']=='project'],key=lambda e:(-scores[e['id']],e['id']))
    return exp+projects

def story(lib,entries):
    result=fixed(lib)
    for kind,title in [('experience','Experience'),('project','Projects')]:
        group=[e for e in entries if e['kind']==kind]
        if group:
            result+=section(title)
            for entry in group:result+=block(entry)
    return result

def select(lib,job):
    model=prepare(lib,job)
    ranked=model['ranking']; scores={r['id']:r['score'] for r in ranked}
    costs=[height(block(e)) for e in lib['entries']]
    budget=HEIGHT-height(fixed(lib))
    heading_cost=height(section('Experience'))
    best_key=None;best_indices=[]
    for mask in range(1,1<<len(costs)):
        indices=[i for i in range(len(costs)) if mask & (1<<i)]
        if any(scores[lib['entries'][i]['id']]<=0 for i in indices):continue
        kinds={lib['entries'][i]['kind'] for i in indices}
        used=sum(costs[i] for i in indices)+heading_cost*len(kinds)
        if used>budget:continue
        ids={lib['entries'][i]['id'] for i in indices}
        # Required coverage dominates preferred coverage. Count each distinct
        # qualification once, rather than stacking repeated words across entries.
        key=(*objective(model,ids),-used)
        if best_key is None or key>best_key:best_key=key;best_indices=indices
    if not best_indices:raise ValueError('No relevant complete entry fits one page. Provide the required/preferred qualifications or review your source layout.')
    entries=ordered(lib,{lib['entries'][i]['id'] for i in best_indices},scores)
    return entries,ranked,report(model,{e['id'] for e in entries})

def verify_pdf(data,lib,entries):
    reader=PdfReader(io.BytesIO(data))
    if len(reader.pages)!=1:raise ValueError('Resume must be exactly one page.')
    clean=lambda s:re.sub(r'\s+',' ',s).strip()
    extracted=clean(reader.pages[0].extract_text())
    cursor=0
    for entry in entries:
        for bullet in entry['bullets']:
            if digest(bullet['text'])!=bullet['sha256']:raise ValueError('Bullet integrity check failed.')
            original=clean(bullet['text'])
            pos=extracted.find(original,cursor)
            if pos<0 or extracted.count(original)!=1:raise ValueError('Rendered bullet text changed, missing, reordered, or duplicated.')
            cursor=pos+len(original)
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for word in pdf.pages[0].extract_words():
            if word['x0']<MARGIN-1 or word['x1']>PAGE_W-MARGIN+1 or word['top']<MARGIN-1 or word['bottom']>PAGE_H-MARGIN+1:
                raise ValueError('Resume text exceeds page content bounds.')

def generate(lib,job):
    validate_library(lib)
    if len(job.get('description','').strip())<80:raise ValueError('Provide at least 80 characters of job description.')
    entries,ranked,qualification_report=select(lib,job)
    parts=story(lib,entries)
    if height(parts)>HEIGHT:raise ValueError('Selected entries exceed one-page layout.')
    output=io.BytesIO();canvas=Canvas(output,pagesize=(PAGE_W,PAGE_H),pageCompression=1)
    canvas.setTitle(lib['contact']['fullName']+' — '+job.get('title','Application'))
    canvas.setAuthor(lib['contact']['fullName']);y=PAGE_H-MARGIN
    for item in parts:
        _,h=item.wrap(WIDTH,HEIGHT);y-=h;item.drawOn(canvas,MARGIN,y)
    canvas.showPage();canvas.save();data=output.getvalue()
    verify_pdf(data,lib,entries)
    return data,{'page_count':1,'template_version':VERSION,'selected_entry_ids':[e['id'] for e in entries],
        'selected_entries':[{'id':e['id'],'name':e.get('name',e.get('organization')),'title':e.get('title','Project')} for e in entries],
        'bullet_hashes':{b['id']:b['sha256'] for e in entries for b in e['bullets']},'ranking':[{k:v for k,v in row.items() if k!='strengths'} for row in ranked],
        'matching_version':MATCHING_VERSION,'qualification_report':qualification_report,'pdf_hash':digest(data)}
