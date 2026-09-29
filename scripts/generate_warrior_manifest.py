import json
import re
from datetime import datetime
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

ASSETS_REPO_ROOT = Path(
    r"C:\Users\aaron\Documents\ConquestCodex\GitHub"
    r"\conquest-codex-assets"
)

WARRIOR_ROOT = ASSETS_REPO_ROOT / "sprites" / "warriors"
WARRIOR_METADATA_ROOT = WARRIOR_ROOT / "metadata-warrior"
ASSET_METADATA_ROOT = WARRIOR_ROOT / "metadata-asset"

MANIFEST_ROOT = ASSETS_REPO_ROOT / "sprites" / "manifest"
MANIFEST_WARRIOR_DIR = MANIFEST_ROOT / "warriors"
WARRIOR_INDEX_PATH = MANIFEST_ROOT / "warrior_index.json"
WARRIOR_REPORT_PATH = MANIFEST_ROOT / "warrior_manifest_report.json"

ASSET_BASE = (
    "https://raw.githubusercontent.com/AaronsAron/conquest-codex-assets/main/sprites/"
)

EXPECTED_META_COUNT = 252

EMOTION_ORDER = [
    "profile",
    "joyful",
    "sad",
    "fierce",
    "shocked",
    "special",
]

ASSET_FILE_LOCATIONS = {
    "characterSelect": "warriors/character-select/{index}.png",
    "battle": "warriors/icons/battle/{index}.png",
    "cropped": "warriors/icons/cropped/{index}.png",
    "full": "warriors/icons/full/{index}.png",
    "intro": "warriors/portraits/intro/{index}.png",
    "overworld": "warriors/portraits/overworld/{index}.png",
    "emotion": "warriors/portraits/emotions/{index}.png",
}

ASSET_METADATA_FILES = {
    "characterSelect": ASSET_METADATA_ROOT / "character-select.json",
    "battle": ASSET_METADATA_ROOT / "icons" / "battle.json",
    "cropped": ASSET_METADATA_ROOT / "icons" / "cropped.json",
    "full": ASSET_METADATA_ROOT / "icons" / "full.json",
    "intro": ASSET_METADATA_ROOT / "portraits" / "intro.json",
    "overworld": ASSET_METADATA_ROOT / "portraits" / "overworld.json",
    "emotion": ASSET_METADATA_ROOT / "portraits" / "emotions.json",
}


# ============================================================
# JSON-ISH TOLERANT PARSING
# ============================================================


def strip_trailing_commas_outside_strings(text: str) -> str:
    output = []
    in_string = False
    escaped = False
    index = 0

    while index < len(text):
        character = text[index]

        if in_string:
            output.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue

        if character == '"':
            in_string = True
            output.append(character)
            index += 1
            continue

        if character == ",":
            next_index = index + 1
            while (
                next_index < len(text)
                and text[next_index] in " \t\r\n"
            ):
                next_index += 1

            if (
                next_index < len(text)
                and text[next_index] in "}]"
            ):
                index += 1
                continue

        output.append(character)
        index += 1

    return "".join(output)


def fix_adjacent_object_tokens(text: str) -> str:
    output = []
    in_string = False
    escaped = False
    index = 0

    while index < len(text):
        character = text[index]

        if in_string:
            output.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue

        if character == '"':
            in_string = True
            output.append(character)
            index += 1
            continue

        if (
            character == "}"
            and index + 1 < len(text)
            and text[index + 1] == "{"
        ):
            output.append("},{")
            index += 2
            continue

        output.append(character)
        index += 1

    return "".join(output)


def load_json_tolerant(path: Path):
    raw = path.read_text(encoding="utf-8-sig")

    try:
        return json.loads(raw), False
    except Exception:
        repaired = strip_trailing_commas_outside_strings(
            fix_adjacent_object_tokens(raw)
        )
        return json.loads(repaired), True


# ============================================================
# GENERAL HELPERS
# ============================================================


def iso_now_local():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def dedupe_preserve_order(values):
    seen = set()
    output = []

    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)

    return output


def format_asset_index(asset_index):
    if asset_index is None:
        return None
    return f"{int(asset_index):04d}"


def asset_relative_path(asset_type, asset_index):
    if asset_index is None:
        return None

    return ASSET_FILE_LOCATIONS[asset_type].format(
        index=format_asset_index(asset_index)
    )


def relative_to_absolute_path(relative_path):
    if not relative_path:
        return None
    return ASSETS_REPO_ROOT / "sprites" / Path(relative_path)


def asset_exists(relative_path):
    absolute_path = relative_to_absolute_path(relative_path)
    return bool(absolute_path and absolute_path.is_file())


def parse_date(value):
    if not isinstance(value, str) or not value.strip():
        return None

    value = value.strip()
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", value)

    if not match:
        return None

    comparable = (
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
    )
    return comparable, value


def max_date_str(date_values):
    best_value = None
    best_string = ""

    for date_value in date_values:
        parsed = parse_date(date_value)
        if parsed is None:
            continue

        comparable, original = parsed
        if best_value is None or comparable > best_value:
            best_value = comparable
            best_string = original

    return best_string


def gallery_sort_key(value):
    if value is None:
        return (999999, 999999, "")

    text = str(value).strip()
    if not text:
        return (999999, 999999, "")

    parts = text.split(".")

    try:
        major = int(parts[0])
    except ValueError:
        return (999999, 999999, text)

    minor = 0
    if len(parts) > 1:
        try:
            minor = int(parts[1])
        except ValueError:
            minor = 0

    return (major, minor, text)


# ============================================================
# ASSET-METADATA LOADING AND RESOLUTION
# ============================================================


def load_asset_metadata(report):
    stores = {}

    for asset_type, metadata_path in ASSET_METADATA_FILES.items():
        if not metadata_path.exists():
            report["errors"].append(
                {
                    "file": str(metadata_path),
                    "error": "Asset-metadata file was not found",
                }
            )
            stores[asset_type] = {}
            continue

        try:
            data, repaired = load_json_tolerant(metadata_path)

            if not isinstance(data, dict):
                raise TypeError(
                    "Asset-metadata file must contain a top-level object"
                )

            stores[asset_type] = data
            report["counts"]["assetMetadataFilesLoaded"] += 1
            report["counts"]["assetMetadataEntriesLoaded"] += len(data)

            if repaired:
                report["counts"][
                    "assetMetadataFilesParsedWithRepair"
                ] += 1

        except Exception as error:
            report["errors"].append(
                {
                    "file": str(metadata_path),
                    "error": str(error),
                }
            )
            stores[asset_type] = {}

    return stores


def resolve_asset_metadata(
    asset_stores,
    asset_type,
    asset_index,
    report,
    warrior_id,
    variant_id,
    logical_asset_name,
):
    if asset_index is None:
        return None

    asset_id = format_asset_index(asset_index)
    store = asset_stores.get(asset_type, {})
    entry = store.get(asset_id)

    if not isinstance(entry, dict):
        report["warnings"].append(
            {
                "warriorId": warrior_id,
                "variantId": variant_id,
                "reason": "Asset metadata entry was not found",
                "asset": logical_asset_name,
                "assetType": asset_type,
                "assetId": asset_id,
            }
        )
        return None

    credits = entry.get("credits", [])
    date_modified = entry.get("dateModified", "")
    history = entry.get("history", [])
    notes = entry.get("notes", "")

    if not isinstance(credits, list):
        credits = []
    if not isinstance(date_modified, str):
        date_modified = ""
    if not isinstance(history, list):
        history = []
    if not isinstance(notes, str):
        notes = ""

    return {
        "credits": credits,
        "dateModified": date_modified,
        "history": history,
        "notes": notes,
    }


# ============================================================
# WARRIOR METADATA VALIDATION
# ============================================================


def validate_meta(meta, meta_path):
    errors = []

    required_fields = [
        "warriorId",
        "variantId",
        "displayName",
        "genderId",
        "tags",
        "galleryNumber",
        "specialityTypeIds",
        "weaknessTypeIds",
        "stats",
        "assetIndexes",
    ]

    for field_name in required_fields:
        if field_name not in meta:
            errors.append(f'Missing required field "{field_name}".')

    warrior_id = meta.get("warriorId")
    variant_id = meta.get("variantId")

    if not isinstance(warrior_id, str) or not warrior_id.strip():
        errors.append("warriorId must be a non-empty string.")

    if not isinstance(variant_id, str) or not variant_id.strip():
        errors.append("variantId must be a non-empty string.")

    expected_warrior_id = meta_path.parent.parent.name
    expected_variant_id = meta_path.parent.name

    if warrior_id != expected_warrior_id:
        errors.append(
            f'warriorId "{warrior_id}" does not match '
            f'folder "{expected_warrior_id}".'
        )

    if variant_id != expected_variant_id:
        errors.append(
            f'variantId "{variant_id}" does not match '
            f'folder "{expected_variant_id}".'
        )

    if meta.get("genderId") not in {"male", "female"}:
        errors.append("genderId must be male or female.")

    for list_field in [
        "tags",
        "specialityTypeIds",
        "weaknessTypeIds",
    ]:
        if not isinstance(meta.get(list_field), list):
            errors.append(f"{list_field} must be a list.")

    stats = meta.get("stats")
    if not isinstance(stats, dict):
        errors.append("stats must be an object.")
    else:
        for stat_name in [
            "power",
            "wisdom",
            "charisma",
            "bst",
            "capacity",
        ]:
            if stat_name not in stats:
                errors.append(f'stats is missing "{stat_name}".')

    if not isinstance(meta.get("assetIndexes"), dict):
        errors.append("assetIndexes must be an object.")

    return errors


# ============================================================
# PATHS, AVAILABILITY, CREDITS, AND DATES
# ============================================================


def build_resolved_assets(meta, asset_stores, report):
    warrior_id = meta["warriorId"]
    variant_id = meta["variantId"]

    indexes = meta.get("assetIndexes", {})
    icon_indexes = indexes.get("icons", {})
    portrait_indexes = indexes.get("portraits", {})
    emotion_indexes = portrait_indexes.get("emotions", {})

    character_select_index = indexes.get("characterSelect")

    asset_specs = [
        {
            "family": "characterSelect",
            "name": "characterSelect",
            "assetType": "characterSelect",
            "index": character_select_index,
        },
        {
            "family": "icons",
            "name": "battle",
            "assetType": "battle",
            "index": icon_indexes.get("battle"),
        },
        {
            "family": "icons",
            "name": "cropped",
            "assetType": "cropped",
            "index": icon_indexes.get("cropped"),
        },
        {
            "family": "icons",
            "name": "full",
            "assetType": "full",
            "index": icon_indexes.get("full"),
        },
        {
            "family": "portraits",
            "name": "intro",
            "assetType": "intro",
            "index": portrait_indexes.get("intro"),
        },
        {
            "family": "portraits",
            "name": "overworld",
            "assetType": "overworld",
            "index": portrait_indexes.get("overworld"),
        },
    ]

    for emotion_name in EMOTION_ORDER:
        asset_specs.append(
            {
                "family": "emotions",
                "name": emotion_name,
                "assetType": "emotion",
                "index": emotion_indexes.get(emotion_name),
            }
        )

    resolved = []

    for spec in asset_specs:
        asset_index = spec["index"]
        relative_path = asset_relative_path(
            spec["assetType"],
            asset_index,
        )

        exists = bool(
            relative_path and asset_exists(relative_path)
        )

        logical_asset_name = (
            spec["name"]
            if spec["family"] == "characterSelect"
            else f"{spec['family']}.{spec['name']}"
        )

        if relative_path and not exists:
            report["warnings"].append(
                {
                    "warriorId": warrior_id,
                    "variantId": variant_id,
                    "reason": "Referenced asset file was not found",
                    "asset": logical_asset_name,
                    "path": relative_path,
                }
            )

        asset_metadata = resolve_asset_metadata(
            asset_stores=asset_stores,
            asset_type=spec["assetType"],
            asset_index=asset_index,
            report=report,
            warrior_id=warrior_id,
            variant_id=variant_id,
            logical_asset_name=logical_asset_name,
        )

        resolved.append(
            {
                **spec,
                "path": relative_path,
                "exists": exists,
                "metadata": asset_metadata,
            }
        )

    return resolved


def build_paths(resolved_assets, warrior_id, variant_id):
    paths = {
        "meta": (
            f"warriors/metadata/{warrior_id}/"
            f"{variant_id}/meta.json"
        ),
        "icons": {},
        "portraits": {"emotions": {}},
    }

    for asset in resolved_assets:
        if not asset["exists"]:
            continue

        family = asset["family"]
        name = asset["name"]
        path = asset["path"]

        if family == "characterSelect":
            paths["characterSelect"] = path
        elif family == "icons":
            paths["icons"][name] = path
        elif family == "portraits":
            paths["portraits"][name] = path
        elif family == "emotions":
            paths["portraits"]["emotions"][name] = path

    if not paths["icons"]:
        paths.pop("icons")

    if not paths["portraits"]["emotions"]:
        paths["portraits"].pop("emotions")

    if not paths["portraits"]:
        paths.pop("portraits")

    return paths


def build_has(resolved_assets):
    lookup = {
        (
            asset["family"],
            asset["name"],
        ): asset["exists"]
        for asset in resolved_assets
    }

    return {
        "characterSelect": lookup.get(
            ("characterSelect", "characterSelect"),
            False,
        ),
        "battleIcon": lookup.get(("icons", "battle"), False),
        "croppedIcon": lookup.get(("icons", "cropped"), False),
        "fullIcon": lookup.get(("icons", "full"), False),
        "introPortrait": lookup.get(("portraits", "intro"), False),
        "overworldPortrait": lookup.get(
            ("portraits", "overworld"),
            False,
        ),
        "emotions": any(
            asset["exists"]
            for asset in resolved_assets
            if asset["family"] == "emotions"
        ),
    }


def build_credits_and_dates(resolved_assets):
    credits = {}
    dates = {}

    for asset in resolved_assets:
        if not asset["exists"] or not asset["metadata"]:
            continue

        family = asset["family"]
        name = asset["name"]
        metadata = asset["metadata"]
        asset_credits = metadata.get("credits", [])
        asset_date = metadata.get("dateModified", "")

        if family == "characterSelect":
            if asset_credits:
                credits["characterSelect"] = asset_credits
            if asset_date:
                dates["characterSelect"] = asset_date

        elif family == "icons":
            if asset_credits:
                credits.setdefault("icons", {})[name] = asset_credits
            if asset_date:
                dates.setdefault("icons", {})[name] = asset_date

        elif family == "portraits":
            if asset_credits:
                credits.setdefault("portraits", {})[name] = asset_credits
            if asset_date:
                dates.setdefault("portraits", {})[name] = asset_date

        elif family == "emotions":
            if asset_credits:
                (
                    credits
                    .setdefault("portraits", {})
                    .setdefault("emotions", {})
                )[name] = asset_credits

            if asset_date:
                (
                    dates
                    .setdefault("portraits", {})
                    .setdefault("emotions", {})
                )[name] = asset_date

    return credits, dates


# ============================================================
# SEARCH AND SORT KEYS
# ============================================================


def extract_names_from_credit_list(credit_list):
    names = []

    if not isinstance(credit_list, list):
        return names

    for entry in credit_list:
        if not isinstance(entry, dict):
            continue

        name = entry.get("name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())

    return names


def extract_artists(credits):
    if not isinstance(credits, dict):
        credits = {}

    character_select = extract_names_from_credit_list(
        credits.get("characterSelect", [])
    )

    icons = []
    for credit_list in credits.get("icons", {}).values():
        icons += extract_names_from_credit_list(credit_list)

    portraits = []
    portrait_credits = credits.get("portraits", {})

    if isinstance(portrait_credits, dict):
        for key, credit_value in portrait_credits.items():
            if key == "emotions" and isinstance(credit_value, dict):
                for emotion_credit_list in credit_value.values():
                    portraits += extract_names_from_credit_list(
                        emotion_credit_list
                    )
            else:
                portraits += extract_names_from_credit_list(
                    credit_value
                )

    character_select = dedupe_preserve_order(character_select)
    icons = dedupe_preserve_order(icons)
    portraits = dedupe_preserve_order(portraits)

    all_names = dedupe_preserve_order(
        character_select + icons + portraits
    )

    return {
        "artistsAll": all_names,
        "artistsCharacterSelect": character_select,
        "artistsIcons": icons,
        "artistsPortraits": portraits,
    }


def collect_string_dates(value):
    dates = []

    if isinstance(value, str):
        if parse_date(value):
            dates.append(value)
        return dates

    if isinstance(value, dict):
        for child_value in value.values():
            dates.extend(collect_string_dates(child_value))

    return dates


def extract_sort_keys(date_modified):
    if not isinstance(date_modified, dict):
        date_modified = {}

    character_select_date = date_modified.get(
        "characterSelect",
        "",
    )

    if not isinstance(character_select_date, str):
        character_select_date = ""

    icon_dates = collect_string_dates(
        date_modified.get("icons", {})
    )

    portrait_dates = collect_string_dates(
        date_modified.get("portraits", {})
    )

    icon_max = max_date_str(icon_dates)
    portrait_max = max_date_str(portrait_dates)

    date_max = max_date_str(
        [
            character_select_date,
            icon_max,
            portrait_max,
        ]
    )

    return {
        "dateModifiedMax": date_max,
        "dateModifiedCharacterSelect": character_select_date,
        "dateModifiedIconsMax": icon_max,
        "dateModifiedPortraitsMax": portrait_max,
    }


# ============================================================
# DETAIL MANIFEST
# ============================================================


def build_detail_variant(
    meta,
    paths,
    has,
    credits,
    date_modified,
):
    emotion_paths = (
        paths
        .get("portraits", {})
        .get("emotions", {})
    )

    return {
        "displayName": meta.get("displayName", ""),
        "genderId": meta.get("genderId", ""),
        "tags": meta.get("tags", []),
        "galleryNumber": meta.get("galleryNumber", ""),
        "specialityTypeIds": meta.get(
            "specialityTypeIds",
            [],
        ),
        "weaknessTypeIds": meta.get(
            "weaknessTypeIds",
            [],
        ),
        "stats": meta.get("stats"),
        "portraitEmotions": [
            emotion_name
            for emotion_name in EMOTION_ORDER
            if emotion_name in emotion_paths
        ],
        "has": has,
        "paths": paths,
        "credits": credits,
        "dateModified": date_modified,
        "history": meta.get("history", []),
        "notes": meta.get("notes", ""),
    }


# ============================================================
# OUTPUT FORMATTING
# ============================================================

INLINE_LIST_KEY_NAMES = {
    "tags",
    "specialityTypeIds",
    "weaknessTypeIds",
    "portraitEmotions",
    "artistsAll",
    "artistsCharacterSelect",
    "artistsIcons",
    "artistsPortraits",
    "artists",
}


def dumps_inline_list(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(", ", ": "),
    )


def is_inline_list(key, value):
    return isinstance(value, list) and key in INLINE_LIST_KEY_NAMES


def is_credit_object(value):
    return (
        isinstance(value, dict)
        and set(value.keys()) == {"name", "role"}
    )


def render_inline_credit(value):
    return (
        "{ "
        f'"name": {json.dumps(value["name"], ensure_ascii=False)}, '
        f'"role": {json.dumps(value["role"], ensure_ascii=False)}'
        " }"
    )


def render(value, indent=0, key_name=None):
    pad = " " * indent

    if isinstance(value, dict):
        if is_credit_object(value):
            return render_inline_credit(value)

        if not value:
            return "{}"

        items = list(value.items())
        lines = ["{"]

        for index, (key, child_value) in enumerate(items):
            comma = "," if index < len(items) - 1 else ""
            rendered = render(
                child_value,
                indent + 2,
                key_name=key,
            )

            if "\n" in rendered:
                rendered_lines = rendered.split("\n")
                rendered_lines = [rendered_lines[0]] + [
                    (" " * (indent + 2)) + line
                    for line in rendered_lines[1:]
                ]
                rendered = "\n".join(rendered_lines)

            lines.append(
                f'{pad}  "{key}": {rendered}{comma}'
            )

            if (
                key_name == "variants"
                and index < len(items) - 1
            ):
                lines.append("")

        lines.append(f"{pad}}}")
        return "\n".join(lines)

    if isinstance(value, list):
        if is_inline_list(key_name, value):
            return dumps_inline_list(value)

        if not value:
            return "[]"

        lines = ["["]

        for index, item in enumerate(value):
            comma = "," if index < len(value) - 1 else ""
            rendered = render(
                item,
                indent + 2,
                key_name=None,
            )

            if "\n" in rendered:
                rendered_lines = rendered.split("\n")
                rendered_lines = [rendered_lines[0]] + [
                    (" " * (indent + 2)) + line
                    for line in rendered_lines[1:]
                ]
                rendered = "\n".join(rendered_lines)

            lines.append(f"{pad}  {rendered}{comma}")

            if (
                key_name == "rows"
                and index < len(value) - 1
            ):
                lines.append("")

        lines.append(f"{pad}]")
        return "\n".join(lines)

    return json.dumps(value, ensure_ascii=False)


def write_json(path: Path, value):
    path.write_text(
        render(value, indent=0) + "\n",
        encoding="utf-8",
    )


# ============================================================
# MAIN
# ============================================================


def main():
    if not WARRIOR_METADATA_ROOT.exists():
        raise RuntimeError(
            "Warrior metadata root not found: "
            f"{WARRIOR_METADATA_ROOT}"
        )

    ensure_dir(MANIFEST_ROOT)
    ensure_dir(MANIFEST_WARRIOR_DIR)

    generated_at = iso_now_local()

    report = {
        "run": {
            "generatedAt": generated_at,
            "assetsRepoRoot": str(ASSETS_REPO_ROOT),
            "warriorRoot": str(WARRIOR_ROOT),
            "warriorMetadataRoot": str(WARRIOR_METADATA_ROOT),
            "assetMetadataRoot": str(ASSET_METADATA_ROOT),
            "manifestRoot": str(MANIFEST_ROOT),
            "assetBase": ASSET_BASE,
        },
        "counts": {
            "warriorFolders": 0,
            "variantFolders": 0,
            "metaFilesFound": 0,
            "metaParsed": 0,
            "metaParsedWithRepair": 0,
            "metaErrors": 0,
            "assetMetadataFilesLoaded": 0,
            "assetMetadataFilesParsedWithRepair": 0,
            "assetMetadataEntriesLoaded": 0,
            "rowsWritten": 0,
            "detailFilesWritten": 0,
        },
        "errors": [],
        "warnings": [],
    }

    asset_stores = load_asset_metadata(report)

    index = {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "assetBase": ASSET_BASE,
        "rows": [],
    }

    metadata_records = []
    seen_pairs = set()

    for meta_path in sorted(
        WARRIOR_METADATA_ROOT.rglob("meta.json")
    ):
        report["counts"]["metaFilesFound"] += 1

        try:
            meta, repaired = load_json_tolerant(meta_path)
            report["counts"]["metaParsed"] += 1

            if repaired:
                report["counts"][
                    "metaParsedWithRepair"
                ] += 1

            validation_errors = validate_meta(meta, meta_path)

            if validation_errors:
                for validation_error in validation_errors:
                    report["errors"].append(
                        {
                            "file": str(meta_path),
                            "error": validation_error,
                        }
                    )

                report["counts"]["metaErrors"] += 1
                continue

            key = (meta["warriorId"], meta["variantId"])

            if key in seen_pairs:
                report["errors"].append(
                    {
                        "file": str(meta_path),
                        "error": (
                            "Duplicate warriorId/variantId pair: "
                            f"{key[0]}/{key[1]}"
                        ),
                    }
                )
                report["counts"]["metaErrors"] += 1
                continue

            seen_pairs.add(key)
            metadata_records.append(
                {
                    "meta": meta,
                    "metaPath": meta_path,
                }
            )

        except Exception as error:
            report["counts"]["metaErrors"] += 1
            report["errors"].append(
                {
                    "file": str(meta_path),
                    "error": str(error),
                }
            )

    if report["counts"]["metaFilesFound"] != EXPECTED_META_COUNT:
        report["warnings"].append(
            {
                "reason": (
                    f"Expected {EXPECTED_META_COUNT} meta files "
                    f"but found "
                    f"{report['counts']['metaFilesFound']}"
                )
            }
        )

    grouped_records = {}

    for record in metadata_records:
        meta = record["meta"]
        grouped_records.setdefault(
            meta["warriorId"],
            [],
        ).append(record)

    report["counts"]["warriorFolders"] = len(grouped_records)
    report["counts"]["variantFolders"] = len(metadata_records)

    for warrior_id in sorted(grouped_records):
        records = grouped_records[warrior_id]

        detail = {
            "warriorId": warrior_id,
            "variants": {},
        }

        records.sort(
            key=lambda item: gallery_sort_key(
                item["meta"].get("galleryNumber", "")
            )
        )

        for record in records:
            meta = record["meta"]
            variant_id = meta["variantId"]

            resolved_assets = build_resolved_assets(
                meta,
                asset_stores,
                report,
            )

            paths = build_paths(
                resolved_assets,
                warrior_id,
                variant_id,
            )

            has = build_has(resolved_assets)

            credits, date_modified = build_credits_and_dates(
                resolved_assets
            )

            detail["variants"][variant_id] = (
                build_detail_variant(
                    meta=meta,
                    paths=paths,
                    has=has,
                    credits=credits,
                    date_modified=date_modified,
                )
            )

            full_icon_path = paths.get("icons", {}).get("full")
            thumb = {}

            if full_icon_path:
                thumb["icon"] = full_icon_path

            row = {
                "warriorId": warrior_id,
                "variantId": variant_id,
                "displayName": meta.get("displayName", ""),
                "galleryNumber": meta.get("galleryNumber", ""),
                "genderId": meta.get("genderId", ""),
                "specialityTypeIds": meta.get(
                    "specialityTypeIds",
                    [],
                ),
                "weaknessTypeIds": meta.get(
                    "weaknessTypeIds",
                    [],
                ),
                "tags": meta.get("tags", []),
                "thumb": thumb,
                "has": has,
                "stats": meta.get("stats"),
                "sortKeys": extract_sort_keys(date_modified),
                "searchKeys": extract_artists(credits),
                "detail": (
                    f"manifest/warriors/{warrior_id}.json"
                    f"#{variant_id}"
                ),
            }

            index["rows"].append(row)
            report["counts"]["rowsWritten"] += 1

        output_detail = (
            MANIFEST_WARRIOR_DIR / f"{warrior_id}.json"
        )

        write_json(output_detail, detail)
        report["counts"]["detailFilesWritten"] += 1

    index["rows"].sort(
        key=lambda row: (
            gallery_sort_key(row.get("galleryNumber", "")),
            row.get("warriorId", ""),
            row.get("variantId", ""),
        )
    )

    write_json(WARRIOR_INDEX_PATH, index)
    write_json(WARRIOR_REPORT_PATH, report)

    print("Warrior manifest generation complete.")
    print(f"Index:  {WARRIOR_INDEX_PATH}")
    print(
        f"Detail: {MANIFEST_WARRIOR_DIR} "
        f"({report['counts']['detailFilesWritten']} files)"
    )
    print(f"Report: {WARRIOR_REPORT_PATH}")
    print(
        "Warrior meta parsed: "
        f"{report['counts']['metaParsed']} "
        "(repaired: "
        f"{report['counts']['metaParsedWithRepair']}), "
        "errors: "
        f"{report['counts']['metaErrors']}"
    )
    print(
        "Asset metadata loaded: "
        f"{report['counts']['assetMetadataFilesLoaded']} files, "
        f"{report['counts']['assetMetadataEntriesLoaded']} entries"
    )
    print(f"Rows written: {report['counts']['rowsWritten']}")


if __name__ == "__main__":
    main()
