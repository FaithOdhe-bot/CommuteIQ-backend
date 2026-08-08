"""Stores community reports in Supabase. If SUPABASE_URL/SUPABASE_KEY
aren't set (e.g. running locally before Supabase is configured), falls
back to an in-memory list so the API still works end-to-end for testing.
"""
import os
import time
from typing import Optional

_supabase_client = None
_memory_store: list[dict] = []

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def _get_client():
    global _supabase_client
    if _supabase_client is None and SUPABASE_URL and SUPABASE_KEY:
        from supabase import create_client
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


async def save_report(report: dict) -> dict:
    client = _get_client()
    record = {
        **report,
        "created_at": report.get("created_at") or time.time(),
    }

    if client is None:
        _memory_store.append(record)
        return {"ok": True, "storage": "memory"}

    # Insert only the columns that exist in the Supabase reports table.
    # expires_at was added in the v2 schema — include it if present.
    row = {
        "city":       record.get("city"),
        "type":       record.get("type"),
        "location":   record.get("location"),
        "lat":        record.get("lat"),
        "lng":        record.get("lng"),
        "timestamp":  record.get("timestamp"),
        "created_at": record.get("created_at"),
    }
    # Only add expires_at if the column exists (v2 schema) — won't break
    # if running against the original schema without it.
    if "expires_at" in record:
        row["expires_at"] = record["expires_at"]

    client.table("reports").insert(row).execute()
    return {"ok": True, "storage": "supabase"}


async def list_reports(city: Optional[str] = None) -> list[dict]:
    client = _get_client()

    if client is None:
        if city:
            return [r for r in _memory_store if r.get("city") == city]
        return list(_memory_store)

    query = (
        client.table("reports")
        .select("*")
        .order("created_at", desc=True)
        .limit(100)
    )
    if city:
        query = query.eq("city", city)
    res = query.execute()
    return res.data
