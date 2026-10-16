"""Нормализация сохранённых текстов; содержание вакансий не переписывается."""
import argparse
from collections import Counter
from datetime import datetime
from html import unescape
import hashlib
import json
from pathlib import Path
import re
import zipfile
from bs4 import BeautifulSoup, NavigableString

ROOT = Path(".github/project_vacancies_export")
DATA = ROOT / "data"
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
def read(path):
    return json.loads(path.read_text(encoding="utf-8"))
def clean(s):
    return re.sub(r"[ \t\u00a0\u200b-\u200f\ufeff]+", " ", unescape(s)).strip()
def plain_html(s):
    return clean(BeautifulSoup(s, "html.parser").get_text(" ", strip=True))
def html_lines(s):
    if not re.search(r"</?(?:p|br|li|ul|ol|b|strong|h[1-6]|div|a)\b", s, re.I):
        return unescape(s.replace("\r\n", "\n").replace("\r", "\n"))
    soup = BeautifulSoup(s, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()
    for node in list(soup.find_all(["b", "strong"])):
        text = node.get_text(" ", strip=True)
        alone = node.parent.name in ("p", "[document]", "div") and (
            node.parent.name == "[document]" or node.parent.get_text(" ", strip=True) == text or
            (getattr(node.next_sibling, "name", None) == "br"))
        node.replace_with(NavigableString("\n@@SUB:" + text + "@@\n" if alone else "**" + text + "**"))
    for node in list(soup.find_all(re.compile(r"^h[1-6]$"))):
        node.replace_with(NavigableString("\n@@SUB:" + node.get_text(" ", strip=True) + "@@\n"))
    for node in list(soup.find_all("li")):
        if node.find_parent("li"):
            continue
        node.replace_with(NavigableString("\n• " + node.get_text(" ", strip=True) + "\n"))
    for node in list(soup.find_all("br")):
        node.replace_with("\n")
    for node in list(soup.find_all(["p","div","ul","ol"])):
        node.insert_before("\n")
        node.insert_after("\n")
    return unescape(soup.get_text("", strip=False))

# Заголовки разделов работодателей, прочитанные в исходном пуле.
LABELS = {
"duties": ["Предстоит", "Задачи, которые могут стать твоими", "Основные обязанности", "Ваши обязанности", "Наши менеджеры строительных проектов", "Чем предстоит заниматься", "Чем нужно заниматься", "Чем заниматься", "Какие задачи вас ждут", "Что предстоит делать", "Что нужно будет делать", "Что нужно делать", "Вам предстоит", "Тебе предстоит", "Вы будете", "Задачи на этой позиции", "Ваши задачи", "Задачи", "Обязанности"],
"requirements": ["Мы ожидаем, что вы", "Мы ждем, что ты", "Мы ждём, что ты", "Мы видим на этой позиции человека, который", "Что мы ждем от кандидата", "Что мы ждём от кандидата", "Мы хотим видеть у вас", "Мы ждем, что вы", "Мы ждём, что вы", "Что для нас важно", "Для нас важно", "Для нас важны", "Мы ожидаем", "Мы ожидаем от вас", "Наши ожидания", "Нам важно", "Требования к кандидату", "Требования", "Мы ждем", "Мы ждём", "Что важно для нас", "Что мы ожидаем"],
"nice": ["Будет вашим весомым преимуществом", "Будет большим плюсом", "Будет вашим преимуществом", "Будет преимуществом", "Будет здорово, если вы", "Будет здорово, если", "Будет плюсом, если", "Будет плюсом", "Будет здорово", "Желательно", "Плюсом будет", "Приветствуется"],
"excluded": ["Мы готовы предложить", "Почему у нас хорошо", "Работа у нас — это", "Работа у нас - это", "Мы предлагаем", "Что мы предлагаем", "Что предлагаем", "Мы предлагаем вам", "Наши условия", "Условия", "Условия работы", "Что вас ждет", "Что вас ждёт", "Что мы предлагаем взамен"],
}
lookup = {clean(v).lower(): k for k, vals in LABELS.items() for v in vals}
patterns = []
for label in sorted(lookup, key=len, reverse=True):
    literal = re.escape(label).replace(r"\ ", r"\s+")
    strict = len(label.split()) < 2 or lookup[label] == "nice"
    suffix = r"(?=\s*:|\s*(?:\n|$)|@@)" if strict else r"(?!\w)"
    patterns.append(literal + suffix)
label_pattern = re.compile(r"(?<![\w-])(" + "|".join(patterns) + r")\s*:?", re.I)
def split_sections(s, default="intro", markers=True):
    text = html_lines(s)
    text = re.sub(r"(?m)^[ \t]*#{1,6}[ \t]+(.+?)[ \t]*$",
                  lambda m: "\n@@SUB:" + m.group(1).strip().strip("*_").strip() + "@@\n", text)
    text = re.sub(r"(?m)^[ \t]*(\*\*|__|_|\*)([^\n]+?)\1[ \t]*$",
                  lambda m: "\n@@SUB:" + m.group(2).strip() + "@@\n", text)
    matches = list(label_pattern.finditer(text)) if markers else []
    spans, cursor, current = [], 0, default
    for m in matches:
        # Подзаголовок с данными не должен терять обрамляющий служебный маркер.
        start, end = m.start(), m.end()
        label = re.sub(r"\s+", " ", clean(m.group(1))).lower()
        prefix = text[text.rfind("\n",0,start)+1:start].strip(" *_#")
        is_standalone = prefix in ("", "@@SUB:")
        if lookup[label] == "nice" and not is_standalone and not m.group().rstrip().endswith(":"):
            continue
        if len(label.split()) < 2 and not is_standalone and not m.group(1)[0].isupper():
            continue
        pre = text[max(0,start-6):start]
        if pre.endswith("@@SUB:"):
            start -= 6
            if text[end:end+2] == "@@":
                end += 2
        if start < cursor:
            continue
        if text[cursor:start].strip():
            spans.append((current, text[cursor:start]))
        current = lookup[re.sub(r"\s+", " ", clean(m.group(1))).lower()]
        cursor = end
    if text[cursor:].strip():
        spans.append((current, text[cursor:]))
    return spans

rows = []
for file in sorted(DATA.glob("snapshot_[0-9]*.json")):
    rows.extend(read(file)["rows"])
selection = read(ROOT / "selection.json")
chosen = set(selection["selected_ids"])
assert len(chosen) == len(selection["selected_ids"])
rows = [r for r in rows if str(r["id"]) in chosen]
assert {str(r["id"]) for r in rows} == chosen
anchors = read(ROOT / "anchors.json")
fixes = read(ROOT / "normalization_overrides.json") if (ROOT / "normalization_overrides.json").exists() else {}
def sources(row):
    ident = str(row["id"])
    native = row.get("native_sections") or {}
    desc = row.get("description") or ""
    if ident in anchors:
        result = []
        used = []
        sections = {"short_summary":"intro","duties":"duties","key_qualifications":"requirements","additional_requirements":"nice","conditions":"excluded"}
        for field, fragment in anchors[ident].items():
            pos = desc.find(fragment)
            assert pos >= 0, (ident, field, "Якорь отсутствует в свежем тексте")
            result.append((pos, sections[field], desc[pos:pos+len(fragment)]))
            used.append((pos,pos+len(fragment)))
        return [(section, text, False) for _,section,text in sorted(result)]
    if "duties" in native and "requirements" in native:
        intro = native.get("introduction", "")
        if not intro and native.get("description"):
            prefix = split_sections(native["description"])
            intro = "\n".join(text for sec,text in prefix if sec == "intro")
        result = [("intro",intro,False),("duties",native["duties"],True),("requirements",native["requirements"],True)]
        return result
    if "html_sections.Обязанности" in native:
        return [("intro",native.get("html_sections.Описание",""),False),
                ("duties",native["html_sections.Обязанности"],True),
                ("requirements",native.get("html_sections.Требования",""),True)]
    if row["company"] in ("МТС","МТС Банк","MWS.AI"):
        parts = [p for p in re.split(r"\n\s*\n",desc.replace("\r","")) if p.strip()]
        assert len(parts) >= 3, ident
        intro = "\n\n".join(parts[:-3])
        d,r = parts[-3],parts[-2]
        if ident in ("mts_714508077801406565","mts_714508077826572383"):
            d,r = r,d
        return [("intro",intro,False),("duties",d,True),("requirements",r,True)]
    return [("intro",native.get("json_ld.description") or desc,True)]

def items(text, section):
    text = text.replace("\r","")
    paragraphs = [x.strip() for x in text.split("\n") if x.strip() and x.strip() not in ("**",":","@@")]
    if len(paragraphs) <= 1 and section != "intro":
        paragraphs = [x.strip() for x in re.split(r"(?:\s*[•●▪]\s*|;\s*)", text) if x.strip()]
    if section != "intro":
        expanded = []
        for part in paragraphs:
            expanded.extend(re.split(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z])",part) if len(paragraphs)==1 else [part])
        paragraphs = expanded
    output = []
    pending = None
    for line in paragraphs:
        line = clean(re.sub(r"^\s*(?:[-*•●▪]|\d+[.)])\s+", "", line))
        if not line or re.fullmatch(r"[#*: _]+", line):
            continue
        sub = re.fullmatch(r"@@SUB:(.*?)@@",line)
        if sub:
            if pending:
                output.append(pending)
            pending = {"text":"", "subheading": clean(sub.group(1))}
            continue
        if line.startswith("@@SUB:"):
            m = re.match(r"@@SUB:(.*?)@@\s*(.*)",line)
            if m:
                if pending:
                    output.append(pending)
                pending = {"text":clean(m.group(2)), "subheading":clean(m.group(1))}
                continue
        if pending:
            pending["text"] += ("\n" if pending["text"] else "") + line
        else:
            output.append({"text":line})
    if pending:
        output.append(pending)
    return output

records, candidates, unresolved, section_counts = [],[],[],Counter()
for row in rows:
    ident = str(row["id"])
    parts = {"intro":[], "duties":[], "requirements":[], "nice":[]}
    recipe = sources(row)
    override = fixes.get("sources",{}).get(ident)
    if override:
        recipe = [(p["section"],p["text"],p.get("markers",False)) for p in override]
        for section,text,_ in recipe:
            assert text in row["description"] or any(text in v for v in (row.get("native_sections") or {}).values()), (ident,"Неисходный текст в ручном плане")
    for default,text,markers in recipe:
        for phrase in fixes.get("break_before",{}).get(ident,[]):
            text = text.replace(phrase,"\n"+phrase)
        if row["company"] == "Т-Банк" and default != "intro":
            starts = ("У вас","Имеете","Знаете","Умеете","Следите","Интересуетесь","Будет",
                      "Управлять","Определять","Вести","Вводить","Реализовывать","Представлять",
                      "Презентовать","Взаимодействовать","Готовить","Выявлять","Разрабатывать",
                      "Формировать","Координировать","Отслеживать")
            joined=[]
            for line in text.splitlines():
                line=clean(line)
                if not line:
                    continue
                if joined and not line.startswith(starts):
                    joined[-1]+=" "+line
                else:
                    joined.append(line)
            text="\n".join(joined)
        elif row["company"] == "Т-Банк" and default == "intro":
            text=" ".join(text.split())
        elif ident == "lamoda_3080" and default == "requirements":
            starts=("Опыт","Практический","Будет","Уверенное","Высокий")
            joined=[]
            for line in text.splitlines():
                line=clean(line)
                if not line:
                    continue
                if joined and not line.startswith(starts):
                    joined[-1]+=" "+line
                else:
                    joined.append(line)
            text="\n".join(joined)
        for section,fragment in split_sections(text,default,markers):
            if section in parts:
                parts[section].extend(items(fragment,section))
    def words(sections):
        return Counter(re.findall(r"\w+", " ".join(
            item.get("subheading","")+" "+item["text"]
            for arr in sections.values() for item in arr).lower()))
    before = words(parts)
    for group in fixes.get("groups",{}).get(ident,[]):
        arr = parts[group["section"]]
        expected = group["expected"]
        positions = [i for i in range(len(arr)-len(expected)+1)
                     if [x["text"] for x in arr[i:i+len(expected)]] == expected]
        assert len(positions) == 1, (ident,"Не найдена группа",expected)
        pos = positions[0]
        if group.get("heading"):
            replacement = {"subheading":expected[0],
                           "text":" ".join(re.sub(r"^[—–-]\s*","",s) for s in expected[1:])}
        else:
            replacement = {"text":" ".join(expected)}
        arr[pos:pos+len(expected)] = [replacement]
    decisions = fixes.get("requirements_by_text",{}).get(ident,{})
    used = set()
    for index in range(len(parts["requirements"])-1,-1,-1):
        item = parts["requirements"][index]
        original = item["text"]
        decision = decisions.get(original)
        if decision is None:
            continue
        used.add(original)
        parts["requirements"].pop(index)
        if decision == "nice":
            parts["nice"].insert(0,item)
        else:
            assert not item.get("subheading"), (ident,"Уточнить разделение подзаголовка")
            fragments = decision.get("requirements",[]) + decision.get("nice",[])
            assert Counter(re.findall(r"\w+",original.lower())) == Counter(
                re.findall(r"\w+"," ".join(fragments).lower())), (ident,"Искажён текст",original)
            for fragment in reversed(decision.get("requirements",[])):
                parts["requirements"].insert(index,{"text":fragment.strip().rstrip(",;")})
            for fragment in decision.get("nice",[]):
                parts["nice"].append({"text":fragment})
    assert used == set(decisions), (ident,"Не применены ручные решения",set(decisions)-used)
    assert before == words(parts), (ident,"При переносе или группировке изменились слова")
    for section in parts:
        section_counts[section] += len(parts[section])
    for index,item in enumerate(parts["requirements"]):
        text = item.get("subheading","")+" "+item["text"]
        if re.search(r"желател|предпочт|преимущ|плюс|приветству|необязател|бонусом",text,re.I):
            reviewed = item["text"] in fixes.get("keep_requirements",{}).get(ident,[])
            candidates.append({"id":ident,"index":index,"text":text.strip(),"reviewed":reviewed})
    if not parts["duties"] or not parts["requirements"]:
        unresolved.append({"id":ident,"company":row["company"],"title":row["title"],"counts":{k:len(v) for k,v in parts.items()},"text":row["description"]})
    record = {k:row.get(k) for k in ("id","title","company","url","is_active")}
    record["sections"]=parts
    records.append(record)
for number,offset in enumerate(range(0,len(records),25),1):
    (OUT/("records_%02d.json"%number)).write_text(json.dumps(records[offset:offset+25],ensure_ascii=False,indent=2),encoding="utf-8")
(OUT/"review.json").write_text(json.dumps({"total":len(records),"candidates":candidates,"unresolved":unresolved,"section_counts":dict(section_counts)},ensure_ascii=False,indent=2),encoding="utf-8")

def bullet(item):
    title=item.get("subheading")
    body=item["text"]
    if title:
        return "- **"+title+"**"+("\n  "+body.replace("\n","\n  ") if body else "")
    return "- "+body.replace("\n","\n  ")
def markdown(record):
    state = "Активна" if record["is_active"] else "Архивная"
    text = "## "+clean(record["title"])+"\n\nКомпания: "+record["company"]+"\n\nИсточник: "+(record["url"] or "")+"\n\nID: "+str(record["id"])+" · "+state+"\n"
    for key,heading in (("intro","### Вступительный блок"),("duties","### Обязанности"),("requirements","### Требования"),("nice","#### Будет плюсом")):
        text+="\n"+heading+"\n\n"
        text+="\n".join(bullet(item) for item in record["sections"][key])+"\n"
    return text.strip()+"\n"
combined="\n\n---\n\n".join(markdown(record).strip() for record in records)+"\n"
assert combined.count("\n\n---\n\n") == len(records)-1
assert all(all(key in record["sections"] for key in ("intro","duties","requirements","nice")) for record in records)
manifest={"snapshot":read(DATA/"snapshot_meta.json"),"total":len(records),"active":sum(bool(r["is_active"]) for r in records),
          "archived":sum(not r["is_active"] for r in records),"companies":dict(Counter(r["company"] for r in records)),
          "records":[{k:r[k] for k in ("id","title","company","url","is_active")} for r in records],
          "missing_sections":[{"id":r["id"],"sections":[k for k in ("duties","requirements") if not r["sections"][k]]}
                              for r in records if not r["sections"]["duties"] or not r["sections"]["requirements"]],
          "normalization":{"manually_reviewed_clauses":sum(len(v) for v in fixes.get("requirements_by_text",{}).values()),
                           "word_conservation_check":True,"separator":"---"},
          "database_writes":0,"telegram_calls":0}
zip_path=OUT/"project_management.zip"
with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED) as z:
    z.writestr("project_management.md",combined)
    for record in records:
        z.writestr("vacancies/"+str(record["id"])+".md",markdown(record))
    z.writestr("source.json",json.dumps({"meta":manifest["snapshot"],"rows":rows},ensure_ascii=False,indent=2))
    z.writestr("index.json",json.dumps(manifest,ensure_ascii=False,indent=2))
with zipfile.ZipFile(zip_path) as z:
    assert z.testzip() is None
    assert len([name for name in z.namelist() if name.startswith("vacancies/") and name.endswith(".md")]) == len(records)
print("EXPORT="+json.dumps({"total":len(records),"active":manifest["active"],"archived":manifest["archived"],
      "candidates":len(candidates),"unresolved":len(unresolved),"section_counts":dict(section_counts),"zip_bytes":zip_path.stat().st_size},ensure_ascii=False))
