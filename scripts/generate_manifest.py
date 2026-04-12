import json
import os
import re
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================
ASSETS_REPO_ROOT = Path(r"C:\Users\aaron\Documents\ConquestCodex\GitHub\conquest-codex-assets")
POKEMON_ROOT = ASSETS_REPO_ROOT / "pokemon"

MANIFEST_ROOT = ASSETS_REPO_ROOT / "manifest"
MANIFEST_POKEMON_DIR = MANIFEST_ROOT / "pokemon"

ASSET_BASE = "https://raw.githubusercontent.com/AaronsAron/conquest-codex-assets/main/"

THUMB_ICON_REL = "icons/full-left.png"  # thumb uses icons/full-left for all variants

EMOTION_ORDER = ["default", "joyful", "sad", "fierce", "shocked"]

REQUIRED_ICON_FILES = [
    "icons/full-left.png",
    "icons/full-right.png",
    "icons/cropped-left.png",
    "icons/cropped-right.png",
]

ALT_ANIM_FILE_RE = re.compile(r"^animation_alt-(.+)\.png$", re.IGNORECASE)

# A derived/alternate variant is detected if:
# - inheritsFrom is not null
# OR
# - tags includes "alternate" (extra safety)
ALT_TAG = "alternate"


# ============================================================
# JSON-ish tolerant parsing (in case any meta still has trailing commas)
# ============================================================
def strip_trailing_commas_outside_strings(s: str) -> str:
    out = []
    in_str = False
    esc = False
    i = 0
    while i < len(s):
        ch = s[i]
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == ",":
            j = i + 1
            while j < len(s) and s[j] in " \t\r\n":
                j += 1
            if j < len(s) and s[j] in "}]":
                i += 1
                continue
        out.append(ch)
        i += 1
    return "".join(out)

def fix_adjacent_object_tokens(s: str) -> str:
    out = []
    in_str = False
    esc = False
    i = 0
    while i < len(s):
        ch = s[i]
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "}" and i + 1 < len(s) and s[i + 1] == "{":
            out.append("},{")
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)

def load_meta_json(meta_path: Path):
    raw = meta_path.read_text(encoding="utf-8")
    try:
        return json.loads(raw), False
    except Exception:
        repaired = strip_trailing_commas_outside_strings(fix_adjacent_object_tokens(raw))
        return json.loads(repaired), True


# ============================================================
# Deep merge (Option A): override only provided subkeys
# Dicts merge recursively, lists replaced, scalars replaced (None does not override)
# ============================================================
def deep_merge(base, override):
    if isinstance(base, dict) and isinstance(override, dict):
        out = dict(base)
        for k, v in override.items():
            if k in out:
                out[k] = deep_merge(out[k], v)
            else:
                out[k] = v
        return out
    if isinstance(override, list):
        return override
    if override is None:
        return base
    return override


# ============================================================
# Helpers
# ============================================================
def iso_now_local():
    return datetime.now().astimezone().isoformat(timespec="seconds")

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def exists_file(variant_dir: Path, rel: str) -> bool:
    return (variant_dir / rel).exists()

def safe_listdir(p: Path):
    if not p.exists():
        return []
    return list(p.iterdir())

def dedupe_preserve_order(seq):
    seen = set()
    out = []
    for x in seq:
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out

def extract_names_from_credit_list(arr):
    names = []
    if not isinstance(arr, list):
        return names
    for ent in arr:
        if isinstance(ent, dict):
            nm = ent.get("name")
            if isinstance(nm, str) and nm.strip():
                names.append(nm.strip())
    return names

def extract_artists(meta):
    credits = meta.get("credits", {})
    if not isinstance(credits, dict):
        credits = {}

    anim = extract_names_from_credit_list(credits.get("animation", []))
    icons = extract_names_from_credit_list(credits.get("icons", []))

    portraits = []
    p = credits.get("portraits", {})
    if isinstance(p, dict):
        portraits += extract_names_from_credit_list(p.get("profile", []))
        portraits += extract_names_from_credit_list(p.get("intro", []))

    emotions = []
    emo = credits.get("emotions")
    if isinstance(emo, dict):
        for _, v in emo.items():
            emotions += extract_names_from_credit_list(v)

    anim = dedupe_preserve_order(anim)
    icons = dedupe_preserve_order(icons)
    portraits = dedupe_preserve_order(portraits)
    emotions = dedupe_preserve_order(emotions)

    all_names = dedupe_preserve_order(anim + icons + portraits + emotions)

    return {
        "artistsAll": all_names,
        "artistsAnimation": anim,
        "artistsIcons": icons,
        "artistsPortraits": portraits,
        "artistsEmotions": emotions,
    }

def parse_date(s):
    if not isinstance(s, str) or not s.strip():
        return None
    s = s.strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))), s

def max_date_str(date_strs):
    best = None
    best_s = ""
    for ds in date_strs:
        parsed = parse_date(ds)
        if parsed is None:
            continue
        t, s = parsed
        if best is None or t > best:
            best = t
            best_s = s
    return best_s

def extract_sort_keys(meta):
    dm = meta.get("dateModified", {})
    if not isinstance(dm, dict):
        dm = {}

    d_anim = dm.get("animation", "") if isinstance(dm.get("animation", ""), str) else ""
    d_icons = dm.get("icons", "") if isinstance(dm.get("icons", ""), str) else ""

    portraits = dm.get("portraits", {})
    d_profile = ""
    d_intro = ""
    if isinstance(portraits, dict):
        d_profile = portraits.get("profile", "") if isinstance(portraits.get("profile", ""), str) else ""
        d_intro = portraits.get("intro", "") if isinstance(portraits.get("intro", ""), str) else ""

    d_portraits_max = max_date_str([d_profile, d_intro])

    emo = dm.get("emotions", {})
    emo_dates = []
    if isinstance(emo, dict):
        for _, v in emo.items():
            if isinstance(v, str):
                emo_dates.append(v)
    d_emo_max = max_date_str(emo_dates)

    d_max = max_date_str([d_anim, d_icons, d_profile, d_intro, d_emo_max])

    out = {
        "dateModifiedMax": d_max,
        "dateModifiedAnimation": d_anim,
        "dateModifiedIcons": d_icons,
        "dateModifiedPortraitsMax": d_portraits_max
    }
    if d_emo_max:
        out["dateModifiedEmotionsMax"] = d_emo_max
    return out

def compute_has_and_emotions(variant_dir: Path, meta):
    has_animation = exists_file(variant_dir, "battle/animation.png")
    has_icons = all(exists_file(variant_dir, f) for f in REQUIRED_ICON_FILES)
    has_profile = exists_file(variant_dir, "portraits/profile.png")
    has_intro = exists_file(variant_dir, "portraits/intro.png")

    pe = meta.get("portraitEmotions", [])
    if not isinstance(pe, list):
        pe = []
    pe_set = {x for x in pe if isinstance(x, str)}
    emo_present = [e for e in EMOTION_ORDER if e in pe_set]

    has_emotions = False
    if emo_present:
        has_emotions = all(exists_file(variant_dir, f"portraits/{e}.png") for e in emo_present)

    has_obj = {
        "animation": bool(has_animation),
        "icons": bool(has_icons),
        "profile": bool(has_profile),
        "intro": bool(has_intro),
        "emotions": bool(has_emotions)
    }
    return has_obj, emo_present

def build_paths(pokemon_id: str, variant_id: str, emo_present):
    base = f"pokemon/{pokemon_id}/{variant_id}"
    paths = {
        "meta": f"{base}/meta.json",
        "battle": {
            "animation": f"{base}/battle/animation.png"
        },
        "icons": {
            "fullLeft": f"{base}/icons/full-left.png",
            "fullRight": f"{base}/icons/full-right.png",
            "croppedLeft": f"{base}/icons/cropped-left.png",
            "croppedRight": f"{base}/icons/cropped-right.png"
        },
        "portraits": {
            "profile": f"{base}/portraits/profile.png",
            "intro": f"{base}/portraits/intro.png",
            "emotions": {}
        }
    }
    for e in emo_present:
        paths["portraits"]["emotions"][e] = f"{base}/portraits/{e}.png"
    return paths

def find_file_alternates_in_variant(variant_dir: Path, pokemon_id: str, variant_id: str):
    alts = []
    battle_dir = variant_dir / "battle"
    if not battle_dir.exists():
        return alts
    for f in safe_listdir(battle_dir):
        if not f.is_file():
            continue
        m = ALT_ANIM_FILE_RE.match(f.name)
        if m:
            suffix = m.group(1)
            alts.append({
                "id": f"alt-{suffix}",
                "path": f"pokemon/{pokemon_id}/{variant_id}/battle/{f.name}"
            })
    alts.sort(key=lambda x: x["id"])
    return alts


# ============================================================
# Formatting rules
# ============================================================
# Inline arrays:
# - types, tags
# - all artists* arrays
# - artists (used on alternates in detail)
# - portraitEmotions
INLINE_LIST_KEY_NAMES = {
    "types", "tags",
    "artistsAll", "artistsAnimation", "artistsIcons", "artistsPortraits", "artistsEmotions",
    "artists",
    "portraitEmotions"
}

# Inline objects:
# - animationFlags should be single-line in manifest/pokemon
INLINE_OBJECT_KEY_NAMES = {"animationFlags"}

def dumps_inline_list(lst):
    return json.dumps(lst, ensure_ascii=False, separators=(", ", ": "))

def dumps_inline_obj(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(", ", ": "))

def is_inline_list(key, value):
    return isinstance(value, list) and (key in INLINE_LIST_KEY_NAMES)

def is_inline_object(key, value):
    return isinstance(value, dict) and (key in INLINE_OBJECT_KEY_NAMES)

def render(value, indent=0, key_name=None):
    """
    Recursive renderer:
    - dict: pretty multi-line (except inline-object keys)
    - list: inline if key_name matches rules; otherwise pretty multi-line
    - Special: insert blank line between items of the 'variants' object in detail manifests
    """
    pad = " " * indent

    if isinstance(value, dict):
        if is_inline_object(key_name, value):
            return dumps_inline_obj(value)

        if not value:
            return "{}"

        items = list(value.items())
        lines = ["{"]

        for idx, (k, v) in enumerate(items):
            comma = "," if idx < len(items) - 1 else ""
            rendered = render(v, indent + 2, key_name=k)

            # If rendered is multi-line, indent continuation lines
            if "\n" in rendered:
                rendered_lines = rendered.split("\n")
                rendered_lines = [rendered_lines[0]] + [(" " * (indent + 2)) + x for x in rendered_lines[1:]]
                rendered = "\n".join(rendered_lines)

            lines.append(f'{pad}  "{k}": {rendered}{comma}')

            # Blank line between variants blocks (only inside the 'variants' dict)
            if key_name == "variants" and idx < len(items) - 1:
                lines.append("")  # empty line (no spaces)

        lines.append(f"{pad}}}")
        return "\n".join(lines)

    if isinstance(value, list):
        if is_inline_list(key_name, value):
            return dumps_inline_list(value)

        if not value:
            return "[]"

        lines = ["["]
        for idx, item in enumerate(value):
            comma = "," if idx < len(value) - 1 else ""
            rendered = render(item, indent + 2, key_name=None)

            if "\n" in rendered:
                rendered_lines = rendered.split("\n")
                rendered_lines = [rendered_lines[0]] + [(" " * (indent + 2)) + x for x in rendered_lines[1:]]
                rendered = "\n".join(rendered_lines)

            lines.append(f"{pad}  {rendered}{comma}")

            # ✅ Blank line between each pokemon row in the main index
            if key_name == "rows" and idx < len(value) - 1:
                lines.append("")  # empty line

        lines.append(f"{pad}]")
        return "\n".join(lines)

    # Scalars
    return json.dumps(value, ensure_ascii=False)

def write_json(path: Path, obj):
    path.write_text(render(obj, indent=0) + "\n", encoding="utf-8")


# ============================================================
# Main
# ============================================================
def main():
    if not POKEMON_ROOT.exists():
        raise RuntimeError(f"Pokemon root not found: {POKEMON_ROOT}")

    ensure_dir(MANIFEST_ROOT)
    ensure_dir(MANIFEST_POKEMON_DIR)

    report = {
        "run": {
            "generatedAt": iso_now_local(),
            "assetsRepoRoot": str(ASSETS_REPO_ROOT),
            "pokemonRoot": str(POKEMON_ROOT),
            "manifestRoot": str(MANIFEST_ROOT),
            "assetBase": ASSET_BASE
        },
        "counts": {
            "pokemonFolders": 0,
            "variantFolders": 0,
            "primaryVariants": 0,
            "derivedVariants": 0,
            "metaParsed": 0,
            "metaParsedWithRepair": 0,
            "metaErrors": 0,
            "rowsWritten": 0,
            "detailFilesWritten": 0
        },
        "errors": [],
        "warnings": []
    }

    # Level 1 index: one row per PRIMARY variant (each listed separately)
    index = {
        "schemaVersion": 1,
        "generatedAt": report["run"]["generatedAt"],
        "assetBase": ASSET_BASE,
        "rows": []
    }

    # Scan each pokemon folder
    for pokemon_dir in sorted(POKEMON_ROOT.iterdir()):
        if not pokemon_dir.is_dir():
            continue

        pokemon_id = pokemon_dir.name
        report["counts"]["pokemonFolders"] += 1

        # Load all variant metas for this pokemon
        metas = {}
        variant_dirs = {}

        for vdir in sorted(pokemon_dir.iterdir()):
            if not vdir.is_dir():
                continue
            meta_path = vdir / "meta.json"
            if not meta_path.exists():
                continue

            report["counts"]["variantFolders"] += 1
            variant_id = vdir.name
            variant_dirs[variant_id] = vdir

            try:
                meta, repaired = load_meta_json(meta_path)
                report["counts"]["metaParsed"] += 1
                if repaired:
                    report["counts"]["metaParsedWithRepair"] += 1
                metas[variant_id] = meta
            except Exception as e:
                report["counts"]["metaErrors"] += 1
                report["errors"].append({"file": str(meta_path), "error": str(e)})
                continue

        if not metas:
            report["warnings"].append({"pokemonId": pokemon_id, "reason": "No variant meta.json files parsed"})
            continue

        primary_ids = []
        derived_ids = []

        for vid, meta in metas.items():
            inh = meta.get("inheritsFrom", None)
            tags = meta.get("tags", [])
            is_alt_tagged = isinstance(tags, list) and (ALT_TAG in tags)
            is_derived = (inh is not None) or is_alt_tagged
            if is_derived:
                derived_ids.append(vid)
            else:
                primary_ids.append(vid)

        report["counts"]["primaryVariants"] += len(primary_ids)
        report["counts"]["derivedVariants"] += len(derived_ids)

        # Detail manifest for this pokemon
        detail = {
            "pokemonId": pokemon_id,
            "nationalDexNumber": None,
            "variants": {}
        }

        def resolve_meta(vid):
            m = metas[vid]
            inh = m.get("inheritsFrom", None)
            if isinstance(inh, str) and inh.strip():
                base_id = inh.strip()
                if base_id in metas:
                    return deep_merge(metas[base_id], m)
                else:
                    report["warnings"].append({
                        "pokemonId": pokemon_id,
                        "variantId": vid,
                        "reason": f'inheritsFrom "{base_id}" not found'
                    })
                    return m
            return m

        # Primary variants
        for vid in sorted(primary_ids):
            meta_eff = resolve_meta(vid)
            vdir = variant_dirs[vid]

            ndex = meta_eff.get("nationalDexNumber", None)
            if detail["nationalDexNumber"] is None and isinstance(ndex, int):
                detail["nationalDexNumber"] = ndex

            display_name = meta_eff.get("displayName", "")
            types = meta_eff.get("types", [])
            tags = meta_eff.get("tags", [])
            stats = meta_eff.get("stats", None)
            animation_flags = meta_eff.get("animationFlags", None)
            idle_motion = meta_eff.get("idleMotion", None)

            if not isinstance(types, list):
                types = []
            if not isinstance(tags, list):
                tags = []
            if not isinstance(display_name, str):
                display_name = ""

            has_obj, emo_present = compute_has_and_emotions(vdir, meta_eff)
            paths = build_paths(pokemon_id, vid, emo_present)

            file_alts = find_file_alternates_in_variant(vdir, pokemon_id, vid)

            detail_variant = {
                "displayName": display_name,
                "types": types,
                "tags": tags,
                "stats": stats,
                "animationFlags": animation_flags,
                "idleMotion": idle_motion,
                "portraitEmotions": emo_present,
                "paths": paths
            }

            if file_alts:
                detail_variant.setdefault("alternates", {})
                detail_variant["alternates"]["battleAnimation"] = [
                    {"id": a["id"], "path": a["path"]} for a in file_alts
                ]

            detail["variants"][vid] = detail_variant

        # Derived variants attached as alternates
        for dvid in sorted(derived_ids):
            dmeta = metas[dvid]
            inh = dmeta.get("inheritsFrom", None)
            if not isinstance(inh, str) or not inh.strip():
                report["warnings"].append({
                    "pokemonId": pokemon_id,
                    "variantId": dvid,
                    "reason": "Derived/alternate variant missing inheritsFrom string"
                })
                continue

            base_vid = inh.strip()
            if base_vid not in detail["variants"]:
                report["warnings"].append({
                    "pokemonId": pokemon_id,
                    "variantId": dvid,
                    "reason": f'Cannot attach alternate; base variant "{base_vid}" not in detail variants'
                })
                continue

            meta_eff = resolve_meta(dvid)
            vdir = variant_dirs[dvid]

            alt_entry_common = {"id": dvid}

            # Battle animation alternate
            if exists_file(vdir, "battle/animation.png"):
                alt_anim = dict(alt_entry_common)
                alt_anim["path"] = f"pokemon/{pokemon_id}/{dvid}/battle/animation.png"
                alt_anim["animationFlags"] = meta_eff.get("animationFlags", None)

                artists = extract_artists(meta_eff)
                sort_keys = extract_sort_keys(meta_eff)
                if artists.get("artistsAnimation"):
                    alt_anim["artists"] = artists["artistsAnimation"]
                if sort_keys.get("dateModifiedAnimation"):
                    alt_anim["dateModified"] = sort_keys["dateModifiedAnimation"]

                detail["variants"][base_vid].setdefault("alternates", {})
                detail["variants"][base_vid]["alternates"].setdefault("battleAnimation", [])
                detail["variants"][base_vid]["alternates"]["battleAnimation"].append(alt_anim)

            # Optional: icon-set alternate
            if (vdir / "icons").exists() and any(p.is_file() for p in safe_listdir(vdir / "icons")):
                alt_icons = dict(alt_entry_common)
                alt_icons["paths"] = {
                    "fullLeft": f"pokemon/{pokemon_id}/{dvid}/icons/full-left.png",
                    "fullRight": f"pokemon/{pokemon_id}/{dvid}/icons/full-right.png",
                    "croppedLeft": f"pokemon/{pokemon_id}/{dvid}/icons/cropped-left.png",
                    "croppedRight": f"pokemon/{pokemon_id}/{dvid}/icons/cropped-right.png",
                }
                artists = extract_artists(meta_eff)
                sort_keys = extract_sort_keys(meta_eff)
                if artists.get("artistsIcons"):
                    alt_icons["artists"] = artists["artistsIcons"]
                if sort_keys.get("dateModifiedIcons"):
                    alt_icons["dateModified"] = sort_keys["dateModifiedIcons"]

                detail["variants"][base_vid].setdefault("alternates", {})
                detail["variants"][base_vid]["alternates"].setdefault("icons", [])
                detail["variants"][base_vid]["alternates"]["icons"].append(alt_icons)

        # Sort alternates for stable diffs
        for base_vid, vobj in detail["variants"].items():
            alts = vobj.get("alternates", {})
            if isinstance(alts, dict):
                if isinstance(alts.get("battleAnimation"), list):
                    alts["battleAnimation"].sort(key=lambda x: x.get("id", ""))
                if isinstance(alts.get("icons"), list):
                    alts["icons"].sort(key=lambda x: x.get("id", ""))
                vobj["alternates"] = alts

        # Write detail file (with requested formatting rules)
        out_detail = MANIFEST_POKEMON_DIR / f"{pokemon_id}.json"
        write_json(out_detail, detail)
        report["counts"]["detailFilesWritten"] += 1

        # Primary variants to index rows
        for vid in sorted(primary_ids):
            meta_eff = resolve_meta(vid)
            vdir = variant_dirs[vid]

            display_name = meta_eff.get("displayName", "")
            ndex = meta_eff.get("nationalDexNumber", None)
            types = meta_eff.get("types", [])
            tags = meta_eff.get("tags", [])
            stats = meta_eff.get("stats", None)

            if not isinstance(display_name, str):
                display_name = ""
            if not isinstance(types, list):
                types = []
            if not isinstance(tags, list):
                tags = []

            has_obj, _ = compute_has_and_emotions(vdir, meta_eff)
            thumb_icon = f"pokemon/{pokemon_id}/{vid}/{THUMB_ICON_REL}"

            sort_keys = extract_sort_keys(meta_eff)
            search_keys = extract_artists(meta_eff)

            stats_out = None
            if isinstance(stats, dict):
                try:
                    stats_out = {
                        "hp": int(stats.get("hp", 0)),
                        "attack": int(stats.get("attack", 0)),
                        "defense": int(stats.get("defense", 0)),
                        "speed": int(stats.get("speed", 0)),
                        "bst": int(stats.get("bst", 0)),
                    }
                except Exception:
                    stats_out = None

            row = {
                "pokemonId": pokemon_id,
                "variantId": vid,
                "displayName": display_name,
                "nationalDexNumber": ndex,
                "types": types,
                "tags": tags,
                "thumb": {"icon": thumb_icon},
                "has": has_obj,
                "stats": stats_out,
                "sortKeys": sort_keys,
                "searchKeys": search_keys,
                "detail": f"manifest/pokemon/{pokemon_id}.json#{vid}"
            }

            index["rows"].append(row)
            report["counts"]["rowsWritten"] += 1

    # Sort index rows for stable output
    def row_sort_key(r):
        nd = r.get("nationalDexNumber")
        nd = nd if isinstance(nd, int) else 99999
        return (nd, r.get("pokemonId", ""), r.get("variantId", ""))

    index["rows"].sort(key=row_sort_key)

    out_index = MANIFEST_ROOT / "index.json"
    out_report = MANIFEST_ROOT / "manifest_report.json"

    write_json(out_index, index)
    write_json(out_report, report)

    print("✅ Manifest generation complete.")
    print(f"Index:  {out_index}")
    print(f"Detail: {MANIFEST_POKEMON_DIR}  ({report['counts']['detailFilesWritten']} files)")
    print(f"Report: {out_report}")
    print(f"Meta parsed: {report['counts']['metaParsed']} (repaired: {report['counts']['metaParsedWithRepair']}), errors: {report['counts']['metaErrors']}")


if __name__ == "__main__":
    main()