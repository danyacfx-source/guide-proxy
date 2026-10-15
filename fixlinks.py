import sys, re, shutil
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from urllib.parse import urljoin, urlparse, quote

OUT = Path(r'C:\Users\Admin\Documents\Default Project\guide-proxy\static')
LANGS = ('de', 'es', 'fr', 'pt', 'zh', 'fi')
SECTIONS = ('loadouts', 'database', 'calculators', 'servers', 'maps', 'news', 'zone',
            'economy', 'account', 'wiki', 'about', 'community', 'contact', 'discord',
            'link', 'progression', 'updates', 'terms', 'privacy', 'signin')

pairs = [
    ('favicon_favicon.2cdghoj80ai61.ico.ico', 'favicon.ico'),
    ('icon_icon.3hgt9pioy3p7w.png.png', 'icon.png'),
    ('apple-icon_apple-icon.2hd5uksdr1l2j.png.png', 'apple-icon.png'),
]
for src, dst in pairs:
    s, d = OUT / src, OUT / dst
    if s.exists() and not d.exists():
        shutil.copy2(s, d)
        print('copied', dst)


def local_path(p: str) -> Path:
    if p in ('/', ''):
        return OUT / 'ru/index.html'
    q = p.lstrip('/')
    if q.endswith('/'):
        return OUT / q / 'index.html'
    if Path(q).suffix:
        return OUT / q
    return OUT / q / 'index.html'


def exists(p: str) -> bool:
    lp = local_path(p)
    return lp.exists() and lp.stat().st_size > 0


DYNAMIC_PREFIX = ('/avatars', '/api/', '/embed', '/signin')


def fix_one(raw: str, page_url: str, rel: str, stats: dict) -> str | None:
    """Return replacement value or None to keep."""
    if not raw or raw.startswith(('data:', '#', 'mailto:', 'tel:', 'javascript:')):
        return None
    if raw.startswith('//') or re.match(r'^https?://', raw):
        return None  # external (incl. already-rewritten wardogs.zone)

    pr0 = urlparse(raw)
    frag = ('#' + pr0.fragment) if pr0.fragment else ''
    query = pr0.query
    resolved = urljoin(page_url, raw)
    pr = urlparse(resolved)
    path = pr.path

    segs = [s for s in path.split('/') if s]

    # language variants -> original site
    if segs and segs[0] in LANGS:
        stats['lang'] += 1
        return 'https://wardogs.zone' + path + (f'?{query}' if query else '') + frag

    # already absolute internal path pointing at real local file
    if raw.startswith('/') and not raw.startswith('/_next/image'):
        look = path
        if exists(look):
            if raw == path and not query and not frag:
                return None
            out = path + (f'?{query}' if query and not Path(path).suffix else '') + frag
            if out != raw:
                stats['rel2abs'] += 1
                return out
            return None

    # relative './...' produced by domain->dot rewrite: original was /<rest>
    if raw.startswith('./') and not raw.startswith('./_next'):
        cand = '/' + raw[2:]
        cpath = urlparse(cand).path
        if exists(cpath):
            stats['rel2abs'] += 1
            base = cpath if cpath.endswith('/') or Path(cpath).suffix else cpath
            return base + frag
        # english unprefixed
        if cpath.lstrip('/').split('/')[0] in SECTIONS:
            ru = '/ru' + cpath
            if exists(ru):
                stats['en2ru'] += 1
                return (ru if ru.endswith('/') or Path(ru).suffix else ru) + frag
        # generic fallback: original site
        stats['dyn'] += 1
        return 'https://wardogs.zone' + cand + frag

    # other relative (../...) -> absolute
    if raw.startswith('.'):
        if exists(path):
            if raw == path:
                return None
            stats['rel2abs'] += 1
            out = path + (f'?{query}' if query and not Path(path).suffix else '') + frag
            return out
        # english unprefixed from relative resolution
        segs2 = [s for s in path.split('/') if s]
        if segs2 and segs2[0] in SECTIONS:
            ru = '/ru' + path
            if exists(ru):
                stats['en2ru'] += 1
                return (ru if ru.endswith('/') or Path(ru).suffix else ru) + frag
        stats['dyn'] += 1
        return 'https://wardogs.zone' + path + frag

    # absolute-path english urls (no /ru)
    if segs and segs[0] in SECTIONS:
        ru = '/ru' + path
        if exists(ru):
            stats['en2ru'] += 1
            out = ru + (f'?{query}' if query and not Path(ru).suffix else '') + frag
            return out

    # /ru/signin and other missing /ru pages -> original
    if path.startswith('/ru') and not exists(path):
        stats['dyn'] += 1
        return 'https://wardogs.zone' + path + (f'?{query}' if query else '') + frag

    # dynamic endpoints (avatars, api, embed, root avatar jpgs) -> original site
    if path.startswith(DYNAMIC_PREFIX) or (segs and Path(segs[0]).suffix in ('.jpg', '.png', '.webp') and not path.startswith('/game/')):
        stats['dyn'] += 1
        return 'https://wardogs.zone' + path + frag

    if raw.startswith('/') and exists(path) and raw != path and not query:
        stats['rel2abs'] += 1
        return path + frag

    return None


ATTR = re.compile(r'(href|src)="([^"]*)"')
# escaped href inside Next.js flight payloads: {\"href\":\"...\"}
FLIGHT = re.compile(r'\\+"href\\+":\\+"([^"\\]+)\\+"')

stats = {'rel2abs': 0, 'lang': 0, 'en2ru': 0, 'dyn': 0, 'unresolved': 0, 'kept': 0}
unresolved = []

for f in OUT.rglob('*.html'):
    rel = f.relative_to(OUT).as_posix()
    page_path = rel[:-10] if rel.endswith('index.html') else rel
    page_path = page_path.rstrip('/')
    page_url = 'https://guide.dendich.online' + ('/' + page_path if page_path else '')
    text = f.read_bytes().decode('utf-8', 'replace')

    def repl(m):
        attr, raw = m.group(1), m.group(2)
        try:
            new = fix_one(raw, page_url, rel, stats)
        except Exception:
            new = None
        if new is None:
            stats['kept'] += 1
            return m.group(0)
        return f'{attr}="{new}"'

    def flight_repl(m):
        raw = m.group(1)
        try:
            new = fix_one(raw, page_url, rel, stats)
        except Exception:
            new = None
        if new is None:
            stats['kept'] += 1
            return m.group(0)
        # keep escaped quotes around value
        esc = new.replace('/', '\\/')
        return m.group(0).replace(m.group(1), esc)

    new = ATTR.sub(repl, text)
    new = FLIGHT.sub(flight_repl, new)
    if new != text:
        f.write_text(new, encoding='utf-8')

print(stats)
