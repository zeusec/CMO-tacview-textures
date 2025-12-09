#!/usr/bin/env python3
import os
import re
import time
import requests
import argparse 
import threading
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

TEXTURES_URL = "https://warfaresims.slitherine.com/Tacview_Textures/"
ELEVATION_URL = "https://warfaresims.slitherine.com/Tacview_SRTM30/"

DEFAULT_TEXTURES_DIR = "textures"
DEFAULT_ELEVATION_DIR = "elevation"

DEFAULT_MAX_WORKERS = 4          # keep this small to be nice to server
DEFAULT_DELAY_S = 0.5            # delay between requests per worker
DEFAULT_RETRIES = 3
TIMEOUT_S = 60                   # network timeout per request (seconds)

SESSION = requests.Session()
STOP_EVENT = threading.Event()

def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{sec:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def print_progress(
    completed: int,
    total: int,
    downloaded: int,
    skipped: int,
    errors: int,
    start_time: float,
) -> None:
    """Single-line progress bar with ETA."""
    elapsed = time.time() - start_time
    rate = completed / elapsed if elapsed > 0 else 0.0
    remaining = max(total - completed, 0)
    eta = remaining / rate if rate > 0 else 0.0
    pct = (completed / total) * 100 if total else 0.0
    bar_width = 40
    filled = int(bar_width * pct / 100)
    bar = "#" * filled + "-" * (bar_width - filled)

    line = (
        f"\r[{bar}] {pct:5.1f}% "
        f"{completed}/{total} "
        f"(ok:{downloaded} skip:{skipped} err:{errors}) "
        f"| ETA {format_duration(eta)} "
        f"| elapsed {format_duration(elapsed)}"
    )
    print(line, end="", flush=True)


def fetch_index(base_url: str) -> str:
    log(f"Fetching index: {base_url}")
    resp = SESSION.get(base_url, timeout=TIMEOUT_S)
    resp.raise_for_status()
    return resp.text


def parse_filenames(html: str, exts: Optional[List[str]] = None) -> List[str]:
    all_links = re.findall(r'href="([^"]+)"', html)
    files: List[str] = []

    for name in all_links:
        # skip parent dir, current dir and subdirectories
        if name in ("../", "./"):
            continue
        if name.endswith("/"):
            continue
        if name.startswith("?"):
            continue

        lower = name.lower()

        if exts is not None:
            if not any(lower.endswith(ext) for ext in exts):
                continue

        files.append(name)

    return sorted(set(files))


def safe_makedirs(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def download_with_retries(
    url: str,
    dest_path: str,
    delay_s: float,
    retries: int,
) -> Tuple[str, str]:
    filename = os.path.basename(dest_path)

    if STOP_EVENT.is_set():
        return filename, "skipped"

    if os.path.exists(dest_path):
        return filename, "exists"

    tmp_path = dest_path + ".part"
    attempt = 0

    while attempt < retries:
        if STOP_EVENT.is_set():
            return filename, "skipped"

        attempt += 1
        try:
            time.sleep(delay_s)

            with SESSION.get(url, stream=True, timeout=TIMEOUT_S) as resp:
                resp.raise_for_status()
                safe_makedirs(os.path.dirname(dest_path) or ".")
                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=512 * 1024):
                        if STOP_EVENT.is_set():
                            raise RuntimeError("stop requested")
                        if not chunk:
                            continue
                        f.write(chunk)

            os.replace(tmp_path, dest_path)
            return filename, "downloaded"

        except Exception as exc:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

            if STOP_EVENT.is_set():
                return filename, "skipped"

            if attempt >= retries:
                return filename, f"error: {exc}"
            else:
                backoff = 2 ** (attempt - 1)
                log(f"{filename}: attempt {attempt} failed ({exc}), retrying in {backoff}s...")
                time.sleep(backoff)

    return filename, "error: unknown"


def download_set(
    label: str,
    base_url: str,
    dest_dir: str,
    exts: Optional[List[str]],
    max_workers: int,
    delay_s: float,
    retries: int,
) -> None:
    """Download one set (textures or elevation)."""
    t0 = time.time()
    safe_makedirs(dest_dir)

    html = fetch_index(base_url)
    files = parse_filenames(html, exts=exts)
    total = len(files)

    if total == 0:
        log(f"[{label}] No matching files found in index. Skipping.")
        return

    log(f"[{label}] Found {total} files.")
    log(f"[{label}] Downloading into: {os.path.abspath(dest_dir)}")
    log(
        f"[{label}] Max workers: {max_workers}, "
        f"delay per request: {delay_s}s, retries: {retries}"
    )

    completed = 0
    errors = 0
    downloaded = 0
    skipped = 0
    start_time = time.time()

    STOP_EVENT.clear()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for fname in files:
            url = base_url + fname
            dest_path = os.path.join(dest_dir, fname)
            fut = executor.submit(
                download_with_retries,
                url,
                dest_path,
                delay_s,
                retries,
            )
            futures.append(fut)

        try:
            for fut in as_completed(futures):
                filename, status = fut.result()
                completed += 1

                if status.startswith("error"):
                    errors += 1
                    print()
                    log(f"[{label}] {filename}: {status}")
                elif status == "downloaded":
                    downloaded += 1
                elif status == "exists":
                    skipped += 1
                elif status == "skipped":
                    skipped += 1

                print_progress(
                    completed=completed,
                    total=total,
                    downloaded=downloaded,
                    skipped=skipped,
                    errors=errors,
                    start_time=start_time,
                )

        except KeyboardInterrupt:
            STOP_EVENT.set()
            print()
            log(f"[{label}] Interrupted by user. Signaling workers to stop...")

    dt = time.time() - t0
    print()
    log(
        f"[{label}] Done (or interrupted). "
        f"Processed: {completed}, errors: {errors}, elapsed: {dt:.1f}s"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download Tacview assets from WarfareSims:\n"
            "- Textures  -> ./textures\n"
            "- Elevation -> ./elevation"
        )
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help=f"Max concurrent downloads (default: {DEFAULT_MAX_WORKERS})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_S,
        help=f"Delay in seconds between requests per worker (default: {DEFAULT_DELAY_S})",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Retries per file on error (default: {DEFAULT_RETRIES})",
    )
    parser.add_argument(
        "--textures-dir",
        default=DEFAULT_TEXTURES_DIR,
        help=f"Textures destination directory (default: {DEFAULT_TEXTURES_DIR})",
    )
    parser.add_argument(
        "--elevation-dir",
        default=DEFAULT_ELEVATION_DIR,
        help=f"Elevation destination directory (default: {DEFAULT_ELEVATION_DIR})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 1. Textures: only .webp
    download_set(
        label="textures",
        base_url=TEXTURES_URL,
        dest_dir=args.textures_dir,
        exts=[".webp"],
        max_workers=max(1, args.workers),
        delay_s=max(0.0, args.delay),
        retries=max(1, args.retries),
    )

    if STOP_EVENT.is_set():
        log("Stop flag set after textures. Skipping elevation download.")
        return

    # 2. Elevation: only .srtm bathymetry tiles
    download_set(
        label="elevation",
        base_url=ELEVATION_URL,
        dest_dir=args.elevation_dir,
        exts=[".srtm"],
        max_workers=max(1, args.workers),
        delay_s=max(0.0, args.delay),
        retries=max(1, args.retries),
    )


if __name__ == "__main__":
    main()
