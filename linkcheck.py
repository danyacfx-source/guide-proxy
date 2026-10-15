import sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from urllib.parse import urljoin, urlparse
from collections import Counter

OUT = Path(r'C:\Users\Admin\Documents\Default Project\guide-proxy\static')
HOST = 'guide.dendich.online'


def local_exists(path: str) -> bool:
    if path in ('/', ''):
        path = '/ru/'
    q = path.lstrip('/')
    if q.endswith('/'):
        p = OUT / q / 'index.html'
    elif Path(q).suffix:
        p = OUT / q
    else:
        p = OUT / q / 'index.html'
    return p.exists() and p.stat().st_size > 0


broken = []
n = 0
for f in OUT.rglob('*.html'):
    rel = f.relative_to(OUT).as_posix()
    pp = (rel[:-10] if rel.endswith('index.html') else rel).rstrip('/')
    page_url = 'https://' + HOST + ('/' + pp if pp else '')
    t = f.read_bytes().decode('utf-8', 'replace')
    for m in re.finditer(r'(?:href|src)="([^"]+)"', t):
        u = m.group(1)
        if u.startswith(('data:', '#', 'mailto:', 'tel:', 'javascript:')):
            continue
        if u.startswith('//') or re.match(r'^https?://', u):
            # external — only count if it points at our host
            if HOST not in u.split('/')[2]:
                continue
        n += 1
        resolved = urljoin(page_url, u)
        pr = urlparse(resolved)
        if pr.netloc and HOST not in pr.netloc:
            continue
        path = pr.path
        if not local_exists(path):
            broken.append((rel, u, path))

print('checked:', n, ' broken:', len(broken))
c = Counter(b[2].split('/')[1] if b[2].count('/') > 1 else b[2] for b in broken)
for k, v in c.most_common(25):
    print(v, '/' + k)
print('--- unique samples ---')
seen = set()
for rel, u, path in broken:
    key = re.sub(r'[^/]+$', '', path)
    if key in seen:
        continue
    seen.add(key)
    print(f'{rel}: {u} -> {path}')
    if len(seen) >= 30:
        break
