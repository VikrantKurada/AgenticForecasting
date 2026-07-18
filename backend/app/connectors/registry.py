from app.config import settings
from app.connectors.bls import BLSConnector
from app.connectors.cache import CachedConnector
from app.connectors.ecb import ECBConnector
from app.connectors.fred import FredConnector
from app.connectors.imf import IMFConnector
from app.connectors.oecd import OECDConnector
from app.connectors.stubs import StubConnector
from app.connectors.worldbank import WorldBankConnector


def build_connectors(session_factory) -> dict:
    connectors = {
        "fred": FredConnector(api_key=settings.fred_api_key),
        "worldbank": WorldBankConnector(),
        "imf": IMFConnector(),
        "bls": BLSConnector(api_key=settings.bls_api_key),
        "ecb": ECBConnector(),
        "oecd": OECDConnector(),
    }
    cached = {name: CachedConnector(conn, session_factory) for name, conn in connectors.items()}
    cached["bea"] = StubConnector(
        "bea", "Bureau of Economic Analysis connector is not yet implemented; "
        "use FRED for US national accounts series instead.",
    )
    cached["census"] = StubConnector(
        "census", "U.S. Census Bureau connector is not yet implemented; "
        "use FRED for US trade and housing series instead.",
    )
    return cached


def datasource_catalog() -> list[dict]:
    return [
        {"name": "fred", "label": "FRED (Federal Reserve)", "available": True,
         "needs_key": True, "key_present": bool(settings.fred_api_key),
         "note": "US macro/financial series. Set FRED_API_KEY."},
        {"name": "worldbank", "label": "World Bank", "available": True,
         "needs_key": False, "key_present": True, "note": "Global development indicators."},
        {"name": "imf", "label": "IMF", "available": True,
         "needs_key": False, "key_present": True, "note": "IFS/BOP macro series."},
        {"name": "bls", "label": "BLS", "available": True,
         "needs_key": False, "key_present": bool(settings.bls_api_key),
         "note": "US labor/CPI series. Optional BLS_API_KEY raises limits."},
        {"name": "ecb", "label": "ECB Data Portal", "available": True,
         "needs_key": False, "key_present": True, "note": "Euro area series."},
        {"name": "oecd", "label": "OECD", "available": True,
         "needs_key": False, "key_present": True, "note": "OECD SDMX series."},
        {"name": "bea", "label": "BEA", "available": False,
         "needs_key": True, "key_present": False, "note": "Planned; use FRED meanwhile."},
        {"name": "census", "label": "U.S. Census Bureau", "available": False,
         "needs_key": True, "key_present": False, "note": "Planned; use FRED meanwhile."},
    ]
