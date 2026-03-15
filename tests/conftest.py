"""Shared test fixtures for the stock-analyst test suite."""
import pytest
import pandas as pd
from src.models import (
    FinancialStatements,
    MarketData,
    InsiderActivity,
    InstitutionalData,
    MacroContext,
    FilingText,
    PeerData,
    DataPackage,
    FinancialRatio,
    FinancialAnalysis,
    InvestmentCase,
    ConfidenceDriver,
    ConfidenceScore,
    InvestmentThesis,
    LimitationNote,
    Recommendation,
    ConfidenceLevel,
    CompanyType,
)


def make_sample_data_package(**overrides) -> DataPackage:
    """Fully populated DataPackage with stub values. Accepts optional overrides."""
    defaults = dict(
        ticker="AAPL",
        company_name="Apple Inc.",
        financials=FinancialStatements(
            income_statement={
                "Revenue": {"2024": 383_285_000_000, "2023": 383_933_000_000},
                "Net Income": {"2024": 93_736_000_000, "2023": 96_995_000_000},
            },
            balance_sheet={
                "Total Assets": {"2024": 352_583_000_000},
                "Total Debt": {"2024": 104_590_000_000},
            },
            cash_flow={
                "Operating Cash Flow": {"2024": 118_254_000_000},
                "Free Cash Flow": {"2024": 108_807_000_000},
            },
            quarterly_revenue=[94_930, 90_753, 85_777, 89_498, 94_836, 90_146, 81_797, 83_083],
        ),
        market_data=MarketData(
            current_price=178.50,
            market_cap=2_750_000_000_000,
            pe_ratio=28.5,
            pb_ratio=45.2,
            ps_ratio=7.3,
            ev_ebitda=22.1,
            eps=6.26,
            dividend_yield=0.55,
            beta=1.24,
            fifty_two_week_high=199.62,
            fifty_two_week_low=164.08,
            sector="Technology",
            industry="Consumer Electronics",
        ),
        price_history=[
            {"date": "2024-01-02", "close": 185.64},
            {"date": "2024-01-03", "close": 184.25},
        ],
        insider_activity=InsiderActivity(
            transactions=[
                {"name": "Tim Cook", "type": "Sale", "shares": 100_000, "date": "2024-06-01"},
            ],
            net_buys=-1,
            source="edgar",
        ),
        institutional=InstitutionalData(
            holders=[
                {"name": "Vanguard Group", "shares": 1_300_000_000, "pct": 8.5},
                {"name": "BlackRock", "shares": 1_100_000_000, "pct": 7.2},
            ],
            institutional_ownership_pct=60.5,
        ),
        macro=MacroContext(
            fed_funds_rate=5.33,
            gdp_growth=2.8,
            unemployment_rate=3.7,
            cpi_yoy=3.1,
            yield_spread=0.15,
            as_of_date="2024-12-01",
        ),
        filing_text=FilingText(
            mda_text="The Company designs, manufactures and markets smartphones...",
            risk_factors_text="Global economic conditions could materially affect...",
            filing_date="2024-11-01",
            filing_type="10-K",
        ),
        peers=[
            PeerData("MSFT", "Microsoft Corp", 2_900_000_000_000, 35.2, 12.1, 0.16, 0.36, 0.38),
            PeerData("GOOGL", "Alphabet Inc", 1_700_000_000_000, 24.1, 6.2, 0.13, 0.25, 0.28),
            PeerData("AMZN", "Amazon.com Inc", 1_500_000_000_000, 62.3, 3.1, 0.12, 0.07, 0.22),
        ],
        company_predictability_score=78,
        warnings=[
            LimitationNote("yfinance", "Peer data incomplete for 1 ticker", "warning"),
        ],
    )
    defaults.update(overrides)
    return DataPackage(**defaults)


@pytest.fixture
def sample_data_package():
    return make_sample_data_package()


@pytest.fixture
def sample_price_data():
    """Minimal price DataFrame with OHLCV columns."""
    return pd.DataFrame({
        "Open": [185.0, 184.0, 186.0],
        "High": [186.5, 185.5, 187.0],
        "Low": [184.0, 183.5, 185.0],
        "Close": [185.64, 184.25, 186.50],
        "Volume": [50_000_000, 48_000_000, 52_000_000],
    }, index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]))


@pytest.fixture
def sample_financial_analysis():
    """Populated FinancialAnalysis for testing."""
    return FinancialAnalysis(
        company_type=CompanyType.GROWTH,
        profitability={"gross_margin": 0.45, "operating_margin": 0.30, "net_margin": 0.24},
        growth={"revenue_growth": 0.08, "earnings_growth": 0.12},
        balance_sheet_health={"debt_to_equity": 1.5, "current_ratio": 1.1},
        cash_flow_quality={"ocf_to_net_income": 1.26, "fcf_trend": "stable"},
        ratios=[
            FinancialRatio("P/E", {"2024": 28.5, "2023": 26.1}, "stable", "In line with peers"),
        ],
        peer_comparison={"vs_median_pe": "premium", "vs_median_growth": "above"},
        trend_assessments={"revenue": "stable", "margins": "improving"},
        forward_outlook={"revenue_trajectory": "stable growth", "margin_outlook": "expanding"},
        risk_factors=["Supply chain concentration", "Regulatory risk in China"],
        macro_impact="Rising rates pressure valuation multiples",
        insider_interpretation="Routine executive selling, no alarm",
        strengths=["Strong brand", "Services growth", "Cash generation"],
        concerns=["iPhone saturation", "China exposure"],
        directional_lean="BULLISH",
        directional_rationale="Strong fundamentals with services tailwind",
        earnings_quality=75,
        valuation_clarity=65,
        macro_conditions=60,
        chain_of_thought="Step 1: Company classified as Growth...",
    )


@pytest.fixture
def sample_investment_thesis(sample_financial_analysis):
    """Populated InvestmentThesis for testing."""
    return InvestmentThesis(
        recommendation=Recommendation.BUY,
        executive_summary="Apple remains a compelling investment...",
        bull_case=InvestmentCase("bull", "Services accelerates", ["AI features", "App Store growth"], 0.30),
        base_case=InvestmentCase("base", "Steady growth continues", ["iPhone stable", "Services grows"], 0.50),
        bear_case=InvestmentCase("bear", "China crackdown hits hard", ["Regulatory risk", "Demand weakness"], 0.20),
        peer_comparison_narrative="Trades at a premium to peers, justified by margins",
        forward_outlook="12-month outlook: moderate upside driven by services",
        risks=["China regulatory", "Antitrust"],
        catalysts=["AI integration", "Services margin expansion"],
        macro_context="Rate cuts could support multiple expansion",
        insider_summary="Net selling, but routine patterns",
        confidence=ConfidenceScore(
            score=72,
            level=ConfidenceLevel.HIGH,
            summary="High confidence driven by data completeness and earnings quality.",
            drivers=[
                ConfidenceDriver("Data Completeness", 100, 0.20, "positive", "All sources available"),
                ConfidenceDriver("Earnings Quality", 75, 0.25, "positive", "Consistent earnings"),
                ConfidenceDriver("Valuation Clarity", 65, 0.20, "positive", "Good peer comps"),
                ConfidenceDriver("Company Predictability", 78, 0.20, "positive", "Stable revenue"),
                ConfidenceDriver("Insider Signal", 45, 0.10, "negative", "Net selling vs bullish lean"),
                ConfidenceDriver("Macro Conditions", 60, 0.05, "neutral", "Mixed macro signals"),
            ],
        ),
    )
