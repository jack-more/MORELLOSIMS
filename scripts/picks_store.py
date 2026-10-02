#!/usr/bin/env python3
"""picks_store — the one door to pick data, and SEAL MODE.

Every script that reads or writes picks/mlb.json or picks/nba.json goes
through here. With seal mode OFF (ops/config/monetization.json, the default)
loading and saving are byte-for-byte what json.load / json.dump(indent=2)
did before; nothing public changes.

With seal mode ON, a pending pick whose game has not started is SEALED in
every public file:

  public record   id, sport, date, matchup, away, home, bet_type, conf, units,
                  game_time, published_at, captured_at, status
                  + "sealed": true, "unlocks_at" (first pitch / tip, UTC),
                  "commitment" = sha256(canonical(pick) + nonce),
                  "sealed_blob" = the full pick + nonce, AES-256-GCM encrypted
                  with a key derived from the PICKS_SEAL_KEY Actions secret.

  side / odds / line / pick_text / sim_projection / model fields are absent.

UNSEAL: once the game starts (MLB: scheduled first pitch, NBA: tip) the
record is rewritten in plaintext with "nonce", "unsealed_at" and "seal_keys"
added, so anyone can check

    sha256(canonical({k: pick[k] for k in seal_keys}) + bytes.fromhex(nonce))
        == commitment

(scripts/verify_seal.py does it for any pick id).

canonical(x) = json.dumps(x, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")

Lifecycle fields that legitimately change after publish (status, result,
pl, settled_at, closing line, last_odds, gates_now, void_reason, ...) are
not part of the commitment; everything that defines the bet is.

Encryption is deterministic (synthetic IV = HMAC of the plaintext), and the
commitment nonce is HMAC(key, id + payload): sealing the same pick twice
yields byte-identical records, so pipelines can rewrite files every run
without churning git, and the nonce stays secret until unseal. Plaintext is
padded to a fixed 4 KiB bucket before encryption so the ciphertext length
cannot reveal which team (2- vs 3-letter abbreviations) was picked.

Internal working files (picks.csv, pick_log.json, daily_picks.json,
mlbsim/picks_log.csv, reports/shadow_mlb.json) use the same encryption to
hide pending rows; they are restored verbatim at unseal (no commitment —
the public commitment lives in picks/<sport>.json).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CONFIG_PATH = os.path.join(REPO, "ops", "config", "monetization.json")
PICK_FILES = {
    "mlb": os.path.join(REPO, "picks", "mlb.json"),
    "nba": os.path.join(REPO, "picks", "nba.json"),
}

KEY_ENV = "PICKS_SEAL_KEY"          # Actions secret: urlsafe base64 of 32 random bytes
NOW_ENV = "PICKS_SEAL_NOW"          # tests/local verification only: override the clock (ISO)
CONFIG_ENV = "MORELLOSIMS_MONETIZATION_CONFIG"  # tests only: alternate config path

ET = ZoneInfo("America/New_York")
UTC = timezone.utc

SEALED_SIDE = "SEALED"
PAD_BLOCK = 4096
_AAD = b"morellosims:seal:v1"

# What a sealed public pick keeps (everything else lives only in sealed_blob).
PUBLIC_PICK_FIELDS = (
    "id", "sport", "date", "matchup", "away", "home", "bet_type", "conf", "units",
    "game_time", "published_at", "captured_at", "status",
)
SEAL_META = ("sealed", "sealed_id", "unlocks_at", "commitment", "sealed_blob", "nonce", "unsealed_at", "seal_keys")
# Fields that legitimately change after publish; not part of the commitment.
LIFECYCLE = (
    "status", "result", "pl", "settled_at",
    "closing_odds", "closing_ts", "closing_book", "closing_line",
    "last_odds", "last_odds_at", "gates_now", "void_reason",
    "restored_from", "restored_reason",
)
# Never allowed in a sealed public record (guardrail + tests use this).
FORBIDDEN_SEALED = (
    "side", "odds", "line", "pick_text", "sim_projection", "sim_edge",
    "model_wp_raw", "model_wp_calibrated", "vector_edge", "vector_xwoba_edge",
    "away_vector_run_delta", "home_vector_run_delta", "away_vector_xwoba", "home_vector_xwoba",
    "last_odds", "gates_now",
)


class SealError(RuntimeError):
    """Seal mode cannot be honored (missing key, tampered blob, sealed pick reached settlement)."""


# ── config ────────────────────────────────────────────────────────────────

def config() -> dict:
    path = os.environ.get(CONFIG_ENV) or CONFIG_PATH
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def seal_mode() -> bool:
    return bool(config().get("seal_mode"))


def whop_url() -> str:
    return str(config().get("whop_checkout_url") or "").strip()


def premium_note() -> str:
    return str(config().get("premium_channel_note") or "").strip()


# ── clock / start times ───────────────────────────────────────────────────

def parse_ts(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def now_utc() -> datetime:
    forced = parse_ts(os.environ.get(NOW_ENV))
    return forced.astimezone(UTC) if forced else datetime.now(UTC)


def parse_game_time(date_iso: str, game_time: str) -> datetime | None:
    """'2026-09-27' + '3:10 PM ET' → aware datetime (America/New_York)."""
    gt = (game_time or "").replace("ET", "").replace("EDT", "").replace("EST", "").strip()
    if not date_iso or not gt:
        return None
    for fmt in ("%Y-%m-%d %I:%M %p", "%Y-%m-%d %I:%M%p", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(f"{date_iso[:10]} {gt}", fmt).replace(tzinfo=ET)
        except ValueError:
            continue
    return None


def _record_date(rec: dict) -> str:
    d = str(rec.get("date") or rec.get("slate_date_iso") or rec.get("slate_date") or "")
    return d[:10] if d[:4].isdigit() else ""


def start_time(rec: dict) -> datetime | None:
    """Scheduled first pitch / tip for a pick-like record, if known."""
    for k in ("_starts_at", "unlocks_at", "tip_at", "starts_at_utc"):
        dt = parse_ts(rec.get(k))
        if dt:
            return dt
    date = _record_date(rec)
    for k in ("game_time", "time"):
        if rec.get(k):
            dt = parse_game_time(date, str(rec[k]))
            if dt:
                return dt
    return None


def unlock_time(rec: dict) -> datetime:
    """When a sealed record may go public. Unknown start → 1 AM ET the next
    day: later than any first pitch / tip, earlier than every settle run."""
    dt = start_time(rec)
    if dt:
        return dt.astimezone(UTC)
    date = _record_date(rec)
    try:
        day = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return datetime.max.replace(tzinfo=UTC)  # undated → never auto-unseal
    return (day + timedelta(days=1)).replace(hour=1, tzinfo=ET).astimezone(UTC)


def has_started(rec: dict, now: datetime | None = None) -> bool:
    return (now or now_utc()) >= unlock_time(rec)


def before_start(rec: dict, now: datetime | None = None) -> bool:
    """Known game that has not started yet — the only records seal mode
    seals. Undated legacy rows (e.g. "MAR 2" slate dates) are history."""
    if start_time(rec) is None and not _record_date(rec):
        return False
    return not has_started(rec, now)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── crypto ────────────────────────────────────────────────────────────────

def generate_key() -> str:
    """New PICKS_SEAL_KEY value (urlsafe base64 of 32 random bytes)."""
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def _key_bytes() -> bytes:
    raw = (os.environ.get(KEY_ENV) or "").strip()
    if not raw:
        raise SealError(f"{KEY_ENV} is not set — sealed picks can be neither written nor opened")
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (ValueError, TypeError) as e:
        raise SealError(f"{KEY_ENV} is not urlsafe base64: {e}") from e
    if len(key) != 32:
        raise SealError(f"{KEY_ENV} must decode to 32 bytes (got {len(key)})")
    return key


def have_key() -> bool:
    try:
        _key_bytes()
        return True
    except SealError:
        return False


def _subkey(label: str) -> bytes:
    return hmac.new(_key_bytes(), f"morellosims/seal/{label}/v1".encode(), hashlib.sha256).digest()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def encrypt(obj) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    pt = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    # length-hiding pad: 0x00 never appears in UTF-8 JSON, strip it on open
    padded = pt + b"\x00" * ((-len(pt)) % PAD_BLOCK or (0 if pt else PAD_BLOCK))
    iv = hmac.new(_subkey("siv"), padded, hashlib.sha256).digest()[:12]
    ct = AESGCM(_subkey("enc")).encrypt(iv, padded, _AAD)
    return "v1." + _b64(iv + ct)


def decrypt(blob: str):
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not isinstance(blob, str) or not blob.startswith("v1."):
        raise SealError("unknown sealed_blob format")
    raw = _unb64(blob[3:])
    try:
        padded = AESGCM(_subkey("enc")).decrypt(raw[:12], raw[12:], _AAD)
    except InvalidTag as e:
        raise SealError("sealed_blob failed authentication (wrong PICKS_SEAL_KEY or tampered)") from e
    return json.loads(padded.rstrip(b"\x00").decode("utf-8"))


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def committed_payload(pick: dict) -> dict:
    return {k: v for k, v in pick.items()
            if k not in SEAL_META and k not in LIFECYCLE and not k.startswith("_")}


def commitment_hex(payload: dict, nonce_hex: str) -> str:
    return hashlib.sha256(canonical(payload) + bytes.fromhex(nonce_hex)).hexdigest()


def _derive_nonce(pick_id: str, payload: dict) -> str:
    return hmac.new(_subkey("nonce"), str(pick_id).encode() + b"\n" + canonical(payload),
                    hashlib.sha256).hexdigest()


def verify_record(rec: dict) -> tuple[bool, str]:
    """Check an unsealed pick against its published commitment."""
    if rec.get("sealed"):
        return False, "still sealed"
    for k in ("commitment", "nonce", "seal_keys"):
        if not rec.get(k):
            return False, f"no {k} (pick was never sealed)"
    missing = [k for k in rec["seal_keys"] if k not in rec]
    if missing:
        return False, f"committed field(s) missing: {missing}"
    payload = {k: rec[k] for k in rec["seal_keys"]}
    got = commitment_hex(payload, rec["nonce"])
    if got != rec["commitment"]:
        return False, f"commitment mismatch: sha256 = {got}, published {rec['commitment']}"
    return True, "commitment verified"


# ── generic record helpers ────────────────────────────────────────────────

def is_raw_sealed(rec) -> bool:
    return isinstance(rec, dict) and rec.get("sealed") is True and bool(rec.get("sealed_blob"))


def _strip(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if k not in SEAL_META and not k.startswith("_")}


def _public_only(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if not k.startswith("_")}


def _sealed_passthrough(rec: dict) -> dict:
    """A sealed record we could not open: write back only what a sealed
    record may hold (a consumer may have stamped extra fields on it)."""
    return {k: v for k, v in rec.items() if k in PUBLIC_PICK_FIELDS or k in SEAL_META}


def seal_record(rec: dict, keep, unlock: datetime | None = None, kind: str = "record") -> dict:
    """Internal-file seal: keep `keep` fields public, hide the rest verbatim."""
    plain = _public_only(rec)
    when = unlock or unlock_time(rec)
    out = {k: plain[k] for k in plain if k in keep}
    out["sealed"] = True
    out["unlocks_at"] = iso(when)
    out["sealed_blob"] = encrypt({"kind": kind, "rec": plain})
    return out


def open_record(rec):
    """Internal-file open: verbatim plaintext when the key is present; the
    sealed record unchanged when it is not (callers must pass it through)."""
    if not is_raw_sealed(rec) or not have_key():
        return rec
    return decrypt(rec["sealed_blob"])["rec"]


def open_records(records):
    return [open_record(r) for r in records]


# ── picks/<sport>.json (the public ledger) ────────────────────────────────

def _path(sport_or_path: str) -> str:
    return PICK_FILES.get(sport_or_path, sport_or_path)


def _read_raw(path: str) -> list:
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    return data if isinstance(data, list) else []


def should_seal_pick(rec: dict, now: datetime | None = None) -> bool:
    return seal_mode() and rec.get("status") == "pending" and before_start(rec, now)


def sealed_public_id(plain: dict, commitment: str) -> str:
    """Public id while sealed. MLB ids name both teams only, so they stay.
    NBA ids end with the picked side ("...-spread-min"): while sealed the
    public id swaps that for a commitment prefix; the real id comes back at
    unseal, with "sealed_id" pointing at the sealed one."""
    pid = str(plain.get("id") or "")
    if (plain.get("sport") or "").lower() != "nba" and "-nba-" not in pid:
        return pid
    base = f"{plain.get('date', '')}-nba-{plain.get('away', '')}-{plain.get('home', '')}-{plain.get('bet_type', '')}"
    return f"{base}-sealed-{commitment[:10]}".lower().replace(" ", "")


def seal_pick(rec: dict) -> dict:
    plain = _strip(rec)
    payload = committed_payload(plain)
    nonce = _derive_nonce(plain.get("id", ""), payload)
    when = unlock_time(rec)
    commitment = commitment_hex(payload, nonce)
    pub = {k: plain[k] for k in plain if k in PUBLIC_PICK_FIELDS}
    if "id" in pub:
        pub["id"] = sealed_public_id(plain, commitment)
    pub["sealed"] = True
    pub["unlocks_at"] = iso(when)
    pub["commitment"] = commitment
    pub["sealed_blob"] = encrypt({"kind": "pick", "pick": plain, "nonce": nonce})
    return pub


def open_pick(rec: dict) -> dict:
    """Sealed public record → plaintext pick for in-memory use. Marked
    "sealed": True (so renderers know the public copy is sealed) and carries
    the commitment; picks_store.save_picks strips/rebuilds both."""
    data = decrypt(rec["sealed_blob"])
    pick = dict(data["pick"])
    pick["sealed"] = True
    pick["commitment"] = rec.get("commitment")
    pick["_starts_at"] = rec.get("unlocks_at")
    pick["_nonce"] = data.get("nonce")
    pick["_sealed_id"] = rec.get("id")
    return pick


def load_picks(sport_or_path: str, decrypt_sealed: bool = True) -> list:
    """All picks. Sealed ones are opened when PICKS_SEAL_KEY is present;
    without the key they stay sealed records (no side/odds/pick_text)."""
    raw = _read_raw(_path(sport_or_path))
    if not decrypt_sealed or not any(is_raw_sealed(r) for r in raw) or not have_key():
        return raw
    return [open_pick(r) if is_raw_sealed(r) else r for r in raw]


def is_sealed(rec: dict, now: datetime | None = None) -> bool:
    """Is this pick sealed for the public right now?"""
    if is_raw_sealed(rec):
        return True
    if rec.get("status") != "pending" or not before_start(rec, now):
        return False
    return rec.get("sealed") is True or seal_mode()


def public_view(rec: dict, now: datetime | None = None) -> dict:
    """What a public renderer may show for this pick."""
    if is_raw_sealed(rec):
        return {k: v for k, v in rec.items() if k != "sealed_blob"}
    if not is_sealed(rec, now):
        return rec
    pub = {k: rec[k] for k in rec if k in PUBLIC_PICK_FIELDS}
    pub["sealed"] = True
    pub["unlocks_at"] = iso(unlock_time(rec))
    if rec.get("commitment"):
        pub["commitment"] = rec["commitment"]
    return pub


def load_public_picks(sport_or_path: str, now: datetime | None = None) -> list:
    """Picks as the public may see them right now (never decrypts; seals any
    plaintext pending pre-start pick when seal mode is on — defense in depth)."""
    raw = _read_raw(_path(sport_or_path))
    if not seal_mode() and not any(is_raw_sealed(r) for r in raw):
        return raw
    return [public_view(r, now) for r in raw]


def _unseal(plain: dict, src: dict, prior: dict | None, now: datetime) -> dict:
    """Plaintext + verification fields. `src` is the in-memory record (may
    carry commitment/_nonce), `prior` the raw record on disk (may be sealed)."""
    nonce = src.get("_nonce")
    commitment = src.get("commitment")
    committed = committed_payload(plain)
    sealed_id = src.get("_sealed_id")
    if prior is not None and is_raw_sealed(prior):
        data = decrypt(prior["sealed_blob"])
        nonce = data.get("nonce") or nonce
        commitment = prior.get("commitment") or commitment
        sealed_id = prior.get("id") or sealed_id
        committed_then = committed_payload(data["pick"])
        if committed_then != committed:
            changed = sorted(k for k in set(committed_then) | set(committed)
                             if committed_then.get(k) != committed.get(k))
            print(f"  WARN seal: {plain.get('id')} committed fields changed while sealed: {changed}")
        committed = committed_then
    if not nonce:
        nonce = _derive_nonce(plain.get("id", ""), committed)
    if not commitment:
        commitment = commitment_hex(committed, nonce)
    out = dict(plain)
    if not sealed_id:
        sealed_id = sealed_public_id(plain, commitment)
    if sealed_id != plain.get("id"):
        out["sealed_id"] = sealed_id
    out["unlocks_at"] = (prior or {}).get("unlocks_at") or iso(unlock_time(src))
    out["commitment"] = commitment
    out["nonce"] = nonce
    out["unsealed_at"] = iso(now)
    out["seal_keys"] = sorted(committed)
    return out


def prepare_picks(records: list, prior_raw: list | None = None, now: datetime | None = None) -> list:
    """Records to write: seal pending pre-start picks (seal mode on), unseal
    started ones, carry verification fields forward. Pure no-op when nothing
    is or was sealed."""
    now = now or now_utc()
    prior = {}
    for r in prior_raw or []:
        if not isinstance(r, dict):
            continue
        prior[r.get("id")] = r
        if is_raw_sealed(r) and have_key():
            # index sealed priors by their real id too (NBA public ids differ)
            prior.setdefault(decrypt(r["sealed_blob"])["pick"].get("id"), r)
    out = []
    for r in records:
        if is_raw_sealed(r):
            if has_started(r, now) and have_key():
                r = open_pick(r)
            else:
                out.append(_sealed_passthrough(r))
                continue
        p = prior.get(r.get("id"))
        was_opened = bool(r.get("nonce") and r.get("commitment")) or bool(
            p and not is_raw_sealed(p) and p.get("nonce") and p.get("commitment"))
        was_sealed = r.get("sealed") is True or (p is not None and is_raw_sealed(p))
        plain = _strip(r)
        if was_opened:
            meta = r if (r.get("nonce") and r.get("commitment")) else p
            out.append({**plain, **{k: meta[k] for k in
                                    ("sealed_id", "unlocks_at", "commitment", "nonce", "unsealed_at", "seal_keys")
                                    if k in meta}})
        elif should_seal_pick(r, now):
            if not have_key():
                raise SealError(f"seal mode is on but {KEY_ENV} is missing — refusing to publish "
                                f"{r.get('id')} in plaintext")
            out.append(seal_pick(r))
        elif was_sealed:
            if not have_key():
                out.append(_sealed_passthrough(p) if p is not None and is_raw_sealed(p) else plain)  # cannot open without the key
                continue
            out.append(_unseal(plain, r, p, now))
        elif any(k.startswith("_") for k in r):
            out.append(_public_only(r))
        else:
            out.append(r)
    return out


def dump_picks(records: list, path: str) -> None:
    with open(path, "w") as f:
        json.dump(records, f, indent=2)


def save_picks(sport_or_path: str, records: list, now: datetime | None = None) -> list:
    """Write picks/<sport>.json exactly as json.dump(records, indent=2) did,
    with seal / unseal applied. Returns what was written."""
    path = _path(sport_or_path)
    out = prepare_picks(records, _read_raw(path), now)
    dump_picks(out, path)
    return out


def assert_settleable(picks) -> None:
    """Settlement must only ever see plaintext (the games are over)."""
    bad = [p.get("id") or p.get("matchup") for p in picks
           if is_raw_sealed(p) or p.get("sealed") is True or str(p.get("side") or "") == SEALED_SIDE]
    if bad:
        raise SealError(f"settlement reached sealed pick(s) {bad} — run scripts/unseal_picks.py first "
                        f"(needs {KEY_ENV}); refusing to grade sealed data")


# ── CSV rows (picks.csv, mlbsim/picks_log.csv) ────────────────────────────

BLOB_COL = "sealed_blob"


def seal_csv_row(row: dict, fields, keep, mask: dict | None = None) -> dict:
    plain = {f: ("" if row.get(f) is None else row.get(f)) for f in fields}
    out = {f: (plain[f] if f in keep else (mask or {}).get(f, "")) for f in fields}
    out[BLOB_COL] = encrypt({"kind": "csv", "row": plain})
    return out


def open_csv_row(row: dict, fields) -> dict:
    """Plaintext row (marked _sealed) when the key is present; else unchanged."""
    if not row.get(BLOB_COL) or not have_key():
        return row
    plain = decrypt(row[BLOB_COL])["row"]
    out = {f: plain.get(f, "") for f in fields}
    out["_sealed"] = True
    return out


def csv_fieldnames(fields, rows) -> list:
    return list(fields) + ([BLOB_COL] if any(r.get(BLOB_COL) for r in rows) else [])


# ── public state files (ops/state/*.json are committed) ───────────────────

def state_ref(pick_id) -> str:
    """How a pick is named in committed bot state. NBA ids end with the
    picked side, so under seal mode they are stored as a keyed hash."""
    pid = str(pick_id or "")
    if seal_mode() and "-nba-" in pid and have_key():
        return "h:" + hmac.new(_subkey("ref"), pid.encode(), hashlib.sha256).hexdigest()[:24]
    return pid


def ref_matches(stored, pick_id) -> bool:
    if stored == pick_id:
        return True
    if not (isinstance(stored, str) and stored.startswith("h:") and have_key()):
        return False
    return stored == "h:" + hmac.new(_subkey("ref"), str(pick_id).encode(), hashlib.sha256).hexdigest()[:24]


def ref_in(refs, pick_id) -> bool:
    return any(ref_matches(r, pick_id) for r in refs or [])


# ── text helpers for renderers ────────────────────────────────────────────

def unlock_label(rec: dict) -> str:
    sport = (rec.get("sport") or "mlb").lower()
    return "TIP" if sport == "nba" else "FIRST PITCH"


def sealed_text(rec: dict) -> str:
    return f"SEALED · UNLOCKS AT {unlock_label(rec)}"


def start_label(rec: dict) -> str:
    """'7:15 PM ET' for display (from game_time, or the unlock time)."""
    if rec.get("game_time"):
        return str(rec["game_time"])
    dt = start_time(rec)
    return dt.astimezone(ET).strftime("%-I:%M %p ET") if dt else ""


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "genkey":
        print(generate_key())
    else:
        print(json.dumps({"seal_mode": seal_mode(), "whop_checkout_url": whop_url(),
                          "key_present": have_key()}, indent=2))
