"""Adapt the retained common report master to PM.02 stages."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Mm
from docx.enum.table import WD_ROW_HEIGHT_RULE
import report_parts as parts

ROOT=Path(__file__).resolve().parents[1]
MASTER=ROOT/'forms/template/Отчет о выполнении.docx'
MASTER_SHA='5b91286458395ae589ded859021f287ce50cca1148cc5b29226b6fb1cb5373c4'

def text(e):return ''.join(t.text or '' for t in e.iter(qn('w:t')))

def label_rows(table,labels,tag):
    original=deepcopy(table.rows[1]._tr)
    while len(table.rows)<len(labels)+1:table._tbl.append(deepcopy(original))
    while len(table.rows)>len(labels)+1:table._tbl.remove(table.rows[-1]._tr)
    for i,label in enumerate(labels,1):
        for j,cell in enumerate(table.rows[i].cells):
            controls=cell._tc.xpath('.//w:sdt')
            for k,c in enumerate(controls):
                c.find('w:sdtPr/w:tag',c.nsmap).set(qn('w:val'),f'{tag}_{i}_{j}_{k}')
                ts=list(c.find(qn('w:sdtContent')).iter(qn('w:t')))
                ts[0].text=label if j==0 else '____________'
                for t in ts[1:]:t.text=''
            if j==0 and not controls:
                ts=cell._tc.xpath('.//w:t');ts[0].text=label
                for t in ts[1:]:t.text=''
    for row in table.rows:
        row.height=Mm(12);row.height_rule=WD_ROW_HEIGHT_RULE.AT_LEAST

def build():
    assert hashlib.sha256(MASTER.read_bytes()).hexdigest()==MASTER_SHA
    data=json.loads((ROOT/'content/report.json').read_text(encoding='utf-8'))
    out=ROOT/'forms/Отчет о выполнении.docx';shutil.copyfile(MASTER,out);doc=Document(out)
    for c in doc.element.xpath('.//w:sdt'):
        tag=c.find('w:sdtPr/w:tag',c.nsmap)
        if tag is not None and tag.get(qn('w:val'))=='practice_name':
            ts=list(c.find(qn('w:sdtContent')).iter(qn('w:t')))
            ts[0].text=data['title']
            for t in ts[1:]:t.text=''
    label_rows(doc.tables[0],['Номер и предметная область варианта','Файлы стенда: паспорт, CSV и подключение','Индивидуальный случай диагностики','Дополнительный случай при наличии назначения'],'inputs')
    label_rows(doc.tables[1],['Гипервизор и ресурсы ВМ','Windows и имя гостя','PostgreSQL, служба, каталоги и порт','pgAdmin','DBeaver и JDBC','Антивирус','Recuva при назначении восстановления','Редактор отчёта'],'environment')
    label_rows(doc.tables[2],['00 → номер своего варианта','PM02-V00 → имя гостя','5540, corpdata_00, lab_sql_00 → параметры БД','dbadmin_00, DBAdmin_00, sql_reports_00 → профиль и пути','5 записей образца → собственные строки CSV','SecurityScan_00 → каталог своего варианта'],'mapping')
    labels=['Собственная область и исходный снимок','Служба, порт и оба клиента','Структура и все исходные записи','Пять ролей: разрешения, отказы, откаты','SQL-выгрузка структуры и данных','Профиль, DB_HOME и ACL Windows','События ОС и учебное досье отдельно','Три элемента автозагрузки','Новое завершённое сканирование','Четыре ресурса, PID и приоритеты','Индивидуальный случай и повторная проверка','Рекомендации, риск и ограничения','Дополнительный случай при назначении','Отчёт, формы и доступный репозиторий']
    label_rows(doc.tables[-1],labels,'final')
    doc.tables[1]._tbl.getprevious().get_or_add_pPr().append(parts.el('pageBreakBefore'))
    doc.tables[2]._tbl.getprevious().get_or_add_pPr().append(parts.el('pageBreakBefore'))
    table=doc.tables[-1];table.autofit=False
    for row in table.rows:
        row.height=Mm(10)
        for cell,w in zip(row.cells,[59,34,35,32]):cell.width=Mm(w)
    body=doc.element.body;children=list(body)
    start=next(i for i,e in enumerate(children) if text(e)=='Этап выполнения работы')
    end=next(i for i,e in enumerate(children) if text(e)=='Итоговая проверка и сдача')
    anchor=children[end]
    for e in children[start:end]:body.remove(e)
    parts.CONTROL_ID=10000;fig=0
    for index,stage in enumerate(data['stages'],1):
        first=len(list(body))-1
        parts.heading(doc,stage['title'],level=2,new_page=index>1)
        doc.add_paragraph(stage['prompt'])
        for label,tag,lines in [('Исходные данные и ожидаемый результат','initial',2),('Выполненные действия','actions',3),('Фактический результат и проверка','actual',2),('Вывод по этапу и объяснение расхождений','conclusion',2)]:
            parts.response(doc,label,f's{index}_{tag}',lines)
        doc.add_page_break();p=doc.add_paragraph();p.add_run('Подтверждения этапа приведены на рис. ')
        for j,caption in enumerate(stage['screenshots']):
            if j:p.add_run(', ')
            parts.field(p,f'REF pm02_fig_{fig+j+1} \\h',str(fig+j+1))
        p.add_run('. Вставить собственные результаты, сохранив подписи.')
        for j,caption in enumerate(stage['screenshots']):
            if j and j%2==0:doc.add_page_break()
            fig+=1;parts.figure_slot(doc,caption,f'pm02_figure_{fig}',fig,f'pm02_fig_{fig}')
        generated=list(body)[first:-1]
        for e in generated:body.remove(e);anchor.addprevious(e)
    for cid,c in enumerate(doc.element.xpath('.//w:sdt'),30000):c.find('w:sdtPr/w:id',c.nsmap).set(qn('w:val'),str(cid))
    doc.core_properties.title='Отчет о выполнении';doc.core_properties.subject='ПМ.02'
    doc.core_properties.author=doc.core_properties.last_modified_by=''
    doc.core_properties.comments=doc.core_properties.keywords=''
    for level in doc.part.numbering_part.element.findall('.//' + qn('w:lvl')):
        suffix=level.find(qn('w:suff'))
        if suffix is not None:suffix.set(qn('w:val'),'nothing')
        rpr=level.find(qn('w:rPr'))
        if rpr is None:rpr=parts.el('rPr');level.append(rpr)
        fonts=rpr.find(qn('w:rFonts'))
        if fonts is None:fonts=parts.el('rFonts');rpr.append(fonts)
        for attr in ('ascii','hAnsi','eastAsia','cs'):fonts.set(qn('w:'+attr),'Times New Roman')
        for attr in ('asciiTheme','hAnsiTheme','eastAsiaTheme','cstheme'):fonts.attrib.pop(qn('w:'+attr),None)
    for paragraph in doc.paragraphs:
        if paragraph.style.name in ('Heading 1','Heading 2','Heading 3'):
            if paragraph.runs:paragraph.runs[0].text=' '+paragraph.runs[0].text
        if paragraph.text == 'Состав передаваемых материалов':
            paragraph.paragraph_format.page_break_before=True
    doc.save(out)
    with zipfile.ZipFile(out) as z:edited={n:z.read(n) for n in z.namelist()}
    with zipfile.ZipFile(MASTER) as z:original={n:z.read(n) for n in z.namelist()}
    allowed={'word/document.xml','docProps/core.xml','word/numbering.xml'}
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,value in original.items():
            info=zipfile.ZipInfo(name,(2026,11,5,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,edited[name] if name in allowed else value)
    with zipfile.ZipFile(out) as z:
        for name,value in original.items():
            if name not in allowed:assert z.read(name)==value,name
    shutil.copyfile(out,ROOT/'downloads/Отчет о выполнении.docx')
    print('Copied common master; adapted',len(data['stages']),'stages and',fig,'figure slots')

if __name__=='__main__':build()
