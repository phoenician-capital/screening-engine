"""
Daily Digest Composer.
Builds an HTML email combining IR events, 8-K signals, cluster insider buys,
and portfolio analog recommendations.
"""
from __future__ import annotations

import datetime as dt


_EVENT_TYPE_LABELS = {
    "earnings_date": "Earnings Date",
    "agm": "AGM",
    "presentation": "Presentation",
    "annual_report": "Annual Report",
    "interim_report": "Interim Report",
    "press_release": "Press Release",
    "webcast": "Webcast",
    "other": "Event",
}

_SIGNAL_COLORS = {
    "buyback_authorization": "#059669",
    "ceo_change": "#d97706",
    "ma_announcement": "#1d4ed8",
    "restatement": "#dc2626",
    "earnings_release": "#374151",
    "debt_issuance": "#9ca3af",
    "other": "#9ca3af",
}

_SENTIMENT_COLORS = {
    "positive": "#059669",
    "negative": "#dc2626",
    "neutral": "#9ca3af",
}


class DigestComposer:

    def compose_daily_digest(
        self,
        ir_events: list[dict],
        high_signal_8ks: list[dict],
        cluster_buys: list[dict],
        portfolio_analogs: dict[str, list[str]] | None = None,
    ) -> tuple[str, str]:
        """Returns (subject, html_body)."""
        today = dt.date.today().strftime("%d %b %Y")
        total_items = len(ir_events) + len(high_signal_8ks) + len(cluster_buys)

        subject = f"Phoenician Capital — Daily Intelligence Digest | {today}"
        if total_items == 0:
            subject = f"Phoenician Capital — No New Signals | {today}"

        sections = []

        if ir_events:
            sections.append(self._render_ir_section(ir_events))

        if high_signal_8ks:
            sections.append(self._render_8k_section(high_signal_8ks))

        if cluster_buys:
            sections.append(self._render_insider_section(cluster_buys))

        if portfolio_analogs:
            analog_tickers = {t for tickers in portfolio_analogs.values() for t in tickers}
            if analog_tickers:
                sections.append(self._render_analogs_section(portfolio_analogs))

        if not sections:
            sections.append(
                '<p style="color:#6b7280;font-size:14px">No new signals today. '
                'All portfolio companies are quiet.</p>'
            )

        body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="max-width:680px;margin:32px auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden">

  <!-- Header -->
  <div style="background:#111827;padding:24px 32px">
    <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;color:#9ca3af">
      PHOENICIAN CAPITAL
    </div>
    <div style="font-size:20px;font-weight:700;color:#ffffff;margin-top:4px">
      Daily Intelligence Digest
    </div>
    <div style="font-size:12px;color:#6b7280;margin-top:4px">{today}</div>
  </div>

  <!-- Summary bar -->
  <div style="background:#f9fafb;border-bottom:1px solid #e5e7eb;padding:12px 32px;
              display:flex;gap:24px;font-size:13px;color:#374151">
    <span><strong style="color:#111827">{len(ir_events)}</strong> IR events</span>
    <span><strong style="color:#111827">{len(high_signal_8ks)}</strong> 8-K signals</span>
    <span><strong style="color:#111827">{len(cluster_buys)}</strong> insider clusters</span>
  </div>

  <!-- Content -->
  <div style="padding:24px 32px">
    {"".join(sections)}
  </div>

  <!-- Footer -->
  <div style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:16px 32px;
              font-size:11px;color:#9ca3af;text-align:center">
    Phoenician Capital — Screening Engine · Confidential Internal Use Only
  </div>
</div>
</body>
</html>"""
        return subject, body

    def _section_header(self, title: str) -> str:
        return (
            f'<div style="font-size:11px;font-weight:600;text-transform:uppercase;'
            f'letter-spacing:0.08em;color:#9ca3af;margin:20px 0 10px">{title}</div>'
        )

    def _render_ir_section(self, events: list[dict]) -> str:
        rows = ""
        for e in events[:15]:
            etype = _EVENT_TYPE_LABELS.get(e.get("event_type", "other"), "Event")
            date_str = e.get("event_date") or ""
            url = e.get("url", "")
            title = e.get("title", "")
            ticker = e.get("ticker", "")
            co = e.get("company_name", ticker)
            link = f'<a href="{url}" style="color:#1d4ed8;text-decoration:none">{title}</a>' if url else title
            rows += (
                f'<tr>'
                f'<td style="padding:8px 12px 8px 0;border-bottom:1px solid #f3f4f6;'
                f'font-weight:700;font-size:13px;color:#111827;white-space:nowrap">{ticker}</td>'
                f'<td style="padding:8px 12px 8px 0;border-bottom:1px solid #f3f4f6;'
                f'font-size:12px;color:#6b7280;white-space:nowrap">{etype}</td>'
                f'<td style="padding:8px 0;border-bottom:1px solid #f3f4f6;font-size:13px;color:#374151">{link}</td>'
                f'<td style="padding:8px 0 8px 12px;border-bottom:1px solid #f3f4f6;'
                f'font-size:12px;color:#9ca3af;white-space:nowrap;text-align:right">{date_str}</td>'
                f'</tr>'
            )
        return (
            self._section_header(f"Portfolio IR Events ({len(events)} new)")
            + f'<table style="width:100%;border-collapse:collapse">{rows}</table>'
        )

    def _render_8k_section(self, signals: list[dict]) -> str:
        items = ""
        for s in signals[:10]:
            ticker = s.get("ticker", "")
            sig_type = s.get("signal_type", "other")
            sentiment = s.get("sentiment", "neutral")
            summary = s.get("summary", "")
            color = _SIGNAL_COLORS.get(sig_type, "#9ca3af")
            sent_color = _SENTIMENT_COLORS.get(sentiment, "#9ca3af")
            items += (
                f'<div style="padding:10px 0;border-bottom:1px solid #f3f4f6">'
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
                f'<span style="font-weight:700;font-size:13px;color:#111827">{ticker}</span>'
                f'<span style="background:{color}15;color:{color};border:1px solid {color}33;'
                f'padding:1px 7px;border-radius:3px;font-size:11px;font-weight:600">'
                f'{sig_type.replace("_"," ").title()}</span>'
                f'<span style="background:{sent_color}15;color:{sent_color};'
                f'padding:1px 7px;border-radius:3px;font-size:11px">{sentiment}</span>'
                f'</div>'
                f'<div style="font-size:13px;color:#374151">{summary}</div>'
                f'</div>'
            )
        return self._section_header(f"SEC 8-K Signals ({len(signals)})") + items

    def _render_insider_section(self, clusters: list[dict]) -> str:
        items = ""
        for c in clusters[:10]:
            ticker = c.get("ticker", "")
            count = c.get("distinct_insiders", "?")
            value = c.get("total_value_usd", 0)
            val_str = f"${value/1e3:.0f}K" if value else "—"
            near_low = c.get("near_52wk_low", False)
            low_badge = (
                '<span style="background:#fef3c7;color:#92400e;border:1px solid #fde68a;'
                'padding:1px 6px;border-radius:3px;font-size:11px;font-weight:600;margin-left:6px">'
                'Near 52wk Low</span>'
            ) if near_low else ""
            items += (
                f'<div style="padding:8px 0;border-bottom:1px solid #f3f4f6">'
                f'<span style="font-weight:700;font-size:13px;color:#111827">{ticker}</span>'
                f'<span style="font-size:13px;color:#374151;margin-left:8px">'
                f'{count} insiders · {val_str} total</span>'
                f'{low_badge}</div>'
            )
        return self._section_header(f"Insider Conviction Clusters ({len(clusters)})") + items

    def _render_analogs_section(self, analogs: dict[str, list[str]]) -> str:
        items = ""
        for seed, tickers in analogs.items():
            if tickers:
                items += (
                    f'<div style="padding:6px 0;border-bottom:1px solid #f3f4f6;font-size:13px;color:#374151">'
                    f'<span style="font-weight:700;color:#111827">{seed}</span>'
                    f' → {", ".join(tickers)}</div>'
                )
        return self._section_header("Portfolio Analogs Found") + items
