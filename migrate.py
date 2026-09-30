#!/usr/bin/env python3
"""
Конвертер официального экспорта Claude в пакет для загрузки в новый аккаунт.

Что делает:
  * читает conversations.json (можно прямо из ZIP), design_chats/*.json и artifacts/;
  * сохраняет каждый чат в отдельный Markdown (дата, название, реплики «Я / Claude»);
  * раскладывает чаты по папкам проектов (config/projects.json);
  * пишет PROJECT_INSTRUCTIONS.md для каждого проекта;
  * копирует последние версии артефактов в папки проектов;
  * пишет INVENTORY.md и index.csv (какой чат куда попал и почему).

Привязки чатов к проектам в экспорте нет, поэтому проект определяется по теме:
ключевые слова из config/projects.json ищутся в названии, кратком содержании и
первых репликах. Ручные исправления: config/overrides.json {"<uuid чата>": "<key проекта>", "artifact:<название>": "<key>"}.

Запуск:
  python3 migrate.py --inputs export1.zip export2.zip ... --out out/
  python3 migrate.py --inputs ... --out out/ --sample 5   # проверка формата на 5 чатах
"""
import argparse
import ast
import csv
import io
import json
import re
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EMPTY_NOTE = ("> ⚠️ **Текст этого чата в экспорт не попал.** В экспорте есть {n} сообщений, "
              "но у всех пустое содержимое (вероятно, голосовой режим или вложения, "
              "которые экспорт не сохраняет). Восстановить содержимое из экспорта нельзя.")


# ---------------------------------------------------------------- загрузка

def load_inputs(paths):
    """Возвращает (conversations, design_chats, artifacts) из ZIP-архивов и/или папок."""
    convs, designs, arts = [], [], {}

    def handle(name, read):
        base = name.replace('\\', '/')
        if base.endswith('conversations.json'):
            convs.extend(json.loads(read()))
        elif '/design_chats/' in '/' + base and base.endswith('.json'):
            designs.append(json.loads(read()))
        elif '/artifacts/' in '/' + base:
            arts[base[base.index('artifacts/'):]] = read

    for p in map(Path, paths):
        if p.suffix == '.zip':
            z = zipfile.ZipFile(p)
            for n in z.namelist():
                if not n.endswith('/'):
                    handle(n, lambda n=n, z=z: z.read(n))
        elif p.is_dir():
            for f in p.rglob('*'):
                if f.is_file():
                    handle(str(f.relative_to(p)), f.read_bytes)
        elif p.name.endswith('.json'):
            handle(p.name, p.read_bytes)
    return convs, designs, arts


def chat_text(c):
    return ''.join(x.get('text') or '' for m in c['chat_messages']
                   for x in m.get('content', []) if x.get('type') == 'text')


# ---------------------------------------------------------------- классификация

def classify(title, summary, body, projects, min_score=2):
    title_l, summary_l, body_l = title.lower(), (summary or '').lower(), body.lower()
    scores = Counter()
    hits = defaultdict(set)
    for p in projects:
        for kw in p['keywords']:
            rx = re.compile(r'(?<!\w)' + re.escape(kw.strip()))
            s = 4 * len(rx.findall(title_l)) + min(len(rx.findall(summary_l)), 3) + min(len(rx.findall(body_l)), 2)
            if s:
                scores[p['key']] += s
                hits[p['key']].add(kw.strip())
    if not scores:
        return 'none', 0, []
    key, s = scores.most_common(1)[0]
    if s < min_score:
        return 'none', s, sorted(hits[key])
    return key, s, sorted(hits[key])


# ---------------------------------------------------------------- Markdown

def slug(s, n=60):
    s = re.sub(r'[\\/:*?"<>|\n\r\t]+', ' ', s or '').strip()
    s = re.sub(r'\s+', '_', s)
    return (s[:n].rstrip('_.') or 'без_названия')


def fmt_ts(ts):
    return (ts or '')[:16].replace('T', ' ')


def render_message(m):
    who = '🧑 Я' if m['sender'] == 'human' else '🤖 Claude'
    parts = []
    for x in m.get('content', []):
        t = x.get('type')
        if t == 'text' and (x.get('text') or '').strip():
            parts.append(x['text'].strip())
        elif t == 'tool_use':
            label = (x.get('message') or '').strip()
            parts.append(f"> 🔧 *{x.get('name')}*" + (f" — {label}" if label else ''))
    for a in m.get('attachments') or []:
        name = a.get('file_name') or 'вложение'
        ec = (a.get('extracted_content') or '').strip()
        if ec:
            parts.append(f"<details><summary>📎 {name} ({a.get('file_size', '?')} байт)</summary>\n\n"
                         f"```text\n{ec.replace('```', 'ʼʼʼ')}\n```\n</details>")
        else:
            parts.append(f"> 📎 {name} — содержимое в экспорт не включено")
    for f in m.get('files') or []:
        parts.append(f"> 📎 файл {f.get('file_name') or f.get('file_uuid')} — сам файл в экспорт не включён")
    if not parts:
        return None
    return f"### {who} · {fmt_ts(m.get('created_at'))}\n\n" + '\n\n'.join(parts)


def render_chat(c, proj, score, hits):
    msgs = [r for r in (render_message(m) for m in c['chat_messages']) if r]
    empty = not chat_text(c).strip()
    head = [f"# {c.get('name') or 'Без названия'}", '',
            f"- **Создан:** {fmt_ts(c['created_at'])} UTC",
            f"- **Обновлён:** {fmt_ts(c.get('updated_at'))} UTC",
            f"- **Сообщений в экспорте:** {len(c['chat_messages'])}",
            f"- **Проект:** {proj['name']}" + (
                f" *(определён по теме, совпадения: {', '.join(hits[:8])})*" if proj['key'] != 'none'
                else ' *(тема не распознана)*'),
            f"- **UUID:** `{c['uuid']}`", '']
    if (c.get('summary') or '').strip():
        head += ['## Краткое содержание (из экспорта)', '', c['summary'].strip(), '']
    head += ['## Переписка', '']
    if empty:
        head += [EMPTY_NOTE.format(n=len(c['chat_messages'])), '']
    return '\n'.join(head) + '\n\n---\n\n'.join(msgs) + '\n', empty


def design_to_chat(d):
    """design_chats/*.json -> формат conversations.json."""
    msgs = []
    for m in d.get('messages', []):
        raw = m.get('content')
        text = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
        try:
            obj = ast.literal_eval(text) if text.strip().startswith('{') else None
        except Exception:
            obj = None
        if isinstance(obj, dict):
            if obj.get('kind') == 'question-record':
                continue
            inner = obj.get('content') or obj.get('text') or ''
            if not isinstance(inner, str):
                inner = ''
            if obj.get('attachments') and not inner:
                continue  # служебные инструкции дизайн-режима
            text = inner
        if not text.strip():
            continue
        msgs.append({'sender': 'human' if m.get('role') == 'user' else 'assistant',
                     'created_at': m.get('created_at'),
                     'content': [{'type': 'text', 'text': text}], 'attachments': [], 'files': []})
    return {'uuid': d['uuid'], 'name': '[Дизайн] ' + (d.get('title') or ''),
            'summary': '', 'created_at': d['created_at'], 'updated_at': d.get('updated_at'),
            'chat_messages': msgs}


def instructions_md(p):
    out = [f"# {p['name']} — инструкции проекта", '',
           f"**Описание:** {p['description']}", '',
           f"**Статус на 25.08.2026:** {p['status_25aug']}", '',
           f"**Источник:** {p['source']}", '']
    if p['instructions']:
        out += ['## Текст для поля «Инструкции» проекта', '', '```text', p['instructions'], '```', '']
    else:
        out += ['## Текст для поля «Инструкции» проекта', '',
                '> В экспорте готового текста инструкций для этого проекта нет.', '']
    return '\n'.join(out)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--inputs', nargs='+', required=True, help='ZIP-архивы экспорта или распакованные папки')
    ap.add_argument('--out', default='out')
    ap.add_argument('--config', default=str(HERE / 'config' / 'projects.json'))
    ap.add_argument('--overrides', default=str(HERE / 'config' / 'overrides.json'))
    ap.add_argument('--sample', type=int, default=0, help='обработать только N чатов (проверка формата)')
    a = ap.parse_args()

    projects = json.load(open(a.config, encoding='utf-8'))
    by_key = {p['key']: p for p in projects}
    overrides = json.load(open(a.overrides, encoding='utf-8')) if Path(a.overrides).exists() else {}

    convs, designs, arts = load_inputs(a.inputs)
    convs = convs + [design_to_chat(d) for d in designs]
    convs.sort(key=lambda c: c['created_at'])
    if a.sample:
        convs = convs[:a.sample]

    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for p in projects:
        (out / p['folder'] / 'чаты').mkdir(parents=True)
        (out / p['folder'] / 'PROJECT_INSTRUCTIONS.md').write_text(instructions_md(p), encoding='utf-8')

    rows, used = [], set()
    for c in convs:
        first = ' '.join(x.get('text') or '' for m in c['chat_messages'][:6] if m['sender'] == 'human'
                         for x in m.get('content', []) if x.get('type') == 'text')
        if c['uuid'] in overrides:
            key, score, hits = overrides[c['uuid']], 99, ['ручная привязка']
        else:
            key, score, hits = classify(c.get('name') or '', c.get('summary'), first, projects)
        p = by_key[key]
        md, empty = render_chat(c, p, score, hits)
        fn = f"{c['created_at'][:10]}_{slug(c.get('name'))}"
        while fn in used:
            fn += '_'
        used.add(fn)
        path = out / p['folder'] / 'чаты' / (fn + '.md')
        path.write_text(md, encoding='utf-8')
        rows.append(dict(date=c['created_at'][:10], title=c.get('name') or '', project=p['name'],
                         messages=len(c['chat_messages']), chars=len(chat_text(c)),
                         empty='да' if empty else '', match=', '.join(hits[:6]),
                         file=str(path.relative_to(out)), uuid=c['uuid']))

    # артефакты: последняя (активная) версия в папку проекта
    art_rows = []
    meta = {k: v for k, v in arts.items() if k.endswith('/artifact.json')}
    for k, read in meta.items():
        d = json.loads(read())
        v = next((x for x in d['versions'] if x['id'] == d.get('active_version')), d['versions'][0])
        title = v.get('title') or d['id']
        key = overrides.get('artifact:' + title) or classify(title, v.get('description'), '', projects, min_score=1)[0]
        p = by_key[key]
        root = k.rsplit('/', 1)[0] + '/versions/' + v['id']
        dest = out / p['folder'] / 'артефакты' / slug(title)
        files = {n: r for n, r in arts.items() if n == root + '.html' or n.startswith(root + '/')}
        for n, r in files.items():
            rel = 'index.html' if n.endswith('.html') and n == root + '.html' else n[len(root) + 1:]
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            (dest / rel).write_bytes(r())
        art_rows.append((title, p['name'], v.get('created_at', '')[:10], len(d['versions'])))

    with open(out / 'index.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    per = Counter(r['project'] for r in rows)
    inv = ['# Инвентарь экспорта', '',
           f"Всего чатов: **{len(rows)}** · пустых в экспорте: **{sum(1 for r in rows if r['empty'])}** · "
           f"сообщений: **{sum(r['messages'] for r in rows)}** · артефактов: **{len(art_rows)}**", '',
           '> Привязки чатов к проектам в экспорте нет — проект определён по теме (ключевые слова). '
           'Колонка «совпадения» показывает, по каким словам.', '',
           '## Чатов по проектам', '', '| Проект | Чатов |', '|---|---|']
    inv += [f"| {p['name']} | {per.get(p['name'], 0)} |" for p in projects]
    inv += ['', '## Артефакты', '', '| Название | Проект | Дата версии | Версий |', '|---|---|---|---|']
    inv += [f"| {t} | {pn} | {dt} | {n} |" for t, pn, dt, n in sorted(art_rows, key=lambda r: r[2])]
    inv += ['', '## Все чаты', '', '| Дата | Название | Проект | Сообщ. | Символов | Пустой | Совпадения |',
            '|---|---|---|---|---|---|---|']
    inv += [f"| {r['date']} | {r['title'].replace('|', '/')} | {r['project']} | {r['messages']} | {r['chars']} | "
            f"{r['empty']} | {r['match']} |" for r in rows]
    (out / 'INVENTORY.md').write_text('\n'.join(inv) + '\n', encoding='utf-8')

    # самопроверка
    md_files = list(out.rglob('чаты/*.md'))
    blank = [f for f in md_files if f.stat().st_size < 200]
    print(f"чатов: {len(rows)}, md-файлов: {len(md_files)}, подозрительно коротких: {len(blank)}")
    for p in projects:
        print(f"  {p['folder']}: {per.get(p['name'], 0)}")
    if len(md_files) != len(rows) or blank:
        sys.exit('ПРОВЕРКА НЕ ПРОЙДЕНА')


if __name__ == '__main__':
    main()
