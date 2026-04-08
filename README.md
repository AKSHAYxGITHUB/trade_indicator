# NSE/BSE Stock Indicator Telegram Bot

## 1. Project Overview
A production-ready Telegram bot for Indian market symbols (NSE/BSE) that computes multi-indicator technical analysis and returns BUY/HOLD/EXIT signals with risk-managed trade levels.

## 2. Features
- NSE (`.NS`) and BSE (`.BO`) symbol handling
- Full indicator stack: RSI, MACD, EMA, SMA, Bollinger Bands, ADX, VWAP, ATR, StochRSI, candlestick patterns
- AI-style score-based signal engine
- Watchlist with scheduled alerts
- Global market snapshot
- Stock news with NewsAPI + Google News RSS fallback
- Deployment-ready for Railway, Render, and VPS

## 3. Tech Stack
- Python 3.11
- python-telegram-bot v20.7
- yfinance, pandas, pandas-ta
- APScheduler
- python-dotenv
- NewsAPI + requests

## 4. Step-by-step Setup
```bash
cd nse_bse_stock_bot
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env 2>/dev/null || true
```
Create `.env` with:
```env
TELEGRAM_TOKEN=your_telegram_bot_token_here
NEWS_API_KEY=your_newsapi_org_key_here
ALLOWED_USERS=123456789,987654321
DEFAULT_EXCHANGE=NSE
MAX_HISTORY_PERIOD=6mo
DEFAULT_INTERVAL=1d
ALERT_CHECK_INTERVAL_MINUTES=30
```

## 5. BotFather Steps
1. Open Telegram and search **@BotFather**.
2. Run `/newbot` and follow prompts.
3. Copy the bot token.
4. Put token into `.env` as `TELEGRAM_TOKEN`.

## 6. Get NewsAPI Key
1. Go to https://newsapi.org
2. Create account and verify email.
3. Copy API key and set `NEWS_API_KEY` in `.env`.

## 7. Run Locally
```bash
cd nse_bse_stock_bot
source venv/bin/activate
python bot.py
```

## 8. Deploy on Railway (with screenshot descriptions)
1. Push repo to GitHub.
2. Create a Railway project and link the repo.
3. Set environment variables from `.env`.
4. Railway will detect `Procfile` and run: `worker: python bot.py`.
5. Screenshot description: **Variables tab with TELEGRAM_TOKEN, NEWS_API_KEY present**.
6. Screenshot description: **Deployments tab showing successful worker deployment**.

## 9. Deploy on Render
1. Create new **Background Worker** on Render.
2. Connect GitHub repository.
3. Build command: `pip install -r requirements.txt`.
4. Start command: `python bot.py`.
5. Add environment variables in Render dashboard.

## 10. Deploy on VPS with systemd
```bash
sudo tee /etc/systemd/system/nse-bse-bot.service > /dev/null << 'EOF'
[Unit]
Description=NSE BSE Stock Telegram Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/nse_bse_stock_bot
Environment="PATH=/opt/nse_bse_stock_bot/venv/bin"
ExecStart=/opt/nse_bse_stock_bot/venv/bin/python /opt/nse_bse_stock_bot/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable nse-bse-bot
sudo systemctl start nse-bse-bot
sudo systemctl status nse-bse-bot
```

## 11. Commands Reference
| Command | Description |
|---|---|
| `/start` | Start bot and show keyboard |
| `/help` | Full help |
| `/analyze SYMBOL` | Full analysis |
| `/price SYMBOL` | Quick quote |
| `/nifty` `/sensex` `/banknifty` | Index snapshot |
| `/global` | Global market view |
| `/news SYMBOL` | Top 5 headlines |
| `/watch SYMBOL` | Add to watchlist |
| `/unwatch SYMBOL` | Remove from watchlist |
| `/watchlist` | Show watchlist |
| `/screener` | NIFTY top-20 screener |
| `/compare A B` | Side-by-side signal view |
| `/market` | Market status and next session |

## 12. Indicator Explanation
| Indicator | Interpretation |
|---|---|
| RSI | Momentum / overbought-oversold |
| MACD | Trend + crossover momentum |
| Bollinger Bands | Volatility + mean-reversion zones |
| EMA/SMA | Trend direction and dynamic support/resistance |
| ADX + DI | Trend strength and directional bias |
| VWAP | Intraday fair value |
| ATR | Volatility for stop/target sizing |
| StochRSI | Fast momentum extremes |
| Candlestick patterns | Short-term reversal clues |

## 13. Disclaimer
This bot is for educational and informational use only. It is not SEBI-registered investment advice. Always do your own research and consult a licensed advisor before investing.
