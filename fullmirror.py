"""Full re-mirror: crawl every /ru page + all assets + API data."""

import html as html_mod
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag, unquote, parse_qs

BASE = "https://wardogs.zone"
OUT = Path(r"C:\Users\Admin\Documents\Default Project\guide-proxy\static")
LOGF = open(Path(r"C:\Users\Admin\Documents\Default Project\guide-proxy\full.log"), "w", encoding="utf-8", buffering=1)


def log(msg):
    print(msg, file=LOGF, flush=True)
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9",
}
TIMEOUT = 20
DELAY = 0.8  # polite delay

BIN_EXT = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp3", ".mp4", ".webm", ".ogg", ".wasm",
}
TEXT_EXT = {".js", ".css", ".json", ".webmanifest", ".txt", ".xml", ".map", ".mjs"}


def fetch(url: str, referer: str = None, retries: int = 3) -> bytes | None:
    headers = dict(UA)
    if referer:
        headers["Referer"] = referer
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return None
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
        except Exception:
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    return None


def url_to_path(url: str) -> str:
    p = urlparse(url)
    path = unquote(p.path)
    if p.query:
        safe_q = re.sub(r"[^A-Za-z0-9._-]", "_", p.query)[:80]
        base, dot, ext = path.rpartition(".")
        if dot and len(ext) <= 10:
            path = f"{base}_{safe_q}.{ext}"
        else:
            path = f"{path}_{safe_q}"
    if not path or path.endswith("/"):
        path = path + "index.html"
    elif not Path(path).suffix:
        path = path + "/index.html"
    return path.lstrip("/")


def resolve_next_image(url: str) -> str:
    p = urlparse(url)
    if p.path == "/_next/image":
        qs = parse_qs(p.query)
        real = qs.get("url", [""])[0]
        if real:
            return urljoin(BASE, real)
    return url


def extract_urls(html: str, page_url: str) -> tuple[set, set]:
    """Returns (asset_urls, page_urls)."""
    assets = set()
    pages = set()

    candidates = set()
    for attr in ("src", "href", "poster", "data-src"):
        for m in re.finditer(rf'{attr}="([^"]*)"', html):
            val = html_mod.unescape(m.group(1)).strip().rstrip("\\")
            if val and not val.startswith(("data:", "javascript:", "#", "mailto:", "tel:", "blob:")):
                candidates.add(val)
    for m in re.finditer(r'srcset="([^"]*)"', html):
        val = html_mod.unescape(m.group(1))
        for part in val.split(","):
            part = part.strip()
            if part:
                u = part.split()[0]
                if u and not u.startswith("data:"):
                    candidates.add(u)
    for m in re.finditer(r"url\(([^)]+)\)", html):
        u = html_mod.unescape(m.group(1)).strip("'\" \\")
        if not u.startswith(("data:", "#")):
            candidates.add(u)
    # RSC / flight payloads
    for m in re.finditer(r'"(/_next/[^"\\]+)"', html):
        candidates.add(m.group(1))
    for m in re.finditer(r'"(/(?:i18n|icons|images|static|fonts|media|assets|brand|game|x|api)/[^"\\]+)"', html):
        candidates.add(m.group(1))
    # internal links
    for m in re.finditer(r'href="(/ru[^"]*)"', html):
        candidates.add(html_mod.unescape(m.group(1)))

    for raw in candidates:
        absu = urljoin(page_url, raw)
        absu, _ = urldefrag(absu)
        absu = absu.rstrip("\\").rstrip(",")
        if not absu or " " in absu or "\t" in absu:
            continue
        if absu.startswith(("data:", "#")):
            continue
        absu = resolve_next_image(absu)
        parsed = urlparse(absu)
        if parsed.netloc and parsed.netloc not in ("wardogs.zone", "www.wardogs.zone"):
            continue
        bad = ("cloudflareinsights", "google-analytics", "yandex", "mc.yandex", "googletagmanager")
        if any(b in absu for b in bad):
            continue
        if parsed.path.startswith("/_next/image"):
            continue
        suffix = Path(parsed.path).suffix.lower()
        if suffix:
            assets.add(absu)
        elif parsed.path.startswith("/ru"):
            pages.add(absu)
    return assets, pages


def main():
    # seed with existing pages + known sections
    page_queue = []
    seen_pages = set()

    # seed from all existing html
    for f in OUT.rglob("*.html"):
        rel = f.relative_to(OUT).as_posix()
        if rel.endswith("/index.html"):
            path = "/" + rel[: -len("index.html")]
        else:
            path = "/" + rel
        page_queue.append(BASE + path)

    # key seeds for new discovery
    seeds = [
        "/ru",
        "/ru/calculators/rewards?t=match&pl=third",
        "/ru/calculators/damage",
        "/ru/calculators/ttk",
        "/ru/calculators/artillery",
        "/ru/calculators/vehicle",
        "/ru/database",
        "/ru/database/weapons",
        "/ru/database/ammo",
        "/ru/database/skins",
        "/ru/database/compare",
        "/ru/wiki",
        "/ru/wiki/classes",
        "/ru/wiki/armor-and-damage",
        "/ru/wiki/economy",
        "/ru/wiki/control-zone",
        "/ru/wiki/parachutes",
        "/ru/news",
        "/ru/loadouts",
        "/ru/loadouts/hub",
        "/ru/loadouts/base",
        "/ru/loadouts/vehicle",
        "/ru/maps",
        "/ru/servers",
        "/ru/servers/rules",
        "/ru/servers/leaderboard",
        "/ru/servers/matches",
        "/ru/economy/gold",
        "/ru/account/progression",
        "/ru/zone",
        "/ru/zone/achievements",
        "/ru/progression",
        "/ru/updates",
        "/ru/about",
        "/ru/community",
        "/ru/contact",
        "/ru/terms",
        "/ru/privacy",
    ]
    for s in seeds:
        page_queue.append(BASE + s)

    # 1. crawl pages
    log("=== PHASE 1: pages ===")
    new_pages = 0

    LANG = {"en", "ru", "fr", "de", "es", "pt", "fi", "zh"}
    MAX_PAGES = 4000

    def valid_page(u: str) -> bool:
        p = urlparse(u)
        if p.netloc not in ("wardogs.zone", "www.wardogs.zone"):
            return False
        segs = [s for s in p.path.split("/") if s]
        if not segs or segs[0] != "ru":
            return False
        if len(segs) > 4:
            return False
        if len(segs) > 2 and segs[1] in LANG and segs[1] != "ru":
            return False
        # any lang code after /ru = junk variant
        if any(s in LANG for s in segs[1:]):
            return False
        # endless user profiles — skip
        if len(segs) >= 2 and segs[1] in ("u", "signin_next__2Fzone"):
            return False
        # junk: repeated segment (ru/discord/ru/discord, x/calculators/y/calculators/z)
        if len(segs) >= 4 and (segs[2] == segs[0] or segs[3] == segs[1]):
            return False
        if len(set(segs)) != len(segs):
            return False
        return True

    while page_queue:
        if new_pages >= MAX_PAGES:
            log("MAX_PAGES hit, stopping page crawl")
            break
        url = page_queue.pop(0)
        if not valid_page(url):
            continue
        key = urlparse(url)._replace(query="").geturl()
        if key in seen_pages:
            continue
        seen_pages.add(key)

        local = url_to_path(url)
        dest = OUT / local
        need_fetch = not dest.exists() or dest.stat().st_size == 0

        if need_fetch:
            log(f"[PAGE] {url}")
            data = fetch(url, referer=BASE + "/ru")
            time.sleep(DELAY)
            if data is None:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            new_pages += 1

        # discover more pages from html
        html = dest.read_bytes().decode("utf-8", "replace")
        _, more_pages = extract_urls(html, BASE + urlparse(url).path)
        for p in more_pages:
            if not valid_page(p):
                continue
            k = urlparse(p)._replace(query="").geturl()
            if k not in seen_pages:
                page_queue.append(p)

    log(f"pages done, new={new_pages}")

    # 2. collect all assets from all html
    all_assets = set()
    for f in OUT.rglob("*.html"):
        rel = f.relative_to(OUT).as_posix()
        path = "/" + (rel[: -len("index.html")] if rel.endswith("/index.html") else rel)
        html = f.read_bytes().decode("utf-8", "replace")
        a, _ = extract_urls(html, BASE + path)
        all_assets.update(a)

    # CSS nested
    for css_f in OUT.rglob("*.css"):
        css = css_f.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"url\(([^)]+)\)", css):
            u = html_mod.unescape(m.group(1)).strip("'\" \\")
            if u.startswith("data:"):
                continue
            absu = urljoin(BASE, u).rstrip("\\")
            if Path(urlparse(absu).path).suffix:
                all_assets.add(absu)

    # core always
    for c in ["/i18n/ru.5512ceb6f976.js", "/manifest.webmanifest",
              "/favicon.ico?favicon.2cdghoj80ai61.ico",
              "/icon.png?icon.3hgt9pioy3p7w.png",
              "/apple-icon.png?apple-icon.2hd5uksdr1l2j.png",
              "/x/script.js"]:
        all_assets.add(BASE + c)

    # filter missing
    missing = []
    for u in sorted(all_assets):
        lp = url_to_path(u)
        d = OUT / lp
        if not d.exists() or d.stat().st_size == 0:
            missing.append(u)

    log(f"=== PHASE 2: assets, missing={len(missing)} ===")

    done = fail = 0
    for i, u in enumerate(missing, 1):
        lp = url_to_path(u)
        d = OUT / lp
        log(f"[{i}/{len(missing)}] {u}")
        data = fetch(u, referer=BASE + "/ru", retries=2)
        time.sleep(DELAY)
        if data is None:
            fail += 1
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_bytes(data)
        done += 1

    log(f"assets: ok={done} fail={fail}")

    # 3. rewrite
    asset_map = {}
    for u in all_assets:
        lp = url_to_path(u)
        d = OUT / lp
        if d.exists() and d.stat().st_size > 0:
            asset_map[u] = lp

    rewritten = 0
    for f in OUT.rglob("*"):
        if not f.is_file():
            continue
        suffix = f.suffix.lower()
        if suffix in BIN_EXT:
            continue
        if suffix not in {".html", ".js", ".css", ".json", ".webmanifest", ".mjs", ".txt", ".map"}:
            continue
        try:
            text = f.read_bytes().decode("utf-8")
        except Exception:
            continue
        rel = f.relative_to(OUT).as_posix()
        depth = rel.count("/")
        prefix = "./" if depth == 0 else "../" * depth
        local_map = {up: prefix + lp for up, lp in asset_map.items()}
        new_text = text
        for up in sorted(local_map.keys(), key=len, reverse=True):
            lp = local_map[up]
            new_text = new_text.replace(up, lp)
            new_text = new_text.replace(up.replace("https://", "//"), lp)
        new_text = new_text.replace("https://wardogs.zone", ".")
        new_text = new_text.replace("//wardogs.zone", ".")

        def img_sub(m):
            raw = m.group(0)
            resolved = resolve_next_image(raw.strip('"\''))
            if resolved in asset_map:
                return '"' + prefix + asset_map[resolved] + '"'
            return raw

        new_text = re.sub(r'"/_next/image\?[^"]+"', img_sub, new_text)
        new_text = re.sub(r'(["\'])/_next/', rf'\1{prefix}_next/', new_text)
        new_text = re.sub(r'(["\'])/i18n/', rf'\1{prefix}i18n/', new_text)
        new_text = re.sub(r'(["\'])/brand/', rf'\1{prefix}brand/', new_text)
        new_text = re.sub(r'(["\'])/x/script', rf'\1{prefix}x/script', new_text)
        new_text = re.sub(r'(["\'])/ru/', rf'\1{prefix}ru/', new_text)
        new_text = re.sub(r'(["\'])/game/', rf'\1{prefix}game/', new_text)
        new_text = re.sub(r'(["\'])/manifest\.webmanifest', rf'\1{prefix}manifest.webmanifest', new_text)
        new_text = re.sub(r'(["\'])/favicon\.ico', rf'\1{prefix}favicon.ico', new_text)
        new_text = re.sub(r'(["\'])/icon\.png', rf'\1{prefix}icon.png', new_text)
        new_text = re.sub(r'(["\'])/apple-icon\.png', rf'\1{prefix}apple-icon.png', new_text)
        if new_text != text:
            f.write_text(new_text, encoding="utf-8")
            rewritten += 1

    log(f"rewrote={rewritten}")
    log("DONE")


if __name__ == "__main__":
    main()
