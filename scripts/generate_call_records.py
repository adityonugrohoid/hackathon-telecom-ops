"""Deterministic generator for the AlloyDB call_records seed CSV.

Produces ~5,000 call detail records (CDRs) over a 180-day window
(2025-11-01 → 2026-04-30) for the 10 Indonesian cities NetPulse covers.
Output: docs/seed-data/call_records.csv (overwrites).

Status mix (designed to give NL2SQL queries non-trivial answers):
  60% completed   (background traffic, uniformly distributed in time)
  25% dropped     (clustered around outage anchor windows for the city)
  15% failed      (clustered around degradation anchor windows)

The clustering ensures NL questions like "Which towers in Denpasar had
the most failed calls last week?" return statistically interesting
answers — the failures concentrate on certain towers/dates rather than
spreading uniformly.

Determinism: a single random.Random(20260426) is used for every roll,
so re-running yields byte-identical output. The seed value matches the
Phase 10 convention and the network-events generator (so anchor windows
land on the same rolled timestamps if both seeds are the same).

Run:
    python scripts/generate_call_records.py
"""

import csv
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_CSV = PROJECT_ROOT / "docs" / "seed-data" / "call_records.csv"

SEED = 20260426
TARGET_ROW_COUNT = 5_000
WINDOW_START = datetime(2025, 11, 1, 0, 0, 0)
WINDOW_END = datetime(2026, 4, 30, 23, 59, 59)
WINDOW_SECONDS = int((WINDOW_END - WINDOW_START).total_seconds())

REGIONS: list[str] = [
    "Jakarta", "Surabaya", "Bandung", "Medan", "Semarang",
    "Yogyakarta", "Denpasar", "Makassar", "Palembang", "Balikpapan",
]
TOWER_PREFIXES: dict[str, str] = {
    "Jakarta": "JKT", "Surabaya": "SBY", "Bandung": "BDG", "Medan": "MDN",
    "Semarang": "SMG", "Yogyakarta": "YOG", "Denpasar": "DPS",
    "Makassar": "MKS", "Palembang": "PLM", "Balikpapan": "BPN",
}
TOWERS_PER_CITY = 6  # matches the 6-tower scheme already in production seed

CALL_TYPE_WEIGHTS: list[tuple[str, float]] = [
    ("voice", 0.55),
    ("data", 0.30),
    ("sms", 0.15),
]
STATUS_TARGETS: list[tuple[str, float]] = [
    ("completed", 0.60),
    ("dropped", 0.25),
    ("failed", 0.15),
]
ANCHORS_PER_CITY = 8  # outage / degradation centers seeded per city
ANCHOR_WINDOW_HOURS = 4  # ± hours around an anchor where failures cluster


@dataclass(slots=True)
class CallRecord:
    """One row of call_records."""

    call_id: int
    caller_number: str
    receiver_number: str
    call_type: str
    duration_seconds: int
    data_usage_mb: float
    call_date: datetime
    region: str
    cell_tower_id: str
    call_status: str

    def to_csv_row(self) -> list[str]:
        return [
            str(self.call_id),
            self.caller_number,
            self.receiver_number,
            self.call_type,
            str(self.duration_seconds),
            f"{self.data_usage_mb:.1f}",
            self.call_date.strftime("%Y-%m-%d %H:%M:%S"),
            self.region,
            self.cell_tower_id,
            self.call_status,
        ]


def _weighted_choice(rng: random.Random, weighted: list[tuple[str, float]]) -> str:
    """Pick a key from a weight list (weights are read in order, not normalized)."""
    roll = rng.random()
    cumulative = 0.0
    for key, weight in weighted:
        cumulative += weight
        if roll < cumulative:
            return key
    return weighted[-1][0]


def _build_anchor_pools(rng: random.Random) -> dict[str, list[datetime]]:
    """Per-city anchor times where dropped/failed calls cluster."""
    anchors: dict[str, list[datetime]] = {}
    for region in REGIONS:
        anchors[region] = sorted(
            WINDOW_START + timedelta(seconds=rng.randint(0, WINDOW_SECONDS))
            for _ in range(ANCHORS_PER_CITY)
        )
    return anchors


def _phone_pool(rng: random.Random, prefix: str, count: int) -> list[str]:
    """Reusable pool of phone numbers, deterministic for a fixed seed."""
    return [f"{prefix}{rng.randint(1_000_000, 9_999_999)}" for _ in range(count)]


def _call_attributes(
    rng: random.Random, call_type: str
) -> tuple[int, float]:
    """duration_seconds + data_usage_mb tuple per call_type."""
    if call_type == "voice":
        return rng.randint(20, 720), 0.0
    if call_type == "data":
        return 0, round(rng.uniform(50.0, 5_000.0), 1)
    return 0, 0.0  # sms


def _pick_failure_time(
    rng: random.Random, anchors: list[datetime]
) -> datetime:
    """Roll a timestamp clustered ±ANCHOR_WINDOW_HOURS around a random anchor."""
    anchor = rng.choice(anchors)
    offset_min = int(rng.gauss(0, ANCHOR_WINDOW_HOURS * 30))
    candidate = anchor + timedelta(minutes=offset_min)
    if candidate < WINDOW_START:
        candidate = WINDOW_START + timedelta(minutes=rng.randint(0, 1440))
    if candidate > WINDOW_END:
        candidate = WINDOW_END - timedelta(minutes=rng.randint(0, 1440))
    return candidate


def generate_records() -> list[CallRecord]:
    """Build the full CDR list, deterministic for a fixed seed."""
    rng = random.Random(SEED)
    callers = _phone_pool(rng, "0812", 50)
    receivers = _phone_pool(rng, "0813", 50)
    anchors_by_region = _build_anchor_pools(rng)

    target_completed = int(TARGET_ROW_COUNT * 0.60)
    target_dropped = int(TARGET_ROW_COUNT * 0.25)
    target_failed = TARGET_ROW_COUNT - target_completed - target_dropped

    records: list[CallRecord] = []
    next_id = 1

    def make_record(status: str, when: datetime, region: str) -> CallRecord:
        nonlocal next_id
        call_type = _weighted_choice(rng, CALL_TYPE_WEIGHTS)
        duration, data_mb = _call_attributes(rng, call_type)
        tower_idx = rng.randint(1, TOWERS_PER_CITY)
        tower_id = f"{TOWER_PREFIXES[region]}-{tower_idx:03d}"
        rec = CallRecord(
            call_id=next_id,
            caller_number=rng.choice(callers),
            receiver_number=rng.choice(receivers),
            call_type=call_type,
            duration_seconds=duration,
            data_usage_mb=data_mb,
            call_date=when,
            region=region,
            cell_tower_id=tower_id,
            call_status=status,
        )
        next_id += 1
        return rec

    # Completed: uniform across the window, all regions equally weighted.
    for _ in range(target_completed):
        when = WINDOW_START + timedelta(seconds=rng.randint(0, WINDOW_SECONDS))
        region = rng.choice(REGIONS)
        records.append(make_record("completed", when, region))

    # Dropped: clustered around per-city anchor windows. ~50% of dropped calls
    # land on the 1-2 most-active towers per city to give NL queries a clear
    # winner (matches the "this tower is failing" narrative).
    for _ in range(target_dropped):
        region = rng.choice(REGIONS)
        when = _pick_failure_time(rng, anchors_by_region[region])
        rec = make_record("dropped", when, region)
        # Bias half of these to the first 2 towers per city.
        if rng.random() < 0.5:
            tower_idx = rng.randint(1, 2)
            rec.cell_tower_id = f"{TOWER_PREFIXES[region]}-{tower_idx:03d}"
        records.append(rec)

    # Failed: clustered around a different per-city anchor offset, biased
    # toward later towers (3-4) so failed and dropped winners differ.
    for _ in range(target_failed):
        region = rng.choice(REGIONS)
        when = _pick_failure_time(rng, anchors_by_region[region])
        rec = make_record("failed", when, region)
        if rng.random() < 0.5:
            tower_idx = rng.randint(3, 4)
            rec.cell_tower_id = f"{TOWER_PREFIXES[region]}-{tower_idx:03d}"
        records.append(rec)

    # Sort by call_date and renumber so call_id increases with time —
    # mirrors how a real CDR sequence would be issued.
    records.sort(key=lambda r: r.call_date)
    for i, rec in enumerate(records, start=1):
        rec.call_id = i
    return records


def write_csv(records: list[CallRecord], path: Path) -> None:
    """Write the CDRs in the schema setup_alloydb.py expects."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "call_id", "caller_number", "receiver_number", "call_type",
        "duration_seconds", "data_usage_mb", "call_date", "region",
        "cell_tower_id", "call_status",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for rec in records:
            writer.writerow(rec.to_csv_row())
    logger.info("Wrote %d rows to %s", len(records), path)


def main() -> None:
    """Generate the seed and write to docs/seed-data/call_records.csv."""
    records = generate_records()
    write_csv(records, OUTPUT_CSV)
    status_counts: dict[str, int] = {}
    for rec in records:
        status_counts[rec.call_status] = status_counts.get(rec.call_status, 0) + 1
    logger.info("Status mix: %s", status_counts)


if __name__ == "__main__":
    main()
