"""FastAPI 应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tradingAgents.server.routers import account, analysis, stocks, trading
from tradingAgents.server.routers import market, screener, news_router, settings_router

app = FastAPI(title="TradingAgents API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account.router)
app.include_router(trading.router)
app.include_router(analysis.router)
app.include_router(stocks.router)
app.include_router(market.router)
app.include_router(screener.router)
app.include_router(news_router.router)
app.include_router(settings_router.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
