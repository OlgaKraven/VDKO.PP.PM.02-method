"""Check identities, student inputs, recovery controls and local teaching links."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import csv,hashlib,io,json,re,zipfile

ROOT=Path(__file__).resolve().parents[1]
areas=json.loads((ROOT/'content/areas.json').read_text(encoding='utf-8'))
stands=json.loads((ROOT/'content/stands.json').read_text(encoding='utf-8'))
shots=json.loads((ROOT/'content/screenshots.json').read_text(encoding='utf-8'))
step_names=set()
for source in ['assignment.md','method.md','reference.md']:
    step_names.update(re.findall(r'^### (.+)$',(ROOT/'content'/source).read_text(encoding='utf-8'),re.M))
assert len({shot['file'] for shot in shots})==len(shots),'Duplicate screenshot entry'
for shot in shots:
    assert shot['after'] in step_names,('Unattached screenshot',shot['file'])
    assert (ROOT/'assets/screens'/shot['file']).is_file(),shot['file']
    assert shot['caption'].strip(),shot['file']
assert [a['variant'] for a in areas]==[f'{n:02d}' for n in range(1,31)]
assert len({a['subject'] for a in areas})==30
assert len(stands)==31
assert len({s['port'] for s in stands})==31
for source,stand in zip(areas,stands[1:]):
    assert (source['variant'],source['subject'],source['context'])==(stand['variant'],stand['subject'],stand['context'])
for stand in stands:
    xy=stand['variant']
    assert stand['computer']=='PM02-V'+xy and stand['database']=='corpdata_'+xy
    assert stand['work_dir']=='C:'+chr(92)+'DBAdmin_'+xy
    with zipfile.ZipFile(ROOT/'downloads'/f'pm02-v{xy}.zip') as z:
        assert z.testzip() is None
        assert json.loads(z.read('stand.json'))==stand
        rows=list(csv.DictReader(io.StringIO(z.read('clients.csv').decode('utf-8-sig'))))
        assert rows==stand['clients']
        assert len({r['email'] for r in rows})==len(rows)
        for row in rows:
            assert re.fullmatch(r'2026-09-\d{2}',row['reg_date'])
            assert row['email'].endswith('@example.test')
        for row in csv.DictReader(io.StringIO(z.read('hashes.csv').decode('utf-8-sig'))):
            assert hashlib.sha256(z.read('recovery-input/'+row['file'])).hexdigest()==row['sha256']
        for name in ['Prepare-Case.ps1','Restore-Case.ps1','Start-Workload.ps1']:
            script=z.read(name).decode('utf-8-sig')
            assert script==(ROOT/'lab'/name).read_text(encoding='utf-8-sig')
        config=json.loads(z.read('client-connection.json'))
        if stand['case']=='port': assert config['port']!=stand['port'] and config['database']==stand['database']
        elif stand['case']=='database': assert config['database']!=stand['database'] and config['port']==stand['port']
        else: assert config['port']==stand['port'] and config['database']==stand['database']

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=set()
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.add(a['id'])
        for key in ['href','src']:
            if key in a:self.links.append(a[key])

documents={}
for file in list(ROOT.glob('*.html'))+list((ROOT/'areas').glob('*.html'))+[ROOT/'index.htm']:
    parsed=Links();parsed.feed(file.read_text(encoding='utf-8'));documents[file.resolve()]=parsed
broken=[]
for file,doc in documents.items():
    for url in doc.links:
        part=urlsplit(url)
        if part.scheme or part.netloc:continue
        target=(file.parent/unquote(part.path)).resolve() if part.path else file
        if not target.is_file():broken.append((str(file.relative_to(ROOT)),url,'file'))
        elif part.fragment and target in documents and unquote(part.fragment) not in documents[target].ids:
            broken.append((str(file.relative_to(ROOT)),url,'anchor'))
assert not broken,broken
print(json.dumps({'areas':30,'packs':31,'client_rows':sum(len(s['clients']) for s in stands),
                  'html_documents':len(documents),'attached_screenshots':len(shots),'local_links':'pass','recovery_hashes':'pass',
                  'scope':'Inputs and structure; VM execution is checked separately.'},ensure_ascii=False))
