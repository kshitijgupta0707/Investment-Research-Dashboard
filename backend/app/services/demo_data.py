"""The demo fixture: two organizations and everything in them.

Kept here rather than inline in the seeding script for one reason: the saved
reports are built through `ResearchReport` itself, so a change to the Turn-2
contract breaks this module loudly at import time instead of quietly writing
JSON that the renderer cannot display. The script does the talking to Postgres
and Supabase; this module decides what the demo *is*.

The content is chosen to make the required demo workflows possible without
running a single live query first:

* Two organizations with overlapping tickers, so isolation is visibly about
  `org_id` and not about the two orgs happening to research different things.
* Two analysts in one org, so "an analyst cannot edit a colleague's report" has
  something to fail against.
* One report with `partial = true`, so the degraded-data banner has a case.
* Query history spanning zero, one, two and three tools, so the claim that the
  agent chooses tools per query is visible in seeded data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.agent.tools import KNOWLEDGE_BASE, MARKET_DATA, NEWS_SENTIMENT
from app.models.research_queries import QueryStatus
from app.schemas.auth import Role
from app.schemas.report import ResearchReport

# Documented in the README and printed by the seed script. Long enough for
# Supabase's default password policy.
DEMO_PASSWORD = "Demo-Passw0rd!42"


@dataclass(frozen=True)
class DemoUser:
    key: str
    email: str
    name: str
    role: Role


@dataclass(frozen=True)
class DemoReport:
    author: str
    query_text: str
    tags: list[str]
    report: ResearchReport
    age_days: int = 0


@dataclass(frozen=True)
class DemoQuery:
    author: str
    query_text: str
    tools_selected: list[str]
    status: QueryStatus
    latency_ms: int
    age_hours: int = 0


@dataclass(frozen=True)
class DemoPin:
    owner: str
    ticker: str
    company_name: str


@dataclass(frozen=True)
class DemoOrg:
    name: str
    users: list[DemoUser]
    reports: list[DemoReport] = field(default_factory=list)
    queries: list[DemoQuery] = field(default_factory=list)
    watchlist: list[DemoPin] = field(default_factory=list)

    @property
    def admin(self) -> DemoUser:
        return next(user for user in self.users if user.role == "admin")


def _source(label: str, *, type_: str = "api", url: str | None = None, as_of: datetime | None = None) -> dict:
    return {"type": type_, "label": label, "url": url, "data_as_of": as_of.isoformat() if as_of else None}


def _chipmaker_comparison(now: datetime) -> ResearchReport:
    """All three tools, four section types. The showcase report."""
    as_of = now - timedelta(days=1)
    return ResearchReport.model_validate(
        {
            "summary": (
                "NVIDIA continues to outgrow both AMD and Intel by a wide margin, with data-centre "
                "demand the dominant driver. AMD is gaining share in accelerators from a small base; "
                "Intel's foundry investment continues to weigh on margins. Sentiment is positive for "
                "NVIDIA and AMD, mixed for Intel."
            ),
            "sections": [
                {
                    "title": "NVIDIA at a glance",
                    "type": "company_card",
                    "content": {
                        "ticker": "NVDA",
                        "company_name": "NVIDIA Corporation",
                        "metrics": [
                            {"label": "Market cap", "value": "$3.1T"},
                            {"label": "P/E (trailing)", "value": "58.4"},
                            {"label": "Revenue (TTM)", "value": "$96.3B"},
                            {"label": "EPS (TTM)", "value": "$2.54"},
                        ],
                    },
                    "confidence": "high",
                    "sources": [_source("Yahoo Finance quote", as_of=as_of)],
                },
                {
                    "title": "Revenue growth compared",
                    "type": "table",
                    "content": {
                        "columns": ["Company", "Ticker", "Revenue (TTM)", "YoY growth", "Gross margin"],
                        "rows": [
                            ["NVIDIA", "NVDA", "$96.3B", "+94%", "73.0%"],
                            ["AMD", "AMD", "$24.3B", "+13%", "51.4%"],
                            ["Intel", "INTC", "$54.2B", "-2%", "41.1%"],
                        ],
                    },
                    "confidence": "high",
                    "sources": [
                        _source("Yahoo Finance fundamentals", as_of=as_of),
                        _source("NVDA FY2025 10-K excerpt", type_="filing"),
                    ],
                },
                {
                    "title": "Indexed price performance",
                    "type": "chart",
                    "content": {
                        "y_label": "Indexed to 100 at period start",
                        "series": [
                            {
                                "label": "NVDA",
                                "points": [
                                    {"date": (now - timedelta(days=days)).date().isoformat(), "value": value}
                                    for days, value in zip(
                                        (150, 120, 90, 60, 30, 0), (100.0, 118.4, 131.2, 127.9, 144.6, 158.3)
                                    )
                                ],
                            },
                            {
                                "label": "AMD",
                                "points": [
                                    {"date": (now - timedelta(days=days)).date().isoformat(), "value": value}
                                    for days, value in zip(
                                        (150, 120, 90, 60, 30, 0), (100.0, 104.2, 111.8, 106.3, 115.7, 121.4)
                                    )
                                ],
                            },
                            {
                                "label": "INTC",
                                "points": [
                                    {"date": (now - timedelta(days=days)).date().isoformat(), "value": value}
                                    for days, value in zip(
                                        (150, 120, 90, 60, 30, 0), (100.0, 96.1, 92.7, 88.4, 91.2, 87.6)
                                    )
                                ],
                            },
                        ],
                    },
                    "confidence": "medium",
                    "sources": [_source("Yahoo Finance historical prices", as_of=as_of)],
                },
                {
                    "title": "Recent news sentiment",
                    "type": "sentiment",
                    "content": {
                        "overall": "positive",
                        "items": [
                            {
                                "headline": "NVIDIA data-centre revenue beats again on sustained AI demand",
                                "sentiment": "positive",
                                "ticker": "NVDA",
                                "url": "https://example.com/nvda-datacentre-beat",
                            },
                            {
                                "headline": "AMD lands multi-year accelerator supply agreement",
                                "sentiment": "positive",
                                "ticker": "AMD",
                                "url": "https://example.com/amd-accelerator-deal",
                            },
                            {
                                "headline": "Intel foundry losses widen as capital spending stays elevated",
                                "sentiment": "negative",
                                "ticker": "INTC",
                                "url": "https://example.com/intc-foundry-losses",
                            },
                            {
                                "headline": "Analysts split on whether AI capex has peaked",
                                "sentiment": "neutral",
                                "url": "https://example.com/ai-capex-debate",
                            },
                        ],
                    },
                    "confidence": "medium",
                    "sources": [_source("NewsAPI", type_="article", url="https://newsapi.org")],
                },
                {
                    "title": "Risk assessment",
                    "type": "text",
                    "content": {
                        "text": (
                            "Concentration risk dominates. NVIDIA's growth depends on a small number of "
                            "hyperscale buyers whose capital spending is discretionary and already at record "
                            "levels; a single budget cycle turning would be felt immediately. AMD's share "
                            "gains are real but start from a base too small to offset that. Intel carries a "
                            "different risk entirely -- execution on foundry, where the spending is committed "
                            "and the returns are not."
                        )
                    },
                    "confidence": "low",
                    "sources": [
                        _source("NVDA FY2025 10-K -- Risk Factors", type_="filing"),
                        _source("INTC FY2024 10-K -- Manufacturing", type_="filing"),
                    ],
                },
            ],
            "partial": False,
            "failed_tools": [],
            "generated_at": (now - timedelta(days=2)).isoformat(),
        }
    )


def _tesla_news(now: datetime) -> ResearchReport:
    """News only -- the report the "must not call market data" query produces."""
    return ResearchReport.model_validate(
        {
            "summary": (
                "Coverage over the last 30 days is mixed. Delivery figures came in below consensus, "
                "offset by continued progress on energy storage margins."
            ),
            "sections": [
                {
                    "title": "Headlines and sentiment",
                    "type": "sentiment",
                    "content": {
                        "overall": "neutral",
                        "items": [
                            {
                                "headline": "Tesla quarterly deliveries miss consensus estimates",
                                "sentiment": "negative",
                                "ticker": "TSLA",
                                "url": "https://example.com/tsla-deliveries-miss",
                            },
                            {
                                "headline": "Energy storage deployments hit a quarterly record",
                                "sentiment": "positive",
                                "ticker": "TSLA",
                                "url": "https://example.com/tsla-energy-record",
                            },
                            {
                                "headline": "Price cuts in two markets draw margin questions",
                                "sentiment": "neutral",
                                "ticker": "TSLA",
                                "url": "https://example.com/tsla-price-cuts",
                            },
                        ],
                    },
                    "confidence": "high",
                    "sources": [_source("NewsAPI", type_="article", url="https://newsapi.org")],
                },
                {
                    "title": "What the coverage adds up to",
                    "type": "text",
                    "content": {
                        "text": (
                            "The automotive narrative and the energy narrative are diverging. Reporting on "
                            "deliveries is uniformly cautious; reporting on storage is uniformly positive. "
                            "No article in the window addresses both."
                        )
                    },
                    "confidence": "medium",
                    "sources": [_source("NewsAPI", type_="article", url="https://newsapi.org")],
                },
            ],
            "partial": False,
            "failed_tools": [],
            "generated_at": (now - timedelta(days=9)).isoformat(),
        }
    )


def _degraded_banks(now: datetime) -> ResearchReport:
    """Deliberately partial, so the degraded-data banner has a demo case."""
    return ResearchReport.model_validate(
        {
            "summary": (
                "Balance-sheet comparison below is drawn from filings only -- the market-data provider "
                "was unavailable for this run, so current valuation figures are missing."
            ),
            "sections": [
                {
                    "title": "Capital position from latest filings",
                    "type": "table",
                    "content": {
                        "columns": ["Bank", "Ticker", "CET1 ratio", "Total assets"],
                        "rows": [
                            ["JPMorgan Chase", "JPM", "15.0%", "$4.2T"],
                            ["Goldman Sachs", "GS", "14.6%", "$1.7T"],
                            ["Morgan Stanley", "MS", "15.1%", "$1.2T"],
                        ],
                    },
                    "confidence": "medium",
                    "sources": [
                        _source("JPM FY2024 10-K excerpt", type_="filing"),
                        _source("GS FY2024 10-K excerpt", type_="filing"),
                        _source("MS FY2024 10-K excerpt", type_="filing"),
                    ],
                },
                {
                    "title": "What is missing",
                    "type": "text",
                    "content": {
                        "text": (
                            "Price-to-book and current market capitalisation are absent: the market-data "
                            "tool timed out and the remaining tools cannot substitute for it. Re-running "
                            "this query is likely to complete."
                        )
                    },
                    "confidence": "low",
                    "sources": [],
                },
            ],
            "partial": True,
            "failed_tools": [MARKET_DATA],
            "generated_at": (now - timedelta(days=4)).isoformat(),
        }
    )


def _semiconductor_supply(now: datetime) -> ResearchReport:
    """Org B's report. Overlaps Org A's tickers on purpose."""
    return ResearchReport.model_validate(
        {
            "summary": (
                "Advanced-node supply remains the binding constraint across the sector. Packaging "
                "capacity, not wafer starts, is the near-term bottleneck."
            ),
            "sections": [
                {
                    "title": "Supply constraints by node",
                    "type": "table",
                    "content": {
                        "columns": ["Constraint", "Affected", "Severity", "Expected easing"],
                        "rows": [
                            ["Advanced packaging", "NVDA, AMD", "High", "H2 next year"],
                            ["HBM memory supply", "NVDA", "High", "Gradual"],
                            ["Leading-edge wafer starts", "Sector-wide", "Moderate", "Ongoing"],
                        ],
                    },
                    "confidence": "medium",
                    "sources": [_source("Sector filings excerpt", type_="filing")],
                },
                {
                    "title": "Read-through",
                    "type": "text",
                    "content": {
                        "text": (
                            "Packaging capacity is contracted well ahead of delivery, so share shifts over "
                            "the next few quarters are largely already decided. Demand commentary is a "
                            "weaker signal than usual in this environment."
                        )
                    },
                    "confidence": "medium",
                    "sources": [_source("Sector filings excerpt", type_="filing")],
                },
            ],
            "partial": False,
            "failed_tools": [],
            "generated_at": (now - timedelta(days=1)).isoformat(),
        }
    )


def demo_orgs(now: datetime) -> list[DemoOrg]:
    """The whole fixture, with timestamps relative to `now`.

    `now` is a parameter rather than read from the clock so the fixture is
    reproducible in tests, and so every seeded artefact lands at a known age --
    which is what makes the staleness affordances demonstrable.
    """
    northwind = DemoOrg(
        name="Northwind Capital",
        users=[
            DemoUser("nw_admin", "admin@northwind.test", "Dana Okonjo", "admin"),
            DemoUser("nw_analyst1", "analyst@northwind.test", "Priya Raman", "analyst"),
            DemoUser("nw_analyst2", "analyst2@northwind.test", "Tom Whitfield", "analyst"),
        ],
        reports=[
            DemoReport(
                author="nw_analyst1",
                query_text=(
                    "Analyze NVIDIA's Q3 earnings, compare revenue growth with AMD and Intel, "
                    "summarize competitive threats and news sentiment, and give a risk assessment"
                ),
                tags=["semiconductors", "comparison", "risk"],
                report=_chipmaker_comparison(now),
                age_days=2,
            ),
            DemoReport(
                author="nw_analyst2",
                query_text="What's the latest news on Tesla?",
                tags=["autos", "news"],
                report=_tesla_news(now),
                age_days=9,
            ),
            DemoReport(
                author="nw_admin",
                query_text="Compare the balance sheets of JPMorgan, Goldman Sachs, and Morgan Stanley",
                tags=["banks", "balance-sheet"],
                report=_degraded_banks(now),
                age_days=4,
            ),
        ],
        queries=[
            DemoQuery("nw_analyst1", "What is a P/E ratio?", [], "success", 2_140, age_hours=2),
            DemoQuery("nw_analyst1", "What's NVIDIA's current P/E and market cap?", [MARKET_DATA], "success", 3_880, age_hours=6),
            DemoQuery("nw_analyst2", "What's the latest news on Tesla?", [NEWS_SENTIMENT], "success", 6_410, age_hours=20),
            DemoQuery(
                "nw_analyst1",
                "Give me a quick overview of Tesla -- stock performance this quarter, major news in the last 30 days, and key risks",
                [MARKET_DATA, NEWS_SENTIMENT, KNOWLEDGE_BASE],
                "success",
                11_260,
                age_hours=30,
            ),
            DemoQuery(
                "nw_admin",
                "Compare the balance sheets of JPMorgan, Goldman Sachs, and Morgan Stanley",
                [MARKET_DATA, KNOWLEDGE_BASE],
                "partial",
                9_030,
                age_hours=96,
            ),
            DemoQuery("nw_analyst2", "How exposed is Intel to foundry losses?", [KNOWLEDGE_BASE], "failed", 1_190, age_hours=120),
        ],
        watchlist=[
            DemoPin("nw_analyst1", "NVDA", "NVIDIA Corporation"),
            DemoPin("nw_analyst1", "AMD", "Advanced Micro Devices, Inc."),
            DemoPin("nw_analyst1", "INTC", "Intel Corporation"),
            DemoPin("nw_analyst2", "TSLA", "Tesla, Inc."),
            DemoPin("nw_admin", "JPM", "JPMorgan Chase & Co."),
        ],
    )

    vector = DemoOrg(
        name="Vector Partners",
        users=[
            DemoUser("vp_admin", "admin@vector.test", "Marta Kovac", "admin"),
            DemoUser("vp_analyst", "analyst@vector.test", "Sam Adeyemi", "analyst"),
        ],
        reports=[
            DemoReport(
                author="vp_analyst",
                query_text="What are the main supply constraints facing semiconductor manufacturers?",
                tags=["semiconductors", "supply-chain"],
                report=_semiconductor_supply(now),
                age_days=1,
            ),
        ],
        queries=[
            DemoQuery("vp_analyst", "What are the main supply constraints facing semiconductor manufacturers?", [KNOWLEDGE_BASE], "success", 5_220, age_hours=26),
            DemoQuery("vp_admin", "What's NVIDIA's current P/E and market cap?", [MARKET_DATA], "success", 3_410, age_hours=48),
        ],
        watchlist=[
            DemoPin("vp_analyst", "NVDA", "NVIDIA Corporation"),
            DemoPin("vp_analyst", "TSM", "Taiwan Semiconductor Manufacturing Company"),
            DemoPin("vp_admin", "AMD", "Advanced Micro Devices, Inc."),
        ],
    )

    return [northwind, vector]


def demo_org_names() -> list[str]:
    """Names the seed script deletes before re-inserting."""
    return [org.name for org in demo_orgs(datetime.now())]
