import json, hashlib
from pathlib import Path

# ── Fix tex_watch.py ──────────────────────────────────────────────────────────
tw_path = Path("tex_watch.py")
tw = tw_path.read_text(encoding="utf-8")

OLD = (
    "<b>Outillage et amp; Pratiques :</b> environnements de développement basés sur Linux "
    "avec des systèmes de construction basés sur CMake. administratrice GitLab. Pilotage de "
    "la création et du déploiement de pipelines GitLab CI/CD, y compris des images Docker "
    "personnalisées avec la chaîne d'outils Yocto SDKs. Défenseur du code propre."
)
NEW = (
    "<b>Outillage &amp; Pratiques :</b> Environnements de développement basés sur Linux "
    "avec des systèmes de construction basés sur CMake. Administratrice GitLab. Pilotage de "
    "la création et du déploiement de pipelines GitLab CI/CD. Images Docker personnalisées "
    "avec des SDK de chaîne d'outils Yocto. Défenseure du code propre."
)

if OLD in tw:
    tw_path.write_text(tw.replace(OLD, NEW), encoding="utf-8")
    print("[OK] Fixed tex_watch.py")
else:
    print("[WARN] Pattern not found in tex_watch.py")
    # Try to find the line
    for i, line in enumerate(tw.splitlines(), 1):
        if "Outillage" in line and "Pratiques" in line:
            print(f"  Line {i}: {line[:100]!r}")

# ── Fix .translation_cache.json ──────────────────────────────────────────────
cache_path = Path(".translation_cache.json")
cache = json.loads(cache_path.read_text(encoding="utf-8"))

# Find and fix any cache entry with the bad translation
fixed = 0
for k, v in list(cache.items()):
    if OLD in v:
        cache[k] = v.replace(OLD, NEW)
        fixed += 1

# Also update the entry keyed by the current EN bullet text
def ck(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]

# The EN text as it would be sent to translate (with &amp; from HTML conversion)
en_bullet = (
    "<b>Tooling &amp; Practices:</b> Version control with Git. GitLab Administrator. "
    "Linux-based development environments with CMake-based build systems. Drove the "
    "creation and rollout of GitLab CI/CD pipelines. Custom Docker images with Yocto "
    "toolchain SDKs. Clean code practices."
)
key = ck(en_bullet)
cache[key] = NEW
print(f"[OK] Set cache[{key}] to corrected translation")

if fixed:
    print(f"[OK] Fixed {fixed} cache entries containing old translation")

cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
print("[OK] Cache saved")
