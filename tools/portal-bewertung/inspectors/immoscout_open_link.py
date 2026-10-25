"""CLI entry point: scrape one ImmoScout24 expose URL into a lead folder.

Usage:
    python immoscout_open_link.py <url> <target-folder> [--force] [--stage N] [--from-html FILE] [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# allow direct invocation from inspectors/ without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from immoscout.orchestrator import Orchestrator  # noqa: E402
from immoscout.output_writer import OutputWriter  # noqa: E402
from immoscout.parser import extract_keyvalues, parse_expose  # noqa: E402
from immoscout.stages.stage1_stealth_headless import Stage1StealthHeadless  # noqa: E402
from immoscout.stages.stage2_stealth_headed import Stage2StealthHeaded  # noqa: E402
from immoscout.stages.stage3_nodriver import Stage3Nodriver  # noqa: E402
from immoscout.stages.stage4_edge_profile import Stage4EdgeProfile  # noqa: E402
from immoscout.stages.stage5_2captcha import Stage5TwoCaptcha  # noqa: E402

EXIT_OK = 0
EXIT_BAD_URL = 1
EXIT_ALL_BLOCKED = 2
EXIT_NO_DATA = 3
EXIT_IMG_PARTIAL = 4
EXIT_IO = 5

URL_PATTERN = re.compile(r"^https?://(?:www\.)?immobilienscout24\.de/expose/(\d+)(?:[/?#].*)?$", re.IGNORECASE)


def _build_stages(forced_stage: int | None):
    all_stages = [
        Stage1StealthHeadless(),
        Stage2StealthHeaded(),
        Stage3Nodriver(),
        Stage4EdgeProfile(),
        Stage5TwoCaptcha(),
    ]
    if forced_stage is None:
        return all_stages
    if not 1 <= forced_stage <= 5:
        raise SystemExit(f"--stage must be 1..5, got {forced_stage}")
    return [all_stages[forced_stage - 1]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape one ImmoScout24 expose URL.")
    parser.add_argument("url", help="full ImmoScout expose URL")
    parser.add_argument("target_folder", help="absolute path to lead folder")
    parser.add_argument("--force", action="store_true", help="overwrite existing output (with backup)")
    parser.add_argument("--stage", type=int, default=None, help="force a specific stage 1..5")
    parser.add_argument("--from-html", type=str, default=None, help="parse this local HTML file instead of fetching")
    parser.add_argument("--dry-run", action="store_true", help="run everything except final writes")
    args = parser.parse_args(argv)

    m = URL_PATTERN.match(args.url)
    if not m:
        print(f"[ERROR] not a valid ImmoScout expose URL: {args.url}", file=sys.stderr)
        return EXIT_BAD_URL
    scout_id = m.group(1)

    target = Path(args.target_folder)
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"[ERROR] cannot create target folder: {exc}", file=sys.stderr)
        return EXIT_IO

    writer = OutputWriter(target)
    writer.log(f"START url={args.url} target={target}")

    # idempotency
    if (target / "expose.json").exists() and not args.force and not args.from_html:
        writer.log(f"SKIP expose.json already exists — pass --force to overwrite")
        return EXIT_OK

    if args.force:
        writer.backup_existing()

    # fetch
    if args.from_html:
        html = Path(args.from_html).read_text(encoding="utf-8")
        final_url = args.url
        writer.log(f"OFFLINE MODE — parsing {args.from_html}")
        successful_stage = "from_html"
        stages_attempted = ["from_html"]
    else:
        stages = _build_stages(args.stage)
        orch = Orchestrator(stages=stages)
        result = orch.run(args.url)
        for att in result.attempts:
            marker_str = ",".join(att.markers) if att.markers else "none"
            writer.log(f"STAGE {att.name} blocked={att.blocked} markers={marker_str} duration={att.duration_s:.1f}s error={att.error}")
        if not result.success or result.result is None:
            writer.log(f"FAIL all stages blocked")
            (target / ".error").write_text(f"all stages blocked: {[a.name for a in result.attempts]}", encoding="utf-8")
            return EXIT_ALL_BLOCKED
        html = result.result.html
        final_url = result.result.final_url
        successful_stage = result.successful_stage
        stages_attempted = result.stages_attempted

    # parse
    kv = extract_keyvalues(html)
    if kv is None:
        writer.log(f"WARN keyValues missing — DOM-only parse")
    expose = parse_expose(html=html, final_url=final_url)
    expose["successful_stage"] = successful_stage
    expose["stages_attempted"] = stages_attempted

    if not expose.get("scout_id") and not kv:
        writer.log(f"NO DATA parser found nothing usable")
        writer.write_html(html)
        return EXIT_NO_DATA

    if args.dry_run:
        writer.log(f"DRY RUN — would write {len(expose)} fields, {len(expose.get('bilder', []))} images")
        return EXIT_OK

    # write
    writer.write_expose_json(expose)
    if kv:
        writer.write_keyvalues(kv)
    writer.write_html(html)
    writer.write_final_url(final_url)

    # images (best effort)
    image_urls = [b["url_original"] for b in expose.get("bilder", []) if b.get("url_original")]
    expected = len(image_urls)
    downloaded = writer.download_images(image_urls)

    # screenshot + pdf — re-open page (acceptable extra load on success path)
    if not args.from_html:
        render_url = final_url if final_url and final_url.startswith("http") else args.url
        try:
            writer.render_pdf_and_screenshot(render_url)
        except Exception as exc:  # noqa: BLE001
            writer.log(f"RENDER FAIL {exc}")

    writer.log(f"DONE successful_stage={successful_stage} images={downloaded}/{expected}")

    if expected > 0 and downloaded < expected * 0.5:
        return EXIT_IMG_PARTIAL
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
