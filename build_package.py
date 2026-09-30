#!/usr/bin/env python3
"""
Этап 5: собирает пакет для загрузки в новый аккаунт.

  * сводит TASKS_*.md всех проектов в ALL_TASKS.md (по дате);
  * кладёт память (MEMORY_IMPORT.md) и инструкцию КАК_ЗАГРУЗИТЬ.md;
  * строит навигатор START_HERE.html в стиле старых артефактов
    (пастель, прованс/персик, красный акцент) — с кнопками «Копировать»;
  * упаковывает всё в ZIP.

Запуск (после migrate.py и выжимок KNOWLEDGE_*/TASKS_*):
  python3 build_package.py --out out/ --memory memory/MEMORY_IMPORT.md --zip Claude_перенос.zip
"""
import argparse
import html
import json
import re
import shutil
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK_RE = re.compile(r'^\s*[-*]\s*\[(\d{4}-\d{2}-\d{2}|[^\]]*)\]\s*(.+)$')


def collect_tasks(out, projects):
    rows = []
    for p in projects:
        for f in sorted((out / p['folder']).glob('TASKS_*.md')):
            for line in f.read_text(encoding='utf-8').splitlines():
                m = TASK_RE.match(line)
                if m:
                    rows.append((m.group(1), p['name'], m.group(2).strip()))
    rows.sort(key=lambda r: (r[0] if re.match(r'\d{4}', r[0]) else '9999', r[1]))
    return rows


def write_all_tasks(out, rows):
    lines = ['# Все незавершённые задачи', '',
             f'Всего: **{len(rows)}**. Задача считается незавершённой, если в экспорте нет подтверждения её выполнения — '
             'часть из них могла быть сделана вне чатов. Проверьте и вычеркните лишнее.', '',
             '| Дата | Проект | Задача |', '|---|---|---|']
    lines += [f'| {d} | {p} | {t.replace("|", "/")} |' for d, p, t in rows]
    (out / 'ALL_TASKS.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


GUIDE = """# Как перенести всё в новый аккаунт — пошагово

Время: примерно 30–40 минут. Все файлы — в этом архиве.

## Шаг 1. Память (5 минут)
1. Откройте `ПАМЯТЬ/MEMORY_IMPORT.md` и скопируйте блок кода целиком.
2. В новом аккаунте: **Настройки → Возможности (Capabilities) → Память → «Импорт памяти»**
   (если такого пункта нет — просто вставьте текст в новый чат с фразой
   «Запомни это обо мне» или используйте навык import-memory).
3. Проверьте, что память включена («Генерировать память из истории чатов» — вкл.).

## Шаг 2. Проекты (по 1–2 минуты на каждый)
Для каждой папки проекта (01…16):
1. **Проекты → Создать проект**, название — как у папки (без номера, например «Секретарь Бхимы»).
2. Откройте `PROJECT_INSTRUCTIONS.md` → скопируйте текст из блока кода → вставьте в поле
   **«Инструкции проекта»**. (То же самое можно сделать кнопкой «Копировать» в START_HERE.html.)
3. В **«Знания проекта»** загрузите:
   - `KNOWLEDGE_*.md` — обязательно (главное: состояние, решения, задачи);
   - `TASKS_*.md` — список открытых задач;
   - при желании — файлы из `чаты/` (архив переписки; загружайте самые важные,
     чтобы не забивать лимит знаний проекта).
4. Подключите Google Drive к проекту — инструкции ссылаются на папки Диска аккаунта 108i56.

Порядок: начните с **Секретаря** и **Планёрок** — это ядро.
Проекты без чатов в экспорте (Мемуары, Выбор минивэна) создайте только с инструкциями и KNOWLEDGE.

## Шаг 3. Общие задачи
`ALL_TASKS.md` загрузите в проект «Секретарь Бхимы» — это единый список хвостов по всем проектам.

## Шаг 4. Артефакты
В папках `артефакты/` — HTML-страницы из старого аккаунта (пульт, прайсы, аттестация…).
Открываются в браузере двойным щелчком. Чтобы снова опубликовать — попросите Claude
«опубликуй этот HTML как артефакт» и приложите файл.

## Что НЕ переносится (ограничения экспорта)
- 22 чата пустые в экспорте (голосовые/вложения) — их текст восстановить нельзя (есть заглушки).
- Вложенные файлы (картинки, PDF) в экспорт не входят — только извлечённый текст документов.
- Автозадачи (trig_…), коннекторы и календарные напоминания нужно заново создать в новом аккаунте.
- Привязки чатов к проектам в экспорте не было — проект определён по теме (см. INVENTORY.md).
"""

CSS = """
:root{--bg:#FBF6EF;--surface:#FFF;--surface-2:#F6EFE5;--ink:#33271F;--ink-2:#71604F;--ink-3:#95836F;
--rule:#E2D6C6;--green:#C9DBC3;--green-deep:#5C7A5E;--green-soft:#EAF1E6;--peach:#F0CDB8;--peach-soft:#FBEDE2;
--accent:#B4402F;--accent-soft:#F6E1DA;--shadow:0 1px 2px rgba(80,58,40,.06),0 8px 24px rgba(80,58,40,.05)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#1A1512;--surface:#231D19;--surface-2:#2B2420;
--ink:#F0E7DB;--ink-2:#B3A190;--ink-3:#8B7A69;--rule:#39312B;--green:#4E6753;--green-deep:#9CBCA1;--green-soft:#26302A;
--peach:#6E4E3D;--peach-soft:#33251E;--accent:#E3775F;--accent-soft:#3B2620;--shadow:0 1px 2px rgba(0,0,0,.4)}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Golos Text","Segoe UI",system-ui,sans-serif;font-size:16px;line-height:1.6}
.wrap{max-width:980px;margin:0 auto;padding:0 16px 96px}
header{padding:56px 0 32px;border-bottom:1px solid var(--rule)}
.eyebrow{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin:0 0 16px}
h1,h2{font-family:"Cormorant Garamond",Georgia,serif;font-weight:600}
h1{font-size:clamp(38px,7vw,64px);line-height:1.03;margin:0 0 18px}
h2{font-size:30px;margin:0 0 8px}
.lede,.sub{color:var(--ink-2);max-width:64ch}
section{padding:40px 0;border-bottom:1px solid var(--rule)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:28px}
.stat{background:var(--surface);border:1px solid var(--rule);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow)}
.stat b{display:block;font-size:30px;font-family:"Cormorant Garamond",Georgia,serif}
.stat span{color:var(--ink-3);font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:14px}
.card{background:var(--surface);border:1px solid var(--rule);border-radius:14px;padding:18px;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:8px}
.card:nth-child(odd){background:linear-gradient(0deg,var(--surface),var(--green-soft))}
.card:nth-child(even){background:linear-gradient(0deg,var(--surface),var(--peach-soft))}
.num{font-family:"IBM Plex Mono",monospace;color:var(--accent);font-size:13px;letter-spacing:.08em}
.card h3{margin:0;font-size:19px}
.card p{margin:0;color:var(--ink-2);font-size:14.5px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{font-size:12.5px;font-weight:600;padding:2px 10px;border-radius:20px;background:var(--surface-2);color:var(--ink-2)}
.chip.red{background:var(--accent-soft);color:var(--accent)}
.chip.green{background:var(--green-soft);color:var(--green-deep)}
details{border-top:1px dashed var(--rule);padding-top:8px}
summary{cursor:pointer;color:var(--accent);font-weight:600;font-size:14px}
pre{white-space:pre-wrap;word-break:break-word;background:var(--surface-2);border-radius:10px;padding:12px;font-size:13px;max-height:420px;overflow:auto}
button{font:inherit;font-size:13px;font-weight:600;border:1px solid var(--accent);color:var(--accent);background:transparent;border-radius:20px;padding:4px 14px;cursor:pointer}
button:hover{background:var(--accent-soft)}
.links a{color:var(--green-deep);font-size:14px;margin-right:12px}
table{width:100%;border-collapse:collapse;font-size:14px;background:var(--surface);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--rule);vertical-align:top}
th{background:var(--green-soft);color:var(--green-deep);font-weight:600}
tr:nth-child(even) td{background:var(--peach-soft)}
.tablewrap{overflow-x:auto}
input[type=search]{width:100%;padding:10px 14px;border:1px solid var(--rule);border-radius:10px;background:var(--surface);color:var(--ink);font:inherit;margin-bottom:12px}
ol li{margin-bottom:6px}
"""


def e(s):
    return html.escape(s or '')


def build_html(out, projects, tasks, memory_text, inv_counts):
    cards = []
    for p in projects:
        folder = out / p['folder']
        chats = len(list((folder / 'чаты').glob('*.md')))
        arts = len(list((folder / 'артефакты').glob('*'))) if (folder / 'артефакты').exists() else 0
        kn = sorted(folder.glob('KNOWLEDGE_*.md'))
        ntask = sum(1 for t in tasks if t[1] == p['name'])
        links = ' '.join(f'<a href="{e(p["folder"])}/{e(f.name)}">{e(f.name)}</a>' for f in kn)
        links += f' <a href="{e(p["folder"])}/PROJECT_INSTRUCTIONS.md">PROJECT_INSTRUCTIONS.md</a>'
        instr = ''
        if p['instructions']:
            instr = (f'<details><summary>Инструкции проекта</summary>'
                     f'<button onclick="cp(this)">Копировать</button><pre>{e(p["instructions"])}</pre></details>')
        kn_block = ''
        if kn:
            kn_block = (f'<details><summary>Выжимка знаний</summary><pre>{e(kn[0].read_text(encoding="utf-8"))}</pre></details>')
        cards.append(f'''<div class="card"><div class="num">{e(p["folder"].split(" ")[0])}</div>
<h3>{e(p["name"])}</h3><p>{e(p["description"])}</p>
<div class="chips"><span class="chip green">чатов: {chats}</span><span class="chip">артефактов: {arts}</span>
<span class="chip red">открытых задач: {ntask}</span></div>
<div class="links">{links}</div>{instr}{kn_block}</div>''')
    trs = '\n'.join(f'<tr><td>{e(d)}</td><td>{e(p)}</td><td>{e(t)}</td></tr>' for d, p, t in tasks)
    mem = re.search(r'```\n(.*?)```', memory_text, re.S)
    mem = mem.group(1) if mem else memory_text
    steps = ''.join(f'<li>{s}</li>' for s in [
        '<b>Память:</b> скопируйте блок ниже → Настройки → Возможности → Память → «Импорт памяти».',
        '<b>Проекты:</b> для каждой карточки создайте проект с тем же названием и нажмите «Копировать» в «Инструкции проекта».',
        '<b>Знания проекта:</b> загрузите KNOWLEDGE_*.md и TASKS_*.md из папки проекта; важные чаты — по желанию.',
        '<b>ALL_TASKS.md</b> загрузите в «Секретарь Бхимы» — единый список хвостов.',
        '<b>Подключите Google Drive</b> и заново создайте автозадачи (они не переносятся экспортом).'])
    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Перенос в новый аккаунт</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600&family=Golos+Text:wght@400;600&family=IBM+Plex+Mono&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<header><p class="eyebrow">Перенос из старого аккаунта · экспорт от 30.09.2026</p>
<h1>Всё, что было в Claude — в одном месте</h1>
<p class="lede">Проекты с готовыми инструкциями, выжимки знаний, архив всех чатов, общий список задач и память. Открывайте карточку, копируйте, загружайте.</p>
<div class="stats">
<div class="stat"><b>{inv_counts["chats"]}</b><span>чатов в архиве</span></div>
<div class="stat"><b>{len(projects) - 1}</b><span>проектов</span></div>
<div class="stat"><b>{len(tasks)}</b><span>открытых задач</span></div>
<div class="stat"><b>{inv_counts["empty"]}</b><span>пустых в экспорте</span></div></div></header>
<section><h2>Порядок действий</h2><ol>{steps}</ol>
<p class="sub">Подробно — в файле <a href="КАК_ЗАГРУЗИТЬ.md">КАК_ЗАГРУЗИТЬ.md</a>. Полный список чатов и куда они разложены — <a href="INVENTORY.md">INVENTORY.md</a>.</p></section>
<section><h2>Проекты</h2><p class="sub">Привязки чатов к проектам в экспорте не было — разложено по теме. Инструкции — из вашей «Пересборки проектов» от 25.08.2026.</p>
<div class="grid">{"".join(cards)}</div></section>
<section><h2>Память</h2><p class="sub">Чистый список фактов для встроенного импорта памяти.</p>
<button onclick="cp(this)">Копировать</button><pre>{e(mem)}</pre></section>
<section><h2>Все открытые задачи</h2><input type="search" placeholder="Поиск по задачам…" oninput="flt(this.value)">
<div class="tablewrap"><table id="t"><thead><tr><th>Дата</th><th>Проект</th><th>Задача</th></tr></thead><tbody>{trs}</tbody></table></div></section>
</div><script>
function cp(b){{const t=b.nextElementSibling.innerText;navigator.clipboard.writeText(t).then(()=>{{b.textContent='Скопировано ✓';setTimeout(()=>b.textContent='Копировать',1500)}})}}
function flt(q){{q=q.toLowerCase();document.querySelectorAll('#t tbody tr').forEach(r=>r.hidden=!r.innerText.toLowerCase().includes(q))}}
</script></body></html>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='out')
    ap.add_argument('--memory', default=str(HERE / 'memory' / 'MEMORY_IMPORT.md'))
    ap.add_argument('--config', default=str(HERE / 'config' / 'projects.json'))
    ap.add_argument('--zip', default='Claude_перенос.zip')
    a = ap.parse_args()
    out = Path(a.out)
    projects = json.load(open(a.config, encoding='utf-8'))

    tasks = collect_tasks(out, projects)
    write_all_tasks(out, tasks)
    (out / 'ПАМЯТЬ').mkdir(exist_ok=True)
    shutil.copy(a.memory, out / 'ПАМЯТЬ' / 'MEMORY_IMPORT.md')
    (out / 'КАК_ЗАГРУЗИТЬ.md').write_text(GUIDE, encoding='utf-8')

    inv = (out / 'INVENTORY.md').read_text(encoding='utf-8')
    counts = {'chats': int(re.search(r'Всего чатов: \*\*(\d+)', inv).group(1)),
              'empty': int(re.search(r'пустых в экспорте: \*\*(\d+)', inv).group(1))}
    memory_text = Path(a.memory).read_text(encoding='utf-8')
    (out / 'START_HERE.html').write_text(build_html(out, projects, tasks, memory_text, counts), encoding='utf-8')

    with zipfile.ZipFile(a.zip, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.rglob('*')):
            if f.is_file():
                z.write(f, Path('Claude_перенос') / f.relative_to(out))
    print(f'задач: {len(tasks)}; архив: {a.zip} ({Path(a.zip).stat().st_size // 1024} КБ)')


if __name__ == '__main__':
    main()
