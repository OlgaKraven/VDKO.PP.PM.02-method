"""Export the three reading editions with a local static preview and Chromium."""
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
import json,shutil,subprocess,threading,os

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'output/playwright/pdf-export';WORK.mkdir(parents=True,exist_ok=True)
npx=shutil.which('npx.cmd' if os.name=='nt' else 'npx')
if not npx:raise SystemExit('Node.js/npm with npx is required for PDF export.')
class QuietHandler(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
handler=partial(QuietHandler,directory=str(ROOT))
server=ThreadingHTTPServer(('127.0.0.1',0),handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
origin=f'http://127.0.0.1:{server.server_port}/'
code='''async (page) => {
const origin = ORIGIN;
const target = TARGET;
const base = 'https://olgakraven.github.io/VDKO.PP.PM.02-method/';
for (const [source,output] of [['index.html','assignment.pdf'],['guide-print.html','guide.pdf'],['areas-print.html','subject-areas.pdf']]) {
 await page.emulateMedia({media:'print'});
 await page.goto(origin+source);
 await page.evaluate(()=>document.fonts.ready);
 await page.evaluate(async()=>{for(const image of document.images){image.loading='eager';await image.decode();}});
 await page.evaluate(base=>{
  for (const a of document.querySelectorAll('a[href]')) {
   const raw=a.getAttribute('href');if(raw.startsWith('#'))continue;
   const url=new URL(a.href);
   if(url.hash && /\\/(guide|reference)\\.html$/.test(url.pathname) && document.getElementById(url.hash.slice(1))) {a.setAttribute('href',url.hash);continue;}
   if(url.origin===location.origin)a.href=base+url.pathname.slice(1)+url.search+url.hash;
  }
 },base);
 await page.pdf({path:target+output,preferCSSPageSize:true,printBackground:true,tagged:true,outline:true,
  displayHeaderFooter:true,headerTemplate:'<span></span>',
  footerTemplate:'<div style="font:9px Arial;width:100%;text-align:center;color:#606773"><span class="pageNumber"></span> / <span class="totalPages"></span></div>'});
}
return 'Exported assignment.pdf, guide.pdf and subject-areas.pdf';
}'''.replace('ORIGIN',json.dumps(origin)).replace('TARGET',json.dumps((ROOT/'downloads').as_posix()+'/'))
script=WORK/'export.js';script.write_text(code,encoding='utf-8')
if os.name=='nt':
 cli=Path(npx).parent/'node_modules/npm/bin/npx-cli.js'
 node=shutil.which('node.exe')
 if not cli.is_file() or not node:raise SystemExit('A standard Node.js/npm installation is required.')
 launcher=[node,str(cli)]
else:launcher=[npx]
prefix=launcher+['--yes','--package','@playwright/cli','playwright-cli','-s=pm02-export']
try:
 for args in [['open',origin],['run-code','--filename',str(script)]]:
  result=subprocess.run(prefix+args,cwd=WORK,text=True,encoding='utf-8',errors='replace',stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  with (WORK/'export.log').open('a',encoding='utf-8') as log:log.write(result.stdout)
  if result.returncode:raise RuntimeError('PDF export failed; inspect output/playwright/pdf-export/export.log')
 print('Exported assignment.pdf, guide.pdf and subject-areas.pdf')
finally:
 subprocess.run(prefix+['close'],cwd=WORK,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 server.shutdown()
