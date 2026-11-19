"""Download a provenance-preserving labeled evaluation corpus.

The corpus labels are based on the configured source query and require human
visual verification before they can be used as evaluation ground truth.
Every downloaded item retains its source page, author, license, and SHA-256 hash.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
from collections import Counter
from urllib.error import HTTPError, URLError
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "data" / "evaluation" / "images"
PROVENANCE_PATH = ROOT / "data" / "evaluation" / "provenance.json"
MANIFEST_PATH = ROOT / "data" / "evaluation" / "manifest.json"

API_URL = "https://commons.wikimedia.org/w/api.php"
OPENVERSE_API_URL = "https://api.openverse.org/v1/images/"
USER_AGENT = "FlyRankCapstoneDataset/1.0 (educational evaluation; contact via project)"
PER_CATEGORY = 10
WIKIMEDIA_ACCEPTED_LICENSES = (
    "CC0",
    "Public domain",
    "CC BY",
    "CC BY-SA",
)
OPENVERSE_ACCEPTED_LICENSES = ("by", "by-sa", "cc0", "pdm", "by-nd")

WIKIMEDIA_CATEGORIES = {
    "wildlife": "Category:Wildlife photography",
    "food": "Category:Food photography",
    "technology": "Category:Computers",
    "travel": "Category:Landscape photography",
}

OPENVERSE_CATEGORIES = {
    "wildlife": "wildlife",
    "food": "food",
    "technology": "laptop",
    "travel": "mountain travel",
}

POST_TEMPLATES = {
    "wildlife": [
        ("Wildlife observation in natural habitats",
         "A field guide discussing animals, insects, and their natural habitats."),
        ("How wildlife adapts to the outdoors",
         "An article about observing wild animals and ecological adaptation."),
        ("Photographing wild species responsibly",
         "A practical guide to wildlife photography and respectful observation."),
    ],
    "food": [
        ("Food photography and prepared dishes",
         "An article about cooking, prepared meals, and food presentation."),
        ("Documenting recipes with images",
         "A guide to using photographs of dishes and ingredients in recipe writing."),
        ("The visual language of cuisine",
         "A discussion of meals, culinary traditions, and food composition."),
    ],
    "technology": [
        ("Computers in modern work",
         "An article about computers, hardware, and digital technology."),
        ("Understanding computer hardware",
         "A beginner guide to computer components and technical equipment."),
    ],
    "travel": [
        ("Mountain landscapes and travel",
         "A travel article about scenic landscapes, mountains, and outdoor destinations."),
        ("Planning a landscape-focused journey",
         "A guide to visiting scenic natural landscapes and travel destinations."),
    ],
}


def request_json(url: str, *, params: dict[str, str | int]) -> tuple[dict, dict]:
    for attempt in range(5):
        request = Request(
            url + "?" + urlencode({**params, "format": "json"}),
            headers={"User-Agent": USER_AGENT},
        )
        try:
            with urlopen(request, timeout=60) as response:
                return json.load(response), dict(response.headers.items())
        except HTTPError as error:
            if error.code not in {408, 429, 500, 502, 503, 504} or attempt == 4:
                raise
            retry_after = error.headers.get("Retry-After")
            delay = int(retry_after) if retry_after and retry_after.isdigit() else 10 * (2**attempt)
            time.sleep(min(180, delay))
        except URLError:
            if attempt == 4:
                raise
            time.sleep(min(180, 10 * (2**attempt)))
    raise RuntimeError("API request did not complete")


def api_request(params: dict[str, str | int]) -> dict:
    result, _ = request_json(API_URL, params={**params, "format": "json"})
    return result


def clean_metadata(value: str | None) -> str | None:
    if not value:
        return None
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip() or None


def category_files(category: str) -> list[str]:
    result = api_request(
        {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmtype": "file",
            "cmlimit": 50,
        }
    )
    return [item["title"] for item in result["query"]["categorymembers"]]


def image_metadata(titles: list[str]) -> list[dict]:
    result = api_request(
        {
            "action": "query",
            "titles": "|".join(titles),
            "prop": "imageinfo",
            "iiprop": "url|mime|size|extmetadata",
            "iiurlwidth": 1024,
        }
    )
    files = []
    for page in result["query"]["pages"].values():
        info = page.get("imageinfo", [{}])[0]
        metadata = info.get("extmetadata", {})
        license_name = clean_metadata(
            metadata.get("LicenseShortName", {}).get("value")
        )
        if (
            info.get("mime") not in {"image/jpeg", "image/png", "image/webp"}
            or not license_name
            or not any(
                license_name.lower().startswith(item.lower())
                for item in WIKIMEDIA_ACCEPTED_LICENSES
            )
            or not info.get("thumburl")
        ):
            continue
        files.append(
            {
                "title": page["title"],
                "source_url": f"https://commons.wikimedia.org/wiki/{page['title'].replace(' ', '_')}",
                "download_url": info.get("thumburl") or info["url"],
                "mime": info["mime"],
                "license": license_name,
                "license_url": clean_metadata(
                    metadata.get("LicenseUrl", {}).get("value")
                ),
                "author": clean_metadata(
                    metadata.get("Artist", {}).get("value")
                ),
                "description": clean_metadata(
                    metadata.get("ImageDescription", {}).get("value")
                ),
            }
        )
    return files


def openverse_metadata(
    query: str,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], dict]:
    result, headers = request_json(
        OPENVERSE_API_URL,
        params={"q": query, "page": page, "page_size": page_size},
    )
    records = []
    for item in result.get("results", []):
        license_id = (item.get("license") or "").lower()
        if license_id not in OPENVERSE_ACCEPTED_LICENSES:
            continue
        if not all(
            item.get(field)
            for field in (
                "id",
                "title",
                "foreign_landing_url",
                "url",
                "license",
                "license_version",
                "license_url",
                "provider",
                "source",
                "attribution",
                "width",
                "height",
            )
        ):
            continue
        if license_id not in {"cc0", "pdm"} and not all(
            item.get(field) for field in ("creator", "creator_url")
        ):
            continue
        records.append(
            {
                "id": item["id"],
                "title": item["title"],
                "creator": item.get("creator"),
                "creator_url": item.get("creator_url"),
                "source": item["source"],
                "provider": item["provider"],
                "source_url": item["foreign_landing_url"],
                "download_url": item["url"],
                "license": item["license"],
                "license_version": item["license_version"],
                "license_url": item["license_url"],
                "attribution": item["attribution"],
                "width": item["width"],
                "height": item["height"],
                "filetype": item.get("filetype"),
            }
        )
    return records, {
        "status": 200,
        "total": result.get("result_count", 0),
        "page_results": len(result.get("results", [])),
        "retry_after": headers.get("Retry-After"),
        "rate_limit": headers.get("X-RateLimit-Limit"),
        "rate_remaining": headers.get("X-RateLimit-Remaining"),
    }


def check_link(url: str) -> int:
    for method in ("HEAD", "GET"):
        request = Request(
            url,
            headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"},
            method=method,
        )
        try:
            with urlopen(request, timeout=30) as response:
                return response.status
        except HTTPError as error:
            if method == "HEAD" and error.code in {405, 403}:
                continue
            if error.code in {408, 429, 500, 502, 503, 504}:
                time.sleep(10)
                continue
            return error.code
        except URLError:
            return 0
    return 0


def valid_image_bytes(content: bytes, mime: str | None) -> tuple[bool, str | None]:
    signatures = {
        "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
        "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
        "image/webp": (b"RIFF", ".webp"),
    }
    for expected_mime, (signature, extension) in signatures.items():
        signature_matches = content.startswith(signature)
        if expected_mime == "image/webp":
            signature_matches = signature_matches and content[8:12] == b"WEBP"
        if signature_matches and mime in {None, expected_mime}:
            return True, extension
    return False, None


def download(url: str) -> bytes:
    for attempt in range(5):
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=120) as response:
                return response.read()
        except HTTPError as error:
            if error.code not in {408, 429, 500, 502, 503, 504} or attempt == 4:
                raise
            retry_after = error.headers.get("Retry-After")
            delay = int(retry_after) if retry_after and retry_after.isdigit() else 15 * (2**attempt)
            time.sleep(min(180, delay))
        except URLError:
            if attempt == 4:
                raise
            time.sleep(min(180, 15 * (2**attempt)))
    raise RuntimeError("Wikimedia media download did not complete")


def openverse_discovery() -> None:
    output = {"source": "openverse", "categories": {}, "accepted_license_ids": OPENVERSE_ACCEPTED_LICENSES}
    for category, query in OPENVERSE_CATEGORIES.items():
        records, response = openverse_metadata(query, page_size=20)
        distribution = Counter()
        for item in records:
            distribution[item["license"]] += 1
        output["categories"][category] = {
            "query": query,
            "response": response,
            "permissive_candidates": len(records),
            "license_distribution": dict(distribution),
            "metadata_complete_candidates": len(records),
        }
        time.sleep(5)
    print(json.dumps(output, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("wikimedia", "openverse"), default="wikimedia")
    parser.add_argument("--discover", action="store_true")
    args = parser.parse_args()
    if args.discover:
        if args.source != "openverse":
            raise SystemExit("--discover currently requires --source openverse")
        openverse_discovery()
        return
    if args.source == "wikimedia":
        prepare_wikimedia()
        return

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    category_ids: dict[str, list[str]] = {}

    for category, query in OPENVERSE_CATEGORIES.items():
        selected: list[dict] = []
        for page in range(1, 6):
            page_records, _ = openverse_metadata(query, page=page, page_size=20)
            selected.extend(page_records)
            if len(selected) >= PER_CATEGORY:
                break
            time.sleep(5)
        validated: list[dict] = []
        for item in selected:
            landing_status = check_link(item["source_url"])
            time.sleep(1)
            license_status = check_link(item["license_url"])
            time.sleep(1)
            if landing_status < 200 or landing_status >= 400:
                continue
            if license_status < 200 or license_status >= 400:
                continue
            validated.append(item)
            if len(validated) >= PER_CATEGORY:
                break
        selected = validated
        if len(selected) < PER_CATEGORY:
            raise RuntimeError(
                f"Openverse query {query!r} supplied only {len(selected)} validated image files"
            )

        category_ids[category] = []
        for index, item in enumerate(selected[:PER_CATEGORY], start=1):
            image_id = f"{category}-{index:02d}"
            content = download(item["download_url"])
            is_valid, extension = valid_image_bytes(content, None)
            if not is_valid:
                continue
            filename = f"{image_id}{extension}"
            path = IMAGE_DIR / filename
            path.write_bytes(content)
            record = {
                "image_id": image_id,
                "category": category,
                "source_query": query,
                "filename": filename,
                "sha256": hashlib.sha256(content).hexdigest(),
                "openverse_id": item["id"],
                "title": item["title"],
                "creator": item["creator"],
                "creator_url": item["creator_url"],
                "provider": item["provider"],
                "source": item["source"],
                "source_url": item["source_url"],
                "download_url": item["download_url"],
                "license": item["license"],
                "license_version": item["license_version"],
                "license_url": item["license_url"],
                "attribution": item["attribution"],
                "width": item["width"],
                "height": item["height"],
                "filetype": extension.lstrip("."),
                "label_basis": (
                    "Openverse search query only; human visual verification is "
                    "required before evaluation use"
                ),
                "source_metadata": {
                    "openverse_id": item["id"],
                    "title": item["title"],
                    "creator": item["creator"],
                    "creator_url": item["creator_url"],
                    "provider": item["provider"],
                    "source": item["source"],
                    "source_url": item["source_url"],
                    "download_url": item["download_url"],
                    "license": item["license"],
                    "license_version": item["license_version"],
                    "license_url": item["license_url"],
                    "attribution": item["attribution"],
                    "width": item["width"],
                    "height": item["height"],
                    "filetype": extension.lstrip("."),
                },
                "evaluation_label": {
                    "category": category,
                    "status": "provisional",
                    "basis": "Openverse search query; not human-verified",
                },
            }
            records.append(record)
            category_ids[category].append(image_id)
            time.sleep(0.5)

    posts = []
    for category, templates in POST_TEMPLATES.items():
        for index, (title, content) in enumerate(templates, start=1):
            relevant = category_ids[category][(index - 1) % PER_CATEGORY]
            mismatch_category = next(
                key for key in OPENVERSE_CATEGORIES if key != category
            )
            posts.append(
                {
                    "post_id": f"post-{len(posts) + 1:02d}",
                    "title": title,
                    "content": content,
                    "category": category,
                    "relevant_image_ids": [relevant],
                    "mismatched_image_ids": [category_ids[mismatch_category][0]],
                    "label_basis": "Provisional category label; human verification required",
                    "post_basis": "Authored evaluation prompt; not a sourced blog post",
                }
            )

    PROVENANCE_PATH.write_text(
        json.dumps(
            {
                "source": "Openverse",
                "source_policy_url": (
                    "https://openverse.org/"
                ),
                "api_documentation_url": (
                    "https://api.openverse.org/v1/"
                ),
                "categories": OPENVERSE_CATEGORIES,
                "accepted_license_ids": OPENVERSE_ACCEPTED_LICENSES,
                "images": records,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "labels_verified": False,
                "image_ids": [record["image_id"] for record in records],
                "categories": sorted(OPENVERSE_CATEGORIES),
                "posts": posts,
                "provenance_file": "provenance.json",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "images": len(records),
                "categories": len(OPENVERSE_CATEGORIES),
                "posts": len(posts),
                "provenance": str(PROVENANCE_PATH),
                "manifest": str(MANIFEST_PATH),
            },
            indent=2,
        )
    )


def prepare_wikimedia() -> None:
    """Retain the original Commons downloader and its source-specific schema."""

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    category_ids: dict[str, list[str]] = {}
    for category, source_category in WIKIMEDIA_CATEGORIES.items():
        candidates = category_files(source_category)
        time.sleep(1)
        selected: list[dict] = []
        for offset in range(0, len(candidates), 50):
            selected.extend(image_metadata(candidates[offset : offset + 50]))
            if len(selected) >= PER_CATEGORY:
                break
            time.sleep(1)
        if len(selected) < PER_CATEGORY:
            raise RuntimeError(
                f"{source_category} supplied only {len(selected)} licensed image files"
            )
        category_ids[category] = []
        for index, item in enumerate(selected[:PER_CATEGORY], start=1):
            image_id = f"{category}-{index:02d}"
            content = download(item["download_url"])
            is_valid, extension = valid_image_bytes(content, item["mime"])
            if not is_valid:
                raise ValueError(f"Invalid image content for {item['title']}")
            filename = f"{image_id}{extension}"
            (IMAGE_DIR / filename).write_bytes(content)
            records.append(
                {
                    "image_id": image_id,
                    "category": category,
                    "source_category": source_category,
                    "filename": filename,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "title": item["title"],
                    "source_url": item["source_url"],
                    "download_url": item["download_url"],
                    "mime": item["mime"],
                    "license": item["license"],
                    "license_url": item["license_url"],
                    "author": item["author"],
                    "description": item["description"],
                    "label_basis": "Wikimedia Commons source category",
                }
            )
            category_ids[category].append(image_id)
            time.sleep(0.5)
    write_outputs(
        records,
        category_ids,
        source="Wikimedia Commons",
        source_policy_url=(
            "https://commons.wikimedia.org/wiki/"
            "Commons:Reusing_content_outside_Wikimedia"
        ),
        api_documentation_url="https://commons.wikimedia.org/wiki/Commons:API/MediaWiki",
        accepted_licenses=WIKIMEDIA_ACCEPTED_LICENSES,
    )


def write_outputs(
    records: list[dict],
    category_ids: dict[str, list[str]],
    *,
    source: str,
    source_policy_url: str,
    api_documentation_url: str,
    accepted_licenses: tuple[str, ...],
) -> None:
    posts = []
    for category, templates in POST_TEMPLATES.items():
        for index, (title, content) in enumerate(templates, start=1):
            relevant = category_ids[category][(index - 1) % PER_CATEGORY]
            mismatch_category = next(key for key in category_ids if key != category)
            posts.append(
                {
                    "post_id": f"post-{len(posts) + 1:02d}",
                    "title": title,
                    "content": content,
                    "category": category,
                    "relevant_image_ids": [relevant],
                    "mismatched_image_ids": [category_ids[mismatch_category][0]],
                    "label_basis": "Provisional category label; human verification required",
                }
            )
    PROVENANCE_PATH.write_text(
        json.dumps(
            {
                "source": source,
                "source_policy_url": source_policy_url,
                "api_documentation_url": api_documentation_url,
                "accepted_licenses": accepted_licenses,
                "images": records,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "labels_verified": False,
                "image_ids": [record["image_id"] for record in records],
                "categories": sorted(category_ids),
                "posts": posts,
                "provenance_file": "provenance.json",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
