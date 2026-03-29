"""
Stock universe: Nifty 50 + Bank Nifty constituents with 5paisa scrip codes.
Scrip codes are NSE Cash segment codes used by the 5paisa API.
"""

# Format: {"SYMBOL": {"scrip_code": int, "name": str, "sector": str}}

NIFTY_50 = {
    "RELIANCE": {"scrip_code": 2885, "name": "Reliance Industries", "sector": "Energy"},
    "TCS": {"scrip_code": 11536, "name": "Tata Consultancy Services", "sector": "IT"},
    "HDFCBANK": {"scrip_code": 1901, "name": "HDFC Bank", "sector": "Banking"},
    "INFY": {"scrip_code": 1594, "name": "Infosys", "sector": "IT"},
    "ICICIBANK": {"scrip_code": 4963, "name": "ICICI Bank", "sector": "Banking"},
    "HINDUNILVR": {"scrip_code": 1394, "name": "Hindustan Unilever", "sector": "FMCG"},
    "ITC": {"scrip_code": 1660, "name": "ITC", "sector": "FMCG"},
    "SBIN": {"scrip_code": 3045, "name": "State Bank of India", "sector": "Banking"},
    "BHARTIARTL": {"scrip_code": 10604, "name": "Bharti Airtel", "sector": "Telecom"},
    "KOTAKBANK": {"scrip_code": 1922, "name": "Kotak Mahindra Bank", "sector": "Banking"},
    "LT": {"scrip_code": 2031, "name": "Larsen & Toubro", "sector": "Capital Goods"},
    "AXISBANK": {"scrip_code": 5900, "name": "Axis Bank", "sector": "Banking"},
    "ASIANPAINT": {"scrip_code": 236, "name": "Asian Paints", "sector": "Consumer"},
    "MARUTI": {"scrip_code": 10999, "name": "Maruti Suzuki", "sector": "Auto"},
    "SUNPHARMA": {"scrip_code": 3351, "name": "Sun Pharma", "sector": "Pharma"},
    "TITAN": {"scrip_code": 3506, "name": "Titan Company", "sector": "Consumer"},
    "BAJFINANCE": {"scrip_code": 16675, "name": "Bajaj Finance", "sector": "Finance"},
    "DMART": {"scrip_code": 40483, "name": "Avenue Supermarts", "sector": "Retail"},
    "TMPV": {"scrip_code": 3456, "name": "Tata Motors", "sector": "Auto"},
    "HCLTECH": {"scrip_code": 7229, "name": "HCL Technologies", "sector": "IT"},
    "NTPC": {"scrip_code": 2754, "name": "NTPC", "sector": "Energy"},
    "POWERGRID": {"scrip_code": 14977, "name": "Power Grid Corp", "sector": "Energy"},
    "WIPRO": {"scrip_code": 3787, "name": "Wipro", "sector": "IT"},
    "ULTRACEMCO": {"scrip_code": 14732, "name": "UltraTech Cement", "sector": "Cement"},
    "ONGC": {"scrip_code": 2630, "name": "ONGC", "sector": "Energy"},
    "NESTLEIND": {"scrip_code": 17963, "name": "Nestle India", "sector": "FMCG"},
    "TATASTEEL": {"scrip_code": 3499, "name": "Tata Steel", "sector": "Metals"},
    "JSWSTEEL": {"scrip_code": 11723, "name": "JSW Steel", "sector": "Metals"},
    "M&M": {"scrip_code": 2031, "name": "Mahindra & Mahindra", "sector": "Auto"},
    "BAJAJFINSV": {"scrip_code": 16678, "name": "Bajaj Finserv", "sector": "Finance"},
    "ADANIENT": {"scrip_code": 6191, "name": "Adani Enterprises", "sector": "Conglomerate"},
    "ADANIPORTS": {"scrip_code": 15083, "name": "Adani Ports", "sector": "Infrastructure"},
    "TECHM": {"scrip_code": 13538, "name": "Tech Mahindra", "sector": "IT"},
    "COALINDIA": {"scrip_code": 20374, "name": "Coal India", "sector": "Mining"},
    "HINDALCO": {"scrip_code": 1363, "name": "Hindalco", "sector": "Metals"},
    "DRREDDY": {"scrip_code": 1093, "name": "Dr Reddy's Labs", "sector": "Pharma"},
    "CIPLA": {"scrip_code": 694, "name": "Cipla", "sector": "Pharma"},
    "EICHERMOT": {"scrip_code": 1134, "name": "Eicher Motors", "sector": "Auto"},
    "DIVISLAB": {"scrip_code": 10940, "name": "Divi's Labs", "sector": "Pharma"},
    "BPCL": {"scrip_code": 526, "name": "Bharat Petroleum", "sector": "Energy"},
    "GRASIM": {"scrip_code": 1232, "name": "Grasim Industries", "sector": "Cement"},
    "BRITANNIA": {"scrip_code": 547, "name": "Britannia Industries", "sector": "FMCG"},
    "SBILIFE": {"scrip_code": 41768, "name": "SBI Life Insurance", "sector": "Insurance"},
    "HDFCLIFE": {"scrip_code": 42464, "name": "HDFC Life Insurance", "sector": "Insurance"},
    "APOLLOHOSP": {"scrip_code": 18921, "name": "Apollo Hospitals", "sector": "Healthcare"},
    "TATACONSUM": {"scrip_code": 3432, "name": "Tata Consumer", "sector": "FMCG"},
    "LTIM": {"scrip_code": 17818, "name": "LTIMindtree", "sector": "IT"},
    "INDUSINDBK": {"scrip_code": 5258, "name": "IndusInd Bank", "sector": "Banking"},
    "HEROMOTOCO": {"scrip_code": 1348, "name": "Hero MotoCorp", "sector": "Auto"},
    "BAJAJ-AUTO": {"scrip_code": 16669, "name": "Bajaj Auto", "sector": "Auto"},
}

BANK_NIFTY_EXTRA = {
    "BANDHANBNK": {"scrip_code": 42291, "name": "Bandhan Bank", "sector": "Banking"},
    "FEDERALBNK": {"scrip_code": 1164, "name": "Federal Bank", "sector": "Banking"},
    "PNB": {"scrip_code": 2730, "name": "Punjab National Bank", "sector": "Banking"},
    "BANKBARODA": {"scrip_code": 422, "name": "Bank of Baroda", "sector": "Banking"},
    "AUBANK": {"scrip_code": 42399, "name": "AU Small Finance Bank", "sector": "Banking"},
    "IDFCFIRSTB": {"scrip_code": 11184, "name": "IDFC First Bank", "sector": "Banking"},
    "CANBK": {"scrip_code": 10794, "name": "Canara Bank", "sector": "Banking"},
    "UNIONBANK": {"scrip_code": 13666, "name": "Union Bank", "sector": "Banking"},
    "IOB": {"scrip_code": 1584, "name": "Indian Overseas Bank", "sector": "Banking"},
    "INDIANB": {"scrip_code": 1554, "name": "Indian Bank", "sector": "Banking"},
}

# Combined universe
ALL_STOCKS = {**NIFTY_50, **BANK_NIFTY_EXTRA}

# Sector groupings for rotation analysis
SECTORS = {}
for symbol, info in ALL_STOCKS.items():
    sector = info["sector"]
    if sector not in SECTORS:
        SECTORS[sector] = []
    SECTORS[sector].append(symbol)
