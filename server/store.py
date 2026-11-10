"""Owner-scoped local and Supabase adapters. No admin key is used."""
import json,sqlite3,uuid
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode,quote

class CloudError(Exception):pass

class Cloud:
    def __init__(self,config,token):self.config=config;self.token=token
    def request(self,path,method='GET',data=None,extra=None,raw=False):
        headers={'apikey':self.config['key'],'Authorization':'Bearer '+self.token}
        if isinstance(data,(dict,list)):
            data=json.dumps(data).encode();headers['Content-Type']='application/json'
        headers.update(extra or {})
        try:
            with urlopen(Request(self.config['url']+path,data=data,headers=headers,method=method),timeout=25) as response:
                body=response.read()
                return body if raw else (json.loads(body) if body else None)
        except HTTPError as error:
            message=''
            try:message=json.loads(error.read()).get('message','')
            except (ValueError,AttributeError):pass
            # Keep credentials/response bodies out of user-visible errors.
            raise CloudError(f'Supabase request failed ({error.code}). Check sign-in, SQL migration, and bucket policies.') from None
    def user(self):return self.request('/auth/v1/user')
    def table(self,name,query='',method='GET',data=None,extra=None):
        return self.request('/rest/v1/'+name+('?' + query if query else ''),method,data,extra)
    def source(self,uid,source_id,lib,profile,source_hash,original):
        query=urlencode({'id':'eq.'+source_id,'user_id':'eq.'+uid,'select':'id'})
        if self.table('af_sources',query):return
        object_path=None
        if original:
            object_path=f'{uid}/sources/{source_id}.pdf'
            try:self.request('/storage/v1/object/'+quote(self.config['source_bucket'])+'/'+object_path,'POST',original,{'Content-Type':'application/pdf','x-upsert':'false'})
            except CloudError:
                # A concurrent source import may have uploaded the same immutable object.
                existing=self.request('/storage/v1/object/authenticated/'+quote(self.config['source_bucket'])+'/'+object_path,raw=True)
                if existing!=original:raise
        data={'id':source_id,'user_id':uid,'source_hash':source_hash,'library':lib,'profile':profile,'original_path':object_path}
        self.table('af_sources','on_conflict=user_id,source_hash','POST',data,{'Prefer':'resolution=ignore-duplicates,return=minimal'})
    def create(self,row):
        created=self.table('af_resumes','on_conflict=user_id,request_key','POST',row,{'Prefer':'resolution=ignore-duplicates,return=representation'})
        if created:return created[0]
        return self.table('af_resumes',urlencode({'user_id':'eq.'+row['user_id'],'request_key':'eq.'+row['request_key'],'select':'*'}))[0]
    def claim(self,uid,rid):
        rows=self.table('af_resumes',urlencode({'id':'eq.'+rid,'user_id':'eq.'+uid,'state':'eq.queued'}),'PATCH',{'state':'generating'},{'Prefer':'return=representation'})
        return bool(rows)
    def update(self,uid,rid,values):
        self.table('af_resumes',urlencode({'id':'eq.'+rid,'user_id':'eq.'+uid}),'PATCH',values)
    def get(self,uid,rid):
        rows=self.table('af_resumes',urlencode({'id':'eq.'+rid,'user_id':'eq.'+uid,'select':'*'}))
        return rows[0] if rows else None
    def history(self,uid):return self.table('af_resumes',urlencode({'user_id':'eq.'+uid,'select':'*','order':'created_at.desc','limit':'40'}))
    def upload(self,uid,rid,data):
        path=f'{uid}/{rid}.pdf'
        self.request('/storage/v1/object/'+quote(self.config['bucket'])+'/'+path,'POST',data,{'Content-Type':'application/pdf','x-upsert':'false'})
        return path
    def remove_pdf(self,path):
        self.request('/storage/v1/object/'+quote(self.config['bucket']),'DELETE',{'prefixes':[path]})
    def pdf(self,row):return self.request('/storage/v1/object/authenticated/'+quote(self.config['bucket'])+'/'+row['object_path'],raw=True)

class Local:
    def __init__(self,config):
        self.path=config['data'];self.path.mkdir(parents=True,exist_ok=True)
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS resumes (id TEXT PRIMARY KEY,user_id TEXT,request_key TEXT,payload TEXT,UNIQUE(user_id,request_key))')
    def db(self):return sqlite3.connect(self.path/'history.sqlite3',timeout=15)
    def source(self,*args):pass
    def create(self,row):
        with self.db() as db:
            db.execute('INSERT OR IGNORE INTO resumes VALUES (?,?,?,?)',(row['id'],row['user_id'],row['request_key'],json.dumps(row)))
            data=db.execute('SELECT payload FROM resumes WHERE user_id=? AND request_key=?',(row['user_id'],row['request_key'])).fetchone()
        return json.loads(data[0])
    def claim(self,uid,rid):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            result=db.execute('SELECT payload FROM resumes WHERE id=? AND user_id=?',(rid,uid)).fetchone()
            if not result:return False
            row=json.loads(result[0])
            if row['state']!='queued':return False
            row['state']='generating';db.execute('UPDATE resumes SET payload=? WHERE id=? AND user_id=?',(json.dumps(row),rid,uid))
        return True
    def update(self,uid,rid,values):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            result=db.execute('SELECT payload FROM resumes WHERE id=? AND user_id=?',(rid,uid)).fetchone()
            if not result:return
            row=json.loads(result[0]);row.update(values)
            db.execute('UPDATE resumes SET payload=? WHERE id=? AND user_id=?',(json.dumps(row),rid,uid))
    def get(self,uid,rid):
        with self.db() as db:row=db.execute('SELECT payload FROM resumes WHERE id=? AND user_id=?',(rid,uid)).fetchone()
        return json.loads(row[0]) if row else None
    def history(self,uid):
        with self.db() as db:rows=db.execute('SELECT payload FROM resumes WHERE user_id=? ORDER BY rowid DESC LIMIT 40',(uid,)).fetchall()
        return [json.loads(row[0]) for row in rows]
    def upload(self,uid,rid,data):
        path=f'{uid}/{rid}.pdf';target=self.path/path;target.parent.mkdir(exist_ok=True)
        # UUID-named outputs are immutable and private to this local data directory.
        with target.open('xb') as f:f.write(data)
        return path
    def remove_pdf(self,path):(self.path/path).unlink(missing_ok=True)
    def pdf(self,row):return (self.path/row['object_path']).read_bytes()
