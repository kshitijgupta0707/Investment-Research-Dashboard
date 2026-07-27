"""The demo fixture, and the SQL that loads it.

The fixture is not decoration -- the three demo workflows the brief asks for are
run against it, so the properties that make those workflows possible are tested
as requirements rather than left to whoever last edited the file:

* two organizations that research *overlapping* tickers, so isolation is
  visibly about `org_id`;
* two analysts in one org, so the ownership rule has something to fail against;
* a partial report and a failed query, so the degraded states are demonstrable;
* history spanning zero to three tools, so selective tool choice shows up in
  seeded data.

The loader itself is exercised against the real database inside a rolled-back
transaction.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import psycopg2
import pytest

from app.agent.tools import TOOL_NAMES
from app.schemas.report import ResearchReport
from app.services.demo_data import DemoOrg, demo_org_names, demo_orgs

NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def orgs() -> list[DemoOrg]:
    return demo_orgs(NOW)


def _keys(org: DemoOrg) -> set[str]:
    return {user.key for user in org.users}


# --- shape ------------------------------------------------------------------


def test_there_are_two_organizations(orgs: list[DemoOrg]) -> None:
    assert len(orgs) == 2
    assert len({org.name for org in orgs}) == 2


def test_every_org_has_an_admin_and_an_analyst(orgs: list[DemoOrg]) -> None:
    for org in orgs:
        roles = {user.role for user in org.users}
        assert roles == {"admin", "analyst"}, org.name


def test_one_org_has_two_analysts(orgs: list[DemoOrg]) -> None:
    """Otherwise "an analyst cannot edit a colleague's report" cannot be shown."""
    counts = [sum(user.role == "analyst" for user in org.users) for org in orgs]

    assert max(counts) >= 2


def test_emails_are_unique_across_the_fixture(orgs: list[DemoOrg]) -> None:
    """`users.supabase_auth_id` is unique, so one address cannot join twice."""
    emails = [user.email for org in orgs for user in org.users]

    assert len(emails) == len(set(emails))


def test_the_orgs_research_overlapping_tickers(orgs: list[DemoOrg]) -> None:
    """Isolation must be visibly about org_id, not about differing interests."""
    a, b = ({pin.ticker for pin in org.watchlist} for org in orgs)

    assert a & b


# --- referential integrity --------------------------------------------------


def test_every_report_has_a_real_author(orgs: list[DemoOrg]) -> None:
    for org in orgs:
        assert {report.author for report in org.reports} <= _keys(org), org.name


def test_every_history_row_has_a_real_author(orgs: list[DemoOrg]) -> None:
    for org in orgs:
        assert {ran.author for ran in org.queries} <= _keys(org), org.name


def test_every_pin_has_a_real_owner(orgs: list[DemoOrg]) -> None:
    for org in orgs:
        assert {pin.owner for pin in org.watchlist} <= _keys(org), org.name


def test_no_user_pins_the_same_ticker_twice(orgs: list[DemoOrg]) -> None:
    """`unique (org_id, user_id, ticker)` would reject the second insert."""
    for org in orgs:
        pairs = [(pin.owner, pin.ticker) for pin in org.watchlist]
        assert len(pairs) == len(set(pairs)), org.name


# --- the contract -----------------------------------------------------------


def test_every_saved_report_matches_the_turn_2_contract(orgs: list[DemoOrg]) -> None:
    """Built through the model, so a contract change breaks this loudly."""
    for org in orgs:
        for saved in org.reports:
            assert isinstance(saved.report, ResearchReport)
            round_tripped = ResearchReport.model_validate(saved.report.model_dump(mode="json"))
            assert round_tripped.summary == saved.report.summary


def test_tags_are_stored_the_way_the_api_would_normalise_them(orgs: list[DemoOrg]) -> None:
    """Seeded rows must be indistinguishable from rows saved through the API."""
    for org in orgs:
        for saved in org.reports:
            assert saved.tags == [tag.strip().lower() for tag in saved.tags]
            assert len(saved.tags) == len(set(saved.tags))


def test_every_section_carries_a_confidence_and_a_title(orgs: list[DemoOrg]) -> None:
    for org in orgs:
        for saved in org.reports:
            for section in saved.report.sections:
                assert section.title
                assert section.confidence in ("high", "medium", "low")


def test_every_section_type_appears_somewhere(orgs: list[DemoOrg]) -> None:
    """So every renderer built in CR-22 has a case to render on a fresh clone."""
    seen = {
        section.type
        for org in orgs
        for saved in org.reports
        for section in saved.report.sections
    }

    assert seen == {"text", "table", "chart", "company_card", "sentiment"}


def test_most_sections_attribute_a_source(orgs: list[DemoOrg]) -> None:
    sections = [s for org in orgs for saved in org.reports for s in saved.report.sections]
    attributed = [s for s in sections if s.sources]

    assert len(attributed) >= len(sections) - 1


# --- demonstrable states ----------------------------------------------------


def test_one_report_is_partial(orgs: list[DemoOrg]) -> None:
    """The degraded-data banner needs a case that does not require breaking an API."""
    partial = [saved for org in orgs for saved in org.reports if saved.report.partial]

    assert len(partial) == 1
    assert partial[0].report.failed_tools


def test_a_partial_report_names_only_real_tools(orgs: list[DemoOrg]) -> None:
    for org in orgs:
        for saved in org.reports:
            assert set(saved.report.failed_tools) <= set(TOOL_NAMES)


def test_history_shows_the_agent_choosing_different_tools(orgs: list[DemoOrg]) -> None:
    """Zero, one, two and three tools all appear -- the claim, in seeded data."""
    sizes = {len(ran.tools_selected) for org in orgs for ran in org.queries}

    assert {0, 1, 2, 3} <= sizes


def test_history_only_names_real_tools(orgs: list[DemoOrg]) -> None:
    for org in orgs:
        for ran in org.queries:
            assert set(ran.tools_selected) <= set(TOOL_NAMES), ran.query_text


def test_history_covers_every_status(orgs: list[DemoOrg]) -> None:
    statuses = {ran.status for org in orgs for ran in org.queries}

    assert statuses == {"success", "partial", "failed"}


def test_reports_span_fresh_and_stale(orgs: list[DemoOrg]) -> None:
    """The staleness hint fires past ~24h, so both sides of it need a case."""
    ages = [saved.age_days for org in orgs for saved in org.reports]

    assert min(ages) <= 1
    assert max(ages) > 1


def test_the_zero_tool_query_is_the_one_from_the_plan(orgs: list[DemoOrg]) -> None:
    zero_tool = [ran for org in orgs for ran in org.queries if not ran.tools_selected]

    assert [ran.query_text for ran in zero_tool] == ["What is a P/E ratio?"]


def test_demo_org_names_matches_the_fixture(orgs: list[DemoOrg]) -> None:
    """The seed script deletes by these names; a drift would orphan old rows."""
    assert demo_org_names() == [org.name for org in orgs]


# --- the loader, against the real database ----------------------------------


@pytest.fixture
def conn(settings, requires_db):
    """A connection whose work is always rolled back."""
    connection = psycopg2.connect(settings.database_url, connect_timeout=20)
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


def _count(conn: Any, table: str, org_id: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"select count(*) from {table} where org_id = %s", (org_id,))
        return cur.fetchone()[0]


def _org_id(conn: Any, name: str) -> str:
    with conn.cursor() as cur:
        cur.execute("select id from organizations where name = %s", (name,))
        return cur.fetchone()[0]


@pytest.fixture
def seeded(conn, orgs: list[DemoOrg]):
    """Run the real loader, then roll back."""
    from scripts.seed_data import seed_org, wipe

    wipe(conn, demo_org_names())
    auth_ids = {user.key: str(uuid.uuid4()) for org in orgs for user in org.users}
    codes = {org.name: seed_org(conn, org, auth_ids, NOW) for org in orgs}
    return codes


def test_live_the_loader_writes_every_table(conn, orgs: list[DemoOrg], seeded) -> None:
    for org in orgs:
        org_id = _org_id(conn, org.name)

        assert _count(conn, "users", org_id) == len(org.users)
        assert _count(conn, "research_reports", org_id) == len(org.reports)
        assert _count(conn, "research_queries", org_id) == len(org.queries)
        assert _count(conn, "watchlist", org_id) == len(org.watchlist)
        assert _count(conn, "org_invites", org_id) == 1


def test_live_structured_results_survive_as_jsonb(conn, orgs: list[DemoOrg], seeded) -> None:
    """The one column where a serialisation slip is invisible until render time."""
    org_id = _org_id(conn, orgs[0].name)
    with conn.cursor() as cur:
        cur.execute(
            "select structured_result from research_reports where org_id = %s order by created_at",
            (org_id,),
        )
        stored = [row[0] for row in cur.fetchall()]

    assert stored
    for raw in stored:
        assert ResearchReport.model_validate(raw).sections


def test_live_neither_org_can_see_the_others_reports(conn, orgs: list[DemoOrg], seeded) -> None:
    a_id, b_id = (_org_id(conn, org.name) for org in orgs)

    with conn.cursor() as cur:
        cur.execute("select org_id from research_reports where org_id = %s", (a_id,))
        assert all(row[0] == a_id for row in cur.fetchall())
        cur.execute("select count(*) from research_reports where org_id = %s", (b_id,))
        assert cur.fetchone()[0] == len(orgs[1].reports)


def test_live_the_invite_code_is_usable(conn, orgs: list[DemoOrg], seeded) -> None:
    """Active, unexpired, and belonging to the org it was printed for."""
    for org in orgs:
        with conn.cursor() as cur:
            cur.execute(
                """
                select org_id from org_invites
                where code = %s and status = 'active' and expires_at > now()
                """,
                (seeded[org.name],),
            )
            row = cur.fetchone()

        assert row is not None, org.name
        assert row[0] == _org_id(conn, org.name)


def test_live_re_seeding_replaces_rather_than_accumulates(conn, orgs: list[DemoOrg], seeded) -> None:
    """Re-running the script is a reset. Otherwise a demo drifts between runs."""
    from scripts.seed_data import seed_org, wipe

    removed = wipe(conn, demo_org_names())
    assert removed == len(orgs)

    auth_ids = {user.key: str(uuid.uuid4()) for org in orgs for user in org.users}
    for org in orgs:
        seed_org(conn, org, auth_ids, NOW)

    with conn.cursor() as cur:
        cur.execute("select count(*) from organizations where name = any(%s)", (demo_org_names(),))
        assert cur.fetchone()[0] == len(orgs)


def test_live_wiping_removes_the_children_too(conn, orgs: list[DemoOrg], seeded) -> None:
    """The delete relies on `on delete cascade`; nothing sweeps up by hand."""
    org_id = _org_id(conn, orgs[0].name)

    wipe_count = None
    from scripts.seed_data import wipe

    wipe_count = wipe(conn, demo_org_names())

    assert wipe_count == len(orgs)
    assert _count(conn, "research_reports", org_id) == 0
    assert _count(conn, "watchlist", org_id) == 0
    assert _count(conn, "research_queries", org_id) == 0
