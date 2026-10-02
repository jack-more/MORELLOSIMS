"""Downloads with an on-disk cache. No credentials, public endpoints only."""

import json
import os
import time
import urllib.request

from config import CACHE, DEPTH_URL, INJURIES_URL, PBP_URL, SCHEDULES_URL

UA = {"User-Agent": "Mozilla/5.0 (compatible; MorelloSims-NFL/1.0)"}


def fetch(url, timeout=120, tries=3):
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:  # network hiccup: retry with backoff
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"fetch failed after {tries} tries: {url}: {last}")


def get_json(url, timeout=30):
    return json.loads(fetch(url, timeout=timeout))


def cached(url, name, refresh=False, max_age_h=None):
    """Path to a cached copy of `url` (downloaded when missing, stale or refresh)."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    if os.path.exists(path) and not refresh:
        if max_age_h is None or (time.time() - os.path.getmtime(path)) < max_age_h * 3600:
            return path
    data = fetch(url)
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)
    return path


def schedules_path(refresh=False):
    return cached(SCHEDULES_URL, "games.csv", refresh=refresh)


def pbp_path(season, refresh=False):
    return cached(PBP_URL.format(season=season), f"play_by_play_{season}.parquet", refresh=refresh)


def injuries_path(season, refresh=False):
    return cached(INJURIES_URL.format(season=season), f"injuries_{season}.parquet", refresh=refresh)


def depth_path(season, refresh=False):
    return cached(DEPTH_URL.format(season=season), f"depth_charts_{season}.parquet", refresh=refresh)
