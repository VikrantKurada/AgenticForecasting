from app.connectors.alphavantage import AlphaVantageConnector
from app.connectors.bls import BLSConnector
from app.connectors.cache import CachedConnector
from app.connectors.catalog import SOURCES
from app.connectors.dbnomics import DBnomicsConnector
from app.connectors.ecb import ECBConnector
from app.connectors.eia import EIAConnector
from app.connectors.faostat import FAOSTATConnector
from app.connectors.fred import FredConnector
from app.connectors.imf import IMFConnector
from app.connectors.keys import get_datasource_key
from app.connectors.oecd import OECDConnector
from app.connectors.stubs import StubConnector
from app.connectors.treasury import TreasuryConnector
from app.connectors.worldbank import WorldBankConnector


def _implemented_connectors(session_factory) -> dict:
    key = lambda name: get_datasource_key(session_factory, name)  # noqa: E731
    return {
        "fred": FredConnector(api_key=key("fred")),
        "worldbank": WorldBankConnector(),
        "imf": IMFConnector(),
        "bls": BLSConnector(api_key=key("bls")),
        "ecb": ECBConnector(),
        "oecd": OECDConnector(),
        "dbnomics": DBnomicsConnector(),
        "treasury": TreasuryConnector(),
        "eia": EIAConnector(api_key=key("eia")),
        "faostat": FAOSTATConnector(),
        "alphavantage": AlphaVantageConnector(api_key=key("alphavantage")),
    }


def build_connectors(session_factory) -> dict:
    connectors = _implemented_connectors(session_factory)
    cached = {name: CachedConnector(conn, session_factory) for name, conn in connectors.items()}
    for source in SOURCES:
        if source["name"] in cached:
            continue
        cached[source["name"]] = StubConnector(
            source["name"],
            f"{source['label']} connector is not yet implemented. {source['note']}",
        )
    return cached


def datasource_catalog(session_factory) -> list[dict]:
    return [
        {
            "name": s["name"],
            "label": s["label"],
            "category": s["category"],
            "available": s["implemented"],
            "needs_key": s["needs_key"],
            "key_present": (not s["needs_key"])
            or bool(get_datasource_key(session_factory, s["name"])),
            "note": s["note"],
        }
        for s in SOURCES
    ]
