"""Test-only wrapper serving a synthetic job from the same allowed API origin."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.app import Service,handler
from server.config import settings
from http.server import ThreadingHTTPServer
cfg=settings();cfg['library']=Path(__file__).resolve().parents[1]/'examples/resume-library.json';cfg['profile']=Path(__file__).resolve().parents[1]/'examples/profile.json';cfg['master']=cfg['data']/'no-original.pdf';svc=Service(cfg)
Base=handler(svc)
class Fixture(Base):
    def do_GET(self):
        if self.path=='/fixture':
            data=(Path(__file__).parent/'job-fixture.html').read_bytes()
            self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        else:super().do_GET()
server=ThreadingHTTPServer((cfg['host'],cfg['port']),Fixture)
try:server.serve_forever()
finally:server.server_close();svc.pool.shutdown(wait=True)
