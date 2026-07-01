# Stock MCP Server

面向中国市场的 Stock MCP Server，提供：

- A 股、北交所、ETF 最新行情
- 历史 K 线查询
- MA / RSI / ATR / MACD 指标计算
- 简化版 Wyckoff 结构分析
- 基于 watchlist / positions 的每日交易计划
- AKShare 失败时的本地 CSV 历史数据回退

## 功能说明

### MCP Tools

- `get_quotes(codes)`
- `get_kline(code, start_date, end_date, adjust="qfq")`
- `get_indicators(code, period="daily", lookback=120)`
- `analyze_wyckoff(code, lookback=120)`
- `generate_daily_plan(use_watchlist=True, use_positions=True)`

### 数据源策略

- 实时行情：优先 AKShare
- 历史 K 线：优先 AKShare，失败时回退本地 CSV
- 财务数据：本地 CSV
- 数据源失败时显式返回 `error`，不输出虚假行情

## 配置

复制 `.env.example` 为 `.env`，或直接设置环境变量：

- `STOCK_HISTORY_DATA_DIR`: 历史行情 CSV 根目录
- `STOCK_FIN_DATA_DIR`: 财务 CSV 根目录
- `STOCK_CONFIG_DIR`: 配置目录，默认 `config`
- `STOCK_ENV`: 当前环境标识，默认 `dev`

默认兼容的目录结构：

```text
/Users/why/data/stock-history-all-2026-05-27/
  sz002435.csv
  sh600519.csv
```

```text
/Users/why/data/stock-fin-data-xbx-2025-12-24/
  sz002790/
    sz002790_一般企业.csv
  sh600901/
    sh600901_商业银行.csv
```

项目内示例配置：

- [watchlist.yaml](/Users/why/Documents/Stock-MCP-Server/config/watchlist.yaml)
- [positions.yaml](/Users/why/Documents/Stock-MCP-Server/config/positions.yaml)
- [codex.mcp.toml.example](/Users/why/Documents/Stock-MCP-Server/config/codex.mcp.toml.example)

## 安装与启动

Python 版本要求：`3.11+`

### 本地开发

```bash
cd /Users/why/Documents/Stock-MCP-Server
uv sync
source .venv/bin/activate
pytest -q
python -m stock_mcp.server
```

如果不使用 `uv`：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pytest -q
python -m stock_mcp.server
```

以 HTTP 方式本地启动：

```bash
python -m stock_mcp.server --transport streamable-http --mount-path /mcp
```

### Codex MCP 配置示例

```toml
[mcp_servers.stock_mcp]
command = "/absolute/path/to/Stock-MCP-Server/.venv/bin/python"
args = ["-m", "stock_mcp.server"]
env = { PYTHONPATH = "/absolute/path/to/Stock-MCP-Server/src" }
```

## 工具调用示例

```text
get_quotes(["000338", "002594", "513120"])
get_kline("000338", "20240101", "20260701")
get_indicators("000338")
analyze_wyckoff("000338")
generate_daily_plan()
```

## 验证

最小验收命令：

```bash
pytest -q
```

手工验收：

```bash
python -m stock_mcp.server
```

然后通过 MCP Inspector 或 Codex 调用上面的五个工具。

如果要用 HTTP Inspector 验证，可启动：

```bash
python -m stock_mcp.server --transport streamable-http --mount-path /mcp
```
