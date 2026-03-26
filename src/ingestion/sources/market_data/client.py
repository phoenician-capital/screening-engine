"""
Market data client — production global data pipeline.

US companies:
  - Universe:   NASDAQ Trader API  (free, no key, ~7000 US tickers + market cap)
  - Financials: SEC EDGAR XBRL API (free, no key, official, ~10 req/sec)
  - Price:      Yahoo Finance v8 chart (free, not rate-limited like v10)

Non-US companies:
  - Universe:   Curated list of major international exchanges
                pulled from GitHub open datasets
  - Price/mktcap: Yahoo Finance v8 chart
  - Financials: Yahoo Finance financialData module (v10 with fresh crumb per session)
                Falls back to LLM single-call if Yahoo blocked

Excluded: China (mainland), Russia, Iran — per investment mandate.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time as _time
from typing import Any

import httpx

from src.config.settings import settings

# ── Redis cache helper ─────────────────────────────────────────────────────────
def _get_redis():
    """Get Redis client, returns None if unavailable."""
    try:
        import redis as _redis
        r = _redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.db,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        r.ping()
        return r
    except Exception:
        return None

_redis_client = None

def _redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = _get_redis()
    return _redis_client

def _cache_get(key: str) -> dict | None:
    try:
        r = _redis()
        if not r:
            return None
        val = r.get(key)
        return json.loads(val) if val else None
    except Exception:
        return None

def _cache_set(key: str, value: dict, ttl: int = 86400) -> None:
    try:
        r = _redis()
        if r:
            r.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass

logger = logging.getLogger(__name__)

_UA   = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36"
_EDGAR_UA = settings.ingestion.sec_edgar_user_agent

# Exchanges excluded per mandate
_EXCLUDED_EXCHANGES = {"SHH", "SHZ", "MOEX", "TSE"}  # Shanghai, Shenzhen, Moscow, Tehran

# XBRL concept fallback chains
_REVENUE_CONCEPTS   = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "RevenuesNetOfInterestExpense",          # banks
    "NetRevenues",
    "TotalRevenues",
    "InvestmentIncomeNet",                   # investment companies / BDCs
    "InvestmentIncomeDividend",
    "RealEstateRevenueNet",                  # REITs
    "InterestAndFeeIncomeLoansAndLeases",    # banks/thrifts
]
# IFRS equivalents (foreign private issuers filing 20-F)
_IFRS_REVENUE   = ["Revenue", "RevenueFromContractsWithCustomers",
                   "Revenues", "OtherOperatingIncome",
                   "RevenueOfCombinedEntity", "SalesRevenueNet"]
_IFRS_GP        = ["GrossProfit"]
_IFRS_EBIT      = ["ProfitLossFromOperatingActivities", "OperatingProfit"]
_IFRS_NI        = ["ProfitLoss", "NetProfitLoss"]
_IFRS_OPCF      = ["CashFlowsFromUsedInOperatingActivities"]
_IFRS_CAPEX     = ["PurchaseOfPropertyPlantAndEquipment",
                   "AcquisitionOfPropertyPlantAndEquipment"]
_IFRS_CASH      = ["CashAndCashEquivalents"]
_IFRS_DEBT      = ["LongtermBorrowings", "Borrowings"]
_IFRS_ASSETS    = ["Assets", "TotalAssets"]
_IFRS_EQUITY    = ["Equity", "TotalEquity"]
_GP_CONCEPTS        = ["GrossProfit"]  # Banks have no gross profit — leave as null
_EBIT_CONCEPTS      = ["OperatingIncomeLoss", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"]
_NI_CONCEPTS        = ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"]
_OPCF_CONCEPTS      = ["NetCashProvidedByUsedInOperatingActivities"]
_CAPEX_CONCEPTS     = ["PaymentsToAcquirePropertyPlantAndEquipment",
                        "CapitalExpendituresIncurredButNotYetPaid"]
_CASH_CONCEPTS      = ["CashAndCashEquivalentsAtCarryingValue",
                        "CashCashEquivalentsAndShortTermInvestments",
                        "CashAndCashEquivalentsAtCarryingValueIncludingDiscontinuedOperations"]
_DEBT_CONCEPTS      = ["LongTermDebt", "LongTermDebtAndCapitalLeaseObligations",
                        "DebtAndCapitalLeaseObligations", "LongTermDebtNoncurrent"]
_ASSETS_CONCEPTS    = ["Assets", "AssetsCurrent"]
_EQUITY_CONCEPTS    = ["StockholdersEquity",
                        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
                        "CommonStockholdersEquity"]
_SHARES_CONCEPTS    = ["CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"]
_DEP_CONCEPTS       = ["DepreciationDepletionAndAmortization", "Depreciation",
                        "DepreciationAndAmortization"]

# SIC 2-digit prefixes to skip at universe build (mirrors scoring hard filters)
_EXCLUDED_SIC_PREFIXES = {
    "10", "11", "12", "13", "14",  # Mining / Oil & Gas / Energy
    "29",                           # Petroleum refining
    "49",                           # Utilities
}

_SIC_SECTOR: dict[str, str] = {
    "10": "Energy", "11": "Energy", "12": "Energy", "13": "Energy", "14": "Mining",
    "15": "Construction", "16": "Construction", "17": "Construction",
    "20": "Consumer Staples", "21": "Consumer Staples",
    "22": "Consumer Discretionary", "23": "Consumer Discretionary",
    "25": "Consumer Discretionary", "26": "Materials", "27": "Communication Services",
    "28": "Health Care", "29": "Energy",
    "30": "Materials", "32": "Materials", "33": "Materials", "34": "Industrials",
    "35": "Information Technology", "36": "Information Technology",
    "37": "Consumer Discretionary", "38": "Health Care",
    "39": "Industrials",
    "40": "Industrials", "41": "Industrials", "42": "Industrials",
    "44": "Industrials", "45": "Industrials", "48": "Communication Services",
    "49": "Utilities",
    "50": "Industrials", "51": "Consumer Staples",
    "52": "Consumer Discretionary", "53": "Consumer Discretionary",
    "54": "Consumer Staples", "55": "Consumer Discretionary",
    "56": "Consumer Discretionary", "57": "Consumer Discretionary",
    "58": "Consumer Discretionary", "59": "Consumer Discretionary",
    "60": "Financials", "61": "Financials", "62": "Financials",
    "63": "Financials", "65": "Real Estate", "67": "Financials",
    "70": "Consumer Discretionary", "72": "Consumer Discretionary",
    "73": "Information Technology", "75": "Consumer Discretionary",
    "78": "Communication Services", "79": "Consumer Discretionary",
    "80": "Health Care", "82": "Consumer Discretionary",
    "87": "Industrials",
}


# ── HTTP helpers ──────────────────────────────────────────────────────────────

async def _get(client: httpx.AsyncClient, url: str,
               headers: dict | None = None, params: dict | None = None,
               retries: int = 3) -> Any:
    for attempt in range(retries):
        try:
            r = await client.get(url, headers=headers or {}, params=params or {})
            if r.status_code in (429, 503):
                await asyncio.sleep(2 ** attempt)
                continue
            if r.status_code == 404:
                return None
            if r.status_code != 200:
                return None
            return r.json()
        except (httpx.TimeoutException, httpx.ConnectError):
            if attempt == retries - 1:
                return None
            await asyncio.sleep(1)
    return None


# ── Yahoo Finance v8 price (not rate-limited) ─────────────────────────────────

async def _get_price_and_shares(client: httpx.AsyncClient,
                                 ticker: str) -> tuple[float | None, float | None, str, str]:
    """Returns (price, shares, exchange, currency) via Yahoo v8 chart."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    data = await _get(client, url,
                      headers={"User-Agent": _UA, "Accept": "application/json"},
                      params={"interval": "1d", "range": "2d"})
    if not data:
        return None, None, "", ""
    meta = (data.get("chart", {}).get("result") or [{}])[0].get("meta", {})
    price    = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
    shares   = meta.get("sharesOutstanding") or meta.get("impliedSharesOutstanding")
    exchange = meta.get("exchangeName", "")
    currency = meta.get("currency", "USD")
    return (float(price) if price else None,
            float(shares) if shares else None,
            exchange, currency)


# ── EDGAR XBRL helpers ────────────────────────────────────────────────────────

def _latest_annual(facts: dict, concepts: list[str],
                   balance_sheet: bool = False) -> float | None:
    """
    Get the most recent 10-K/20-F annual value for a list of fallback concepts.
    Tries USD first, then any available currency (for foreign filers reporting in EUR/CAD/GBP etc).
    balance_sheet=True skips the period-length filter (point-in-time balance sheet items).
    """
    _ANNUAL_FORMS = ("10-K", "10-K/A", "20-F", "20-F/A")

    for c in concepts:
        data = facts.get(c)
        if not data:
            continue
        units = data.get("units", {})
        # Try USD first, then any other currency (foreign filers)
        currencies_to_try = ["USD"] + [k for k in units if k not in ("USD", "shares", "pure")]
        raw: list = []
        for currency in currencies_to_try:
            raw = units.get(currency) or []
            if raw:
                break
        if not raw:
            raw = units.get("shares") or []
        usd = raw  # may be non-USD but we'll use it as a relative magnitude
        if balance_sheet:
            # Balance sheet: just filter by form type, no period check
            annual = [v for v in usd
                      if v.get("form") in _ANNUAL_FORMS
                      and v.get("val") is not None]
        else:
            # Income / cash flow: must be ~12-month period
            annual = [v for v in usd
                      if v.get("form") in _ANNUAL_FORMS
                      and v.get("val") is not None
                      and _months(v.get("start", ""), v.get("end", "")) in range(10, 15)]
        if not annual:
            continue
        annual.sort(key=lambda x: x.get("end", ""), reverse=True)
        return float(annual[0]["val"])
    return None


def _annual_series(facts: dict, concepts: list[str], n: int = 4) -> list[float]:
    _ANNUAL_FORMS = ("10-K", "10-K/A", "20-F", "20-F/A")
    for c in concepts:
        data = facts.get(c)
        if not data:
            continue
        units = data.get("units", {})
        currencies_to_try = ["USD"] + [k for k in units if k not in ("USD", "shares", "pure")]
        usd: list = []
        for currency in currencies_to_try:
            usd = units.get(currency) or []
            if usd:
                break
        annual = [v for v in usd
                  if v.get("form") in _ANNUAL_FORMS
                  and v.get("val") is not None
                  and _months(v.get("start",""), v.get("end","")) in range(10, 15)]
        if not annual:
            continue
        annual.sort(key=lambda x: x.get("end", ""))
        return [float(v["val"]) for v in annual[-n:]]
    return []


def _months(start: str, end: str) -> int:
    try:
        return (int(end[:4]) - int(start[:4])) * 12 + (int(end[5:7]) - int(start[5:7]))
    except Exception:
        return 0


async def _fetch_fmp_financials(client: httpx.AsyncClient,
                                ticker: str) -> dict[str, Any] | None:
    """
    Fetch full financial profile from FMP Stable API.
    Returns a dict compatible with _compute_metrics() or None if unavailable.
    Covers both US and international tickers.
    """
    # Check cache first (24h TTL)
    cache_key = f"fmp:fin:{ticker}"
    cached = _cache_get(cache_key)
    if cached:
        logger.debug("FMP cache hit for %s", ticker)
        return cached

    key = settings.ingestion.fmp_api_key
    if not key:
        return None

    base = "https://financialmodelingprep.com/stable"

    async def _fmp(endpoint: str, **params) -> list | dict | None:
        url = f"{base}/{endpoint}"
        for attempt in range(3):
            try:
                r = await client.get(url, params={"symbol": ticker, "limit": 2,
                                                   "apikey": key, **params})
                if r.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                    continue
                if r.status_code in (402, 403):
                    return None   # not on this plan
                if r.status_code != 200:
                    return None
                return r.json()
            except Exception:
                if attempt == 2:
                    return None
                await asyncio.sleep(1)
        return None

    # Parallel fetch
    income_task    = asyncio.create_task(_fmp("income-statement"))
    cashflow_task  = asyncio.create_task(_fmp("cash-flow-statement"))
    metrics_task   = asyncio.create_task(_fmp("key-metrics"))
    ratios_task    = asyncio.create_task(_fmp("ratios"))
    profile_task   = asyncio.create_task(_fmp("profile"))

    income_data, cf_data, metrics_data, ratios_data, profile_data = await asyncio.gather(
        income_task, cashflow_task, metrics_task, ratios_task, profile_task
    )

    # Need at least income data
    if not income_data or not isinstance(income_data, list) or not income_data:
        return None

    inc  = income_data[0]
    inc1 = income_data[1] if len(income_data) > 1 else {}
    cf   = (cf_data or [{}])[0]
    km   = (metrics_data or [{}])[0]
    rat  = (ratios_data or [{}])[0]
    pro  = profile_data[0] if isinstance(profile_data, list) and profile_data else (profile_data or {})

    revenue      = inc.get("revenue")
    gross_profit = inc.get("grossProfit")
    ebit         = inc.get("ebit") or inc.get("operatingIncome")
    net_income   = inc.get("netIncome") or inc.get("bottomLineNetIncome")
    ebitda       = inc.get("ebitda")
    dep          = inc.get("depreciationAndAmortization")
    op_cf            = cf.get("netCashProvidedByOperatingActivities") or cf.get("operatingCashFlow")
    capex_raw        = cf.get("capitalExpenditure") or cf.get("investmentsInPropertyPlantAndEquipment")
    capex            = abs(capex_raw) if capex_raw is not None else None
    fcf              = cf.get("freeCashFlow") or ((op_cf - capex) if op_cf and capex else op_cf)
    cash             = cf.get("cashAtEndOfPeriod")
    stock_repurchased = cf.get("commonStockRepurchased") or cf.get("netCommonStockIssuance")
    stock_based_comp  = cf.get("stockBasedCompensation")
    acquisitions_net  = cf.get("acquisitionsNet")
    market_cap        = km.get("marketCap") or (pro.get("marketCap") if isinstance(pro, dict) else None)

    # Revenue growth
    rev_yoy = None
    rev1 = inc1.get("revenue") if inc1 else None
    if revenue and rev1 and rev1 > 0:
        rev_yoy = (revenue - rev1) / rev1

    # Net debt
    net_debt_ebitda = km.get("netDebtToEBITDA")

    # ROIC / ROE from key-metrics
    roic = km.get("returnOnInvestedCapital")
    roe  = km.get("returnOnEquity")

    # Sector from profile
    sector      = pro.get("sector", "")      if isinstance(pro, dict) else ""
    country     = pro.get("country", "")     if isinstance(pro, dict) else ""
    website     = pro.get("website", "")     if isinstance(pro, dict) else ""
    description = pro.get("description", "") if isinstance(pro, dict) else ""
    ceo_name    = pro.get("ceo", "")         if isinstance(pro, dict) else ""
    ipo_date    = pro.get("ipoDate", "")     if isinstance(pro, dict) else ""
    company_name_pro = pro.get("companyName", "") if isinstance(pro, dict) else ""
    is_etf  = pro.get("isEtf",  False) if isinstance(pro, dict) else False
    is_fund = pro.get("isFund", False) if isinstance(pro, dict) else False

    if is_etf or is_fund:
        return {"excluded": True}

    # ── Founder detection ──────────────────────────────────────────────────────
    # Heuristic: if company is < 25 years old AND CEO has been there a long time
    # OR if CEO last name appears in company name (eponymous founders)
    is_founder_led = None
    try:
        import datetime as _dt
        if ipo_date and ceo_name:
            ipo_year = int(str(ipo_date)[:4])
            company_age = _dt.date.today().year - ipo_year
            ceo_last = ceo_name.strip().split()[-1].lower() if ceo_name.strip() else ""
            name_lower = (company_name_pro or ticker).lower()

            # Strong signal: CEO last name in company name (e.g. Bezos/Amazon excluded but
            # Walton/Walmart, Wozniak/Apple type patterns)
            if len(ceo_last) > 3 and ceo_last in name_lower:
                is_founder_led = True
            # Moderate signal: company < 20 years old (founder likely still at helm)
            elif company_age <= 20:
                is_founder_led = True
            # Professional management signal: large old company
            elif company_age >= 40 and market_cap and market_cap > 5e9:
                is_founder_led = False
    except Exception:
        pass

    # ── Insider / institutional ownership from key-metrics ───────────────────
    insider_ownership_pct = km.get("insiderOwnershipTTM") or km.get("insiderOwnership")

    # EV metrics
    ev_ebitda   = km.get("evToEBITDA")
    fcf_yield   = km.get("freeCashFlowYield")
    capex_rev   = km.get("capexToRevenue")

    logger.info("FMP financials for %s: rev=$%.0fM gm=%.1f%% roic=%.1f%%",
                ticker,
                (revenue or 0) / 1e6,
                ((gross_profit / revenue * 100) if gross_profit and revenue else 0),
                (roic or 0) * 100)

    result = {
        "sector":               sector,
        "country":              country,
        "website":              website,
        "description":          description,
        "revenue":              revenue,
        "gross_profit":         gross_profit,
        "ebit":                 ebit,
        "net_income":           net_income,
        "fcf":                  fcf,
        "capex":                capex,
        "cash":                 cash,
        "total_debt":           None,
        "net_debt":             None,
        "ebitda":               ebitda,
        "total_assets":         None,
        "equity":               None,
        "rev_series":           [rev1, revenue] if rev1 and revenue else ([revenue] if revenue else []),
        "revenue_growth":       rev_yoy,
        "roic":                 roic,
        "roe":                  roe,
        "net_debt_ebitda_direct": net_debt_ebitda,
        "ev_ebitda_direct":     ev_ebitda,
        "fcf_yield_direct":     fcf_yield,
        "capex_rev_direct":     capex_rev,
        "market_cap_fmp":       market_cap,
        "is_founder_led":        is_founder_led,
        "insider_ownership_pct": insider_ownership_pct,
        "ceo_name":              ceo_name,
        "stock_repurchased":     stock_repurchased,
        "stock_based_compensation": stock_based_comp,
        "acquisitions_net":      acquisitions_net,
    }
    _cache_set(f"fmp:fin:{ticker}", result, ttl=86400)  # cache 24h
    return result


async def _fetch_llm_financials(ticker: str, company_name: str, country: str) -> dict[str, Any]:
    """
    Use Claude web search to fetch financial data for international companies
    that don't have SEC EDGAR filings.
    Returns a dict compatible with _compute_metrics() expectations.
    """
    import json as _json
    try:
        from src.shared.llm.client_factory import complete_with_search
        from src.config.settings import settings
        from src.prompts.loader import load_prompt

        system = load_prompt("ingestion/llm_financials_system.j2")
        user   = load_prompt("ingestion/llm_financials.j2",
                             ticker=ticker, company_name=company_name, country=country)

        response = await complete_with_search(
            prompt=user,
            model=settings.llm.primary_model,
            max_searches=1,
            system=system,
        )

        text = response.strip()
        # Strip markdown fences
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                if "{" in part:
                    text = part.strip()
                    if text.startswith("json"):
                        text = text[4:].strip()
                    break
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end+1]

        data = _json.loads(text)
        logger.info("LLM financials for %s: revenue=%s gm=%s", ticker,
                    data.get("revenue"), data.get("gross_margin"))
        return data
    except Exception as e:
        logger.warning("LLM financials failed for %s: %s", ticker, e)
        return {}


async def _fetch_edgar_financials(client: httpx.AsyncClient,
                                   cik: str) -> dict[str, Any]:
    """Fetch XBRL facts from EDGAR for a US company."""
    cik_p = str(cik).zfill(10)

    # Submissions (sector)
    subs = await _get(client, f"https://data.sec.gov/submissions/CIK{cik_p}.json",
                      headers={"User-Agent": _EDGAR_UA, "Accept": "application/json"})
    sic     = str((subs or {}).get("sic", "") or "")
    sic2    = sic[:2] if len(sic) >= 2 else sic
    # Early exit for excluded sectors — skip XBRL fetch entirely
    if sic2 in _EXCLUDED_SIC_PREFIXES:
        logger.debug("Skipping CIK %s — excluded SIC %s", cik, sic)
        return {"sector": _SIC_SECTOR.get(sic2, ""), "excluded": True,
                "website": "", "description": "",
                "revenue": None, "gross_profit": None, "ebit": None,
                "net_income": None, "fcf": None, "capex": None,
                "cash": None, "total_debt": None, "net_debt": None,
                "ebitda": None, "total_assets": None, "equity": None,
                "dep": None, "rev_series": []}
    sector  = _SIC_SECTOR.get(sic2, "")
    website = (subs or {}).get("website", "")
    desc    = (subs or {}).get("description", "")

    # XBRL facts — try us-gaap first, fall back to ifrs-full for foreign filers
    facts_data = await _get(client, f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_p}.json",
                            headers={"User-Agent": _EDGAR_UA, "Accept": "application/json"})
    all_facts = (facts_data or {}).get("facts", {})
    facts     = all_facts.get("us-gaap", {})
    is_ifrs   = not facts or len(facts) < 5  # fewer than 5 concepts → likely IFRS filer

    if is_ifrs:
        facts = all_facts.get("ifrs-full", {})
        rev_concepts  = _IFRS_REVENUE;   gp_concepts   = _IFRS_GP
        ebit_concepts = _IFRS_EBIT;      ni_concepts    = _IFRS_NI
        cf_concepts   = _IFRS_OPCF;      capex_concepts = _IFRS_CAPEX
        dep_concepts  = _DEP_CONCEPTS    # same names
        cash_concepts = _IFRS_CASH;      debt_concepts  = _IFRS_DEBT
        asset_concepts= _IFRS_ASSETS;    equity_concepts= _IFRS_EQUITY
    else:
        rev_concepts  = _REVENUE_CONCEPTS; gp_concepts   = _GP_CONCEPTS
        ebit_concepts = _EBIT_CONCEPTS;    ni_concepts    = _NI_CONCEPTS
        cf_concepts   = _OPCF_CONCEPTS;    capex_concepts = _CAPEX_CONCEPTS
        dep_concepts  = _DEP_CONCEPTS
        cash_concepts = _CASH_CONCEPTS;    debt_concepts  = _DEBT_CONCEPTS
        asset_concepts= _ASSETS_CONCEPTS;  equity_concepts= _EQUITY_CONCEPTS

    # Income statement + cash flow (period items — need ~12-month start→end)
    revenue      = _latest_annual(facts, rev_concepts)
    gross_profit = _latest_annual(facts, gp_concepts)
    ebit         = _latest_annual(facts, ebit_concepts)
    net_income   = _latest_annual(facts, ni_concepts)
    op_cf        = _latest_annual(facts, cf_concepts)
    capex_raw    = _latest_annual(facts, capex_concepts)
    capex        = abs(capex_raw) if capex_raw is not None else None
    dep          = _latest_annual(facts, dep_concepts)
    rev_series   = _annual_series(facts, rev_concepts)
    # Balance sheet (point-in-time — no start date, skip period filter)
    cash         = _latest_annual(facts, cash_concepts,   balance_sheet=True)
    total_debt   = _latest_annual(facts, debt_concepts,   balance_sheet=True)
    total_assets = _latest_annual(facts, asset_concepts,  balance_sheet=True)
    equity       = _latest_annual(facts, equity_concepts, balance_sheet=True)

    fcf      = (op_cf - capex) if (op_cf and capex) else op_cf
    net_debt = (total_debt - cash) if (total_debt is not None and cash is not None) else None
    ebitda   = (ebit + (dep or 0)) if ebit is not None else None

    return {
        "sector":        sector,
        "website":       website,
        "description":   desc,
        "revenue":       revenue,
        "gross_profit":  gross_profit,
        "ebit":          ebit,
        "net_income":    net_income,
        "fcf":           fcf,
        "capex":         capex,
        "cash":          cash,
        "total_debt":    total_debt,
        "net_debt":      net_debt,
        "ebitda":        ebitda,
        "total_assets":  total_assets,
        "equity":        equity,
        "rev_series":    rev_series,
    }


def _compute_metrics(ticker: str, market_cap: float | None,
                     shares: float | None, fin: dict) -> dict[str, Any]:
    """Build metrics dict from financial data."""
    revenue      = fin.get("revenue")
    gross_profit = fin.get("gross_profit")
    ebit         = fin.get("ebit")
    net_income   = fin.get("net_income")
    fcf          = fin.get("fcf")
    capex        = fin.get("capex")
    net_debt     = fin.get("net_debt")
    ebitda       = fin.get("ebitda")
    total_assets = fin.get("total_assets")
    equity       = fin.get("equity")
    rev_series   = fin.get("rev_series", [])

    # Use `is not None` (not falsy) so 0.0 values are preserved correctly
    gm      = (gross_profit / revenue) if (gross_profit is not None and revenue) else None
    em      = (ebit / revenue)         if (ebit is not None and revenue)         else None
    fcf_y   = (fcf / market_cap)       if (fcf is not None and market_cap)       else None
    cap_rev = (capex / revenue)        if (capex is not None and revenue)        else None
    nd_eb   = (net_debt / ebitda)      if (net_debt is not None and ebitda and ebitda > 0) else None
    roic    = fin.get("roic") or ((ebit / total_assets) if (ebit is not None and total_assets and total_assets > 0) else None)
    roe     = fin.get("roe")  or ((net_income / equity) if (net_income is not None and equity and equity > 0) else None)

    ev      = (market_cap + net_debt) if (market_cap is not None and net_debt is not None) else market_cap
    ev_ebit = (ev / ebit) if (ev is not None and ebit and ebit > 0) else None
    ev_fcf  = (ev / fcf)  if (ev is not None and fcf  and fcf  > 0) else None

    rev_yoy = rev_cagr = None
    # Use rev_series (EDGAR/FMP) or revenue_growth (direct) or revenue + prior year
    if fin.get("revenue_growth") is not None:
        rev_yoy = float(fin["revenue_growth"])
    elif len(rev_series) >= 2 and rev_series[-2] and rev_series[-2] > 0:
        rev_yoy = (rev_series[-1] - rev_series[-2]) / rev_series[-2]
    elif revenue and fin.get("revenue_prior_year") and fin["revenue_prior_year"] > 0:
        rev_yoy = (revenue - fin["revenue_prior_year"]) / fin["revenue_prior_year"]
    if len(rev_series) >= 4 and rev_series[0] and rev_series[0] > 0:
        rev_cagr = (rev_series[-1] / rev_series[0]) ** (1 / 3) - 1

    # Use FMP direct values when available (more accurate than computed)
    if fin.get("fcf_yield_direct") is not None:
        fcf_y = fin["fcf_yield_direct"]
    if fin.get("net_debt_ebitda_direct") is not None:
        nd_eb = fin["net_debt_ebitda_direct"]
    if fin.get("ev_ebitda_direct") is not None:
        ev_ebit = fin["ev_ebitda_direct"]   # use EV/EBITDA as proxy for EV/EBIT
    if fin.get("capex_rev_direct") is not None:
        cap_rev = fin["capex_rev_direct"]
    # Use FMP market cap if Yahoo didn't return one
    if (market_cap is None or market_cap <= 500_000_000) and fin.get("market_cap_fmp"):
        market_cap = fin["market_cap_fmp"]

    return {
        "ticker": ticker, "market_cap_usd": market_cap,
        "revenue": revenue, "gross_profit": gross_profit,
        "gross_margin": gm, "ebit": ebit, "ebit_margin": em,
        "net_income": net_income, "fcf": fcf, "fcf_yield": fcf_y,
        "capex": capex, "capex_to_revenue": cap_rev,
        "net_debt": net_debt, "net_debt_ebitda": nd_eb,
        "total_assets": total_assets, "roic": roic, "roe": roe,
        "revenue_growth_yoy": rev_yoy, "revenue_growth_3yr_cagr": rev_cagr,
        "ev_ebit": ev_ebit, "ev_fcf": ev_fcf,
        "shares_outstanding": shares,
        "pe_ratio": None, "avg_daily_volume": None,
        "insider_ownership_pct":     fin.get("insider_ownership_pct"),
        "institutional_ownership_pct": None,
        "analyst_count":             None,
        "stock_repurchased":         fin.get("stock_repurchased"),
        "stock_based_compensation":  fin.get("stock_based_compensation"),
        "acquisitions_net":          fin.get("acquisitions_net"),
    }


# ── US universe via NASDAQ Trader API ────────────────────────────────────────

async def _get_us_candidates(client: httpx.AsyncClient,
                              min_cap: float, max_cap: float) -> list[dict]:
    """Get US companies in market cap range from NASDAQ Trader API.
    Returns [{"ticker", "name", "market_cap", "cik"}]
    """
    # EDGAR ticker-to-CIK map — cache for 24h
    edgar_data = _cache_get("edgar:company_tickers_exchange")
    if not edgar_data:
        edgar_data = await _get(
            client, "https://www.sec.gov/files/company_tickers_exchange.json",
            headers={"User-Agent": _EDGAR_UA, "Accept": "application/json"})
        if edgar_data:
            _cache_set("edgar:company_tickers_exchange", edgar_data, ttl=86400)
    cik_map: dict[str, str] = {}
    name_map: dict[str, str] = {}
    if edgar_data:
        fields = edgar_data.get("fields", [])
        ci = {f: i for i, f in enumerate(fields)}
        for row in edgar_data.get("data", []):
            t = row[ci["ticker"]].upper()
            cik_map[t] = str(row[ci["cik"]])
            name_map[t] = row[ci["name"]]

    # Also load the simpler tickers.json which includes more companies
    basic = await _get(client, "https://www.sec.gov/files/company_tickers.json",
                       headers={"User-Agent": _EDGAR_UA, "Accept": "application/json"})
    if basic:
        for entry in basic.values():
            t = str(entry.get("ticker", "")).upper()
            if t and t not in cik_map:
                cik_map[t] = str(entry.get("cik_str", ""))
                name_map[t] = entry.get("title", "")

    candidates = []
    for exchange in ("nasdaq", "nyse", "amex"):
        data = await _get(
            client, "https://api.nasdaq.com/api/screener/stocks",
            headers={"User-Agent": _UA, "Accept": "application/json"},
            params={"tableonly": "true", "limit": 9999, "exchange": exchange})
        rows = (data or {}).get("data", {}).get("table", {}).get("rows", [])
        for row in rows:
            try:
                mc = float(row.get("marketCap", "0").replace(",", "").replace("$", ""))
            except (ValueError, AttributeError):
                continue
            if min_cap <= mc <= max_cap:
                ticker = row.get("symbol", "").upper()
                cik = cik_map.get(ticker)
                candidates.append({
                    "ticker":     ticker,
                    "name":       row.get("name", "") or name_map.get(ticker, ticker),
                    "market_cap": mc,
                    "cik":        cik,
                    "exchange":   exchange.upper(),
                    "country":    "US",
                })

    # Shuffle so each run explores a different part of the universe
    import random
    random.shuffle(candidates)
    logger.info("US candidates in range: %d (shuffled)", len(candidates))
    return candidates


# ── International universe via curated GitHub lists ──────────────────────────

_INTL_TICKER_SOURCES = [
    # Major international index constituents — open datasets on GitHub
    ("https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv",
     "csv", "Symbol", "Name", "US"),
    # FTSE 100
    ("https://raw.githubusercontent.com/ranaroussi/yfinance/main/tests/data/stocks.csv",
     "csv", "Ticker", "Name", "INTL"),
]

# Hardcoded curated list of major non-US exchanges with suffix mapping
# Format: (exchange_suffix, country, exchange_name)
_INTL_EXCHANGES = [
    (".L",   "GB",  "LSE"),        # London
    (".DE",  "DE",  "XETRA"),      # Germany
    (".PA",  "FR",  "Euronext"),   # Paris
    (".AS",  "NL",  "Euronext"),   # Amsterdam
    (".BR",  "BE",  "Euronext"),   # Brussels
    (".MC",  "ES",  "Madrid"),     # Spain
    (".MI",  "IT",  "Milan"),      # Italy
    (".TO",  "CA",  "TSX"),        # Canada
    (".AX",  "AU",  "ASX"),        # Australia
    (".NZ",  "NZ",  "NZX"),        # New Zealand
    (".HK",  "HK",  "HKEX"),       # Hong Kong
    (".T",   "JP",  "TSE"),        # Japan
    (".KS",  "KR",  "KRX"),        # Korea
    (".NS",  "IN",  "NSE"),        # India
    (".BO",  "IN",  "BSE"),        # India BSE
    (".SW",  "CH",  "SIX"),        # Switzerland
    (".ST",  "SE",  "Nasdaq Stockholm"),
    (".OL",  "NO",  "Oslo"),       # Norway
    (".CO",  "DK",  "Copenhagen"), # Denmark
    (".HE",  "FI",  "Helsinki"),   # Finland
    (".LS",  "PT",  "Lisbon"),     # Portugal
    (".WA",  "PL",  "Warsaw"),     # Poland
    (".PR",  "CZ",  "Prague"),     # Czech
    (".BD",  "HU",  "Budapest"),   # Hungary
    (".SG",  "SG",  "SGX"),        # Singapore
    (".KL",  "MY",  "Bursa"),      # Malaysia
    (".BK",  "TH",  "SET"),        # Thailand
    (".JK",  "ID",  "IDX"),        # Indonesia
    (".SA",  "BR",  "B3"),         # Brazil
    (".MX",  "MX",  "BMV"),        # Mexico
]

# Excluded country codes per mandate
_EXCLUDED_COUNTRIES = {"CN", "RU", "IR"}


async def _get_intl_candidates(client: httpx.AsyncClient,
                                min_cap: float, max_cap: float,
                                max_per_exchange: int = 50) -> list[dict]:
    """
    Get international candidates by sampling known major stocks per exchange.
    Uses Yahoo v8 chart to get price, derives market cap from shares when available.
    Returns companies with estimated market cap in range.
    """
    # Use a curated list of major international companies
    # We pull from a well-known open dataset
    intl_tickers: list[dict] = []

    # Primary: use Wikipedia/public lists via a reliable source
    sources = [
        # Euro Stoxx 600 components via a GitHub dataset
        "https://raw.githubusercontent.com/datasets/euronext/main/data/euronext.csv",
        # FTSE All-Share
        "https://raw.githubusercontent.com/JerBouma/FinanceDatabase/main/database/equities.json",
    ]

    # Fallback: build from exchange suffixes using known large-cap anchors
    # and then get their market caps from Yahoo
    # This is the most reliable approach given no premium data source

    # Small/mid-cap international companies in $100M–$10B range
    # Focused on exchanges represented in Phoenician portfolio
    known_intl = [
        # ── UK — small/mid caps ───────────────────────────────────────────────
        ("JET2.L","Jet2","GB"),("ASAL.L","ASA International","GB"),
        ("AT.L","Ashtead Technology","GB"),("SPSY.L","Spectra Systems","GB"),
        ("BOY.L","Bodycote","GB"),("RWSA.L","Renewi","GB"),
        ("CARD.L","Card Factory","GB"),("TRN.L","Trainline","GB"),
        ("HFD.L","Halfords","GB"),("SHI.L","SHI International","GB"),
        ("IGR.L","Inchcape","GB"),("MTO.L","Mitie","GB"),
        ("FOUR.L","4imprint","GB"),("RWS.L","RWS Holdings","GB"),
        ("IGP.L","IG Group","GB"),("NCC.L","NCC Group","GB"),
        ("SLP.L","Sylvania Platinum","GB"),("MGAM.L","Morgan Advanced Materials","GB"),
        ("JTC.L","JTC","GB"),("BEW.L","Bewick","GB"),
        # ── Poland — Warsaw Stock Exchange ────────────────────────────────────
        ("DNP.WA","Dino Polska","PL"),("APR.WA","Auto Partner","PL"),
        ("SNT.WA","Synektik","PL"),("CDR.WA","CD Projekt","PL"),
        ("PCO.WA","Polskie Gornictwo","PL"),("CCC.WA","CCC","PL"),
        ("LPP.WA","LPP","PL"),("ALE.WA","Allegro","PL"),
        ("PKN.WA","PKN Orlen","PL"),("MBK.WA","mBank","PL"),
        ("GPW.WA","Warsaw Stock Exchange","PL"),("KGH.WA","KGHM","PL"),
        ("ING.WA","ING Bank Slaski","PL"),("PZU.WA","PZU","PL"),
        # ── Finland — Helsinki ────────────────────────────────────────────────
        ("TNOM.HE","Talenom","FI"),("PUUILO.HE","Puuilo","FI"),
        ("METSO.HE","Metso","FI"),("NESTE.HE","Neste","FI"),
        ("NOKIA.HE","Nokia","FI"),("SAMPO.HE","Sampo","FI"),
        ("FORTUM.HE","Fortum","FI"),("UPM.HE","UPM-Kymmene","FI"),
        ("KEMIRA.HE","Kemira","FI"),("TIETO.HE","TietoEVRY","FI"),
        ("OLVI.HE","Olvi","FI"),("HARVIA.HE","Harvia","FI"),
        ("KAMUX.HE","Kamux","FI"),("REMEDY.HE","Remedy Entertainment","FI"),
        # ── Sweden ────────────────────────────────────────────────────────────
        ("TEQ.ST","Teqnion","SE"),("BETT-B.ST","Betsson","SE"),
        ("NIBE-B.ST","NIBE","SE"),("SWMA.ST","Swedish Match","SE"),
        ("ADDV-B.ST","AddLife","SE"),("BUFAB.ST","Bufab","SE"),
        ("DIOS.ST","Diös Fastigheter","SE"),("HPOL-B.ST","H&M","SE"),
        ("INDU-C.ST","Industrivärden","SE"),("LATO-B.ST","Latour","SE"),
        ("NCAB.ST","NCAB Group","SE"),("OEM-B.ST","OEM International","SE"),
        ("VITEC-B.ST","Vitec Software","SE"),("XANO-B.ST","XANO Industri","SE"),
        # ── Norway ────────────────────────────────────────────────────────────
        ("MOWI.OL","Mowi","NO"),("SALM.OL","SalMar","NO"),
        ("BAKKA.OL","Bakkafrost","NO"),("LSG.OL","Lerøy Seafood","NO"),
        ("ASTK.OL","Astock","NO"),("KAHOOT.OL","Kahoot","NO"),
        ("SCATC.OL","Scatec","NO"),("SRBANK.OL","SpareBank 1 SR","NO"),
        # ── Denmark ───────────────────────────────────────────────────────────
        ("DEMANT.CO","Demant","DK"),("COLO-B.CO","Coloplast","DK"),
        ("PNDORA.CO","Pandora","DK"),("GMAB.CO","Genmab","DK"),
        ("RBREW.CO","Royal Unibrew","DK"),("NETC.CO","Netcompany","DK"),
        ("ROCK-B.CO","Rockwool","DK"),("FLS.CO","FLSmidth","DK"),
        # ── Germany — small/mid ───────────────────────────────────────────────
        ("MBB.DE","MBB SE","DE"),("DWS.DE","DWS Group","DE"),
        ("ARND.DE","Aroundtown","DE"),("BCMH.DE","Bilfinger","DE"),
        ("EVK.DE","Evonik","DE"),("FNTN.DE","freenet","DE"),
        ("GFT.DE","GFT Technologies","DE"),("HAG.DE","Hensoldt","DE"),
        ("KNEBV.DE","Kone","DE"),("PDM.DE","Vossloh","DE"),
        # ── Canada — small/mid ────────────────────────────────────────────────
        ("GSY.TO","goeasy","CA"),("FOOD.TO","Goodfood Market","CA"),
        ("TOY.TO","Spin Master","CA"),("PBH.TO","Premium Brands","CA"),
        ("BYD.TO","Boyd Group","CA"),("CSW-A.TO","Corby Spirit","CA"),
        ("FFH.TO","Fairfax Financial","CA"),("IFP.TO","Interfor","CA"),
        ("MTY.TO","MTY Food Group","CA"),("SIS.TO","Savaria","CA"),
        ("TVE.TO","Tamarack Valley","CA"),("WPK.TO","Winpak","CA"),
        # ── Australia — small/mid ─────────────────────────────────────────────
        ("MAD.AX","Mader Group","AU"),("NWL.AX","Netwealth Group","AU"),
        ("ARB.AX","ARB Corporation","AU"),("EML.AX","EML Payments","AU"),
        ("HUB.AX","Hub24","AU"),("ILU.AX","Iluka Resources","AU"),
        ("JAN.AX","Janison Education","AU"),("LNK.AX","Link Administration","AU"),
        ("MCR.AX","Mincor Resources","AU"),("MON.AX","Monash IVF","AU"),
        ("NHF.AX","nib Holdings","AU"),("PME.AX","Pro Medicus","AU"),
        ("REH.AX","Reece Group","AU"),("SKI.AX","Spark Infrastructure","AU"),
        # ── Japan — small/mid ─────────────────────────────────────────────────
        ("3445.T","RS Technologies","JP"),("2282.T","NH Foods","JP"),
        ("2791.T","Nafco","JP"),("3048.T","BicCamera","JP"),
        ("3382.T","Seven & i Holdings","JP"),("3563.T","FOOD & LIFE","JP"),
        ("4021.T","Nissan Chemical","JP"),("4062.T","Ibiden","JP"),
        ("4185.T","JSR Corp","JP"),("4452.T","Kao Corp","JP"),
        ("6273.T","SMC Corp","JP"),("6367.T","Daikin","JP"),
        ("6448.T","Brother Industries","JP"),("6501.T","Hitachi","JP"),
        ("7741.T","Hoya Corp","JP"),("7751.T","Canon","JP"),
        ("8750.T","Dai-ichi Life","JP"),("9843.T","Nitori Holdings","JP"),
        # ── Singapore ─────────────────────────────────────────────────────────
        ("QES.SI","China Sunsine","SG"),("S58.SI","SATS","SG"),
        ("C6L.SI","Singapore Airlines","SG"),("A17U.SI","CapitaLand Ascendas","SG"),
        ("ME8U.SI","Mapletree Industrial","SG"),("M44U.SI","Mapletree Logistics","SG"),
        ("9CI.SI","CapitaLand Invest","SG"),("V03.SI","Venture Corp","SG"),
        ("BN4.SI","Keppel Corp","SG"),("F34.SI","Wilmar Intl","SG"),
        # ── Netherlands / Belgium ─────────────────────────────────────────────
        ("IMCD.AS","IMCD Group","NL"),("BESI.AS","BE Semiconductor","NL"),
        ("SBMO.AS","SBM Offshore","NL"),("FLOW.AS","Flows","NL"),
        ("FAGR.BR","Fagron","BE"),("LOTB.BR","Lotus Bakeries","BE"),
        ("UCB.BR","UCB","BE"),("COLR.BR","Colruyt","BE"),
        # ── Greece ────────────────────────────────────────────────────────────
        ("KRI.AT","Kri-Kri Milk","GR"),("MYTIL.AT","Mytilineos","GR"),
        ("OPAP.AT","OPAP","GR"),("ETE.AT","NBG","GR"),
        ("LAMDA.AT","Lamda Development","GR"),("EXAE.AT","ATHEX Group","GR"),
        # ── India (non-excluded) — listed on US exchanges ──────────────────────
        ("INTR","Inter & Co","BR"),  # Brazilian digital bank, US-listed
    ]

    # Exclude mandate countries
    known_intl = [(t, n, c) for t, n, c in known_intl if c not in _EXCLUDED_COUNTRIES]

    import random
    random.shuffle(known_intl)

    # Return the curated list directly — no external API needed for the universe.
    # Market cap and financials will be fetched by LLM in the ingestion step.
    # Use a sentinel market_cap=500_000_000 ($500M) so the pipeline processes them;
    # the LLM financial lookup will update with the real market cap.
    results = [
        {
            "ticker":     t,
            "name":       n,
            "market_cap": 500_000_000,  # placeholder — LLM will set real value
            "exchange":   "",
            "country":    c,
            "cik":        None,
        }
        for t, n, c in known_intl
    ]
    logger.info("International candidates: %d from curated list (LLM will fetch financials)", len(results))
    return results


# ── Main universe screen ──────────────────────────────────────────────────────

async def screen_universe_global(
    min_market_cap: float = 100_000_000,
    max_market_cap: float = 10_000_000_000,
    max_companies: int = 200,
    include_us: bool = True,
    include_intl: bool = True,
    concurrency: int = 10,
    exclude_tickers: set[str] | None = None,
    preselected_tickers: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Build global investable universe.
    If preselected_tickers is provided, only fetch financials for those tickers
    (Claude pre-screening path). Otherwise falls back to full universe scan.
    Returns list of {"company": {...}, "metrics": {...}} dicts.
    """
    results: list[dict] = []
    stop_event = asyncio.Event()

    async with httpx.AsyncClient(timeout=20) as client:

        # ── Fast path: Claude pre-selected tickers ────────────────────────────
        if preselected_tickers:
            logger.info("Fast path: fetching financials for %d pre-selected tickers", len(preselected_tickers))
            print(f"Fetching financials for {len(preselected_tickers)} Claude-selected candidates...", flush=True)

            # Build a combined candidate map from both US and intl lists
            us_raw   = await _get_us_candidates(client, min_market_cap, max_market_cap)
            intl_raw = await _get_intl_candidates(client, min_market_cap, max_market_cap)
            all_map  = {c["ticker"]: {**c, "is_intl": False} for c in us_raw}
            all_map.update({c["ticker"]: {**c, "is_intl": True} for c in intl_raw})

            fmp_sem = asyncio.Semaphore(15)
            llm_sem = asyncio.Semaphore(8)

            async def _process_preselected(ticker: str):
                if stop_event.is_set():
                    return
                co = all_map.get(ticker)
                if not co:
                    # Ticker not in our lists — build minimal stub for FMP lookup
                    co = {"ticker": ticker, "name": ticker, "market_cap": 500_000_000,
                          "country": "US", "exchange": "", "cik": None, "is_intl": False}
                try:
                    fin: dict = {}
                    async with fmp_sem:
                        fmp_fin = await _fetch_fmp_financials(client, ticker)
                    if fmp_fin and not fmp_fin.get("excluded") and fmp_fin.get("revenue"):
                        fin = fmp_fin
                    elif co.get("is_intl"):
                        async with llm_sem:
                            fin = await _fetch_llm_financials(ticker, co["name"], co.get("country",""))

                    if not fin or fin.get("excluded"):
                        return

                    mc = fin.get("market_cap_fmp") or co.get("market_cap") or 500_000_000
                    country = fin.get("country") or co.get("country","US") or "US"

                    # Skip debt instruments
                    name = co.get("name","")
                    _DEBT_KW = ("debenture","subordinated","notes due","% fixed","% senior",
                                "preferred shares","depositary shares","warrant","rights",
                                "unit trust","closed-end"," etf "," fund ")
                    if any(kw in name.lower() for kw in _DEBT_KW):
                        return

                    company_info = {
                        "ticker":              ticker,
                        "name":                name,
                        "exchange":            co.get("exchange",""),
                        "country":             country[:10],
                        "gics_sector":         (fin.get("sector") or "")[:100],
                        "gics_industry":       "",
                        "gics_industry_group": "",
                        "gics_sub_industry":   "",
                        "market_cap_usd":      float(mc) if mc else None,
                        "description":         (fin.get("description") or "")[:2000],
                        "website":             fin.get("website") or "",
                        "cik":                 co.get("cik"),
                        "is_founder_led":      fin.get("is_founder_led"),
                        "founder_name":        fin.get("ceo_name") or "",
                        "is_active":           True,
                    }
                    metrics = _compute_metrics(ticker, mc, fin.get("shares_outstanding"), fin)

                    results.append({"company": company_info, "metrics": metrics})
                    n = len(results)
                    rev = fin.get("revenue") or 0
                    gm  = (fin.get("gross_profit") or 0) / rev * 100 if rev else 0
                    logger.info("[%d/%d] %s %s $%.0fM rev=$%.0fM gm=%.0f%%",
                                n, max_companies, country, ticker, (mc or 0)/1e6, rev/1e6, gm)
                    if n >= max_companies:
                        stop_event.set()
                except Exception as e:
                    logger.debug("Skip %s: %s", ticker, e)

            await asyncio.gather(*[_process_preselected(t) for t in preselected_tickers],
                                  return_exceptions=True)
            logger.info("Fast path complete: %d companies with financials", len(results))
            return results[:max_companies]

        # ── Slow path: full universe scan (fallback) ──────────────────────────
        us_quota   = max_companies
        intl_quota = max_companies

        # ── US companies ──────────────────────────────────────────────────────
        if include_us:
            us_candidates = await _get_us_candidates(client, min_market_cap, max_market_cap)
            if exclude_tickers:
                us_candidates = [c for c in us_candidates if c["ticker"] not in exclude_tickers]
            us_candidates = us_candidates[:max_companies * 4]
            print(f"Processing {len(us_candidates)} US candidates (excl. {len(exclude_tickers or [])} already in DB)...", flush=True)

            # Two separate semaphores:
            # - price_sem: 10 concurrent Yahoo v8 price calls (fast, no rate limit)
            # - edgar_sem: 3 concurrent EDGAR XBRL calls (respect 10 req/sec limit;
            #              each call makes 2 requests so 3 concurrent = 6 req/sec)
            price_sem = asyncio.Semaphore(15)
            edgar_sem = asyncio.Semaphore(5)

            async def _process_us(co: dict):
                if stop_event.is_set():
                    return
                ticker = co["ticker"]
                cik    = co.get("cik")
                try:
                    # Step 1: price fetch (fast, parallel)
                    async with price_sem:
                        price, shares, exchange, _ = await _get_price_and_shares(client, ticker)
                    mc = co["market_cap"]

                    # Step 2: FMP financials (primary — covers US + intl, fast)
                    fin: dict[str, Any] = {}
                    fmp_fin = await _fetch_fmp_financials(client, ticker)
                    if fmp_fin and not fmp_fin.get("excluded") and fmp_fin.get("revenue"):
                        fin = fmp_fin
                        # FMP returns real market cap — use it if Yahoo didn't
                        if fmp_fin.get("market_cap_fmp") and (not mc or mc <= 500_000_000):
                            mc = fmp_fin["market_cap_fmp"]
                    elif cik:
                        # Fallback to EDGAR XBRL for US companies
                        async with edgar_sem:
                            if stop_event.is_set():
                                return
                            fin = await _fetch_edgar_financials(client, cik)
                            await asyncio.sleep(0.1)
                    # Skip debt instruments / non-equity by name
                    _DEBT_KW = ("debenture","subordinated","notes due","% fixed","% senior",
                                "preferred shares","depositary shares","warrant","rights",
                                "unit trust","closed-end"," etf "," fund ")
                    if any(kw in co["name"].lower() for kw in _DEBT_KW):
                        logger.debug("Skipping %s — debt/non-equity instrument", ticker)
                        return

                    # Skip excluded sectors entirely
                    if fin.get("excluded"):
                        logger.debug("Skipping %s — excluded sector %s", ticker, fin.get("sector"))
                        return
                    # Skip non-operating entities: funds, BDCs, shell cos, pre-revenue biotechs
                    # If no revenue AND no gross profit AND no EBIT — not an investable company
                    if (fin.get("revenue") is None and
                            fin.get("ebit") is None and
                            fin.get("net_income") is None and
                            cik):  # only skip if we tried EDGAR (has CIK)
                        logger.debug("Skipping %s — no income statement data (fund/BDC/shell)", ticker)
                        return

                    company_info = {
                        "ticker":              ticker,
                        "name":                co["name"],
                        "exchange":            co.get("exchange", ""),
                        "country":             "US",
                        "gics_sector":         (fin.get("sector") or "")[:100],
                        "gics_industry":       "",
                        "gics_industry_group": "",
                        "gics_sub_industry":   "",
                        "market_cap_usd":      mc,
                        "description":         (fin.get("description") or "")[:2000],
                        "website":             fin.get("website") or "",
                        "cik":                 cik,
                        "is_founder_led":      None,
                        "is_active":           True,
                    }
                    metrics = _compute_metrics(ticker, mc, shares, fin)

                    if stop_event.is_set():
                        return
                    results.append({"company": company_info, "metrics": metrics})
                    n = len(results)
                    rev = fin.get("revenue") or 0
                    gm  = (fin.get("gross_profit") or 0) / rev * 100 if rev else 0
                    msg = (f"[{n}/{max_companies}] US  {ticker:8s} "
                           f"${mc/1e6:.0f}M  rev=${rev/1e6:.0f}M  gm={gm:.0f}%")
                    logger.info(msg)
                    print(msg, flush=True)

                    if n >= max_companies:
                        stop_event.set()
                except Exception as e:
                    logger.debug("US skip %s: %s", ticker, e)

            await asyncio.gather(*[_process_us(co) for co in us_candidates],
                                  return_exceptions=True)

        # ── International companies — always run independently ────────────────
        if include_intl:
            intl_results: list[dict] = []
            intl_candidates = await _get_intl_candidates(client, min_market_cap, max_market_cap)
            if exclude_tickers:
                intl_candidates = [c for c in intl_candidates if c["ticker"] not in exclude_tickers]
            print(f"Processing {len(intl_candidates)} intl candidates...", flush=True)

            # Run financial lookups: FMP first, LLM fallback
            fmp_sem = asyncio.Semaphore(15)
            llm_sem = asyncio.Semaphore(8)

            async def _process_intl(co: dict) -> dict | None:
                ticker  = co["ticker"]
                country = co.get("country", "")
                mc      = co.get("market_cap")
                if not mc:
                    return None
                try:
                    # Try FMP first — works for many intl tickers on paid plan
                    fin: dict = {}
                    async with fmp_sem:
                        fmp_fin = await _fetch_fmp_financials(client, ticker)
                    if fmp_fin and not fmp_fin.get("excluded") and fmp_fin.get("revenue"):
                        fin = fmp_fin
                    else:
                        # LLM fallback for tickers FMP doesn't cover
                        async with llm_sem:
                            fin = await _fetch_llm_financials(ticker, co["name"], country)

                    # Use FMP/LLM market cap if available
                    real_mc = fin.get("market_cap_fmp") or fin.get("market_cap_usd")
                    real_mc = float(real_mc) if real_mc and float(real_mc) > 1_000_000 else mc

                    company_info = {
                        "ticker":              ticker,
                        "name":                co["name"],
                        "exchange":            co.get("exchange", ""),
                        "country":             country,
                        "gics_sector":         (fin.get("sector") or "")[:100],
                        "gics_industry":       "",
                        "gics_industry_group": "",
                        "gics_sub_industry":   "",
                        "market_cap_usd":      real_mc,
                        "description":         (fin.get("description") or "")[:2000],
                        "website":             fin.get("website") or "",
                        "cik":                 None,
                        "is_founder_led":      fin.get("is_founder_led"),
                        "is_active":           True,
                    }
                    metrics = _compute_metrics(ticker, mc, fin.get("shares_outstanding"), fin)
                    rev = fin.get("revenue") or 0
                    gm  = (fin.get("gross_profit") or 0) / rev * 100 if rev else 0
                    msg = f"[intl {ticker:12s}] ${mc/1e6:.0f}M {country} rev=${rev/1e6:.0f}M gm={gm:.0f}%"
                    logger.info(msg)
                    print(msg, flush=True)
                    return {"company": company_info, "metrics": metrics}
                except Exception as e:
                    logger.debug("Intl skip %s: %s", ticker, e)
                    return None

            # Cap to intl_quota before calling LLM — never process more than needed
            intl_candidates = intl_candidates[:intl_quota]
            print(f"Capped to {len(intl_candidates)} intl candidates for LLM lookup...", flush=True)
            intl_tasks = [_process_intl(co) for co in intl_candidates]
            intl_task_results = await asyncio.gather(*intl_tasks, return_exceptions=True)
            for r in intl_task_results:
                if isinstance(r, dict):
                    intl_results.append(r)

            # Merge: international FIRST (priority), then fill remaining slots with US
            import random as _random
            _random.shuffle(intl_results)
            _random.shuffle(results)
            # Intl gets priority — fills up to 50% of slots, rest is US
            intl_quota_final = min(len(intl_results), max_companies // 2)
            us_quota_final   = max_companies - intl_quota_final
            merged = intl_results[:intl_quota_final] + results[:us_quota_final]
            _random.shuffle(merged)  # shuffle so UI shows mixed, not grouped
            us_iter   = iter([])   # already consumed above
            intl_iter = iter([])
            while len(merged) < max_companies:
                added = False
                u = next(us_iter, None)
                if u:
                    merged.append(u)
                    added = True
                i = next(intl_iter, None)
                if i and len(merged) < max_companies:
                    merged.append(i)
                    added = True
                if not added:
                    break
            results = merged
            print(f"Combined universe: {len(results)} companies ({sum(1 for r in results if r['company']['country']=='US')} US + {sum(1 for r in results if r['company']['country']!='US')} intl)", flush=True)

    msg = f"Global universe complete: {len(results)} companies"
    logger.info(msg)
    print(msg, flush=True)
    return results[:max_companies]


# ── MarketDataClient (backward-compatible interface) ──────────────────────────

class MarketDataClient:

    async def get_all_data(self, ticker: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """Get company info + metrics for a single ticker."""
        async with httpx.AsyncClient(timeout=20) as client:
            # Get price
            price, shares, exchange, currency = await _get_price_and_shares(client, ticker)

            # Try EDGAR first (US companies)
            edgar_data = await _get(
                client, "https://www.sec.gov/files/company_tickers_exchange.json",
                headers={"User-Agent": _EDGAR_UA})
            cik = name = None
            if edgar_data:
                fields = edgar_data.get("fields", [])
                ci = {f: i for i, f in enumerate(fields)}
                for row in edgar_data.get("data", []):
                    if row[ci["ticker"]].upper() == ticker.upper():
                        cik  = str(row[ci["cik"]])
                        name = row[ci["name"]]
                        break

            fin: dict[str, Any] = {}
            if cik:
                fin = await _fetch_edgar_financials(client, cik)

            mc = (shares * price) if (shares and price) else None

            company_info = {
                "ticker":              ticker,
                "name":                name or ticker,
                "exchange":            exchange,
                "country":             "US" if cik else "",
                "gics_sector":         (fin.get("sector") or "")[:100],
                "gics_industry":       "",
                "gics_industry_group": "",
                "gics_sub_industry":   "",
                "market_cap_usd":      mc,
                "description":         (fin.get("description") or "")[:2000],
                "website":             fin.get("website") or "",
                "cik":                 cik,
                "is_founder_led":      None,
                "is_active":           True,
            }
            metrics = _compute_metrics(ticker, mc, shares, fin)
            return company_info, metrics

    async def get_company_info(self, ticker: str) -> dict[str, Any]:
        co, _ = await self.get_all_data(ticker)
        return co

    async def get_financial_metrics(self, ticker: str) -> dict[str, Any]:
        _, m = await self.get_all_data(ticker)
        return m

    async def screen_universe(self, min_market_cap: float = 100_000_000,
                               max_market_cap: float = 10_000_000_000,
                               exchange: str | None = None) -> list[str]:
        results = await screen_universe_global(min_market_cap=min_market_cap,
                                               max_market_cap=max_market_cap,
                                               max_companies=500)
        return [r["company"]["ticker"] for r in results]


# ── Keep _parse_tickers for similarity/thematic search ────────────────────────

_TICKER_RE = re.compile(r"\b([A-Z]{1,5}(?:\.[A-Z]{1,2})?)\b")

def _parse_tickers(text: str) -> list[str]:
    noise = {
        "THE","AND","FOR","ARE","NOT","BUT","ALL","CAN","WAS","ONE","OUR",
        "OUT","YOU","HAD","HAS","HIS","HOW","ITS","MAY","NEW","NOW","SEE",
        "WAY","WHO","DID","GET","LET","SAY","TOO","USE","WITH","THAT",
        "THIS","FROM","THEY","BEEN","HAVE","MANY","SOME","THEM","THAN",
        "MAKE","LIKE","LONG","LOOK","ONLY","COME","OVER","SUCH","TAKE",
        "ALSO","BACK","INTO","YOUR","JUST","KNOW","MOST","FIND","HERE",
        "WELL","VERY","WHEN","WILL","MORE","NEED","MUCH","HIGH","LOW",
        "USD","INC","LTD","LLC","CORP","NYSE","AMEX","CEO","ABOUT","THESE",
        "WOULD","THEIR","WHICH","COULD","OTHER","MARKET","SMALL","LARGE",
        "TOTAL","REVENUE","GROWTH","STOCK","SHARE","PRICE","RETURN",
        "SECTOR","CAP","BASED","COMPANY","US","OF","IN","TO","AT","OR",
        "IF","NO","SO","UP","ON","AN","IT","IS","DO","AS","BY","WE","BE",
    }
    seen: set[str] = set()
    tickers: list[str] = []
    for line in text.strip().split("\n"):
        clean = re.sub(r"[*_`#\-]", " ", line).strip()
        clean = re.sub(r"^\d+[\.\)]\s*", "", clean)
        first = clean.split()[0].upper() if clean.split() else ""
        matches = _TICKER_RE.findall(clean.upper())
        candidates = []
        if first and re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z]{1,2})?", first):
            candidates.append(first)
        candidates.extend(matches)
        for t in candidates:
            if t not in seen and t not in noise and len(t) >= 2:
                seen.add(t)
                tickers.append(t)
                break
    return tickers
