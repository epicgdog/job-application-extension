from pathlib import Path
import base64,hashlib,os
ROOT=Path(__file__).resolve().parents[1]
def read_env(path):
    values={}
    if path.exists():
        for line in path.read_text().splitlines():
            line=line.strip()
            if not line or line.startswith('#'):continue
            if '=' not in line:raise ValueError('Invalid .env line.')
            key,value=line.split('=',1);value=value.strip()
            if len(value)>=2 and value[0]==value[-1] and value[0] in ('"',"'"):value=value[1:-1]
            values[key.strip()]=value
    return values

def env():return {**read_env(ROOT/'.env'),**os.environ}

def extension_id():
    import json
    key=json.loads((ROOT/'extension/manifest.json').read_text()).get('key')
    if not key:return ''
    return ''.join(chr(ord('a')+int(c,16)) for c in hashlib.sha256(base64.b64decode(key)).hexdigest()[:32])

def settings():
    e=env();local=e.get('APPLYFLOW_LOCAL_MODE','true').lower()=='true'
    resolve=lambda key,default: (ROOT/e.get(key,default)).resolve()
    return {'local':local,'url':e.get('SUPABASE_URL','').rstrip('/'),'key':e.get('SUPABASE_PUBLISHABLE_KEY',''),
      'owner':e.get('APPLYFLOW_OWNER_USER_ID',''),'bucket':e.get('SUPABASE_RESUME_BUCKET','resumes'),
      'source_bucket':e.get('SUPABASE_SOURCE_BUCKET','resume-sources'),
      'api':e.get('APPLYFLOW_API_BASE_URL','http://127.0.0.1:8000').rstrip('/'),
      'origins':[v.strip() for v in e.get('APPLYFLOW_ALLOWED_ORIGINS','chrome-extension://'+extension_id()).split(',') if v.strip()],
      'host':e.get('APPLYFLOW_API_HOST','127.0.0.1'),'port':int(e.get('APPLYFLOW_API_PORT','8000')),
      'library':resolve('APPLYFLOW_RESUME_LIBRARY_PATH','examples/resume-library.json'),
      'profile':resolve('APPLYFLOW_PROFILE_PATH','examples/profile.json'),
      'master':resolve('APPLYFLOW_MASTER_RESUME_PATH','private-data/master.pdf'),
      'data':resolve('APPLYFLOW_DATA_DIR','.data')}
