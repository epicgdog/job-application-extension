"""Authenticated local/cloud resume API. Run: python -m server.app"""
from __future__ import annotations
import concurrent.futures,datetime,hashlib,hmac,json,re,secrets,threading,time,uuid
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse
from .config import settings
from .resume import generate,validate_library,library_hash,digest,VERSION
from .store import Cloud,CloudError,Local

class APIError(Exception):
    def __init__(self,status,message):self.status=status;self.message=message

class Service:
    def __init__(self,config):
        self.config=config;self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.pending=threading.BoundedSemaphore(8)
        self.lib=validate_library(json.loads(config['library'].read_text()))
        self.profile=json.loads(config['profile'].read_text())['profile']
        self.source_hash=library_hash(self.lib)
        self.original=config['master'].read_bytes() if config['master'].exists() else None
        if self.original and digest(self.original)!=self.lib['source']['sha256']:raise ValueError('Original PDF hash differs from source library.')
        config['data'].mkdir(parents=True,exist_ok=True)
        if config['local']:
            if config['host'] not in ('127.0.0.1','localhost','::1'):raise ValueError('Local mode must bind to loopback only.')
            path=config['data']/'local-token'
            if not path.exists():path.write_text(secrets.token_urlsafe(32));path.chmod(0o600)
            self.local_token=path.read_text().strip();self.local=Local(config)
        else:
            if not config['url'].startswith('https://') or not config['key'].startswith('sb_publishable_') or not config['owner']:
                raise ValueError('Cloud mode needs HTTPS Supabase URL, publishable key, and APPLYFLOW_OWNER_USER_ID.')
    def auth(self,header):
        token=header.removeprefix('Bearer ').strip() if header.startswith('Bearer ') else ''
        if self.config['local']:
            if not token or not hmac.compare_digest(token,self.local_token):raise APIError(401,'Local API token missing. Run scripts/build.py and reload the extension.')
            return 'local',self.local
        if not token:raise APIError(401,'Sign in to Supabase first.')
        store=Cloud(self.config,token)
        try:user=store.user()
        except CloudError:raise APIError(401,'Sign-in expired or invalid. Sign in again.') from None
        if user.get('id')!=self.config['owner']:raise APIError(403,'This private resume service belongs to a different account.')
        return user['id'],store
    def submit(self,uid,store,body):
        job=body.get('job',{})
        if not isinstance(job,dict):raise APIError(400,'Job must be an object.')
        job={k:str(job.get(k,'')).strip() for k in ['title','company','url','description']}
        if not job['title'] or not job['company']:raise APIError(400,'Confirm the job title and company first.')
        if len(job['description'])<80 or len(job['description'])>40000:raise APIError(400,'Job description must contain 80–40,000 characters.')
        if any(len(job[k])>1000 for k in ['title','company','url']):raise APIError(400,'Job metadata is too long.')
        if job['url'] and not re.match(r'^https?://',job['url']):raise APIError(400,'Use an HTTP(S) job URL.')
        nonce=body.get('regeneration_id','')
        if nonce:
            try:nonce=str(uuid.UUID(nonce))
            except (ValueError,TypeError,AttributeError):raise APIError(400,'Regeneration ID must be a UUID.')
        key=digest(json.dumps({'job':job,'source':self.source_hash,'template':VERSION,'nonce':nonce},sort_keys=True))
        source_id=str(uuid.uuid5(uuid.NAMESPACE_URL,uid+':'+self.source_hash))
        store.source(uid,source_id,self.lib,self.profile,self.source_hash,self.original)
        row={'id':str(uuid.uuid4()),'user_id':uid,'source_id':source_id,'request_key':key,'job':job,'state':'queued','result':None,'object_path':None,'error':None,'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        if not self.pending.acquire(blocking=False):raise APIError(429,'Generation queue is full. Try again shortly.')
        try:
            row=store.create(row)
            if store.claim(uid,row['id']):
                try:self.pool.submit(self.worker,uid,store,row)
                except Exception:
                    store.update(uid,row['id'],{'state':'failed','error':'Could not start generation. Regenerate to retry.'});raise
            else:self.pending.release()
        except Exception:
            # Release only if the worker did not take ownership.
            # submit() only fails before scheduling in ordinary request handling.
            try:self.pending.release()
            except ValueError:pass
            raise
        return row
    def worker(self,uid,store,row):
        uploaded=None
        try:
            data,result=generate(self.lib,row['job'])
            store.update(uid,row['id'],{'state':'uploading'})
            uploaded=store.upload(uid,row['id'],data)
            store.update(uid,row['id'],{'state':'complete','result':result,'object_path':uploaded,'error':None})
        except Exception as error:
            if uploaded:
                # A lost HTTP response can follow a committed metadata write.
                # Never delete its PDF until the actual row state is known.
                try:current=store.get(uid,row['id'])
                except Exception:return
                if current and current['state']=='complete':return
                try:store.remove_pdf(uploaded)
                except Exception:pass
            message=str(error) if isinstance(error,(ValueError,CloudError)) else 'Generation failed. Check server availability and regenerate.'
            try:store.update(uid,row['id'],{'state':'failed','error':message})
            except Exception:pass
        finally:self.pending.release()
    def reconcile(self,uid,store,row):
        if row and row['state'] in ('queued','generating','uploading'):
            age=time.time()-datetime.datetime.fromisoformat(row['created_at'].replace('Z','+00:00')).timestamp()
            if age>600:
                store.update(uid,row['id'],{'state':'failed','error':'Generation timed out or server restarted. Regenerate to retry.'})
                row=store.get(uid,row['id'])
        return row

def summary(row):
    return {k:row.get(k) for k in ('id','job','state','result','error','created_at')}

def handler(service):
    class Handler(BaseHTTPRequestHandler):
        server_version='ApplyFlow/2'
        def log_message(self,*args):pass # Never log job bodies, auth headers, or private URLs.
        def origin(self):
            origin=self.headers.get('Origin')
            if origin and origin not in service.config['origins']:raise APIError(403,'Origin not allowed. Check APPLYFLOW_ALLOWED_ORIGINS.')
            return origin
        def send(self,status,data,content_type='application/json'):
            body=json.dumps(data).encode() if content_type=='application/json' else data
            self.send_response(status)
            if self.headers.get('Origin') in service.config['origins']:
                self.send_header('Access-Control-Allow-Origin',self.headers['Origin']);self.send_header('Vary','Origin')
            self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS')
            self.send_header('Access-Control-Allow-Headers','Authorization,Content-Type')
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_OPTIONS(self):
            try:self.origin();self.send(200,{'ok':True})
            except APIError as e:self.send(e.status,{'error':e.message})
        def do_GET(self):self.dispatch()
        def do_POST(self):self.dispatch()
        def dispatch(self):
            try:
                self.origin();path=urlparse(self.path).path
                if path=='/health' and self.command=='GET':return self.send(200,{'ok':True,'mode':'local' if service.config['local'] else 'supabase'})
                uid,store=service.auth(self.headers.get('Authorization',''))
                if path=='/bootstrap' and self.command=='GET':return self.send(200,{'profile':service.profile,'source_hash':service.source_hash,'entry_count':len(service.lib['entries']),'mode':'local' if service.config['local'] else 'supabase'})
                if path=='/resumes' and self.command=='POST':
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=200000:raise APIError(413,'Request body is too large or missing.')
                    if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise APIError(415,'JSON is required.')
                    try:body=json.loads(self.rfile.read(length))
                    except (ValueError,UnicodeError):raise APIError(400,'Invalid JSON body.')
                    if not isinstance(body,dict):raise APIError(400,'Expected a JSON object.')
                    return self.send(202,summary(service.submit(uid,store,body)))
                if path=='/resumes' and self.command=='GET':
                    return self.send(200,[summary(service.reconcile(uid,store,r)) for r in store.history(uid)])
                match=re.fullmatch(r'/resumes/([0-9a-f-]{36})(/pdf)?',path)
                if match and self.command=='GET':
                    row=service.reconcile(uid,store,store.get(uid,match[1]))
                    if not row:raise APIError(404,'Resume not found.')
                    if match[2]:
                        if row['state']!='complete':raise APIError(409,'Resume is not ready.')
                        return self.send(200,store.pdf(row),'application/pdf')
                    return self.send(200,summary(row))
                raise APIError(404,'Endpoint not found.')
            except APIError as e:self.send(e.status,{'error':e.message})
            except CloudError as e:self.send(502,{'error':str(e)})
            except (ConnectionError,TimeoutError):self.send(503,{'error':'Storage service unavailable. Try again.'})
            except Exception:self.send(500,{'error':'Request failed. Verify the server configuration and source files.'})
    return Handler

def main():
    config=settings();service=Service(config)
    server=ThreadingHTTPServer((config['host'],config['port']),handler(service))
    print(f"ApplyFlow API listening on {config['host']}:{config['port']} ({'local only' if config['local'] else 'Supabase private storage'})",flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();service.pool.shutdown(wait=True)
if __name__=='__main__':main()
