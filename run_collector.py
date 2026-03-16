"""Quick runner to test the Data Collector agent."""
import sys

from src.agents.data_collector import DataCollectorAgent

def main():
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"Collecting data for {ticker}...\n")

    agent = DataCollectorAgent()
    package = agent.run(ticker)

    # Show what Claude would actually receive
    print(package.to_prompt_text())

    # Meta info
    print(f"\n{'='*60}")
    print(f"Company Predictability Score: {package.company_predictability_score}")
    print(f"Data Completeness Score: {package.data_completeness_score}")

    if package.warnings:
        print(f"\nWarnings ({len(package.warnings)}):")
        for w in package.warnings:
            print(f"  - [{w.source}] {w.message}")


if __name__ == "__main__":
    main()
