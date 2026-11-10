"""Read-only two-user isolation check against an existing completed test resume."""
import argparse,os,sys
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.config import settings
from server.store import Cloud,CloudError

def main():
    parser=argparse.ArgumentParser(description='Verify that user B cannot read user A’s existing test resume, source metadata, or private PDF. Requires AF_TEST_USER_A_TOKEN and AF_TEST_USER_B_TOKEN in the environment. Uses your .env Supabase URL/publishable key. Does not create, update, or delete data.')
    parser.add_argument('--resume-id',required=True,help='A completed test resume owned by user A')
    args=parser.parse_args();cfg=settings()
    tokens=[os.environ.get('AF_TEST_USER_A_TOKEN',''),os.environ.get('AF_TEST_USER_B_TOKEN','')]
    if not all(tokens):raise ValueError('Set both test-user access tokens in environment variables.')
    a,b=[Cloud(cfg,t) for t in tokens];ua,ub=a.user(),b.user()
    if ua['id']==ub['id']:raise ValueError('Use two different users.')
    row=a.get(ua['id'],args.resume_id)
    if not row or row['state']!='complete':raise ValueError('User A needs a completed test resume.')
    if not a.pdf(row).startswith(b'%PDF'):raise ValueError('User A’s PDF is unavailable.')
    if b.get(ua['id'],row['id']) is not None:raise AssertionError('RLS failure: user B can read user A’s resume metadata.')
    sources=b.table('af_sources','id=eq.'+row['source_id']+'&select=id')
    if sources:raise AssertionError('RLS failure: user B can read source metadata.')
    try:b.pdf(row)
    except CloudError:pass
    else:raise AssertionError('Storage policy failure: user B can download user A’s PDF.')
    # A public URL must also be unreadable without authorization.
    url=cfg['url']+'/storage/v1/object/public/'+cfg['bucket']+'/'+row['object_path']
    try:
        with urlopen(Request(url),timeout=20) as response:
            if response.status==200:raise AssertionError('Bucket is publicly readable.')
    except HTTPError as error:
        if error.code not in (400,401,403,404):raise
    print('PASS: owner can read; other user cannot read metadata/source/PDF; public URL denied.')
if __name__=='__main__':
    try:main()
    except Exception as error:print(str(error),file=sys.stderr);raise SystemExit(1)
