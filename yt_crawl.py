#!/usr/bin/env python3
"""MPM YouTube Monitoring - cari video YouTube untuk 3 tier keyword lewat YouTube Data API v3,
lalu buat dashboard interaktif (dashboard.html) dengan hot topic dan hot content.

  Tier 1  entitas MPM        dicari SETIAP run, urut terbaru (semua video yang menyebut MPM)
  Tier 2  istilah industri   dicari BERGILIRAN, urut tayangan terbanyak N hari terakhir (yang sedang ramai)
  Tier 3  pesaing / peer     dicari BERGILIRAN, urut tayangan terbanyak N hari terakhir

Hanya library bawaan Python (3.9+). Tidak perlu pip install.

    python yt_crawl.py                 # run biasa: tier 1 + giliran tier 2/3 sampai batas pencarian, lalu dashboard
    python yt_crawl.py --hari 7        # tier 1: hanya video 7 hari terakhir (default 30)
    python yt_crawl.py --hari-hot 7    # tier 2/3: konten terpopuler 7 hari terakhir (default 14)
    python yt_crawl.py --maks-cari 40  # pakai paling banyak 40 pencarian di run ini (default 90)
    python yt_crawl.py --tanpa-cari    # tanpa pencarian: hanya perbarui tayangan/suka video tersimpan + dashboard
    python yt_crawl.py --dashboard     # hanya buat ulang dashboard dari data yang ada (tanpa API)

Keyword dibaca dari keywords.xlsx (sheet "Keywords"); keywords.csv dipakai bila xlsx tidak ada.
Kunci API dari youtube_api_key.txt, variabel YOUTUBE_API_KEY (GitHub Secret), atau ditanyakan.

Kuota (developers.google.com/youtube/v3/determine_quota_cost, dicek 16 Okt 2026):
  search.list = bucket sendiri, 100 panggilan per hari (1 per panggilan)
  endpoint lain (videos.list, channels.list) = 10.000 unit per hari, 1 unit per panggilan (maks 50 id)
Tier 1 butuh ±21 pencarian per run; sisa jatah dipakai bergiliran untuk tier 2/3 (yang paling lama belum
dicari didahulukan; status di data/pencarian.json), jadi semua ±165 kata pencarian tercakup kira-kira tiap 2 hari.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DB = DATA / "videos.json"
KUOTA = DATA / "kuota.json"
GILIRAN = DATA / "pencarian.json"
KEY_FILE = HERE / "youtube_api_key.txt"
TEMPLATE = HERE / "dashboard_template.html"
OUT_HTML = HERE / "dashboard.html"
API = "https://www.googleapis.com/youtube/v3/"
WIB = timezone(timedelta(hours=7))
PACIFIC = timezone(timedelta(hours=-8))      # kuota YouTube direset tengah malam waktu Pasifik (perkiraan)
BATAS_CARI_HARIAN = 95                       # sisakan 5 dari 100 pencarian per hari
CTX = ssl.create_default_context()
TIER_NAMA = {1: "Tier 1 · MPM", 2: "Tier 2 · Industri", 3: "Tier 3 · Pesaing"}
YA = ("ya", "y", "yes", "true", "1")


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- konfigurasi keyword
def _read_xlsx(path: Path, sheet: str = "Keywords") -> list[list[str]]:
    """Baca satu sheet .xlsx tanpa library tambahan (teks dan angka saja)."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = None
        sheets = wb.findall("m:sheets/m:sheet", ns)
        chosen = next((s for s in sheets if s.get("name") == sheet), sheets[0] if sheets else None)
        if chosen is not None:
            rid = chosen.get(f"{{{ns['r']}}}id")
            for rel in rels:
                if rel.get("Id") == rid:
                    target = rel.get("Target").lstrip("/")
                    target = target if target.startswith("xl/") else "xl/" + target
        root = ET.fromstring(z.read(target or "xl/worksheets/sheet1.xml"))
    rows = []
    for row in root.iter(f"{{{ns['m']}}}row"):
        cells = {}
        for c in row.findall("m:c", ns):
            ref = c.get("r", "")
            col = 0
            for ch in re.match(r"[A-Z]+", ref).group(0):
                col = col * 26 + ord(ch) - 64
            t, v = c.get("t"), c.find("m:v", ns)
            if t == "s" and v is not None:
                val = shared[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(f"{{{ns['m']}}}t"))
            elif v is not None and v.text is not None:
                val = v.text
                if re.fullmatch(r"-?\d+\.0", val):
                    val = val[:-2]
            else:
                val = ""
            cells[col - 1] = val
        if cells:
            rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
    return rows


def _read_csv(path: Path) -> list[list[str]]:
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    if lines and lines[0].lower().startswith("sep="):
        lines = lines[1:]
    head = lines[0] if lines else ""
    delim = ";" if head.count(";") > head.count(",") else ","      # Excel berbahasa Indonesia menyimpan CSV dengan ';'
    return [r for r in csv.reader(lines, delimiter=delim)]


def load_keywords() -> list[dict]:
    xp, cp = HERE / "keywords.xlsx", HERE / "keywords.csv"
    rows = _read_xlsx(xp) if xp.exists() else _read_csv(cp)
    head = [h.strip().lower() for h in rows[0]]
    out = []
    for r in rows[1:]:
        d = {h: (r[i].strip() if i < len(r) and r[i] is not None else "") for i, h in enumerate(head)}
        kw = d.get("keyword", "")
        if not kw:
            continue
        tier = int(d.get("tier") or 1) if (d.get("tier") or "1").isdigit() else 1
        kel = d.get("kelompok") or d.get("grup") or "Lainnya"
        query = d.get("kata_pencarian") or kw
        aliases = [x.strip() for x in (d.get("alias") or "").split("|") if x.strip()]
        out.append(dict(tier=tier, kelompok=kel, keyword=kw, query=query, aliases=aliases,
                        kapital=(d.get("huruf_kapital") or "").lower() in YA,
                        cari=(d.get("cari_di_youtube") or "ya").lower() in YA,
                        kecuali=[x.strip() for x in (d.get("kecuali") or "").split("|") if x.strip()]))
    if not out:
        sys.exit("Tidak ada keyword di keywords.xlsx / keywords.csv.")
    return out


KEY_RX = re.compile(r"^AIza[0-9A-Za-z_\-]{35}$")      # format kunci API Google (39 karakter)


def _mask(k: str) -> str:
    return (k[:6] + "..." + k[-4:]) if len(k) > 12 else "(terlalu pendek)"


def ask_key(reason: str = "") -> str:
    """Minta kunci baru, cek formatnya, simpan ke youtube_api_key.txt."""
    if reason:
        log(reason)
    log("Cara membuat kunci ada di PANDUAN.md (langkah 1). Kunci diawali 'AIza' dan panjangnya 39 karakter.")
    for _ in range(3):
        try:
            k = input("Tempel kunci API YouTube, lalu Enter (kosongkan untuk berhenti): ")
        except EOFError:
            k = ""
        k = re.sub(r"\s+", "", k).strip("'\"")
        if not k:
            sys.exit("Dihentikan: kunci API kosong.")
        if KEY_RX.match(k):
            KEY_FILE.write_text(k, encoding="utf-8")
            log(f"Kunci {_mask(k)} disimpan di {KEY_FILE.name} (jangan dibagikan).")
            return k
        log(f"Itu bukan format kunci API Google ({len(k)} karakter, diawali '{k[:4]}'). Salin lagi dari "
            "console.cloud.google.com > APIs & Services > Credentials (kolom 'Key', tombol Show key).")
    sys.exit("Dihentikan: kunci API tidak valid.")


def api_key() -> tuple[str, str]:
    """(kunci, sumber). Urutan: youtube_api_key.txt, lalu variabel YOUTUBE_API_KEY, lalu ditanyakan."""
    import os
    if KEY_FILE.exists():
        k = re.sub(r"\s+", "", KEY_FILE.read_text(encoding="utf-8-sig")).strip("'\"")
        if k and KEY_RX.match(k):
            return k, f"file {KEY_FILE.name}"
        if k:
            return ask_key(f"Isi {KEY_FILE.name} bukan kunci API yang valid ({_mask(k)})."), f"file {KEY_FILE.name}"
    k = re.sub(r"\s+", "", os.environ.get("YOUTUBE_API_KEY", "")).lstrip("\ufeff")
    if k:
        return k, ("GitHub Secret YOUTUBE_API_KEY" if os.environ.get("GITHUB_ACTIONS") else "variabel lingkungan Windows YOUTUBE_API_KEY")
    return ask_key("Kunci API YouTube belum ada."), f"file {KEY_FILE.name}"


def checked_key() -> str:
    """Ambil kunci lalu uji dengan 1 panggilan murah (videos.list, 1 unit; tidak memakai kuota pencarian).
    Bila YouTube menolaknya, minta kunci baru (maks 2 kali)."""
    key, src = api_key()
    log(f"Memakai kunci {_mask(key)} dari {src}.")
    for attempt in range(3):
        try:
            call("videos", {"part": "id", "id": "dQw4w9WgXcQ"}, key)
            return key
        except QuotaExceeded:
            return key                     # kuota unit habis: kunci sah, pencarian punya bucket sendiri
        except ApiError as e:
            msg = str(e)
            if "accessNotConfigured" in msg or "has not been used" in msg or "is disabled" in msg:
                sys.exit("YouTube Data API v3 belum diaktifkan di project Google Cloud kunci ini.\n"
                         "Buka console.cloud.google.com > APIs & Services > Library > YouTube Data API v3 > Enable,\n"
                         "tunggu 1-2 menit, lalu jalankan lagi. (" + msg[:150] + ")")
            if not ("API key not valid" in msg or "keyInvalid" in msg or "API_KEY_INVALID" in msg
                    or "API_KEY_SERVICE_BLOCKED" in msg or "ipRefererBlocked" in msg or "forbidden" in msg):
                raise
            if attempt == 2:
                sys.exit("Kunci masih ditolak YouTube: " + msg[:200])
            if not sys.stdin or not sys.stdin.isatty():      # GitHub Actions / Task Scheduler: nobody to type a key
                where = ("Perbarui secret YOUTUBE_API_KEY di GitHub: Settings > Secrets and variables > Actions."
                         if "GitHub" in src else "Jalankan JALANKAN.bat sekali secara manual untuk memasukkan kunci baru.")
                sys.exit(f"YouTube menolak kunci {_mask(key)} dari {src}: {msg[:160]}\n{where}")
            extra = ""
            if src.startswith("variabel"):
                extra = (" (Kunci ini berasal dari variabel lingkungan Windows YOUTUBE_API_KEY; kunci baru yang kamu"
                         " tempel akan disimpan ke file dan dipakai lebih dulu.)")
            if "ipRefererBlocked" in msg or "SERVICE_BLOCKED" in msg or "forbidden" in msg:
                extra += (" Kunci ini dibatasi (Application/API restrictions). Di Credentials, set Application"
                          " restrictions = None dan API restrictions = YouTube Data API v3.")
            key = ask_key(f"YouTube menolak kunci {_mask(key)}: {msg[:160]}.{extra}")
            src = f"file {KEY_FILE.name}"
    return key


# ---------------------------------------------------------------- pencocokan keyword
_STOP = {"indonesia", "di", "dan", "yang", "untuk", "of", "the", "and"}


def _caps_sensitive(word: str) -> bool:
    """Singkatan kapital (EV, OJK, ACA, MPMX) hanya cocok bila ditulis kapital."""
    return word.isupper() and any(ch.isalpha() for ch in word) and len(word.replace(" ", "")) <= 8


def _phrase_rx(text: str, caps: bool):
    parts = [re.escape(p) for p in text.split()]
    body = r"[\s\-\.]*".join(parts) if len(parts) > 1 else parts[0]
    return re.compile(r"(?<![A-Za-z0-9])" + body + r"(?![A-Za-z0-9])", 0 if caps else re.I)


def _derive_aliases(label: str) -> list[str]:
    """'PT Serasi Autoraya (SERA)' -> ['Serasi Autoraya', 'SERA'] bila kolom alias kosong."""
    out = []
    main = re.sub(r"\(.*?\)", "", label)
    for part in main.split("/"):
        p = re.sub(r"^\s*PT\.?\s+", "", part.strip(), flags=re.I)
        p = re.sub(r"\s+Tbk\.?$", "", p, flags=re.I).strip()
        if p:
            out.append(p)
    out += [x.strip() for x in re.findall(r"\((.*?)\)", label) if x.strip()]
    return out


def prepare(k: dict):
    """Siapkan pencocok untuk satu keyword (sekali saja)."""
    if "_m" in k:
        return k["_m"]
    if k["tier"] == 2:
        sets = []
        for src in dict.fromkeys([k["query"], k["keyword"]]):
            toks = [t for t in re.findall(r"[A-Za-z0-9]+", src) if t.lower() not in _STOP]
            if toks:
                sets.append([re.compile(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])",
                                        0 if (_caps_sensitive(t) or k["kapital"]) else re.I) for t in toks])
        k["_m"] = ("tokens", sets)
    else:
        phrases = [k["keyword"]] if k["tier"] == 1 else (k["aliases"] or _derive_aliases(k["keyword"]))
        k["_m"] = ("phrases", [_phrase_rx(p, k["kapital"] or _caps_sensitive(p)) for p in phrases])
    return k["_m"]


def match_video(v: dict, kws: list[dict]) -> list[dict]:
    """Keyword yang benar-benar muncul di judul / deskripsi / tag (pencarian YouTube juga mengembalikan video 'mirip').
    Tier 1 & 3: frasa persis (keyword/alias). Tier 2: semua kata dari kata_pencarian atau keyword-nya ada di teks."""
    fields = (("judul", v.get("title", "")), ("deskripsi", v.get("_desc_full", v.get("desc", ""))),
              ("tag", " | ".join(v.get("_tags", []))))
    allt = " \n ".join(t or "" for _, t in fields)
    spans: dict[str, list[tuple[int, int, dict]]] = {name: [] for name, _ in fields}
    found: dict[int, list[str]] = {}
    for idx, k in enumerate(kws):
        kind, ms = prepare(k)
        if kind == "tokens":
            for toks in ms:
                if all(t.search(allt) for t in toks):
                    if any(x.lower() in allt.lower() for x in k["kecuali"]):
                        break
                    found[idx] = [name for name, text in fields if any(t.search(text or "") for t in toks)]
                    break
            continue
        for rx in ms:
            for name, text in fields:
                for m in rx.finditer(text or ""):
                    ctx = text[max(0, m.start() - 80): m.end() + 80].lower()
                    if any(x.lower() in ctx for x in k["kecuali"]):
                        continue
                    spans[name].append((m.start(), m.end(), idx))
    # frasa pendek yang hanya muncul di dalam frasa lebih panjang dari tier yang sama tidak dihitung
    # ("MPM" di dalam "MPM Honda Jatim"; sama dengan aturan suppress_contained di crawler berita)
    for name, sp in spans.items():
        for s, e, idx in sp:
            if any(s2 <= s and e <= e2 and (e2 - s2) > (e - s) and kws[i2]["tier"] == kws[idx]["tier"]
                   for s2, e2, i2 in sp):
                continue
            w = found.setdefault(idx, [])
            if name not in w:
                w.append(name)
    return [{"kw": kws[i]["keyword"], "tier": kws[i]["tier"], "kel": kws[i]["kelompok"], "di": found[i]}
            for i in sorted(found)]


# ---------------------------------------------------------------- API
class QuotaExceeded(Exception):
    pass


class ApiError(Exception):
    pass


def call(endpoint: str, params: dict, key: str) -> dict:
    url = API + endpoint + "?" + urllib.parse.urlencode({**params, "key": key})
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            try:
                err = json.loads(body)["error"]
                reason = (err.get("errors") or [{}])[0].get("reason", "")
                msg = err.get("message", "")
            except Exception:
                reason, msg = "", body[:200]
            if reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded") and e.code == 403:
                raise QuotaExceeded(msg)
            if e.code in (400, 403) and reason in ("keyInvalid", "badRequest", "accessNotConfigured",
                                                   "forbidden", "ipRefererBlocked", "API_KEY_INVALID"):
                raise ApiError(f"{reason}: {msg}")
            if e.code in (500, 502, 503, 504) and attempt < 3:
                time.sleep(2 * (attempt + 1))
                last = e
                continue
            raise ApiError(f"HTTP {e.code} {reason}: {msg}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            if attempt < 3:
                time.sleep(2 * (attempt + 1))
                continue
    raise ApiError(f"tidak bisa tersambung ke YouTube API: {last}")


def iso_dur(s: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def best_thumb(th: dict) -> str:
    for k in ("medium", "high", "standard", "default"):
        if th.get(k, {}).get("url"):
            return th[k]["url"]
    return ""


# ---------------------------------------------------------------- penyimpanan
def load_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def quota_state() -> dict:
    today = datetime.now(PACIFIC).date().isoformat()
    q = load_json(KUOTA, {})
    if q.get("tanggal_pasifik") != today:
        q = {"tanggal_pasifik": today, "cari": 0, "unit_lain": 0}
    return q


# ---------------------------------------------------------------- pencarian bergilir
def search_plan(kws: list[dict], giliran: dict, budget: int) -> tuple[list[dict], int]:
    """Daftar kata pencarian unik untuk run ini: tier 1 semua (setiap run), lalu tier 2/3 yang paling lama belum
    dicari, sampai jatah habis. Mengembalikan (rencana, jumlah kata pencarian tier 2/3 seluruhnya)."""
    qs: dict[str, dict] = {}
    for i, k in enumerate(kws):
        if not k["cari"]:
            continue
        e = qs.setdefault(k["query"], {"query": k["query"], "tier": k["tier"], "idx": i, "kws": []})
        e["tier"] = min(e["tier"], k["tier"])
        e["kws"].append(k["keyword"])
    t1 = [e for e in qs.values() if e["tier"] == 1]
    rest = sorted((e for e in qs.values() if e["tier"] != 1),
                  key=lambda e: (giliran.get(e["query"], ""), e["tier"], e["idx"]))
    return (t1 + rest)[:max(0, budget)], len(rest)


def search_all(plan, key, hari, hari_hot, halaman, q, giliran) -> tuple[dict, list[str]]:
    """search.list per kata pencarian. Tier 1: terbaru dalam `hari`; tier 2/3: tayangan terbanyak dalam `hari_hot`.
    Mengembalikan {video_id: {"q": [kata pencarian], "t": tier terendah}} dan catatan."""
    now = datetime.now(timezone.utc)
    after = {1: (now - timedelta(days=hari)).strftime("%Y-%m-%dT%H:%M:%SZ"),
             2: (now - timedelta(days=hari_hot)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    found: dict[str, dict] = {}
    notes = []
    for i, e in enumerate(plan, 1):
        hot = e["tier"] != 1
        token = None
        for page in range(1 if hot else halaman):
            if q["cari"] >= BATAS_CARI_HARIAN:
                notes.append(f"Batas pencarian harian tercapai ({q['cari']}); sisanya dilanjutkan di run berikutnya.")
                log("  ! " + notes[-1])
                return found, notes
            text = e["query"]
            query = f'"{text}"' if (" " in text and not hot) else text      # tier 1: frasa persis
            params = dict(part="snippet", q=query, type="video", maxResults=50,
                          order="viewCount" if hot else "date", publishedAfter=after[2 if hot else 1],
                          regionCode="ID", relevanceLanguage="id", safeSearch="none")
            if token:
                params["pageToken"] = token
            try:
                r = call("search", params, key)
            except QuotaExceeded as ex:
                notes.append(f"Kuota YouTube habis saat mencari '{text}' ({ex}). Data yang sudah didapat tetap disimpan.")
                log("  ! " + notes[-1])
                q["cari"] = BATAS_CARI_HARIAN
                return found, notes
            q["cari"] += 1
            giliran[e["query"]] = datetime.now(WIB).isoformat(timespec="minutes")
            ids = [it["id"]["videoId"] for it in r.get("items", []) if it.get("id", {}).get("videoId")]
            for vid in ids:
                f = found.setdefault(vid, {"q": [], "t": e["tier"]})
                f["t"] = min(f["t"], e["tier"])
                if text not in f["q"]:
                    f["q"].append(text)
            log(f"  [{i:3}/{len(plan)}] T{e['tier']} {text[:42]:42} {'populer' if hot else 'terbaru'}: {len(ids):2} video")
            token = r.get("nextPageToken")
            if not token:
                break
    return found, notes


def fetch_details(ids: list[str], key: str, q: dict) -> dict:
    out = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        r = call("videos", dict(part="snippet,statistics,contentDetails", id=",".join(chunk), maxResults=50), key)
        q["unit_lain"] += 1
        for it in r.get("items", []):
            out[it["id"]] = it
    return out


def fetch_channels(ids: list[str], key: str, q: dict) -> dict:
    out = {}
    for i in range(0, len(ids), 50):
        r = call("channels", dict(part="snippet,statistics", id=",".join(ids[i:i + 50]), maxResults=50), key)
        q["unit_lain"] += 1
        for it in r.get("items", []):
            st = it.get("statistics", {})
            out[it["id"]] = {"nama": it["snippet"]["title"],
                             "subscriber": None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0) or 0),
                             "url": "https://www.youtube.com/channel/" + it["id"]}
    return out


def apply_details(db: dict, details: dict, kws: list[dict], now_iso: str, today: str):
    for vid, it in details.items():
        sn, st, cd = it.get("snippet", {}), it.get("statistics", {}), it.get("contentDetails", {})
        v = db["videos"].setdefault(vid, {"id": vid, "first_seen": now_iso, "queries": [], "hist": []})
        v.update(title=sn.get("title", ""), channel_id=sn.get("channelId", ""), channel=sn.get("channelTitle", ""),
                 published=sn.get("publishedAt", ""), thumb=best_thumb(sn.get("thumbnails", {})),
                 duration=iso_dur(cd.get("duration", "")), live=sn.get("liveBroadcastContent", "none"),
                 views=int(st.get("viewCount", 0) or 0),
                 likes=None if "likeCount" not in st else int(st["likeCount"] or 0),
                 comments=None if "commentCount" not in st else int(st["commentCount"] or 0),
                 desc=(sn.get("description") or "")[:500], last_updated=now_iso)
        v.pop("unavailable", None)
        v.pop("groups", None)                                   # format lama
        v["_desc_full"] = sn.get("description") or ""
        v["_tags"] = sn.get("tags") or []
        v["matched"] = match_video(v, kws)
        h = [x for x in v.get("hist", []) if x[0] != today]
        v["hist"] = (h + [[today, v["views"]]])[-60:]
        v.pop("_desc_full", None)
        v.pop("_tags", None)


def prune(db: dict, simpan_hari: int) -> int:
    """Buang video tier 2/3 yang tidak menyebut keyword (hasil 'mirip' saja) dan video yang terbit lebih dari
    `simpan_hari` hari lalu. Hasil 'mirip' tier 1 tetap disimpan (jumlahnya kecil, berguna untuk dicek manual)."""
    lim = (datetime.now(timezone.utc) - timedelta(days=simpan_hari)).strftime("%Y-%m-%dT%H:%M:%SZ")
    drop = [vid for vid, v in db["videos"].items()
            if (not v.get("matched") and v.get("q_tier", 1) != 1) or (v.get("published") and v["published"] < lim)]
    for vid in drop:
        del db["videos"][vid]
    return len(drop)


def build_dashboard(db: dict, q: dict, kws: list[dict], notes: list[str], giliran: dict) -> Path:
    tiers = {}
    for k in kws:
        t = tiers.setdefault(k["tier"], {"nama": TIER_NAMA.get(k["tier"], f"Tier {k['tier']}"), "kelompok": []})
        if k["kelompok"] not in t["kelompok"]:
            t["kelompok"].append(k["kelompok"])
    payload = {
        "generated": datetime.now(WIB).isoformat(timespec="minutes"),
        "last_run": db.get("runs", [])[-1] if db.get("runs") else None,
        "videos": list(db["videos"].values()),
        "channels": db.get("channels", {}),
        "tiers": tiers,
        "keywords": [{"kw": k["keyword"], "tier": k["tier"], "kel": k["kelompok"], "q": k["query"],
                      "cari": k["cari"], "last": giliran.get(k["query"], "")} for k in kws],
        "quota": {"search_used": q.get("cari", 0), "search_limit": 100, "units_used": q.get("unit_lain", 0),
                  "units_limit": 10000, "day_pacific": q.get("tanggal_pasifik")},
        "notes": notes,
    }
    js = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", js)
    OUT_HTML.write_text(html, encoding="utf-8")
    return OUT_HTML


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="MPM YouTube Monitoring")
    ap.add_argument("--hari", type=int, default=30, help="tier 1: video yang terbit N hari terakhir (default 30)")
    ap.add_argument("--hari-hot", type=int, default=14, help="tier 2/3: konten terpopuler N hari terakhir (default 14)")
    ap.add_argument("--maks-cari", type=int, default=90, help="maksimal pencarian di run ini (default 90; batas YouTube 100/hari)")
    ap.add_argument("--halaman", type=int, default=1, help="tier 1: halaman hasil per keyword, 50 video/halaman (default 1)")
    ap.add_argument("--simpan-hari", type=int, default=120, help="buang video yang terbit lebih dari N hari lalu (default 120)")
    ap.add_argument("--tanpa-cari", action="store_true", help="hanya perbarui statistik video yang sudah ada")
    ap.add_argument("--dashboard", action="store_true", help="hanya buat ulang dashboard, tanpa memanggil API")
    ap.add_argument("--tidak-buka", action="store_true", help="jangan buka dashboard di browser")
    a = ap.parse_args(argv)

    kws = load_keywords()
    db = load_json(DB, {"videos": {}, "channels": {}, "runs": []})
    giliran = load_json(GILIRAN, {})
    q = quota_state()
    notes: list[str] = []
    log("Keyword: " + ", ".join(f"tier {t} = {sum(1 for k in kws if k['tier'] == t)}" for t in sorted({k['tier'] for k in kws})))

    if not a.dashboard:
        key = checked_key()
        now = datetime.now(WIB)
        now_iso, today = now.isoformat(timespec="minutes"), now.date().isoformat()
        before = set(db["videos"])
        try:
            found = {}
            if not a.tanpa_cari:
                budget = min(a.maks_cari, BATAS_CARI_HARIAN - q["cari"])
                plan, n_rest = search_plan(kws, giliran, budget)
                n1 = sum(1 for e in plan if e["tier"] == 1)
                log(f"Mencari {len(plan)} kata pencarian (tier 1: {n1}, tier 2/3: {len(plan) - n1} dari {n_rest} bergiliran; "
                    f"pencarian hari ini: {q['cari']}/100) ...")
                if budget <= 0:
                    notes.append("Jatah pencarian hari ini sudah habis; hanya statistik yang diperbarui.")
                    log("  ! " + notes[-1])
                found, n2 = search_all(plan, key, a.hari, a.hari_hot, max(1, a.halaman), q, giliran)
                notes += n2
                save_json(GILIRAN, giliran)
            ids = sorted(set(found) | set(db["videos"]))
            log(f"Mengambil detail & statistik {len(ids)} video ...")
            details = fetch_details(ids, key, q)
            apply_details(db, details, kws, now_iso, today)
            for vid, f in found.items():
                if vid in db["videos"]:
                    v = db["videos"][vid]
                    v["queries"] = sorted(set(v.get("queries", [])) | set(f["q"]))
                    v["q_tier"] = min(v.get("q_tier", f["t"]), f["t"])
            for vid in [vid for vid in db["videos"] if vid not in details]:   # dihapus / dijadikan privat
                db["videos"][vid]["unavailable"] = True
            dropped = prune(db, a.simpan_hari)
            if dropped:
                log(f"  {dropped} video dibuang (tidak menyebut keyword tier 2/3, atau lebih tua dari {a.simpan_hari} hari).")
            ch_ids = sorted({v["channel_id"] for v in db["videos"].values() if v.get("channel_id")})
            log(f"Mengambil info {len(ch_ids)} channel ...")
            db["channels"] = {**{c: db["channels"][c] for c in ch_ids if c in db.get("channels", {})},
                              **fetch_channels(ch_ids, key, q)}
        except ApiError as e:
            save_json(KUOTA, q)
            save_json(GILIRAN, giliran)
            msg = str(e)
            log("\nGAGAL: " + msg)
            if not db["videos"]:
                return 1
            notes.append("Run terakhir gagal: " + msg[:200])
        new = sorted(set(db["videos"]) - before)
        for vid in new:
            db["videos"][vid]["new_run"] = now_iso
        per_tier = {t: sum(1 for v in db["videos"].values() if any(m["tier"] == t for m in v.get("matched", [])))
                    for t in (1, 2, 3)}
        db.setdefault("runs", []).append({"waktu": now_iso, "baru": len(new), "total": len(db["videos"]),
                                          "per_tier": per_tier, "cari": q["cari"]})
        db["runs"] = db["runs"][-200:]
        save_json(DB, db)
        save_json(KUOTA, q)
        log(f"Selesai: {len(db['videos'])} video tersimpan (menyebut keyword: tier 1 {per_tier[1]}, tier 2 {per_tier[2]}, "
            f"tier 3 {per_tier[3]}), {len(new)} baru. Kuota hari ini: pencarian {q['cari']}/100, unit lain {q['unit_lain']}/10000.")

    out = build_dashboard(db, q, kws, notes, giliran)
    log(f"Dashboard: {out}")
    if not a.tidak_buka:
        webbrowser.open(out.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
