"""Data models — typed contracts between agents.

All models use dataclasses with to_dict()/from_dict() for serialization.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# --- Enums ---


class Recommendation(Enum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"


class ConfidenceLevel(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CompanyType(Enum):
    GROWTH = "GROWTH"
    VALUE = "VALUE"
    DIVIDEND = "DIVIDEND"
    TURNAROUND = "TURNAROUND"
    CYCLICAL = "CYCLICAL"


# --- Utility Models ---


@dataclass
class LimitationNote:
    source: str
    message: str
    severity: str  # "warning" or "error"

    def to_dict(self) -> dict:
        return {"source": self.source, "message": self.message, "severity": self.severity}

    @classmethod
    def from_dict(cls, d: dict) -> LimitationNote:
        return cls(source=d["source"], message=d["message"], severity=d["severity"])


# --- Data Models ---


@dataclass
class FinancialStatements:
    """Multi-year income statement, balance sheet, cash flow data."""
    income_statement: dict[str, Any] = field(default_factory=dict)
    balance_sheet: dict[str, Any] = field(default_factory=dict)
    cash_flow: dict[str, Any] = field(default_factory=dict)
    quarterly_revenue: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "income_statement": self.income_statement,
            "balance_sheet": self.balance_sheet,
            "cash_flow": self.cash_flow,
            "quarterly_revenue": self.quarterly_revenue,
        }

    @classmethod
    def from_dict(cls, d: dict) -> FinancialStatements:
        return cls(
            income_statement=d.get("income_statement", {}),
            balance_sheet=d.get("balance_sheet", {}),
            cash_flow=d.get("cash_flow", {}),
            quarterly_revenue=d.get("quarterly_revenue", []),
        )


@dataclass
class MarketData:
    """Current market data — price, ratios, sector info."""
    current_price: float = 0.0
    market_cap: float = 0.0
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    ps_ratio: float | None = None
    ev_ebitda: float | None = None
    eps: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    sector: str = ""
    industry: str = ""
    quote_type: str = "EQUITY"

    def to_dict(self) -> dict:
        return {
            "current_price": self.current_price,
            "market_cap": self.market_cap,
            "pe_ratio": self.pe_ratio,
            "pb_ratio": self.pb_ratio,
            "ps_ratio": self.ps_ratio,
            "ev_ebitda": self.ev_ebitda,
            "eps": self.eps,
            "dividend_yield": self.dividend_yield,
            "beta": self.beta,
            "fifty_two_week_high": self.fifty_two_week_high,
            "fifty_two_week_low": self.fifty_two_week_low,
            "sector": self.sector,
            "industry": self.industry,
            "quote_type": self.quote_type,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MarketData:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class InsiderActivity:
    """Insider transactions and net sentiment."""
    transactions: list[dict] = field(default_factory=list)
    net_buys: int = 0
    source: str = "edgar"  # "edgar" or "yfinance"

    def to_dict(self) -> dict:
        return {
            "transactions": self.transactions,
            "net_buys": self.net_buys,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict) -> InsiderActivity:
        return cls(
            transactions=d.get("transactions", []),
            net_buys=d.get("net_buys", 0),
            source=d.get("source", "edgar"),
        )


@dataclass
class InstitutionalData:
    """Top institutional holders."""
    holders: list[dict] = field(default_factory=list)
    institutional_ownership_pct: float | None = None

    def to_dict(self) -> dict:
        return {
            "holders": self.holders,
            "institutional_ownership_pct": self.institutional_ownership_pct,
        }

    @classmethod
    def from_dict(cls, d: dict) -> InstitutionalData:
        return cls(
            holders=d.get("holders", []),
            institutional_ownership_pct=d.get("institutional_ownership_pct"),
        )


@dataclass
class MacroContext:
    """FRED macro indicators."""
    fed_funds_rate: float | None = None
    gdp_growth: float | None = None
    unemployment_rate: float | None = None
    cpi_yoy: float | None = None
    yield_spread: float | None = None
    as_of_date: str = ""

    def to_dict(self) -> dict:
        return {
            "fed_funds_rate": self.fed_funds_rate,
            "gdp_growth": self.gdp_growth,
            "unemployment_rate": self.unemployment_rate,
            "cpi_yoy": self.cpi_yoy,
            "yield_spread": self.yield_spread,
            "as_of_date": self.as_of_date,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MacroContext:
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})


@dataclass
class FilingText:
    """Extracted MD&A and risk factors text from SEC filings."""
    mda_text: str = ""
    risk_factors_text: str = ""
    filing_date: str = ""
    filing_type: str = ""  # "10-K" or "10-Q"

    def to_dict(self) -> dict:
        return {
            "mda_text": self.mda_text,
            "risk_factors_text": self.risk_factors_text,
            "filing_date": self.filing_date,
            "filing_type": self.filing_type,
        }

    @classmethod
    def from_dict(cls, d: dict) -> FilingText:
        return cls(**{k: d.get(k, "") for k in cls.__dataclass_fields__})


@dataclass
class PeerData:
    """Comparison data for a single sector peer."""
    ticker: str = ""
    name: str = ""
    market_cap: float = 0.0
    pe_ratio: float | None = None
    ps_ratio: float | None = None
    revenue_growth: float | None = None
    profit_margin: float | None = None
    roe: float | None = None

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "name": self.name,
            "market_cap": self.market_cap,
            "pe_ratio": self.pe_ratio,
            "ps_ratio": self.ps_ratio,
            "revenue_growth": self.revenue_growth,
            "profit_margin": self.profit_margin,
            "roe": self.roe,
        }

    @classmethod
    def from_dict(cls, d: dict) -> PeerData:
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})


@dataclass
class DataPackage:
    """Complete Data Collector output — aggregates all data sources."""
    ticker: str = ""
    company_name: str = ""
    financials: FinancialStatements | None = None
    market_data: MarketData | None = None
    price_history: list[dict] | None = None
    insider_activity: InsiderActivity | None = None
    institutional: InstitutionalData | None = None
    macro: MacroContext | None = None
    filing_text: FilingText | None = None
    peers: list[PeerData] | None = None
    company_predictability_score: int = 50
    warnings: list[LimitationNote] = field(default_factory=list)

    @property
    def data_completeness_score(self) -> int:
        """Weighted score: yfinance=40, EDGAR=35, FRED=25."""
        score = 0
        # yfinance (40 pts) — market_data is the essential indicator
        if self.market_data is not None:
            score += 40
        # EDGAR (35 pts) — financials or filing_text present
        if self.financials is not None or self.filing_text is not None:
            score += 35
        # FRED (25 pts)
        if self.macro is not None:
            score += 25
        return score

    def to_prompt_text(self) -> str:
        """Format data as structured text for Claude prompts."""
        sections = [f"# Financial Data for {self.ticker} ({self.company_name})"]

        if self.market_data:
            md = self.market_data
            sections.append(f"\n## Market Data\n"
                          f"- Current Price: ${md.current_price:.2f}\n"
                          f"- Market Cap: ${md.market_cap:,.0f}\n"
                          f"- P/E Ratio: {md.pe_ratio}\n"
                          f"- Sector: {md.sector}\n"
                          f"- Industry: {md.industry}")

        if self.financials:
            fs = self.financials
            sections.append("\n## Financial Statements")
            if fs.income_statement:
                sections.append("\n### Income Statement")
                for key, val in fs.income_statement.items():
                    sections.append(f"- {key}: {val}")
            if fs.balance_sheet:
                sections.append("\n### Balance Sheet")
                for key, val in fs.balance_sheet.items():
                    sections.append(f"- {key}: {val}")
            if fs.cash_flow:
                sections.append("\n### Cash Flow")
                for key, val in fs.cash_flow.items():
                    sections.append(f"- {key}: {val}")
            if fs.quarterly_revenue:
                sections.append(f"\n### Quarterly Revenue (last {len(fs.quarterly_revenue)} quarters)")
                sections.append(f"- Values: {fs.quarterly_revenue}")

        if self.peers:
            sections.append(f"\n## Peer Comparison ({len(self.peers)} peers)")
            for p in self.peers:
                sections.append(f"- {p.ticker} ({p.name}): MCap=${p.market_cap:,.0f}, "
                              f"P/E={p.pe_ratio}, Margin={p.profit_margin}")

        if self.insider_activity:
            ia = self.insider_activity
            sections.append(f"\n## Insider Activity (source: {ia.source})\n"
                          f"- Net buys: {ia.net_buys}\n"
                          f"- Transactions: {len(ia.transactions)}")

        if self.institutional:
            inst = self.institutional
            sections.append(f"\n## Institutional Ownership\n"
                          f"- Ownership: {inst.institutional_ownership_pct}%\n"
                          f"- Top holders: {len(inst.holders)}")

        if self.macro:
            m = self.macro
            sections.append(f"\n## Macro Context (as of {m.as_of_date})\n"
                          f"- Fed Funds Rate: {m.fed_funds_rate}%\n"
                          f"- GDP Growth: {m.gdp_growth}%\n"
                          f"- Unemployment: {m.unemployment_rate}%\n"
                          f"- CPI YoY: {m.cpi_yoy}%\n"
                          f"- Yield Spread (10Y-2Y): {m.yield_spread}%")

        if self.filing_text:
            ft = self.filing_text
            if ft.mda_text:
                sections.append(f"\n## MD&A ({ft.filing_type}, {ft.filing_date})\n{ft.mda_text[:4000]}")
            if ft.risk_factors_text:
                sections.append(f"\n## Risk Factors\n{ft.risk_factors_text[:4000]}")

        sections.append(f"\n## Data Quality\n"
                       f"- Completeness Score: {self.data_completeness_score}/100\n"
                       f"- Company Predictability Score: {self.company_predictability_score}/100")

        if self.warnings:
            sections.append("\n## Warnings")
            for w in self.warnings:
                sections.append(f"- [{w.severity.upper()}] {w.source}: {w.message}")

        return "\n".join(sections)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "company_name": self.company_name,
            "financials": self.financials.to_dict() if self.financials else None,
            "market_data": self.market_data.to_dict() if self.market_data else None,
            "price_history": self.price_history,
            "insider_activity": self.insider_activity.to_dict() if self.insider_activity else None,
            "institutional": self.institutional.to_dict() if self.institutional else None,
            "macro": self.macro.to_dict() if self.macro else None,
            "filing_text": self.filing_text.to_dict() if self.filing_text else None,
            "peers": [p.to_dict() for p in self.peers] if self.peers else None,
            "company_predictability_score": self.company_predictability_score,
            "warnings": [w.to_dict() for w in self.warnings],
        }

    @classmethod
    def from_dict(cls, d: dict) -> DataPackage:
        return cls(
            ticker=d.get("ticker", ""),
            company_name=d.get("company_name", ""),
            financials=FinancialStatements.from_dict(d["financials"]) if d.get("financials") else None,
            market_data=MarketData.from_dict(d["market_data"]) if d.get("market_data") else None,
            price_history=d.get("price_history"),
            insider_activity=InsiderActivity.from_dict(d["insider_activity"]) if d.get("insider_activity") else None,
            institutional=InstitutionalData.from_dict(d["institutional"]) if d.get("institutional") else None,
            macro=MacroContext.from_dict(d["macro"]) if d.get("macro") else None,
            filing_text=FilingText.from_dict(d["filing_text"]) if d.get("filing_text") else None,
            peers=[PeerData.from_dict(p) for p in d["peers"]] if d.get("peers") else None,
            company_predictability_score=d.get("company_predictability_score", 50),
            warnings=[LimitationNote.from_dict(w) for w in d.get("warnings", [])],
        )


# --- Analysis Models ---


@dataclass
class FinancialRatio:
    """A single financial ratio with historical values and trend."""
    name: str = ""
    values: dict[str, float] = field(default_factory=dict)  # year -> value
    trend: str = ""  # "improving", "stable", "declining"
    assessment: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "values": self.values,
            "trend": self.trend,
            "assessment": self.assessment,
        }

    @classmethod
    def from_dict(cls, d: dict) -> FinancialRatio:
        return cls(
            name=d.get("name", ""),
            values=d.get("values", {}),
            trend=d.get("trend", ""),
            assessment=d.get("assessment", ""),
        )


@dataclass
class FinancialAnalysis:
    """Financial Analyst agent output."""
    company_type: CompanyType = CompanyType.GROWTH
    profitability: dict[str, Any] = field(default_factory=dict)
    growth: dict[str, Any] = field(default_factory=dict)
    balance_sheet_health: dict[str, Any] = field(default_factory=dict)
    cash_flow_quality: dict[str, Any] = field(default_factory=dict)
    ratios: list[FinancialRatio] = field(default_factory=list)
    peer_comparison: dict[str, Any] = field(default_factory=dict)
    trend_assessments: dict[str, str] = field(default_factory=dict)
    forward_outlook: dict[str, Any] = field(default_factory=dict)
    risk_factors: list[str] = field(default_factory=list)
    macro_impact: str = ""
    insider_interpretation: str = ""
    strengths: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    directional_lean: str = "NEUTRAL"  # BULLISH, NEUTRAL, BEARISH
    directional_rationale: str = ""
    # LLM-assessed confidence sub-scores
    earnings_quality: int = 50
    valuation_clarity: int = 50
    macro_conditions: int = 50
    chain_of_thought: str = ""

    def to_dict(self) -> dict:
        return {
            "company_type": self.company_type.value,
            "profitability": self.profitability,
            "growth": self.growth,
            "balance_sheet_health": self.balance_sheet_health,
            "cash_flow_quality": self.cash_flow_quality,
            "ratios": [r.to_dict() for r in self.ratios],
            "peer_comparison": self.peer_comparison,
            "trend_assessments": self.trend_assessments,
            "forward_outlook": self.forward_outlook,
            "risk_factors": self.risk_factors,
            "macro_impact": self.macro_impact,
            "insider_interpretation": self.insider_interpretation,
            "strengths": self.strengths,
            "concerns": self.concerns,
            "directional_lean": self.directional_lean,
            "directional_rationale": self.directional_rationale,
            "earnings_quality": self.earnings_quality,
            "valuation_clarity": self.valuation_clarity,
            "macro_conditions": self.macro_conditions,
            "chain_of_thought": self.chain_of_thought,
        }

    @classmethod
    def from_dict(cls, d: dict) -> FinancialAnalysis:
        return cls(
            company_type=CompanyType(d.get("company_type", "GROWTH")),
            profitability=d.get("profitability", {}),
            growth=d.get("growth", {}),
            balance_sheet_health=d.get("balance_sheet_health", {}),
            cash_flow_quality=d.get("cash_flow_quality", {}),
            ratios=[FinancialRatio.from_dict(r) for r in d.get("ratios", [])],
            peer_comparison=d.get("peer_comparison", {}),
            trend_assessments=d.get("trend_assessments", {}),
            forward_outlook=d.get("forward_outlook", {}),
            risk_factors=d.get("risk_factors", []),
            macro_impact=d.get("macro_impact", ""),
            insider_interpretation=d.get("insider_interpretation", ""),
            strengths=d.get("strengths", []),
            concerns=d.get("concerns", []),
            directional_lean=d.get("directional_lean", "NEUTRAL"),
            directional_rationale=d.get("directional_rationale", ""),
            earnings_quality=d.get("earnings_quality", 50),
            valuation_clarity=d.get("valuation_clarity", 50),
            macro_conditions=d.get("macro_conditions", 50),
            chain_of_thought=d.get("chain_of_thought", ""),
        )


@dataclass
class InvestmentCase:
    """A single investment scenario (bull/base/bear)."""
    scenario: str = ""  # "bull", "base", "bear"
    narrative: str = ""
    drivers: list[str] = field(default_factory=list)
    probability: float = 0.0

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "narrative": self.narrative,
            "drivers": self.drivers,
            "probability": self.probability,
        }

    @classmethod
    def from_dict(cls, d: dict) -> InvestmentCase:
        return cls(
            scenario=d.get("scenario", ""),
            narrative=d.get("narrative", ""),
            drivers=d.get("drivers", []),
            probability=d.get("probability", 0.0),
        )


# --- Confidence Models ---


@dataclass
class ConfidenceDriver:
    """Single scoring factor with its contribution to overall confidence."""
    factor: str
    score: int  # 0-100
    weight: float
    impact: str  # "positive", "negative", "neutral"
    detail: str

    def to_dict(self) -> dict:
        return {
            "factor": self.factor,
            "score": self.score,
            "weight": self.weight,
            "impact": self.impact,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ConfidenceDriver:
        return cls(
            factor=d["factor"],
            score=d["score"],
            weight=d["weight"],
            impact=d["impact"],
            detail=d["detail"],
        )


@dataclass
class ConfidenceScore:
    """Overall confidence with breakdown."""
    score: int  # 0-100 weighted average
    level: ConfidenceLevel  # >=70 High, 40-69 Medium, <40 Low
    summary: str
    drivers: list[ConfidenceDriver]

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "level": self.level.value,
            "summary": self.summary,
            "drivers": [d.to_dict() for d in self.drivers],
        }

    @classmethod
    def from_dict(cls, d: dict) -> ConfidenceScore:
        return cls(
            score=d["score"],
            level=ConfidenceLevel(d["level"]),
            summary=d["summary"],
            drivers=[ConfidenceDriver.from_dict(dr) for dr in d["drivers"]],
        )


# --- Thesis Models ---


@dataclass
class InvestmentThesis:
    """Thesis Builder agent output."""
    recommendation: Recommendation = Recommendation.HOLD
    executive_summary: str = ""
    bull_case: InvestmentCase | None = None
    base_case: InvestmentCase | None = None
    bear_case: InvestmentCase | None = None
    peer_comparison_narrative: str = ""
    forward_outlook: str = ""
    risks: list[str] = field(default_factory=list)
    catalysts: list[str] = field(default_factory=list)
    macro_context: str = ""
    insider_summary: str = ""
    confidence: ConfidenceScore | None = None
    revision_request: RevisionRequest | None = None

    def to_dict(self) -> dict:
        return {
            "recommendation": self.recommendation.value,
            "executive_summary": self.executive_summary,
            "bull_case": self.bull_case.to_dict() if self.bull_case else None,
            "base_case": self.base_case.to_dict() if self.base_case else None,
            "bear_case": self.bear_case.to_dict() if self.bear_case else None,
            "peer_comparison_narrative": self.peer_comparison_narrative,
            "forward_outlook": self.forward_outlook,
            "risks": self.risks,
            "catalysts": self.catalysts,
            "macro_context": self.macro_context,
            "insider_summary": self.insider_summary,
            "confidence": self.confidence.to_dict() if self.confidence else None,
            "revision_request": self.revision_request.to_dict() if self.revision_request else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> InvestmentThesis:
        return cls(
            recommendation=Recommendation(d.get("recommendation", "HOLD")),
            executive_summary=d.get("executive_summary", ""),
            bull_case=InvestmentCase.from_dict(d["bull_case"]) if d.get("bull_case") else None,
            base_case=InvestmentCase.from_dict(d["base_case"]) if d.get("base_case") else None,
            bear_case=InvestmentCase.from_dict(d["bear_case"]) if d.get("bear_case") else None,
            peer_comparison_narrative=d.get("peer_comparison_narrative", ""),
            forward_outlook=d.get("forward_outlook", ""),
            risks=d.get("risks", []),
            catalysts=d.get("catalysts", []),
            macro_context=d.get("macro_context", ""),
            insider_summary=d.get("insider_summary", ""),
            confidence=ConfidenceScore.from_dict(d["confidence"]) if d.get("confidence") else None,
            revision_request=RevisionRequest.from_dict(d["revision_request"]) if d.get("revision_request") else None,
        )


# --- Revision Models ---


@dataclass
class RevisionRequest:
    """Thesis Builder's request for Financial Analyst re-examination."""
    questions: list[str] = field(default_factory=list)
    factors_to_reexamine: list[str] = field(default_factory=list)
    context: str = ""

    def to_dict(self) -> dict:
        return {
            "questions": self.questions,
            "factors_to_reexamine": self.factors_to_reexamine,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, d: dict) -> RevisionRequest:
        return cls(
            questions=d.get("questions", []),
            factors_to_reexamine=d.get("factors_to_reexamine", []),
            context=d.get("context", ""),
        )


@dataclass
class RevisedAnalysis:
    """Financial Analyst's response to revision request."""
    revised_assessments: dict[str, str] = field(default_factory=dict)
    revised_subscores: dict[str, int] = field(default_factory=dict)
    revision_rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "revised_assessments": self.revised_assessments,
            "revised_subscores": self.revised_subscores,
            "revision_rationale": self.revision_rationale,
        }

    @classmethod
    def from_dict(cls, d: dict) -> RevisedAnalysis:
        return cls(
            revised_assessments=d.get("revised_assessments", {}),
            revised_subscores=d.get("revised_subscores", {}),
            revision_rationale=d.get("revision_rationale", ""),
        )
