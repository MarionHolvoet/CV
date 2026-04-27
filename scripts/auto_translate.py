"""
auto_translate.py — Google-Translate-powered automatic French translation for tex_watch.py

Compares the current English CV content against the cached FR translations in
tex_watch.py and only sends NEW or CHANGED strings to Google Translate, then
writes the results back into the FR dict in tex_watch.py.

Usage:
    python scripts/auto_translate.py            # translate missing entries
    python scripts/auto_translate.py --force    # retranslate everything

Requires:
    pip install deep-translator
"""


import re
import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
import json
import hashlib
from pathlib import Path

# ── Resolve paths ──────────────────────────────────────────────────────────────
SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_DIR    = SCRIPTS_DIR.parent
sys.path.insert(0, str(REPO_DIR))

TEX_FILE        = REPO_DIR / "CV_Marion_Holvoet.tex"
TEX_WATCH_FILE  = REPO_DIR / "tex_watch.py"
CACHE_FILE      = REPO_DIR / ".translation_cache.json"   # hash → FR text


# ── Cache helpers ──────────────────────────────────────────────────────────────
def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}

def save_cache(cache: dict):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

def cache_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


# ── Translation ────────────────────────────────────────────────────────────────
# Terms that must NOT be translated (passed through DeepL as non-translatable)
GLOSSARY_TERMS = [
    "C++", "Go", "Python", "JavaScript", "CMake", "Git", "GitLab", "Docker",
    "Yocto", "Mender", "Perforce", "REST API", "HTTPS", "HDF5",
    "GoogleTest", "Pytest", "CI/CD", "Qt", "Svelte", "GitHub Copilot",
    "Boost", "Embedded Linux", "ARM", "x86", "Linux", "MacOS", "Windows", "OTA",
    "Tizen", "Node.js", "Modbus", "STM32", "SDK", "I2C", "OOP", "UML", "arc42",
]

# Masculine → feminine corrections applied after every translation.
# Google Translate always produces masculine agreements — this fixes them.
FEMININE_CORRECTIONS = [
    # adjectives / participles
    (r"\baxé\b",           "axée"),
    (r"\bspécialisé\b",    "spécialisée"),
    (r"\bcertifié\b",      "certifiée"),
    (r"\bprofessionnel\b", "professionnelle"),
    (r"\bindépendant\b",   "indépendante"),
    (r"\btravailleur\b",   "travailleuse"),
    (r"\bpenseur\b",       "penseuse"),
    (r"\bpositif\b",       "positive"),
    (r"\bclair\b",         "claire"),
    (r"\bcommunicateur\b", "communicatrice"),
    (r"\bcollaboratif\b",  "collaborative"),
    (r"\borienté\b",       "orientée"),
    # nouns
    (r"\bstagiaire chercheur\b", "stagiaire chercheuse"),
    (r"\badministrateur\b",      "administratrice"),
    (r"\bDéfenseur\b",           "Défenseure"),
    # word-order fixes (must come after gender corrections above)
    (r"GitLab\s+administratrice\b", "Administratrice GitLab"),
]

def _apply_feminine(text: str) -> str:
    """Apply feminine grammar corrections to a translated French string."""
    import re as _re
    for pattern, replacement in FEMININE_CORRECTIONS:
        def _make_repl(repl):
            def _repl(m):
                # Preserve leading capitalisation of the matched token
                return repl[0].upper() + repl[1:] if m.group(0)[0].isupper() else repl
            return _repl
        text = _re.sub(pattern, _make_repl(replacement), text, flags=_re.IGNORECASE)
    return text

def _fix_capitalization(text: str) -> str:
    """Capitalize first letter after bold closing tags and sentence boundaries."""
    import re as _re
    # After </b> + whitespace (incl. \xa0 inserted by Google for French punctuation)
    text = _re.sub(
        r'(</b>[\xa0\s]+)([a-z\u00e0-\u00ff])',
        lambda m: m.group(1) + m.group(2).upper(),
        text,
    )
    # After ". ": capitalize first letter of next sentence
    text = _re.sub(
        r'(\.\s+)([a-z\u00e0-\u00ff])',
        lambda m: m.group(1) + m.group(2).upper(),
        text,
    )
    return text

def translate_text(text: str, cache: dict, force: bool = False) -> str:
    """Translate a single string EN→FR, using cache to avoid redundant API calls."""
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        print("[translate] ERROR: deep-translator not installed. Run: pip install deep-translator")
        sys.exit(1)

    key = cache_key(text)
    if not force and key in cache:
        return cache[key]

    # Protect HTML entities (e.g. &amp;) so the translator cannot mangle them
    entity_map = {}
    protected = text
    for m in re.finditer(r'&[a-z]+;', text):
        entity = m.group(0)
        if entity not in entity_map.values():
            ph = f"ENT{len(entity_map):02d}"
            entity_map[ph] = entity
    for ph, entity in entity_map.items():
        protected = protected.replace(entity, ph)

    # Protect known tech terms with placeholders so Google Translate leaves them alone
    placeholders = {}
    for term in sorted(GLOSSARY_TERMS, key=len, reverse=True):
        if term in protected:
            ph = f"TECH{len(placeholders):03d}"
            placeholders[ph] = term
            protected = protected.replace(term, ph)

    translated = GoogleTranslator(source="en", target="fr").translate(protected)

    # Restore tech-term placeholders
    for ph, term in placeholders.items():
        translated = translated.replace(ph, term)

    # Restore HTML entities
    for ph, entity in entity_map.items():
        translated = translated.replace(ph, entity)

    # Fix "et amp;" mangling introduced by some translator versions
    import re as _re2
    translated = _re2.sub(r'\bet amp;(\s)', r'&amp;\1', translated)

    # Apply feminine grammar corrections
    translated = _apply_feminine(translated)

    # Fix sentence-start capitalisation lost during translation
    translated = _fix_capitalization(translated)

    cache[key] = translated
    return translated


def translate_list(items: list, cache: dict, force: bool) -> list:
    return [translate_text(item, cache, force) for item in items]


# ── Parse current EN content from tex_watch ───────────────────────────────────
def get_current_en_content() -> dict:
    """Import tex_watch and parse the TeX to get current English content."""
    import tex_watch
    data = tex_watch.parse_tex(TEX_FILE)
    left  = data["left"]
    right = data["right"]

    companies = []
    for exp in right["experience"]:
        company_key = exp["company"].split(" | ")[0].split("\u202f|")[0].strip()
        companies.append({
            "key":   company_key,
            "items": exp["items"],
        })

    return {
        "profile":   left.get("profile_raw", ""),
        "skills":    left["skills"],
        "traits":    left["traits"],
        "companies": companies,
        "edu":       right["education"],
    }


# ── Write back to tex_watch.py ─────────────────────────────────────────────────
def _replace_list_in_source(source: str, section_key: str, new_items: list) -> str:
    """
    Replace the list values for a given key inside the FR dict in tex_watch.py source.
    Handles both "skills_fr" / "traits_fr" style and nested "exp_items_fr" sub-keys.
    """
    # Build the replacement list literal
    items_str = ",\n        ".join(f'"{item}"' for item in new_items)
    replacement = f'[\n        {items_str},\n    ]'

    pattern = rf'("{re.escape(section_key)}"\s*:\s*)\[.*?\]'
    new_source = re.sub(pattern, lambda m: m.group(1) + replacement, source, flags=re.DOTALL)
    return new_source


def _replace_nested_list_in_source(source: str, outer_key: str, inner_key: str, new_items: list) -> str:
    """Replace a list inside a nested dict (e.g. exp_items_fr → "Metrolab Technology SA")."""
    items_str = ",\n            ".join(f'"{item}"' for item in new_items)
    replacement_list = f'[\n            {items_str},\n        ]'

    # Find the outer dict block
    outer_pattern = rf'("{re.escape(outer_key)}"\s*:\s*\{{)(.*?)(\}})'
    outer_match = re.search(outer_pattern, source, re.DOTALL)
    if not outer_match:
        return source

    inner_block = outer_match.group(2)
    inner_pattern = rf'("{re.escape(inner_key)}"\s*:\s*)\[.*?\]'
    new_inner = re.sub(inner_pattern, lambda m: m.group(1) + replacement_list, inner_block, flags=re.DOTALL)

    return source[:outer_match.start(2)] + new_inner + source[outer_match.end(2):]


# ── Main ───────────────────────────────────────────────────────────────────────
def run(force: bool = False) -> dict:
    """Translate missing/changed EN strings and write them back to tex_watch.py.
    Returns the updated FR dicts so callers can update their in-memory FR directly."""
    import tex_watch

    print("[translate] Loading cache...")
    cache = load_cache()

    print("[translate] Parsing TeX for current EN content...")
    en = get_current_en_content()

    source = TEX_WATCH_FILE.read_text(encoding="utf-8")
    changed = False

    # ── Skills ──
    print("[translate] Checking skills...")
    fr_skills = tex_watch.FR["skills_fr"]
    new_skills = []
    for i, skill_en in enumerate(en["skills"]):
        if not force and i < len(fr_skills) and fr_skills[i] and cache_key(skill_en) in cache:
            new_skills.append(fr_skills[i])
        else:
            fr = translate_text(skill_en, cache, force)
            new_skills.append(fr)
            if i >= len(fr_skills) or fr != fr_skills[i]:
                changed = True
                print(f"  skill: {skill_en!r} → {fr!r}")
    if new_skills != fr_skills:
        source = _replace_list_in_source(source, "skills_fr", new_skills)
        changed = True

    # ── Traits ──
    print("[translate] Checking traits...")
    fr_traits = tex_watch.FR["traits_fr"]
    new_traits = []
    for i, trait_en in enumerate(en["traits"]):
        if not force and i < len(fr_traits) and fr_traits[i] and cache_key(trait_en) in cache:
            new_traits.append(fr_traits[i])
        else:
            fr = translate_text(trait_en, cache, force)
            new_traits.append(fr)
            if i >= len(fr_traits) or fr != fr_traits[i]:
                changed = True
                print(f"  trait: {trait_en!r} → {fr!r}")
    if new_traits != fr_traits:
        source = _replace_list_in_source(source, "traits_fr", new_traits)
        changed = True

    # ── Experience bullets ──
    print("[translate] Checking experience bullets...")
    exp_fr = dict(tex_watch.FR["exp_items_fr"])
    ottobock_idx = 0
    for company_data in en["companies"]:
        key = company_data["key"]
        items_en = company_data["items"]

        # Determine the cache key used in FR dict
        if "Ottobock" in key:
            ottobock_idx += 1
            fr_key = f"Ottobock_{ottobock_idx}"
        else:
            fr_key = key

        existing_fr = tex_watch.FR["exp_items_fr"].get(fr_key, [])
        new_fr_items = []
        for i, item_en in enumerate(items_en):
            en_stripped = re.sub(r"<[^>]+>", "", item_en).strip()
            if not force and i < len(existing_fr) and cache_key(en_stripped) in cache:
                new_fr_items.append(existing_fr[i])
            else:
                fr = translate_text(item_en, cache, force)
                new_fr_items.append(fr)
                if i >= len(existing_fr) or fr != existing_fr[i]:
                    changed = True
                    print(f"  [{fr_key}] bullet {i}: translated")
        if new_fr_items != existing_fr:
            source = _replace_nested_list_in_source(source, "exp_items_fr", fr_key, new_fr_items)
            changed = True
        exp_fr[fr_key] = new_fr_items

    # ── Write back ──
    if changed:
        print("[translate] Writing updated translations to tex_watch.py...")
        TEX_WATCH_FILE.write_text(source, encoding="utf-8")
        save_cache(cache)
        print("[translate] Done.")
    else:
        print("[translate] All translations up to date — nothing to do.")

    return {
        "skills_fr":    new_skills,
        "traits_fr":    new_traits,
        "exp_items_fr": exp_fr,
    }


if __name__ == "__main__":
    force = "--force" in sys.argv
    run(force=force)
