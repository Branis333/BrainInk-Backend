#!/usr/bin/env python3
"""
Backfill script: Populate as_course_assignments.block_id for existing rows.

Strategy (safe defaults):
- For each course and week, assign assignments with NULL block_id to an existing
    block in the same (course_id, week).
- If multiple blocks exist (e.g., block_number 1 and 2), assignments are
    distributed in round-robin order by assignment id to balance load.
- If no block exists for that (course_id, week), we SKIP and log; we DO NOT
    create placeholder blocks.

Usage examples:
    python migrate_backfill_block_ids.py                # all courses, round-robin
    python migrate_backfill_block_ids.py --course-id 1  # only course 1
    python migrate_backfill_block_ids.py --dry-run      # preview only

This script reuses the project's SQLAlchemy configuration when available.
"""
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import argparse
from collections import defaultdict

from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker

# Make local package imports work
sys.path.append(os.path.dirname(__file__))

try:
    from users_micro.db.database import engine as app_engine, SessionLocal as AppSession
    ENGINE = app_engine
    SessionLocal = AppSession
    print("✅ Using existing database configuration from users_micro.db.database")
except Exception as e:
    # Fallback to DATABASE_URL
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set and db.database could not be imported")
    ENGINE = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=ENGINE, autocommit=False, autoflush=False)
    print("⚠️ Using fallback DATABASE_URL from environment")

@dataclass
class Block:
    id: int
    course_id: int
    week: int
    block_number: int

@dataclass
class Assignment:
    id: int
    course_id: int
    week_assigned: Optional[int]


def fetch_blocks(session, course_ids: Optional[List[int]] = None) -> Dict[Tuple[int, int], List[Block]]:
    """Return mapping (course_id, week) -> [Block sorted by block_number]."""
    params = {}
    where = ""
    if course_ids:
        where = "WHERE course_id = ANY(:course_ids)"
        params["course_ids"] = course_ids

    rows = session.execute(text(f"""
        SELECT id, course_id, week, block_number
        FROM as_course_blocks
        {where}
        ORDER BY course_id, week, block_number
    """), params).fetchall()

    mapping: Dict[Tuple[int, int], List[Block]] = defaultdict(list)
    for r in rows:
        mapping[(r.course_id, r.week)].append(Block(id=r.id, course_id=r.course_id, week=r.week, block_number=r.block_number))
    return mapping


def fetch_assignments(session, course_id: Optional[int] = None) -> List[Assignment]:
    """Fetch assignments with NULL block_id but a week_assigned value."""
    params = {}
    where = "WHERE a.block_id IS NULL AND a.week_assigned IS NOT NULL"
    if course_id is not None:
        where += " AND a.course_id = :course_id"
        params["course_id"] = course_id

    rows = session.execute(text(f"""
        SELECT a.id, a.course_id, a.week_assigned
        FROM as_course_assignments a
        {where}
        ORDER BY a.course_id, a.week_assigned, a.id
    """), params).fetchall()

    return [Assignment(id=r.id, course_id=r.course_id, week_assigned=r.week_assigned) for r in rows]


def backfill(session, course_id: Optional[int], dry_run: bool, distribute: str) -> Dict[str, int]:
    """Perform the backfill and return a summary of operations."""
    assert distribute in {"first", "roundrobin"}

    # Target courses set for fetching blocks efficiently
    course_ids = [course_id] if course_id is not None else None
    blocks_map = fetch_blocks(session, course_ids)

    assignments = fetch_assignments(session, course_id)

    summary = {
        "assignments_considered": len(assignments),
        "updated": 0,
        "skipped_no_week": 0,
        "skipped_no_block": 0,
    }

    # Group assignments by (course_id, week)
    grouped: Dict[Tuple[int, int], List[Assignment]] = defaultdict(list)
    for a in assignments:
        if a.week_assigned is None:
            summary["skipped_no_week"] += 1
            continue
        grouped[(a.course_id, a.week_assigned)].append(a)

    for (cid, week), items in grouped.items():
        blocks = blocks_map.get((cid, week), [])
        if not blocks:
            print(f"⏭️  No blocks for course={cid}, week={week} — skipping {len(items)} assignment(s)")
            summary["skipped_no_block"] += len(items)
            continue

        # Sort blocks by block_number already; assign
        if distribute == "first" or len(blocks) == 1:
            target_id = blocks[0].id
            for a in items:
                if not dry_run:
                    session.execute(text("UPDATE as_course_assignments SET block_id = :bid WHERE id = :aid"), {"bid": target_id, "aid": a.id})
                summary["updated"] += 1
            print(f"✅ Course {cid} Week {week}: set block_id={target_id} for {len(items)} assignment(s)")
        else:
            # round robin across blocks for that week
            for idx, a in enumerate(items):
                target_id = blocks[idx % len(blocks)].id
                if not dry_run:
                    session.execute(text("UPDATE as_course_assignments SET block_id = :bid WHERE id = :aid"), {"bid": target_id, "aid": a.id})
                summary["updated"] += 1
            print(f"✅ Course {cid} Week {week}: distributed {len(items)} assignment(s) across {len(blocks)} block(s)")

    if not dry_run:
        session.commit()
        print("💾 Changes committed")
    else:
        session.rollback()
        print("🧪 Dry run: rolled back changes")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Backfill block_id for course assignments")
    parser.add_argument("--course-id", type=int, default=None, help="Limit to a single course id")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without committing")
    parser.add_argument("--assign-mode", choices=["first", "roundrobin"], default="roundrobin", help="How to assign when multiple blocks exist in a week")

    args = parser.parse_args()

    session = SessionLocal()
    try:
        summary = backfill(
            session,
            course_id=args.course_id,
            dry_run=args.dry_run,
            distribute=args.assign_mode,
        )
        print("\n📊 Summary:")
        for k, v in summary.items():
            print(f"  - {k}: {v}")
        print("\n🎉 Backfill completed")
    except Exception as e:
        session.rollback()
        print(f"❌ Backfill failed: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
