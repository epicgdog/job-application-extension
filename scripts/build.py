"""Generate only allowlisted client config; never copy the entire environment."""
from pathlib import Path
import json,secrets,sys
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.config import settings,extension_id

def main():
    cfg=settings();root=ROOT/'extension'
    api=urlparse(cfg['api'])
    if api.scheme not in ('http','https') or not api.hostname or api.username or api.password or api.path not in ('','/'):
        raise ValueError('API URL must be an HTTP(S) origin without path or credentials.')
    if api.scheme=='http' and api.hostname not in ('127.0.0.1','localhost','::1'):
        raise ValueError('Remote API endpoints must use HTTPS.')
    config={'api':cfg['api'],'localMode':cfg['local']}
    hosts=[f'{api.scheme}://{api.netloc}/*']
    if cfg['local']:
        if api.hostname not in ('127.0.0.1','localhost','::1'):raise ValueError('Local mode API must be on loopback.')
        cfg['data'].mkdir(exist_ok=True,parents=True);token=cfg['data']/'local-token'
        if not token.exists():token.write_text(secrets.token_urlsafe(32));token.chmod(0o600)
        config['localToken']=token.read_text().strip()
    else:
        url=urlparse(cfg['url'])
        if url.scheme!='https' or not url.hostname or not cfg['key'].startswith('sb_publishable_') or 'REPLACE' in cfg['key']:
            raise ValueError('Configure your Supabase HTTPS URL and publishable key.')
        if not cfg['owner']:raise ValueError('Set APPLYFLOW_OWNER_USER_ID to your Supabase Auth user UUID.')
        config.update(supabaseUrl=cfg['url'],supabaseKey=cfg['key'])
        hosts.append('https://'+url.netloc+'/*')
    (root/'config.js').write_text('globalThis.ApplyFlowConfig = '+json.dumps(config,indent=2)+';\n')
    manifest=json.loads((root/'manifest.json').read_text());manifest['host_permissions']=hosts
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Built extension config for '+('local mode' if cfg['local'] else 'Supabase mode'))
    print('Load unpacked folder: '+str(root))
    print('Extension origin: chrome-extension://'+extension_id())
    if 'chrome-extension://'+extension_id() not in cfg['origins']:
        print('Update APPLYFLOW_ALLOWED_ORIGINS to include this extension origin.')
if __name__=='__main__':main()
