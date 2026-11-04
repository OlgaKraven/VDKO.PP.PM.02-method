"""Build the static teaching materials and individual lab input archives."""
from pathlib import Path
from html import escape
import csv
import hashlib
import io
import json
import re
import zipfile
import markdown

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://olgakraven.github.io/VDKO.PP.PM.02-method/'
AREAS = json.loads((ROOT/'content/areas.json').read_text(encoding='utf-8'))
SHOTS = json.loads((ROOT/'content/screenshots.json').read_text(encoding='utf-8')) if (ROOT/'content/screenshots.json').exists() else []
TYPES = ['port','database','readonly','data','startup']
CASE_TEXT = {
 'port': ('Проверить неверный порт клиента', 'Исходное подключение содержит другой порт. Установить фактический слушающий порт, исправить одно значение и подтвердить вход client03.'),
 'database': ('Проверить имя базы в подключении', 'Сервер доступен, но профиль обращается к отсутствующей БД с окончанием _archive. Сопоставить список БД с паспортом и исправить только имя.'),
 'readonly': ('Объяснить ожидаемый отказ изменения', 'Под client03 подтвердить чтение, затем отказ UPDATE в отдельной транзакции с ROLLBACK. Обосновать сохранение ограничений роли.'),
 'data': ('Проверить контрольную запись области', 'Сверить количество и контрольный email с CSV; получить соответствующие имя и дату. Совпадение количества без проверки содержимого недостаточно.'),
 'startup': ('Проверить лишнюю учебную автозагрузку', 'Сравнить входы в Windows до и после отключения только PM02Lab-Workload. Сопоставить PID и ресурсы; сохранить два остальных учебных элемента до окончания анализа.')
}

def md(text):
    return markdown.markdown(text, extensions=['fenced_code','tables','attr_list','sane_lists'])

def write(path, content):
    target=ROOT/path; target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(content,encoding='utf-8',newline='\n')

def nav(prefix=''):
    return '<nav class="site-nav" aria-label="Материалы практики">'+''.join(
        f'<a href="{prefix}{url}">{label}</a>' for url,label in [
        ('index.html','Задание'),('areas.html','Предметные области'),('files.html','Файлы'),
        ('guide.html','Методические рекомендации'),('reference.html','Диагностические случаи')])+'</nav>'

def shell(title, body, subtitle='', prefix='', pdf=None):
    kind='subject-area' if prefix=='../' or title=='Предметные области' else 'method'
    download=f'<a class="button" href="{prefix}downloads/{pdf}">Скачать PDF</a>' if pdf else ''
    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · ПМ.02</title><link rel="icon" href="{prefix}assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{prefix}styles.css"></head><body class="{kind}">
<a class="skip" href="#content">Перейти к содержанию</a>{nav(prefix)}
<header class="masthead"><div class="page"><p class="eyebrow">Учебная практика ПМ.02</p>
<h1>{escape(title)}</h1>{f'<p>{escape(subtitle)}</p>' if subtitle else ''}{download}</div></header>
<main id="content" class="page">{body}</main>
<footer class="page footer"><a href="{prefix}index.html">Задание практики</a><a href="{prefix}areas.html">Предметные области</a></footer>
<script src="{prefix}materials.js" defer></script></body></html>'''

def route_card(number, title, text, check='', id=''):
    anchor=f' id="{escape(id,quote=True)}"' if id else ''
    result=f'<div class="check">{check}</div>' if check else ''
    return f'<section class="step"{anchor}><span class="step-number">{number}</span><div class="step-body"><h3>{escape(title)}</h3>{text}{result}</div></section>'

def render_document(source):
    text=(ROOT/'content'/source).read_text(encoding='utf-8')
    title=text.splitlines()[0].removeprefix('# ')
    pieces=re.split(r'^## (.+)$',text,flags=re.M)
    intro=md('\n'.join(pieces[0].splitlines()[1:]))
    html=[]; contents=[]; step_no=0
    for section_no in range(1,len(pieces),2):
        head=pieces[section_no].strip()
        explicit=re.search(r'\{#([^}]+)\}',head)
        sid=explicit.group(1) if explicit else 'section-'+str((section_no+1)//2)
        head=re.sub(r'\s*\{#[^}]+\}','',head)
        contents.append((sid,head))
        html.append(f'<section class="chapter" id="{sid}"><h2>{escape(head)}</h2>')
        cards=re.split(r'^### (.+)$',pieces[section_no+1],flags=re.M)
        if cards[0].strip(): html.append(md(cards[0]))
        for i in range(1,len(cards),2):
            step_no+=1; name=cards[i].strip(); body=cards[i+1].strip()
            before, sep, check=body.partition('> **Проверка:**')
            if not sep: before,sep,check=body.partition('> **Результат:**')
            check_html=md(('**Проверка:** ' if sep.startswith('> **Проверка') else '**Результат:** ')+check.strip()) if sep else ''
            continuations=before.split('<!-- continue -->')
            for part_no,part in enumerate(continuations):
                heading=name if part_no==0 else name+' (продолжение)'
                anchor=f'step-{step_no}' if part_no==0 else f'step-{step_no}-continued-{part_no+1}'
                html.append(route_card(step_no,heading,md(part),check_html if part_no==len(continuations)-1 else '',id=anchor))
            for shot in SHOTS:
                if shot.get('after')==name:
                    if not (ROOT/'assets/screens'/shot['file']).is_file(): raise FileNotFoundError(shot['file'])
                    html.append(f'<figure class="evidence"><a href="assets/screens/{escape(shot["file"])}"><img src="assets/screens/{escape(shot["file"])}" alt="{escape(shot["caption"])}" loading="lazy"></a><figcaption>Рисунок {SHOTS.index(shot)+1} — {escape(shot["caption"])}</figcaption></figure>')
        html.append('</section>')
    toc='<nav class="contents" aria-label="Содержание">'+''.join(f'<a href="#{sid}">{escape(label)}</a>' for sid,label in contents)+'</nav>'
    return title, intro+toc+''.join(html)

def profile(area):
    n=int(area['variant']); xy=f'{n:02d}'; kind=TYPES[n%5]
    rows=[{'name':f'Учебный клиент {xy}-{i:02d}', 'email':f'v{xy}-c{i:02d}@example.test',
           'reg_date':f'2026-09-{1+(n+i)%28:02d}'} for i in range(1,6+n%4)]
    return dict(area,computer='PM02-V'+xy,vm_cpu=4,vm_memory_mb=6144,vm_disk_gb=80,
        recovery_disk_gb=1,os='Windows 11 x64',server='lab_sql_'+xy,port=5540+n,
        database='corpdata_'+xy,os_user='dbadmin_'+xy,work_dir='C:\\DBAdmin_'+xy,
        db_home='C:\\Program Files\\PostgreSQL\\17',reports='sql_reports_'+xy,
        scan='SecurityScan_'+xy,case=kind,clients=rows)

def csv_bytes(rows):
    f=io.StringIO(newline=''); writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return f.getvalue().encode('utf-8-sig')

def docx_fixture(text):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:
        def put(name,content):
            info=zipfile.ZipInfo(name,date_time=(2026,11,3,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,content)
        put('[Content_Types].xml','''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>''')
        put('_rels/.rels','''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>''')
        put('word/document.xml',f'''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:pPr><w:jc w:val="both"/><w:ind w:firstLine="709"/><w:spacing w:line="360" w:lineRule="auto"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="28"/><w:color w:val="000000"/></w:rPr><w:t>{escape(text)}</w:t></w:r></w:p><w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1701"/></w:sectPr></w:body></w:document>''')
    return data.getvalue()

def pack(p):
    xy=p['variant']; config={'host':'127.0.0.1','port':p['port'],'database':p['database'],'user':'client03'}
    if p['case']=='port': config['port']+=1000
    if p['case']=='database': config['database']+='_archive'
    files={'stand.json':(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf-8'),
        'clients.csv':csv_bytes(p['clients']),
        'client-connection.json':(json.dumps(config,ensure_ascii=False,indent=2)+'\n').encode('utf-8'),
        'README.txt':(f"ПМ.02. Область {xy}: {p['subject']}\nРаспаковать в C:\\PM02\\v{xy} внутри {p['computer']}.\n"
            f"Карточка и маршрут: {BASE}areas/{xy}.html\n"
            f"Методические рекомендации: {BASE}guide.html\n"
            "checks — пустые протоколы; заполнить фактическими наблюдениями.\n"
            "Prepare-Case.ps1 создаёт помеченные учебные события и автозагрузку, не настраивает СУБД вместо обучающегося.\n"
            "Образ Windows, ВМ и установщики не входят в архив; ссылки и подготовка даны в методичке.\n").encode('utf-8'),
        'checks/sql-access.csv':'Пользователь,БД и порт,Операция,Ожидание,Фактический результат,Свидетельство\n'.encode('utf-8-sig'),
        'checks/events.csv':'Происхождение,Начало окна,Конец окна,Время,Код или имя,Источник,Описание,Связь с симптомом,Свидетельство\n'.encode('utf-8-sig'),
        'checks/startup.csv':'Элемент,Путь,Назначение,Исходное состояние,Необходимость,Действие,Проверка\n'.encode('utf-8-sig'),
        'checks/resources.csv':'Состояние,Начало и длительность,Процесс,PID,CPU,Память,Диск,Сеть,Приоритет,Наблюдение\n'.encode('utf-8-sig'),
        'checks/problems.csv':'Компонент,Проблема или ошибка,Причина или гипотеза,Рекомендация,Риск для пользователя,Доказательство\n'.encode('utf-8-sig')}
    for script in (ROOT/'lab').glob('*.ps1'):
        files[script.name]=script.read_text(encoding='utf-8-sig').encode('utf-8-sig')
    recovery={'note.txt':f"ПМ.02, область {xy}: {p['subject']}. Контроль восстановления.\n".encode('utf-8'),
        'clients.csv':csv_bytes(p['clients']), 'sample.docx':docx_fixture(f"Контрольный документ области {xy}: {p['subject']}")}
    hashes=[]
    for name,data in recovery.items():
        files['recovery-input/'+name]=data
        hashes.append({'file':name,'sha256':hashlib.sha256(data).hexdigest()})
    files['hashes.csv']=csv_bytes(hashes)
    dest=ROOT/'downloads'/f'pm02-v{xy}.zip'; dest.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():
            info=zipfile.ZipInfo(name,date_time=(2026,11,3,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,data)
    return dest

def table(rows,headings=('Параметр','Значение')):
    return '<div class="table-wrap"><table><thead><tr>'+''.join(f'<th scope="col">{escape(x)}</th>' for x in headings)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{escape(str(x))}</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'

def area_body(p,prefix='../'):
    xy=p['variant']; title,desc=CASE_TEXT[p['case']]
    values=[('Компьютер',p['computer']),('Ресурсы ВМ',f"{p['vm_cpu']} CPU · {p['vm_memory_mb']} МБ · {p['vm_disk_gb']} ГБ"),
        ('Сеть','NAT; подключение к БД внутри гостя'),('Сервер в pgAdmin',p['server']),('Хост и порт',f"127.0.0.1:{p['port']}"),('БД',p['database']),
        ('Таблица','public.clients'),('Пользователь Windows',p['os_user']),('Рабочая папка',p['work_dir']),('DB_HOME',p['db_home']),
        ('Каталог на рабочем столе',p['reports']),('Результат сканирования',p['scan']),('Каталог архива',f'C:\\PM02\\v{xy}')]
    intro=f'''<div class="comparison"><div><strong>Индивидуальная работа — {escape(p['subject'])}</strong><p>{escape(p['context'])}. Использовать собственные параметры и записи ниже.</p></div><div><strong>Образец — учебный центр «Меридиан»</strong><p>Показывает способ выполнения. Номер 00, порт 5540 и записи образца не являются ответами этой области.</p></div></div>'''
    branches=f'<div class="branches"><div><strong>ВМ ещё нет</strong><p>Открыть <a href="{prefix}guide.html#prepare">подготовку среды</a>, создать ВМ с параметрами ниже и установить Windows.</p></div><div><strong>ВМ уже сохранена</strong><p>Проверить имя гостя, ресурсы и исходный снимок. Использовать существующую ВМ, если она соответствует этому паспорту.</p></div></div>'
    html=intro+route_card('1','Подготовить индивидуальную среду',branches+f'<p>После входа в гостевую Windows скачать <a href="{prefix}downloads/pm02-v{xy}.zip">индивидуальный комплект области {xy}</a> и распаковать в каталог из паспорта. Полный порядок действий приведён в <a href="{prefix}guide.html">методических рекомендациях</a>.</p>'+table(values[:6]),
        '<p><strong>Перед следующим этапом:</strong> сверить номер области, имя гостя и порт. ВМ ещё не существует — создать её по началу методики; ВМ сохранена — проверить паспорт и исходный снимок, повторно не создавать.</p>')
    html+=route_card('1','Паспорт стенда: продолжение подготовки',table(values[6:]),'<p><strong>Проверить:</strong> имена пользователя и каталогов относятся к назначенному номеру. Параметры профиля будут настроены на этапе 3; сейчас их нужно сохранить как исходные требования.</p>')
    html+=route_card('2','Развернуть СУБД и проверить собственные записи',f'<p>Установить PostgreSQL 17 и клиенты, зарегистрировать {p["server"]}, создать {p["database"]} и clients. Назначить пять ролей по общему заданию. Импортировать clients.csv ровно один раз. Приведённые id соответствуют первому импорту в пустую таблицу.</p>'+table([(i+1,r['name'],r['email'],r['reg_date']) for i,r in enumerate(p['clients'])],('id','name','email','reg_date')),
        f'<p><strong>Проверить:</strong> {len(p["clients"])} исходных записей, значения всех полей и контрольный email <code>{p["clients"][-1]["email"]}</code>. Под каждой ролью подтвердить разрешённую и запрещённую операции; изменения откатить.</p>')
    html+=route_card('3','Настроить профиль и доступ ОС',f'<p>Настроить {p["os_user"]}, рабочую папку {p["work_dir"]}, DB_HOME и каталог {p["reports"]} на рабочем столе. Отдельно создать Windows client03. Сохранить снимок PM02-{xy}-configured.</p>',
        '<p><strong>Проверить:</strong> DB_HOME в новом окне; Administrators — F, client03 — RX; чтение разрешено, запись отклонена.</p>')
    html+=route_card('4','Выполнить единую диагностику',f'<p>Сохранить паспорт, события за 48 часов, анализ трёх элементов автозагрузки и новое сканирование в {p["scan"]}. Измерить CPU, RAM, диск, сеть и приоритеты двух–трёх процессов. Учебное досье подготовить через Prepare-Case.ps1.</p>',
        '<p><strong>Проверить:</strong> события ОС и учебные PM02Lab различены; сканирование действительно завершено после нового запуска.</p>')
    html+=route_card('5',title,f'<p>{escape(desc)}</p><p>Использовать client-connection.json и clients.csv этой области. Способ проверки раскрыт в <a href="{prefix}reference.html#cases">индивидуальных случаях</a>.</p>',
        '<p><strong>Сохранить:</strong> исходное состояние, ожидание, фактический результат, обоснованное действие и проверку после изменения.</p>')
    html+=route_card('6','Подготовить отчёт и сохранить результат',f'<p>Представить «Отчет о выполнении.docx» с блоками СУБД/ОС и диагностики, clients_{xy}.sql, заполненные протоколы и собственные снимки по <a href="{prefix}guide.html#submission">порядку сдачи</a>. Восстановление файлов выполнить отдельно, если назначено.</p>',
        f'<p><strong>Проверить:</strong> область {xy}, собственные данные и ссылка на репозиторий согласованы. Пароли и диски ВМ в сдачу не включены.</p>')
    return html

def build():
    with zipfile.ZipFile(ROOT/'downloads/sample-results-00.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for file in sorted((ROOT/'content/sample-results').glob('*')):
            if file.is_file():
                entry=zipfile.ZipInfo(file.name,date_time=(2026,11,3,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(entry,file.read_bytes())
    write('styles.css',(ROOT/'content/materials.css').read_text(encoding='utf-8'))
    course_title=(ROOT/'content/assignment.md').read_text(encoding='utf-8').splitlines()[0].removeprefix('# ')
    if len(AREAS)!=30 or len({a['variant'] for a in AREAS})!=30: raise ValueError('Expected 30 distinct areas')
    profiles=[profile(a) for a in AREAS]
    demo=profile({'variant':'00','subject':'Учебный центр «Меридиан»','context':'Рабочие места администраторов и учёт учебных клиентов'})
    for p in [demo]+profiles: pack(p)
    for source,out,pdf in [('assignment.md','index.html','assignment.pdf'),('method.md','guide.html','assignment.pdf'),('reference.md','reference.html',None)]:
        title,body=render_document(source)
        if source=='assignment.md': body+='<div class="next"><a class="button dark" href="files.html">Далее: файлы для работы</a></div>'
        write(out,shell(title,body,subtitle=course_title if source=='method.md' else '',pdf=pdf))
    _,assignment_body=render_document('assignment.md')
    assignment_body=assignment_body.replace('id="step-','id="assignment-step-').replace('id="section-','id="assignment-section-').replace('href="#section-','href="#assignment-section-')
    _,files_body=render_document('files.md')
    files_body=files_body.replace('id="step-','id="files-step-')
    _,method_body=render_document('method.md')
    _,reference_body=render_document('reference.md')
    reference_body=reference_body.replace('id="step-','id="reference-step-')
    book='<nav class="contents" aria-label="Разделы методических рекомендаций"><a href="#book-assignment">1. Общее задание</a><a href="#book-files">2. Файлы для работы</a><a href="#book-method">3. Выполнение на образце</a><a href="#book-reference">4. Дополнительные случаи</a></nav>'
    for sid,title,body in [('book-assignment','1. Общее задание',assignment_body),('book-files','2. Файлы для работы',files_body),('book-method','3. Выполнение на образце',method_body),('book-reference','4. Дополнительные диагностические случаи',reference_body)]:
        book+=f'<article class="document-part"><h2 class="appendix-title" id="{sid}">{title}</h2>{body}</article>'
    write('guide-print.html',shell('Методические рекомендации',book,subtitle=course_title))
    write('index.htm',(ROOT/'index.html').read_text(encoding='utf-8'))
    cards=''.join(f'<a class="area-link" href="areas/{p["variant"]}.html"><span>{p["variant"]}</span><strong>{escape(p["subject"])}</strong></a>' for p in profiles)
    write('areas.html',shell('Предметные области',f'<div class="area-list">{cards}</div>',pdf='guide.pdf'))
    for p in [demo]+profiles:
        write('areas/'+p['variant']+'.html',shell(p['subject'],area_body(p),subtitle='Область '+p['variant'],prefix='../'))
    area_index='<nav class="area-index" aria-label="Предметные области">'+''.join(f'<a href="#area-{p["variant"]}">{p["variant"]}. {escape(p["subject"])}</a>' for p in profiles)+'</nav>'
    all_areas=area_index+''.join(f'<article class="area-print" id="area-{p["variant"]}"><h2>Область {p["variant"]}. {escape(p["subject"])}</h2>'+area_body(p,prefix='')+'</article>' for p in profiles)
    write('areas-print.html',shell('Предметные области',all_areas))
    links=''.join(f'<li><a href="downloads/pm02-v{p["variant"]}.zip">{p["variant"]}. {escape(p["subject"])}</a></li>' for p in profiles)
    files=route_card('1','Получить комплект собственной области',f'<p>Выбрать назначенный номер из списка этой практики. Архив содержит паспорт, исходные записи, профиль клиента, сценарии подготовки учебного случая, контрольные файлы восстановления и пустые протоколы.</p><ul class="file-list">{links}</ul>', '<p><strong>Использование:</strong> распаковать в своей ВМ перед установкой и настройкой. Это входные данные, а не готовые отчёты.</p>')
    files+=route_card('2','Открыть образец и формы протоколов','<p><a href="downloads/pm02-v00.zip">Учебный тестовый комплект образца «Меридиан»</a> показывает способ выполнения. <a href="areas/00.html">Паспорт образца</a> содержит его контрольные записи.</p><p>Папка checks в каждом архиве содержит пустые CSV-формы. Их можно открыть в табличном редакторе; результаты вносятся по собственным действиям. Чистая <a href="downloads/Отчет%20о%20выполнении.docx">форма «Отчет о выполнении.docx»</a> содержит оба блока результатов. Заполнение разобрано в конце методики. <a href="downloads/sample-results-00.zip">Результаты образца 00 для сверки</a> открываются после собственного выполнения.</p>', '<p><strong>Различить:</strong> паспорт и CSV — исходные данные; образец — объяснение; checks — заготовки; собственные отчёты — сдача.</p>')
    files+=route_card('3','Подготовить установщики',md('''- [Oracle VirtualBox](https://www.virtualbox.org/wiki/Downloads) — установить на основном компьютере до создания ВМ.
- Windows 11 x64 ISO — образ учреждения либо [официальная ознакомительная редакция](https://www.microsoft.com/en-us/evalcenter/download-windows-11-enterprise); использовать при установке гостевой ОС.
- [PostgreSQL 17.11 для Windows x64](https://get.enterprisedb.com/postgresql/postgresql-17.11-1-windows-x64.exe) — сервер, pgAdmin и командные инструменты; установить внутри ВМ.
- [DBeaver Community 26.2.4, Windows x86-64 ZIP](https://github.com/dbeaver/dbeaver/releases/download/26.2.4/dbeaver-ce-26.2.4-windows-x86_64.zip) — извлечь внутри ВМ и запустить dbeaver.exe.
- [PostgreSQL JDBC 42.7.8](https://jdbc.postgresql.org/download/postgresql-42.7.8.jar) — для подключения DBeaver, если драйвер не получен автоматически; Libraries → Add File.
- [Recuva 1.54](https://download.ccleaner.com/rcsetup154.exe) — только для дополнительного случая восстановления, устанавливается на системный диск ВМ.
'''),'<p><strong>Проверить:</strong> установщики получены от разработчиков и соответствуют x64 Windows. При занятии без интернета подготовить их заранее вместе с JDBC-драйвером; отсутствующее скачивание не подменять неработающей ссылкой.</p>')
    files+='<div class="next"><a class="button dark" href="guide.html">Далее: выполнение на образце</a></div>'
    write('files.html',shell('Файлы для работы',files))
    legacy={1:'guide.html#prepare',2:'guide.html#diagnostics',3:'reference.html#repair',4:'reference.html#maintenance',5:'guide.html#diagnostics',6:'reference.html#maintenance'}
    for old,target in legacy.items():
        write(str(old)+'.html',f'<!doctype html><html lang="ru"><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={target}"><title>ПМ.02</title><p><a href="{target}">Открыть раздел практики</a></p></html>')
    write('README.md',f'# Учебная практика ПМ.02\n\n**Настройка и обеспечение работоспособности программных и аппаратных средств устройств инфокоммуникационных систем**\n\n- [Задание]({BASE}).\n- [Предметные области и индивидуальные стенды]({BASE}areas.html).\n- [Методические рекомендации]({BASE}guide.html).\n- [Диагностические случаи]({BASE}reference.html).\n- [Методические рекомендации — PDF](downloads/assignment.pdf).\n- [Предметные области — PDF](downloads/guide.pdf).\n- [Чистая форма отчёта](downloads/Отчет%20о%20выполнении.docx).\n')
    write('content/stands.json',json.dumps([demo]+profiles,ensure_ascii=False,indent=2)+'\n')
    print('Built: 30 individual areas, demonstration pack, assignment, method and reference.')

if __name__=='__main__': build()
