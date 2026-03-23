"""
Database helpers for the Streamlit dashboard — thin async wrappers.

Each call creates a fresh async engine to avoid event-loop conflicts
with Streamlit's asyncio.run() calls.
"""

from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import func as sqlfunc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config.settings import settings
from src.db.models.feedback import Feedback
from src.db.models.insider_purchase import InsiderPurchase
from src.db.models.price_alert import PriceAlert
from src.db.repositories import (
    CompanyRepository,
    FeedbackRepository,
    MetricRepository,
    RecommendationRepository,
)
from src.db.repositories.insider_repo import InsiderRepository
from src.db.repositories.price_alert_repo import PriceAlertRepository

_WEIGHTS_FILE = Path(settings.scoring.weights_file)


# ── Session factory ───────────────────────────────────────────────────────────

async def _get_session():
    engine = create_async_engine(settings.db.dsn, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = factory()
    return engine, session


# ── Rankings ──────────────────────────────────────────────────────────────────

async def get_top_recommendations(limit: int = 20) -> list[dict]:
    engine, session = await _get_session()
    try:
        async with session:
            repo = RecommendationRepository(session)
            company_repo = CompanyRepository(session)
            recs = await repo.get_top_ranked(limit=limit)
            results = []
            for rec in recs:
                company = await company_repo.get_by_ticker(rec.ticker)
                results.append({
                    "id": str(rec.id),
                    "ticker": rec.ticker,
                    "name": company.name if company else "",
                    "exchange": company.exchange if company else "",
                    "country": company.country if company else "",
                    "market_cap_usd": float(company.market_cap_usd) if company and company.market_cap_usd else None,
                    "is_founder_led": company.is_founder_led if company else None,
                    "gics_sector": company.gics_sector if company else "",
                    "fit_score": float(rec.fit_score),
                    "risk_score": float(rec.risk_score),
                    "rank_score": float(rec.rank_score),
                    "rank": rec.rank,
                    "status": rec.status,
                    "memo_text": rec.memo_text,
                    "scoring_detail": rec.scoring_detail,
                    "citations": rec.citations,
                    "generated_at": rec.generated_at,
                })
            return results
    finally:
        await engine.dispose()


# ── Company detail ─────────────────────────────────────────────────────────────

async def get_company(ticker: str) -> dict | None:
    engine, session = await _get_session()
    try:
        async with session:
            repo = CompanyRepository(session)
            company = await repo.get_by_ticker(ticker)
            if not company:
                return None
            return {
                "ticker": company.ticker,
                "name": company.name,
                "exchange": company.exchange,
                "country": company.country,
                "market_cap_usd": float(company.market_cap_usd) if company.market_cap_usd else None,
                "is_founder_led": company.is_founder_led,
                "founder_name": company.founder_name,
                "gics_sector": company.gics_sector,
                "gics_industry": company.gics_industry,
                "gics_sub_industry": company.gics_sub_industry,
                "description": company.description,
                "website": company.website,
                "cik": company.cik,
            }
    finally:
        await engine.dispose()


async def get_company_metrics(ticker: str) -> dict | None:
    engine, session = await _get_session()
    try:
        async with session:
            repo = MetricRepository(session)
            m = await repo.get_latest(ticker)
            if not m:
                return None
            return {
                "revenue": float(m.revenue) if m.revenue else None,
                "gross_margin": float(m.gross_margin) if m.gross_margin else None,
                "ebit_margin": float(m.ebit_margin) if m.ebit_margin else None,
                "roic": float(m.roic) if m.roic else None,
                "roe": float(m.roe) if m.roe else None,
                "fcf": float(m.fcf) if m.fcf else None,
                "fcf_yield": float(m.fcf_yield) if m.fcf_yield else None,
                "capex_to_revenue": float(m.capex_to_revenue) if m.capex_to_revenue else None,
                "net_debt": float(m.net_debt) if m.net_debt else None,
                "net_debt_ebitda": float(m.net_debt_ebitda) if m.net_debt_ebitda else None,
                "revenue_growth_yoy": float(m.revenue_growth_yoy) if m.revenue_growth_yoy else None,
                "revenue_growth_3yr_cagr": float(m.revenue_growth_3yr_cagr) if m.revenue_growth_3yr_cagr else None,
                "ev_ebit": float(m.ev_ebit) if m.ev_ebit else None,
                "ev_fcf": float(m.ev_fcf) if m.ev_fcf else None,
                "pe_ratio": float(m.pe_ratio) if m.pe_ratio else None,
                "analyst_count": m.analyst_count,
                "insider_ownership_pct": float(m.insider_ownership_pct) if m.insider_ownership_pct else None,
                "institutional_ownership_pct": float(m.institutional_ownership_pct) if m.institutional_ownership_pct else None,
                "market_cap_usd": float(m.market_cap_usd) if m.market_cap_usd else None,
                "period_end": str(m.period_end) if m.period_end else None,
            }
    finally:
        await engine.dispose()


async def get_company_recommendation(ticker: str) -> dict | None:
    engine, session = await _get_session()
    try:
        async with session:
            repo = RecommendationRepository(session)
            rec = await repo.get_latest_for_ticker(ticker)
            if not rec:
                return None
            return {
                "id": str(rec.id),
                "fit_score": float(rec.fit_score),
                "risk_score": float(rec.risk_score),
                "rank_score": float(rec.rank_score),
                "rank": rec.rank,
                "status": rec.status,
                "memo_text": rec.memo_text,
                "citations": rec.citations,
                "scoring_detail": rec.scoring_detail,
                "generated_at": rec.generated_at,
            }
    finally:
        await engine.dispose()


async def get_company_documents(ticker: str) -> list[dict]:
    engine, session = await _get_session()
    try:
        async with session:
            from src.db.models.document import Document
            stmt = (
                select(Document)
                .where(Document.ticker == ticker)
                .order_by(Document.published_at.desc().nullslast())
                .limit(50)
            )
            result = await session.execute(stmt)
            docs = result.scalars().all()
            return [
                {
                    "doc_type": d.doc_type,
                    "title": d.title,
                    "source": d.source,
                    "source_url": d.source_url,
                    "accession_no": d.accession_no,
                    "published_at": str(d.published_at)[:10] if d.published_at else "—",
                }
                for d in docs
            ]
    finally:
        await engine.dispose()


async def get_company_feedback_history(ticker: str) -> list[dict]:
    engine, session = await _get_session()
    try:
        async with session:
            repo = FeedbackRepository(session)
            entries = await repo.get_for_ticker(ticker)
            return [
                {
                    "date": str(e.created_at)[:10] if e.created_at else "—",
                    "action": e.action,
                    "reject_reason": e.reject_reason or "—",
                    "notes": e.notes or "—",
                    "analyst_id": e.analyst_id or "—",
                }
                for e in entries
            ]
    finally:
        await engine.dispose()


# ── Feedback submission ───────────────────────────────────────────────────────

async def submit_feedback(
    rec_id: str,
    ticker: str,
    action: str,
    reject_reason: str | None = None,
    notes: str | None = None,
) -> None:
    engine, session = await _get_session()
    try:
        async with session:
            fb = Feedback(
                recommendation_id=uuid.UUID(rec_id),
                ticker=ticker,
                action=action,
                reject_reason=reject_reason,
                notes=notes,
            )
            session.add(fb)

            rec_repo = RecommendationRepository(session)
            status_map = {
                "reject": "rejected",
                "watch": "watched",
                "research_now": "researching",
            }
            new_status = status_map.get(action)
            if new_status:
                await rec_repo.update_status(uuid.UUID(rec_id), new_status)

            await session.commit()
    finally:
        await engine.dispose()


# ── Watchlist ─────────────────────────────────────────────────────────────────

async def get_watchlist_with_scores() -> list[dict]:
    engine, session = await _get_session()
    try:
        async with session:
            from src.db.models.watchlist import WatchlistEntry
            stmt = (
                select(WatchlistEntry)
                .order_by(WatchlistEntry.added_at.desc())
                .limit(100)
            )
            result = await session.execute(stmt)
            entries = result.scalars().all()

            company_repo = CompanyRepository(session)
            rec_repo = RecommendationRepository(session)

            out = []
            for e in entries:
                company = await company_repo.get_by_ticker(e.ticker)
                rec = await rec_repo.get_latest_for_ticker(e.ticker)
                out.append({
                    "id": str(e.id),
                    "ticker": e.ticker,
                    "name": company.name if company else "",
                    "exchange": company.exchange if company else "",
                    "market_cap_usd": float(company.market_cap_usd) if company and company.market_cap_usd else None,
                    "fit_score": float(rec.fit_score) if rec else None,
                    "risk_score": float(rec.risk_score) if rec else None,
                    "rec_id": str(rec.id) if rec else None,
                    "trigger_condition": e.trigger_condition,
                    "added_at": str(e.added_at)[:10] if e.added_at else "—",
                })
            return out
    finally:
        await engine.dispose()


async def remove_from_watchlist(entry_id: str) -> None:
    engine, session = await _get_session()
    try:
        async with session:
            from src.db.models.watchlist import WatchlistEntry
            stmt = select(WatchlistEntry).where(WatchlistEntry.id == uuid.UUID(entry_id))
            result = await session.execute(stmt)
            entry = result.scalar_one_or_none()
            if entry:
                await session.delete(entry)
                await session.commit()
    finally:
        await engine.dispose()


# ── Analytics ─────────────────────────────────────────────────────────────────

async def get_feedback_summary() -> dict[str, Any]:
    engine, session = await _get_session()
    try:
        async with session:
            repo = FeedbackRepository(session)
            stmt = (
                select(Feedback.action, sqlfunc.count(Feedback.id))
                .group_by(Feedback.action)
            )
            result = await session.execute(stmt)
            counts = {row[0]: row[1] for row in result.all()}
            total = sum(counts.values())
            reject_reasons = await repo.get_reject_reasons_summary()
            return {
                "total": total,
                "research_now": counts.get("research_now", 0),
                "watch": counts.get("watch", 0),
                "reject": counts.get("reject", 0),
                "reject_reasons": reject_reasons,
            }
    finally:
        await engine.dispose()


async def get_action_rates() -> dict:
    summary = await get_feedback_summary()
    total = summary["total"] or 1
    return {
        "total": summary["total"],
        "research_rate": round(summary["research_now"] / total * 100, 1),
        "watch_rate": round(summary["watch"] / total * 100, 1),
        "reject_rate": round(summary["reject"] / total * 100, 1),
        "research_now": summary["research_now"],
        "watch": summary["watch"],
        "reject": summary["reject"],
    }


async def get_recent_actions(limit: int = 20) -> list[dict]:
    engine, session = await _get_session()
    try:
        async with session:
            stmt = (
                select(Feedback)
                .order_by(Feedback.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            entries = result.scalars().all()
            return [
                {
                    "date": str(e.created_at)[:16].replace("T", " ") if e.created_at else "—",
                    "ticker": e.ticker,
                    "action": e.action,
                    "reject_reason": e.reject_reason or "—",
                    "notes": e.notes or "",
                }
                for e in entries
            ]
    finally:
        await engine.dispose()


async def get_weight_evolution() -> list[dict]:
    """Extract weight snapshots from scoring_run config_snapshot JSONB."""
    engine, session = await _get_session()
    try:
        async with session:
            from src.db.models.scoring_run import ScoringRun
            stmt = (
                select(ScoringRun)
                .where(ScoringRun.config_snapshot.isnot(None))
                .order_by(ScoringRun.run_at.asc())
                .limit(30)
            )
            result = await session.execute(stmt)
            runs = result.scalars().all()
            snapshots = []
            for run in runs:
                snap = run.config_snapshot or {}
                cats = snap.get("categories", {})
                if cats:
                    snapshots.append({
                        "run_at": str(run.run_at)[:10],
                        **{k: v.get("weight", 0) for k, v in cats.items()},
                    })
            return snapshots
    finally:
        await engine.dispose()


# ── Settings (YAML read/write) ────────────────────────────────────────────────

def load_current_settings() -> dict:
    if _WEIGHTS_FILE.exists():
        with open(_WEIGHTS_FILE) as f:
            return yaml.safe_load(f) or {}
    return {}


def save_settings(data: dict) -> None:
    with open(_WEIGHTS_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


# ── Insider Buying ─────────────────────────────────────────────────────────────

async def get_cluster_buys(lookback_days: int = 14) -> list[dict]:
    engine, session = await _get_session()
    try:
        async with session:
            repo = InsiderRepository(session)
            company_repo = CompanyRepository(session)
            purchases = await repo.get_cluster_buys(days=lookback_days)

            clusters: dict[str, dict] = {}
            for p in purchases:
                if p.ticker not in clusters:
                    company = await company_repo.get_by_ticker(p.ticker)
                    clusters[p.ticker] = {
                        "ticker": p.ticker,
                        "name": company.name if company else p.ticker,
                        "insiders": [],
                        "total_value": 0.0,
                        "dates": [],
                    }
                if p.insider_name not in clusters[p.ticker]["insiders"]:
                    clusters[p.ticker]["insiders"].append(p.insider_name)
                clusters[p.ticker]["total_value"] += float(p.total_value or 0)
                if p.transaction_date:
                    date_str = str(p.transaction_date)
                    if date_str not in clusters[p.ticker]["dates"]:
                        clusters[p.ticker]["dates"].append(date_str)

            return list(clusters.values())
    finally:
        await engine.dispose()


async def get_top_conviction_purchases(limit: int = 20, lookback_days: int = 30) -> list[dict]:
    engine, session = await _get_session()
    try:
        async with session:
            repo = InsiderRepository(session)
            company_repo = CompanyRepository(session)
            purchases = await repo.get_top_conviction(limit=limit, days=lookback_days)
            out = []
            for i, p in enumerate(purchases, 1):
                company = await company_repo.get_by_ticker(p.ticker)
                out.append({
                    "rank": i,
                    "id": str(p.id),
                    "ticker": p.ticker,
                    "name": company.name if company else "",
                    "insider_name": p.insider_name,
                    "insider_title": p.insider_title or "—",
                    "shares": p.shares,
                    "total_value": float(p.total_value or 0),
                    "conviction_score": float(p.conviction_score or 0),
                    "is_cluster": p.is_cluster,
                    "transaction_date": str(p.transaction_date),
                    "form4_url": p.form4_url,
                })
            return out
    finally:
        await engine.dispose()


async def get_all_insider_purchases(lookback_days: int = 30) -> list[dict]:
    engine, session = await _get_session()
    try:
        async with session:
            repo = InsiderRepository(session)
            purchases = await repo.get_recent(days=lookback_days)
            return [
                {
                    "id": str(p.id),
                    "ticker": p.ticker,
                    "insider_name": p.insider_name,
                    "insider_title": p.insider_title or "—",
                    "shares": p.shares,
                    "price_per_share": float(p.price_per_share or 0),
                    "total_value": float(p.total_value or 0),
                    "conviction_score": float(p.conviction_score or 0),
                    "is_cluster": p.is_cluster,
                    "transaction_date": str(p.transaction_date),
                    "form4_url": p.form4_url,
                }
                for p in purchases
            ]
    finally:
        await engine.dispose()


# ── Price Alerts ──────────────────────────────────────────────────────────────

async def get_triggered_alerts() -> list[dict]:
    engine, session = await _get_session()
    try:
        async with session:
            repo = PriceAlertRepository(session)
            company_repo = CompanyRepository(session)
            alerts = await repo.get_triggered()
            out = []
            for a in alerts:
                company = await company_repo.get_by_ticker(a.ticker)
                target = float(a.target_price)
                triggered = float(a.triggered_price) if a.triggered_price else None
                pct_below = ((target - triggered) / target * 100) if triggered else None
                out.append({
                    "id": str(a.id),
                    "ticker": a.ticker,
                    "name": company.name if company else a.ticker,
                    "target_price": target,
                    "triggered_price": triggered,
                    "pct_below": pct_below,
                    "triggered_at": str(a.triggered_at)[:10] if a.triggered_at else "—",
                    "notes": a.notes or "",
                })
            return out
    finally:
        await engine.dispose()


async def get_active_price_targets() -> list[dict]:
    engine, session = await _get_session()
    try:
        async with session:
            repo = PriceAlertRepository(session)
            company_repo = CompanyRepository(session)
            alerts = await repo.get_active()
            out = []
            for a in alerts:
                company = await company_repo.get_by_ticker(a.ticker)
                target = float(a.target_price)
                out.append({
                    "id": str(a.id),
                    "ticker": a.ticker,
                    "name": company.name if company else a.ticker,
                    "target_price": target,
                    "current_price": None,
                    "notes": a.notes or "",
                    "expires_at": str(a.expires_at) if a.expires_at else "—",
                    "created_at": str(a.created_at)[:10] if a.created_at else "—",
                })
            return out
    finally:
        await engine.dispose()


async def get_alert_history(limit: int = 50) -> list[dict]:
    engine, session = await _get_session()
    try:
        async with session:
            repo = PriceAlertRepository(session)
            alerts = await repo.get_history(limit=limit)
            return [
                {
                    "id": str(a.id),
                    "ticker": a.ticker,
                    "target_price": float(a.target_price),
                    "triggered_price": float(a.triggered_price) if a.triggered_price else None,
                    "status": a.status,
                    "notes": a.notes or "",
                    "triggered_at": str(a.triggered_at)[:10] if a.triggered_at else "—",
                }
                for a in alerts
            ]
    finally:
        await engine.dispose()


async def create_price_alert(
    ticker: str,
    target_price: float,
    notes: str = "",
    expires_at: dt.date | None = None,
) -> None:
    engine, session = await _get_session()
    try:
        async with session:
            alert = PriceAlert(
                ticker=ticker.upper().strip(),
                target_price=target_price,
                notes=notes,
                expires_at=expires_at,
                status="active",
            )
            session.add(alert)
            await session.commit()
    finally:
        await engine.dispose()


async def dismiss_alert(alert_id: str) -> None:
    engine, session = await _get_session()
    try:
        async with session:
            repo = PriceAlertRepository(session)
            await repo.dismiss(uuid.UUID(alert_id))
            await session.commit()
    finally:
        await engine.dispose()
