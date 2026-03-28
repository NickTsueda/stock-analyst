"""Experiment report generator — performance analysis vs SPY benchmark.

Usage: python -m src.experiment.report
"""
from __future__ import annotations

import sys

from src.experiment.db import DEFAULT_DB_PATH, get_all_analyses, get_snapshots


def _compute_return(start_price: float, end_price: float) -> float:
    """Compute percentage return."""
    if start_price == 0:
        return 0.0
    return ((end_price - start_price) / start_price) * 100


def generate_report(db_path: str = DEFAULT_DB_PATH) -> str:
    """Generate a performance report comparing recommendation buckets vs SPY.

    Returns the report as a formatted string.
    """
    analyses = get_all_analyses(db_path)
    all_snapshots = get_snapshots(db_path)

    if not analyses:
        return "No analysis data found. Run batch_runner first."

    lines = []
    lines.append("=" * 60)
    lines.append("VALIDATION EXPERIMENT — PERFORMANCE REPORT")
    lines.append("=" * 60)
    lines.append(f"Total stocks analyzed: {len(analyses)}")

    buckets: dict[str, list[dict]] = {}
    for a in analyses:
        rec = a["recommendation"]
        buckets.setdefault(rec, []).append(a)

    lines.append(f"Buckets: {', '.join(f'{k}={len(v)}' for k, v in sorted(buckets.items()))}")
    lines.append("")

    snap_lookup: dict[str, dict[int, dict]] = {}
    for s in all_snapshots:
        snap_lookup.setdefault(s["ticker"], {})[s["quarter"]] = s

    if not all_snapshots:
        lines.append("No snapshot data yet — report will populate after first quarterly snapshot.")
        return "\n".join(lines)

    all_quarters = {s["quarter"] for s in all_snapshots}
    latest_q = max(all_quarters)

    lines.append(f"Latest snapshot: Q{latest_q}")
    lines.append("")

    lines.append("-" * 60)
    lines.append("BUCKET PERFORMANCE (latest quarter)")
    lines.append("-" * 60)

    bucket_returns: dict[str, list[float]] = {}
    spy_returns: list[float] = []

    for rec, stocks in sorted(buckets.items()):
        returns = []
        for a in stocks:
            ticker = a["ticker"]
            if ticker not in snap_lookup or latest_q not in snap_lookup[ticker]:
                continue
            snap = snap_lookup[ticker][latest_q]
            stock_ret = _compute_return(a["price_at_analysis"], snap["price"])
            spy_ret = _compute_return(a["spy_price_at_analysis"], snap["spy_price"])
            returns.append(stock_ret)
            spy_returns.append(spy_ret)

        bucket_returns[rec] = returns
        if returns:
            avg = sum(returns) / len(returns)
            lines.append(f"  {rec:6s}: avg return = {avg:+.2f}% ({len(returns)} stocks)")
        else:
            lines.append(f"  {rec:6s}: no snapshot data")

    if spy_returns:
        spy_avg = sum(spy_returns) / len(spy_returns)
        lines.append(f"  {'SPY':6s}: avg return = {spy_avg:+.2f}% (benchmark)")

    lines.append("")
    lines.append("-" * 60)
    lines.append("WIN RATES (stock return > SPY return)")
    lines.append("-" * 60)

    for rec, stocks in sorted(buckets.items()):
        wins = 0
        total = 0
        for a in stocks:
            ticker = a["ticker"]
            if ticker not in snap_lookup or latest_q not in snap_lookup[ticker]:
                continue
            snap = snap_lookup[ticker][latest_q]
            stock_ret = _compute_return(a["price_at_analysis"], snap["price"])
            spy_ret = _compute_return(a["spy_price_at_analysis"], snap["spy_price"])
            total += 1
            if stock_ret > spy_ret:
                wins += 1
        if total > 0:
            lines.append(f"  {rec:6s}: {wins}/{total} ({wins/total*100:.0f}%) beat SPY")

    lines.append("")
    lines.append("-" * 60)
    lines.append("CONFIDENCE VALIDATION")
    lines.append("-" * 60)

    buy_stocks = buckets.get("BUY", [])
    if buy_stocks:
        high_conf = [a for a in buy_stocks if a["confidence_score"] >= 70]
        low_conf = [a for a in buy_stocks if a["confidence_score"] < 70]

        for label, group in [("High-confidence BUYs (>=70)", high_conf),
                             ("Low-confidence BUYs (<70)", low_conf)]:
            returns = []
            for a in group:
                ticker = a["ticker"]
                if ticker not in snap_lookup or latest_q not in snap_lookup[ticker]:
                    continue
                snap = snap_lookup[ticker][latest_q]
                returns.append(_compute_return(a["price_at_analysis"], snap["price"]))
            if returns:
                avg = sum(returns) / len(returns)
                lines.append(f"  {label}: avg return = {avg:+.2f}% ({len(returns)} stocks)")
            else:
                lines.append(f"  {label}: no data")

    lines.append("")
    lines.append("-" * 60)
    lines.append("INDIVIDUAL STOCKS")
    lines.append("-" * 60)
    lines.append(f"  {'Ticker':<8s} {'Rec':<6s} {'Conf':>4s} {'Return':>10s} {'vs SPY':>10s}")

    for a in sorted(analyses, key=lambda x: x["recommendation"]):
        ticker = a["ticker"]
        if ticker in snap_lookup and latest_q in snap_lookup[ticker]:
            snap = snap_lookup[ticker][latest_q]
            ret = _compute_return(a["price_at_analysis"], snap["price"])
            spy_ret = _compute_return(a["spy_price_at_analysis"], snap["spy_price"])
            alpha = ret - spy_ret
            lines.append(
                f"  {ticker:<8s} {a['recommendation']:<6s} {a['confidence_score']:>4d} "
                f"{ret:>+9.2f}% {alpha:>+9.2f}%"
            )
        else:
            lines.append(
                f"  {ticker:<8s} {a['recommendation']:<6s} {a['confidence_score']:>4d} "
                f"{'--':>10s} {'--':>10s}"
            )

    lines.append("")
    lines.append("This is AI-generated analysis for educational purposes only. Not financial advice.")
    return "\n".join(lines)


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_PATH
    print(generate_report(db))
