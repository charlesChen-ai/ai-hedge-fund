# AI Hedge Fund

This is a proof of concept for an AI-powered hedge fund. The goal of this project is to explore the use of AI to make trading decisions. This project is for **educational** purposes only and is not intended for real trading or investment.

## Supported Markets

| Market | Ticker Format | Data Provider | Trading Rules |
|--------|-------------|---------------|---------------|
| US Equities | `AAPL`, `MSFT`, `NVDA` | Financial Datasets API | No restrictions |
| China A-share | `600519.SH`, `000858.SZ`, `300750.SZ` | AkShare | Long-only, T+1, 10% price limit, 100-share board lots |

The system auto-detects market type from ticker format and routes to the appropriate data provider.

## How It Works

This system employs several agents working together:

1. Aswath Damodaran Agent - The Dean of Valuation, focuses on story, numbers, and disciplined valuation
2. Ben Graham Agent - The godfather of value investing, only buys hidden gems with a margin of safety
3. Bill Ackman Agent - An activist investor, takes bold positions and pushes for change
4. Cathie Wood Agent - The queen of growth investing, believes in the power of innovation and disruption
5. Charlie Munger Agent - Warren Buffett's partner, only buys wonderful businesses at fair prices
6. Michael Burry Agent - The Big Short contrarian who hunts for deep value
7. Mohnish Pabrai Agent - The Dhandho investor, who looks for doubles at low risk
8. Nassim Taleb Agent - The Black Swan risk analyst, focuses on tail risk, antifragility, and asymmetric payoffs
9. Peter Lynch Agent - Practical investor who seeks "ten-baggers" in everyday businesses
10. Phil Fisher Agent - Meticulous growth investor who uses deep "scuttlebutt" research
11. Rakesh Jhunjhunwala Agent - The Big Bull of India
12. Stanley Druckenmiller Agent - Macro legend who hunts for asymmetric opportunities with growth potential
13. Warren Buffett Agent - The oracle of Omaha, seeks wonderful companies at a fair price
14. Valuation Agent - Calculates the intrinsic value of a stock and generates trading signals
15. Sentiment Agent - Analyzes market sentiment and generates trading signals
16. Fundamentals Agent - Analyzes fundamental data and generates trading signals
17. Technicals Agent - Analyzes technical indicators and generates trading signals
18. Risk Manager - Calculates risk metrics and sets position limits
19. Portfolio Manager - Makes final trading decisions and generates orders

For China A-share analysis, agent prompts are augmented with market-specific context (CNY currency, regulatory/policy risk, state ownership considerations, 涨跌停 price-limit regime, retail-driven liquidity patterns).

<img width="1042" alt="Screenshot 2025-03-22 at 6 19 07 PM" src="https://github.com/user-attachments/assets/cbae3dcf-b571-490d-b0ad-3f0f035ac0d4" />

Note: the system does not actually make any trades.

[![Twitter Follow](https://img.shields.io/twitter/follow/virattt?style=social)](https://twitter.com/virattt)

## Disclaimer

This project is for **educational and research purposes only**

- Not intended for real trading or investment
- No investment advice or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions
- Past performance does not indicate future results
- China A-share market carries additional risks including T+1 settlement, price limit circuits, state/policy intervention, and limited short-selling access

By using this software, you agree to use it solely for learning purposes.

## Table of Contents

- [How to Install](#how-to-install)
- [How to Run](#how-to-run)
  - [Command Line Interface](#command-line-interface)
  - [Web Application](#web-application)
- [A-share Specific Notes](#a-share-specific-notes)
- [How to Contribute](#how-to-contribute)
- [Feature Requests](#feature-requests)
- [License](#license)

## How to Install

Before you can run the AI Hedge Fund, you'll need to install it and set up your API keys. These steps are common to both the full-stack web application and command line interface.

### 1. Clone the Repository

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

### 2. Set up API keys

Create a `.env` file for your API keys:

```bash
# Create .env file for your API keys (in the root directory)
cp .env.example .env
```

Open and edit the `.env` file to add your API keys:

```bash
# For running LLMs (required)
OPENAI_API_KEY=your-openai-key

# For US equity data (required for US tickers)
FINANCIAL_DATASETS_API_KEY=your-financialdatasets-key
```

#### Data Provider Configuration

By default (`DATA_PROVIDER=auto`), the system auto-detects market type from ticker format:

| Ticker Pattern | Market | Data Provider |
|---------------|--------|---------------|
| `AAPL`, `MSFT` (US format) | US | Financial Datasets API |
| `600519.SH`, `000858.SZ`, `300750.SZ` | China A-share | AkShare (free, no key required) |

Override manually:

```bash
# Force use of a specific provider regardless of ticker
DATA_PROVIDER=financialdatasets   # all tickers go to FD API
DATA_PROVIDER=akshare            # all tickers go to AkShare (US data may be unavailable)
DATA_PROVIDER=auto               # auto-detect from ticker format (default)
```

#### A-share Configuration (optional)

```bash
# Price adjustment for A-share historical data (default: qfq = forward-adjusted)
A_SHARE_PRICE_ADJUST=qfq        # qfq (前复权) or hfq (后复权) or None

# Benchmark used in A-share backtests (default: 000300.SH = CSI 300)
A_SHARE_BENCHMARK=000300.SH
```

**Important**: You must set at least one LLM API key (e.g. `OPENAI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, or `DEEPSEEK_API_KEY`) for the hedge fund to work.

## How to Run

### Command Line Interface

You can run the AI Hedge Fund directly via terminal. This approach offers more granular control and is useful for automation, scripting, and integration purposes.

<img width="992" alt="Screenshot 2025-01-06 at 5 50 17 PM" src="https://github.com/user-attachments/assets/e8ca04bf-9989-4a7d-a8b4-34e04666663b" />

#### Quick Start

1. Install Poetry (if not already installed):

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Install dependencies:

```bash
poetry install
```

#### Run with US Equities

```bash
poetry run python src/main.py --tickers AAPL,MSFT,NVDA
```

#### Run with China A-shares

```bash
poetry run python src/main.py --tickers 600519.SH,000858.SZ,300750.SZ
```

A-share tickers use exchange suffixes: `.SH` (Shanghai), `.SZ` (Shenzhen), `.BJ` (Beijing).

You can also specify a `--ollama` flag to run the AI hedge fund using local LLMs.

```bash
poetry run python src/main.py --tickers AAPL,MSFT,NVDA --ollama
```

You can optionally specify the start and end dates to make decisions over a specific time period.

```bash
poetry run python src/main.py --tickers AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01
```

#### Run the Backtester

```bash
# US equities
poetry run python src/backtester.py --tickers AAPL,MSFT,NVDA

# China A-shares
poetry run python src/backtester.py --tickers 600519.SH,000858.SZ --start-date 2024-01-01 --end-date 2024-12-31
```

**Example Output:**
<img width="941" alt="Screenshot 2025-01-06 at 5 47 52 PM" src="https://github.com/user-attachments/assets/00e794ea-8628-44e6-9a84-8f8a31ad3b47" />

Note: The `--ollama`, `--start-date`, and `--end-date` flags work for the backtester, as well!

### Web Application

The new way to run the AI Hedge Fund is through our web application that provides a user-friendly interface. This is recommended for users who prefer visual interfaces over command line tools.

Please see detailed instructions on how to install and run the web application [here](https://github.com/virattt/ai-hedge-fund/tree/main/app).

<img width="1721" alt="Screenshot 2025-06-28 at 6 41 03 PM" src="https://github.com/user-attachments/assets/b95ab696-c9f4-416c-9ad1-51feb1f537b" />

## A-share Specific Notes

### Trading Rules Enforced in Backtesting

| Rule | Detail |
|------|--------|
| Board lot | Buy quantities round down to nearest 100 shares |
| Long-only | Short selling (open/cover) is disabled |
| T+1 awareness | Selling limitations not modeled in simulation layer (future work) |
| Price limits | 涨跌停 circuit breaker respected by data layer |

### Ticker Format Reference

```
Shanghai (SSE):    600519.SH    (index: 000300.SH, 000016.SH)
Shenzhen (SZSE):   000858.SZ    (index: 399001.SZ)
Beijing (BSE):    430047.BJ
```

If exchange suffix is omitted, the system infers: 6-digit codes starting with 6/9/5/4/3/2/8/0 go to Shanghai or Shenzhen based on prefix rules; 4/8/9 prefixed codes go to Beijing.

### Data Notes

- AkShare provides free China market data. No API key needed.
- All A-share financial data is in CNY.
- Price adjustment (`qfq`/forward-adjusted) is applied by default for historical data, matching Chinese market convention.
- Insider trading data is not available for A-shares via AkShare (returns empty).

## How to Contribute

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

**Important**: Please keep your pull requests small and focused. This will make it easier to review and merge.

## Feature Requests

If you have a feature request, please open an [issue](https://github.com/virattt/ai-hedge-fund/issues) and make sure it is tagged with `enhancement`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
