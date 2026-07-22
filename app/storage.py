"""Stores community reports in Supabase. If SUPABASE_URL/SUPABASE_KEY
aren't set (e.g. running locally before Supabase is configured), falls
back to an in-memory list so the API still works end-to-end for testing —
mirroring the frontend's mock-until-configured pattern.
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
    record = {**report, "created_at": report.get("created_at") or time.time()}

    if client is None:
        _memory_store.append(record)
        return {"ok": True, "storage": "memory"}

    client.table("reports").insert(record).execute()
    return {"ok": True, "storage": "supabase"}


async def list_reports(city: Optional[str] = None) -> list[dict]:
    client = _get_client()

    if client is None:
        if city:
            return [r for r in _memory_store if r.get("city") == city]
        return list(_memory_store)

    query = client.table("reports").select("*").order("created_at", desc=True).limit(100)
    if city:
        query = query.eq("city", city)
    res = query.execute()
    return res.data
