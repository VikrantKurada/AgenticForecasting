"""Catalog of every configurable data source API.

`implemented` sources have a working connector; the rest store keys/config now so
their connectors can ship later without another settings change.
"""

CATEGORIES = [
    "Sovereign & Macroeconomic",
    "Aggregators",
    "Equities, Forex & Crypto",
    "Brokerage",
    "Fixed Income & Commodities",
    "Alternative, Civic & Real Estate",
]


def _src(name, label, category, *, needs_key=False, implemented=False, note=""):
    return {
        "name": name, "label": label, "category": category,
        "needs_key": needs_key, "implemented": implemented, "note": note,
    }


SOVEREIGN = "Sovereign & Macroeconomic"
AGG = "Aggregators"
EQ = "Equities, Forex & Crypto"
BROKER = "Brokerage"
FIC = "Fixed Income & Commodities"
ALT = "Alternative, Civic & Real Estate"

SOURCES: list[dict] = [
    # --- Sovereign & Macroeconomic -----------------------------------------
    _src("fred", "FRED (Federal Reserve)", SOVEREIGN, needs_key=True, implemented=True,
         note="US macro/financial series. Free key: fred.stlouisfed.org."),
    _src("bls", "Bureau of Labor Statistics", SOVEREIGN, needs_key=True, implemented=True,
         note="US labor & CPI. Works keyless at low rate limits; key raises them."),
    _src("bea", "Bureau of Economic Analysis", SOVEREIGN, needs_key=True,
         note="US NIPA accounts. Connector planned; use FRED meanwhile."),
    _src("eia", "Energy Information Administration", SOVEREIGN, needs_key=True, implemented=True,
         note="US & world energy production/consumption. Free key: eia.gov/opendata."),
    _src("treasury", "US Treasury Fiscal Data", SOVEREIGN, implemented=True,
         note="Federal debt, interest rates, revenue. No key needed."),
    _src("census", "US Census Bureau", SOVEREIGN, needs_key=True,
         note="Trade, housing, demographics. Connector planned; use FRED meanwhile."),
    _src("ecb", "European Central Bank", SOVEREIGN, implemented=True,
         note="Euro area rates, HICP, yield curves. No key needed."),
    _src("boe", "Bank of England", SOVEREIGN,
         note="UK rates and financial series. Reachable today via DBnomics (provider BOE)."),
    _src("bank_of_london", "Bank of London", SOVEREIGN, needs_key=True,
         note="Registered for key config; no public statistical API documented."),
    _src("bundesbank", "Deutsche Bundesbank", SOVEREIGN,
         note="German macro series. Reachable today via DBnomics (provider BUBA)."),
    _src("rbi", "Reserve Bank of India", SOVEREIGN,
         note="Indian macro series. Reachable today via DBnomics where mirrored."),
    _src("cnb", "Czech National Bank", SOVEREIGN,
         note="Czech rates/FX. Reachable today via DBnomics where mirrored."),
    _src("eurostat", "Eurostat", SOVEREIGN,
         note="EU statistics. Reachable today via DBnomics (provider Eurostat)."),
    _src("gus", "Statistics Poland (GUS)", SOVEREIGN, needs_key=True,
         note="Polish statistics (BDL API key optional). Connector planned."),
    _src("undata", "UN Data", SOVEREIGN,
         note="UN statistical databases. Connector planned; many series on DBnomics."),
    _src("faostat", "FAO FAOSTAT", SOVEREIGN, implemented=True,
         note="Global food & agriculture production/trade. No key needed."),
    _src("worldbank", "World Bank Indicators", SOVEREIGN, implemented=True,
         note="Global development indicators. No key needed."),
    _src("imf", "IMF Data", SOVEREIGN, implemented=True,
         note="IFS/BOP macro series. No key needed."),
    _src("oecd", "OECD", SOVEREIGN, implemented=True,
         note="OECD SDMX series. No key needed."),
    # --- Aggregators --------------------------------------------------------
    _src("dbnomics", "DBnomics", AGG, implemented=True,
         note="Aggregates 80+ providers (ECB, BoE, Bundesbank, Eurostat, IMF, "
              "national banks). No key needed."),
    _src("chinadata", "ChinaData.live", AGG, needs_key=True,
         note="Chinese macro data. Connector planned."),
    # --- Equities, Forex & Crypto ------------------------------------------
    _src("polygon", "Polygon.io", EQ, needs_key=True,
         note="US equities/options/FX/crypto. Connector planned."),
    _src("finnhub", "Finnhub", EQ, needs_key=True,
         note="Equities, FX, crypto, fundamentals. Connector planned."),
    _src("alphavantage", "Alpha Vantage", EQ, needs_key=True, implemented=True,
         note="Equities, FX, crypto daily series. Free key: alphavantage.co."),
    _src("fmp", "Financial Modeling Prep", EQ, needs_key=True,
         note="Fundamentals & prices. Connector planned."),
    _src("twelvedata", "Twelve Data", EQ, needs_key=True,
         note="Equities/FX/crypto. Connector planned."),
    _src("eodhd", "EODHD", EQ, needs_key=True,
         note="EOD historical data. Connector planned."),
    _src("tiingo", "Tiingo", EQ, needs_key=True,
         note="Equities/news/crypto. Connector planned."),
    _src("marketstack", "Marketstack", EQ, needs_key=True,
         note="EOD market data. Connector planned."),
    # --- Brokerage ----------------------------------------------------------
    _src("alpaca", "Alpaca", BROKER, needs_key=True,
         note="Market data with brokerage account (key:secret). Connector planned."),
    _src("tradier", "Tradier", BROKER, needs_key=True,
         note="Market data with brokerage account. Connector planned."),
    # --- Fixed Income & Commodities ----------------------------------------
    _src("apininjas", "API Ninjas (Commodities)", FIC, needs_key=True,
         note="Spot commodity prices. Connector planned."),
    _src("commoditiesapi", "Commodities-API", FIC, needs_key=True,
         note="Commodity price feeds. Connector planned."),
    _src("cbonds", "CBonds", FIC, needs_key=True,
         note="Bond reference data. Connector planned."),
    _src("usda_psd", "USDA FAS PSD", FIC, needs_key=True,
         note="Global agricultural production/supply/distribution. Connector planned; "
              "FAOSTAT covers production meanwhile."),
    _src("jodi", "JODI Oil & Gas", FIC,
         note="Global oil/gas production, demand, stocks. Connector planned; "
              "EIA world series cover petroleum meanwhile."),
    # --- Alternative, Civic & Real Estate ----------------------------------
    _src("companieshouse", "UK Companies House", ALT, needs_key=True,
         note="UK company filings. Connector planned."),
    _src("globalscreen", "GlobalScreen", ALT, needs_key=True,
         note="Screening data. Connector planned."),
    _src("landregistry", "HM Land Registry", ALT,
         note="UK property prices (open data). Connector planned."),
    _src("propertydata", "PropertyData", ALT, needs_key=True,
         note="UK property analytics. Connector planned."),
    _src("homedata", "HomeData", ALT, needs_key=True,
         note="Housing data. Connector planned."),
    _src("idealpostcodes", "Ideal Postcodes", ALT, needs_key=True,
         note="UK address/postcode lookup. Connector planned."),
    _src("geodojo", "GeoDojo", ALT, needs_key=True,
         note="Geocoding utilities. Connector planned."),
    _src("civiq", "CIV.IQ", ALT, needs_key=True,
         note="Civic data. Connector planned."),
]

SOURCE_BY_NAME = {s["name"]: s for s in SOURCES}
