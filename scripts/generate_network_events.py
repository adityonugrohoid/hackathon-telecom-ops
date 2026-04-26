"""Deterministic generator for the BigQuery network_events seed CSV.

Produces ~50,000 telecom network events over a 180-day window
(2025-11-01 → 2026-04-30) with a realistic outage / maintenance /
degradation / restoration mix for the 10 Indonesian cities the demo
covers. Output: docs/seed-data/network_events.csv (overwrites).

Mix (chosen to look like real ops volume — most events are scheduled):
  70% maintenance   (overnight window, 1-3 h, affected_customers=0)
  22% degradation   (random across the day, 30 min - 6 h, medium impact)
   5% outage        (clustered around regional anchor windows, 2-12 h)
   3% restoration   (paired with each outage, marks resolution)

Determinism: a single random.Random(20260426) is used for every roll,
so re-running yields byte-identical output. The seed value matches the
Phase 10 convention.

Run:
    python scripts/generate_network_events.py
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
OUTPUT_CSV = PROJECT_ROOT / "docs" / "seed-data" / "network_events.csv"

SEED = 20260426
TARGET_ROW_COUNT = 50_000
WINDOW_START = datetime(2025, 11, 1, 0, 0, 0)
WINDOW_END = datetime(2026, 4, 30, 23, 59, 59)
WINDOW_SECONDS = int((WINDOW_END - WINDOW_START).total_seconds())

REGIONS: list[str] = [
    "Jakarta", "Surabaya", "Bandung", "Medan", "Semarang",
    "Yogyakarta", "Denpasar", "Makassar", "Palembang", "Balikpapan",
]

MAINT_DESCRIPTIONS: list[str] = [
    "Firmware upgrade on access layer switches",
    "Battery replacement at multiple cell sites",
    "Capacity expansion on regional fiber backbone",
    "Power system maintenance at switching center",
    "Software upgrade on core router fleet",
    "Antenna realignment on macro tower cluster",
    "Cooling system overhaul at edge data center",
    "BSS database compaction and reindexing",
    "Routine fiber splice inspection on metro ring",
    "Load balancer software patch deployment",
]

DEGRADATION_DESCRIPTIONS: list[str] = [
    "Intermittent DNS resolution failures",
    "Elevated packet loss on regional core link",
    "BGP session flapping on transit peer",
    "Capacity exhaustion on metro aggregation switch",
    "VoLTE codec negotiation failures",
    "Slow paging response on HLR cluster",
    "Throughput degradation on northbound peering link",
    "Authentication latency spikes on AAA cluster",
    "Increased error rate on E1 backhaul circuit",
    "Carrier aggregation failures on LTE-A cells",
]

OUTAGE_DESCRIPTIONS: list[str] = [
    "Submarine cable cut affecting {region} gateway",
    "Fiber backbone cut between {region} and adjacent metro",
    "Tower equipment damage from severe weather event",
    "Power failure at {region} central exchange",
    "Backbone disruption between {region} and Singapore",
    "Submarine cable damage south of {region} landing",
    "Volcanic ash damage to tower fleet near {region}",
    "Flooding damaged ground-level equipment in {region}",
    "Earthquake damage to fiber conduit near {region}",
    "Transformer fire at {region} aggregation hub",
    "Backhoe strike on metro fiber in {region}",
    "DDoS-induced link saturation in {region} POP",
]

RESTORATION_DESCRIPTIONS: list[str] = [
    "Service restored after fiber splice in {region}",
    "Failover to backup path completed for {region}",
    "Equipment replacement complete in {region}",
    "Power restored at {region} central exchange",
    "Cable repair vessel completed splice serving {region}",
]

EVENT_TYPE_WEIGHTS: list[tuple[str, float]] = [
    ("maintenance", 0.70),
    ("degradation", 0.22),
    ("outage", 0.05),
    ("restoration", 0.03),
]


@dataclass(slots=True)
class NetworkEvent:
    """One row of network_events."""

    event_id: str
    event_type: str
    region: str
    severity: str
    description: str
    started_at: datetime
    resolved_at: datetime | None
    affected_customers: int

    def to_csv_row(self) -> list[str]:
        return [
            self.event_id,
            self.event_type,
            self.region,
            self.severity,
            self.description,
            self.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            self.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if self.resolved_at else "",
            str(self.affected_customers),
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


def _maintenance_event(rng: random.Random, event_id: str, region: str) -> NetworkEvent:
    """Overnight scheduled maintenance, low impact."""
    day_offset = rng.randint(0, 179)
    hour = rng.choice([0, 1, 2, 3, 4, 5, 22, 23])
    started = WINDOW_START + timedelta(days=day_offset, hours=hour, minutes=rng.choice([0, 15, 30, 45]))
    duration_min = rng.choice([60, 90, 120, 150, 180])
    resolved = started + timedelta(minutes=duration_min)
    return NetworkEvent(
        event_id=event_id,
        event_type="maintenance",
        region=region,
        severity="minor",
        description=rng.choice(MAINT_DESCRIPTIONS),
        started_at=started,
        resolved_at=resolved,
        affected_customers=0,
    )


def _degradation_event(rng: random.Random, event_id: str, region: str) -> NetworkEvent:
    """Random-time degradation, medium impact, mostly major/minor."""
    started = WINDOW_START + timedelta(seconds=rng.randint(0, WINDOW_SECONDS))
    duration_min = rng.randint(30, 360)
    resolved = started + timedelta(minutes=duration_min)
    severity = rng.choices(["minor", "major", "critical"], weights=[0.55, 0.40, 0.05])[0]
    affected = rng.randint(1_000, 20_000)
    return NetworkEvent(
        event_id=event_id,
        event_type="degradation",
        region=region,
        severity=severity,
        description=rng.choice(DEGRADATION_DESCRIPTIONS),
        started_at=started,
        resolved_at=resolved,
        affected_customers=affected,
    )


def _outage_event(rng: random.Random, event_id: str, region: str) -> NetworkEvent:
    """High-impact outage. Severity skews toward major/critical."""
    started = WINDOW_START + timedelta(seconds=rng.randint(0, WINDOW_SECONDS))
    duration_min = rng.randint(120, 720)
    resolved = started + timedelta(minutes=duration_min)
    severity = rng.choices(["minor", "major", "critical"], weights=[0.10, 0.55, 0.35])[0]
    affected = rng.randint(10_000, 200_000)
    template = rng.choice(OUTAGE_DESCRIPTIONS)
    return NetworkEvent(
        event_id=event_id,
        event_type="outage",
        region=region,
        severity=severity,
        description=template.format(region=region),
        started_at=started,
        resolved_at=resolved,
        affected_customers=affected,
    )


def _restoration_event(
    rng: random.Random, event_id: str, paired_outage: NetworkEvent
) -> NetworkEvent:
    """Pair a restoration row to a parent outage's resolved_at timestamp."""
    started = paired_outage.resolved_at or paired_outage.started_at
    template = rng.choice(RESTORATION_DESCRIPTIONS)
    return NetworkEvent(
        event_id=event_id,
        event_type="restoration",
        region=paired_outage.region,
        severity="minor",
        description=template.format(region=paired_outage.region),
        started_at=started,
        resolved_at=started + timedelta(minutes=rng.randint(5, 30)),
        affected_customers=0,
    )


def generate_events() -> list[NetworkEvent]:
    """Build the full event list, deterministic for a fixed seed."""
    rng = random.Random(SEED)
    events: list[NetworkEvent] = []
    outages: list[NetworkEvent] = []

    next_id = 1

    def make_id() -> str:
        nonlocal next_id
        out = f"EVT{next_id:05d}"
        next_id += 1
        return out

    # First pass: produce maintenance / degradation / outage rows up to budget
    # leaving 3% room for paired restorations.
    primary_target = int(TARGET_ROW_COUNT * 0.97)
    primary_weights = [
        ("maintenance", 0.70 / 0.97),
        ("degradation", 0.22 / 0.97),
        ("outage", 0.05 / 0.97),
    ]
    for _ in range(primary_target):
        event_type = _weighted_choice(rng, primary_weights)
        region = rng.choice(REGIONS)
        eid = make_id()
        if event_type == "maintenance":
            events.append(_maintenance_event(rng, eid, region))
        elif event_type == "degradation":
            events.append(_degradation_event(rng, eid, region))
        else:
            outage = _outage_event(rng, eid, region)
            events.append(outage)
            outages.append(outage)

    # Second pass: pair a restoration row to (most) outages until total = target.
    remaining = TARGET_ROW_COUNT - len(events)
    rng.shuffle(outages)
    for outage in outages[:remaining]:
        events.append(_restoration_event(rng, make_id(), outage))

    # Sort by started_at so the CSV reads chronologically (nicer for humans;
    # BigQuery does not care about row order).
    events.sort(key=lambda e: e.started_at)
    return events


def write_csv(events: list[NetworkEvent], path: Path) -> None:
    """Write the events to CSV in the schema setup_bigquery.py expects."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "event_id", "event_type", "region", "severity", "description",
        "started_at", "resolved_at", "affected_customers",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for event in events:
            writer.writerow(event.to_csv_row())
    logger.info("Wrote %d rows to %s", len(events), path)


def main() -> None:
    """Generate the seed and write to docs/seed-data/network_events.csv."""
    events = generate_events()
    write_csv(events, OUTPUT_CSV)
    type_counts: dict[str, int] = {}
    for event in events:
        type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1
    logger.info("Type mix: %s", type_counts)


if __name__ == "__main__":
    main()
