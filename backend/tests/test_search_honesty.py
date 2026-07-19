"""Search must not invent plausible-looking results.

Catalog-backed connectors used to return the head of their catalog when nothing
matched. An agent cannot distinguish that from a real hit: a search for
"GBP/INR" answered "GDP growth (annual %)", so the fetcher kept re-searching,
burned its whole iteration budget, never called fetch_series, and the run
produced no data and therefore no charts.
"""
import pytest

from app.agents.tools import ToolContext, build_toolbelt, execute_tool
from app.connectors.alphavantage import AlphaVantageConnector
from app.connectors.eia import EIAConnector
from app.connectors.faostat import FAOSTATConnector
from app.connectors.treasury import TreasuryConnector
from app.connectors.worldbank import WorldBankConnector

CONNECTORS = [
    WorldBankConnector,
    AlphaVantageConnector,
    EIAConnector,
    FAOSTATConnector,
    TreasuryConnector,
]


@pytest.mark.parametrize("connector_cls", CONNECTORS)
def test_no_match_returns_nothing_not_catalog_filler(connector_cls):
    connector = connector_cls()
    assert connector.search("zzzz no such series qqqq", limit=5) == []


@pytest.mark.parametrize("connector_cls", CONNECTORS)
def test_a_real_match_is_still_returned(connector_cls):
    connector = connector_cls()
    # every catalog has something; search for a word from its own first entry
    from app.connectors import alphavantage, eia, faostat, treasury, worldbank

    catalogs = {
        WorldBankConnector: [t for _c, t in worldbank.CATALOG],
        AlphaVantageConnector: [t for _c, t in alphavantage.CATALOG],
        EIAConnector: [t for _c, t in eia.CATALOG],
        FAOSTATConnector: [t for _c, t in faostat.CATALOG],
        TreasuryConnector: [s[3] for s in treasury.CATALOG.values()],
    }
    first_title = catalogs[connector_cls][0]
    word = max(first_title.split(), key=len).strip("(),%")
    assert connector.search(word, limit=5), f"expected a hit for {word!r}"


def test_search_series_explains_an_empty_result(tmp_path):
    from app.db import init_db, make_engine, make_session_factory

    engine = make_engine(f"sqlite:///{(tmp_path / 'search.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    ctx = ToolContext(
        session_factory=factory,
        connectors={"worldbank": WorldBankConnector()},
        memory=None,
    )
    result = execute_tool(
        build_toolbelt(), "search_series", {"query": "zzzz no such series qqqq"}, ctx
    )
    assert result["results"] == []
    # the agent is told not to just search again
    assert "note" in result
    assert "fetch_series" in result["note"]
