"""Export the approved 10.5/16 pt reading profile independently of screen CSS."""
from pathlib import Path
from html import escape
from urllib.parse import urljoin
import shutil
from bs4 import BeautifulSoup, NavigableString, Tag
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate,Frame,PageTemplate,Paragraph,Flowable,Spacer,PageBreak,Image,Table,TableStyle,HRFlowable,KeepTogether
import build

ROOT=Path(__file__).resolve().parents[1]
BASE=build.BASE
W,H=210*mm,297*mm
WIDTH=160*mm
CARD=WIDTH-33
INNER=CARD-26
for alias,name in [('Body','Regular'),('Semi','SemiBold'),('Bold','Bold')]:
    pdfmetrics.registerFont(TTFont(alias,str(ROOT/'assets/fonts'/f'GolosText-{name}.ttf')))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Bold',italic='Body',boldItalic='Bold')
mono=next((p for p in [Path('C:/Windows/Fonts/consola.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')] if p.is_file()),None)
if not mono:raise RuntimeError('A monospaced font is required for code.')
pdfmetrics.registerFont(TTFont('Mono',str(mono)))
BODY=ParagraphStyle('body',fontName='Body',fontSize=10.5,leading=16,spaceAfter=6)
HEAD=ParagraphStyle('head',fontName='Semi',fontSize=13,leading=18,spaceAfter=10)
CODE=ParagraphStyle('code',fontName='Mono',fontSize=8.5,leading=12,splitLongWords=True,wordWrap='CJK')
SMALL=ParagraphStyle('small',fontName='Body',fontSize=9.5,leading=15,spaceAfter=6)
TITLE=ParagraphStyle('title',fontName='Bold',fontSize=24,leading=28,textColor=colors.white)
KICK=ParagraphStyle('kick',fontName='Semi',fontSize=9,leading=13,textColor=colors.white)
CELL=ParagraphStyle('cell',parent=SMALL,fontSize=9,leading=13,spaceAfter=0,splitLongWords=True)
CELL_HEAD=ParagraphStyle('cell-head',parent=CELL,fontName='Semi')

class Banner(Flowable):
    keepWithNext=True
    def __init__(self,label,title,key):
        super().__init__();self.label=Paragraph(escape(label),KICK)
        self.label.wrap(WIDTH-36,1000)
        self.title=Paragraph(escape(title),TITLE);self.key=key;self.name=title
        self.width=WIDTH;self.th=self.title.wrap(WIDTH-36,1000)[1]
        self.height=19+13+12+self.th+20+4
    def wrap(self,w,h):return self.width,self.height
    def draw(self):
        c=self.canv;c.setFillColor(colors.HexColor('#1c1c1c'));c.rect(0,0,self.width,self.height,fill=1,stroke=0)
        c.setFillColor(colors.HexColor('#ed131c'));c.rect(0,0,self.width,4,fill=1,stroke=0)
        self.label.drawOn(c,18,self.height-32);self.title.drawOn(c,18,24)
        c.bookmarkPage(self.key);c.addOutlineEntry(self.name,self.key,level=0,closed=False)

class Card(Flowable):
    def __init__(self,n,name,parts,continued=False):
        super().__init__();self.n=n;self.name=name;self.parts=parts;self.continued=continued
        self.width=WIDTH;self.spaceAfter=13
        self.head=Paragraph(escape(name)+(' — продолжение' if continued else ''),HEAD)
    def measure(self):
        self.hh=self.head.wrap(INNER,10000)[1]
        self.hs=[p.wrap(INNER,10000)[1]+p.getSpaceAfter() for p in self.parts]
        return 26+self.hh+10+sum(self.hs)
    def wrap(self,w,h):self.height=self.measure();return self.width,self.height
    def split(self,w,h):
        if self.measure()<=360 or h<180:return []
        used=26+self.head.wrap(INNER,10000)[1]+10;first=[];rest=[]
        for i,p in enumerate(self.parts):
            ph=p.wrap(INNER,10000)[1]+p.getSpaceAfter()
            if used+ph<=h:first.append(p);used+=ph;continue
            split=p.split(INNER,h-used-p.getSpaceAfter()) if h-used>=32 else []
            if split:first.append(split[0]);rest=split[1:]+self.parts[i+1:]
            else:rest=self.parts[i:]
            break
        if not first or not rest:return []
        return [Card(self.n,self.name,first,self.continued),Card(self.n,self.name,rest,True)]
    def draw(self):
        self.measure();c=self.canv
        c.setStrokeColor(colors.HexColor('#dfe1e5'));c.setLineWidth(.6);c.line(12,0,12,self.height-35)
        c.setFillColor(colors.HexColor('#f4f4f6'));c.roundRect(33,0,CARD,self.height,10,fill=1,stroke=0)
        c.setFillColor(colors.white);c.setStrokeColor(colors.HexColor('#ed131c'));c.setLineWidth(1.1)
        c.circle(12,self.height-24,11,fill=1,stroke=1)
        c.setFillColor(colors.HexColor('#1c1c1c'));c.setFont('Body',9);c.drawCentredString(12,self.height-27,str(self.n))
        y=self.height-13-self.hh;self.head.drawOn(c,46,y);y-=10
        for p in self.parts:
            ph=p.wrap(INNER,10000)[1];y-=ph;p.drawOn(c,46,y);y-=p.getSpaceAfter()

def inline(node):
    if isinstance(node,NavigableString):return escape(str(node))
    content=''.join(inline(n) for n in node.children)
    if node.name in ('b','strong'):return '<b>'+content+'</b>'
    if node.name in ('em','i'):return '<i>'+content+'</i>'
    if node.name=='code':return '<font name="Mono">'+content+'</font>'
    if node.name=='br':return '<br/>'
    if node.name=='a' and node.get('href'):
        return '<link href="'+escape(urljoin(BASE,node['href']),quote=True)+'" color="#a50d14"><u>'+content+'</u></link>'
    return content

def elements(nodes):
    result=[]
    for node in nodes:
        if isinstance(node,NavigableString):
            if node.strip():result.append(Paragraph(escape(str(node).strip()),BODY))
            continue
        name=node.name
        if name in ('p','blockquote'):
            if node.get_text().strip():result.append(Paragraph(inline(node),BODY))
        elif name in ('ul','ol'):
            for i,li in enumerate(node.find_all('li',recursive=False),1):
                result.append(Paragraph((str(i)+') ' if name=='ol' else '• ')+inline(li),BODY))
        elif name=='pre':
            for line in node.get_text().splitlines():
                result.append(Paragraph(escape(line.expandtabs(4)).replace(' ','&#160;') or '&#160;',CODE))
            result.append(Spacer(1,6))
        elif name=='table':
            rows=[[Paragraph(inline(cell),CELL_HEAD if cell.name=='th' else CELL) for cell in tr.find_all(['td','th'],recursive=False)] for tr in node.find_all('tr')]
            count=max(map(len,rows));weights=[1]*count
            if count==2:weights=[.9,1.5]
            if count==4:weights=[.25,1.2,1.25,.9]
            table=Table(rows,colWidths=[INNER*x/sum(weights) for x in weights],repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,-1),.5,colors.HexColor('#dfe1e5'))]))
            table.spaceAfter=6;result.append(table)
        elif name in ('h2','h3','h4'):result.append(Paragraph(inline(node),HEAD))
        else:result.extend(elements(node.children))
    return result

def figure(shot,number):
    image=Image(str(ROOT/'assets/screens'/shot['file']));image._restrictSize(WIDTH,430)
    caption=Paragraph(f'Рисунок {number} — '+escape(shot['caption'])+f'<br/><link href="{BASE}assets/screens/{shot["file"]}" color="#a50d14"><u>Открыть снимок в исходном размере</u></link>',SMALL)
    return KeepTogether([image,Spacer(1,8),caption,Spacer(1,13)])

def document(source,label):
    title,html=build.render_document(source);soup=BeautifulSoup(html,'html.parser');story=[];intro=[]
    if source=='assignment.md':intro.append(BeautifulSoup('<p><b>'+escape(title)+'</b></p>','html.parser').p)
    for n in soup.contents:
        if isinstance(n,Tag) and n.get('class')==['contents']:break
        if isinstance(n,Tag):intro.append(n)
    for index,chapter in enumerate(soup.select('.chapter'),1):
        name=chapter.find('h2',recursive=False).get_text()
        gap=Spacer(1,18);gap.keepWithNext=True
        story.extend([Spacer(1,15),Banner(label,name,f'{source}-{index}'),gap])
        if index==1 and intro:story.append(Card('•','Условия работы',elements(intro)))
        for step in chapter.select('.step'):
            n=step.select_one('.step-number').get_text();body=step.select_one('.step-body')
            title=body.h3.get_text();body.h3.extract();check=body.select_one('.check')
            if check:check.extract()
            children=elements(body.contents)
            if check:children+=[HRFlowable(width=INNER,thickness=.6,color=colors.HexColor('#dfe1e5'),spaceAfter=11)]+elements(check.contents)
            story.append(Card(n,title,children))
            for number,shot in enumerate(build.SHOTS,1):
                if shot['after']==title:story.append(figure(shot,number))
    return story

def footer(c,doc):
    c.saveState();c.setFillColor(colors.HexColor('#606773'));c.setFont('Body',8)
    c.drawCentredString(W/2,10*mm,str(doc.page));c.restoreState()

def save(path,story,title):
    doc=BaseDocTemplate(str(path),pagesize=(W,H),leftMargin=30*mm,rightMargin=20*mm,topMargin=20*mm,bottomMargin=20*mm,title=title,author='',invariant=1)
    frame=Frame(30*mm,20*mm,WIDTH,H-40*mm,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id='page',frames=[frame],onPage=footer));doc.build(story)

def main():
    story=[]
    for source,label in [('assignment.md','1. Общее задание'),('files.md','2. Файлы для работы'),('method.md','3. Выполнение на образце'),('reference.md','4. Диагностические случаи')]:
        if story:story.append(PageBreak())
        story.extend(document(source,label))
    save(ROOT/'downloads/assignment.pdf',story,'Методические рекомендации — ПМ.02')
    story=[]
    for area in build.AREAS:
        p=build.profile(area);xy=p['variant']
        if story:story.append(PageBreak())
        gap=Spacer(1,18);gap.keepWithNext=True
        story.extend([Banner('Вариант '+xy,p['subject'],'area-'+xy),gap])
        soup=BeautifulSoup(build.area_body(p,prefix=''),'html.parser')
        story.append(Card('•','Индивидуальная работа и образец',elements(soup.select_one('.comparison').children)))
        for step in soup.select('.step'):
            body=step.select_one('.step-body');name=body.h3.get_text();body.h3.extract();check=body.select_one('.check');check.extract()
            children=elements(body.contents)+[HRFlowable(width=INNER,thickness=.6,color=colors.HexColor('#dfe1e5'),spaceAfter=11)]+elements(check.contents)
            story.append(Card(step.select_one('.step-number').get_text(),name,children))
    save(ROOT/'downloads/guide.pdf',story,'Список предметных областей — ПМ.02')
    shutil.copyfile(ROOT/'downloads/guide.pdf',ROOT/'downloads/subject-areas.pdf')
    print('Exported full assignment.pdf and guide.pdf (30 areas); legacy area PDF alias retained.')

if __name__=='__main__':main()
