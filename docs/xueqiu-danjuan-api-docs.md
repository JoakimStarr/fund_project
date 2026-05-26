# 雪球(雪球) & 蛋卷基金 API 接口文档

> 整理时间：2026-05-26
> 注：所有 API 请求均需携带 `User-Agent` 模拟浏览器访问（如 `Mozilla/5.0 ... Chrome/120.0.0.0 Safari/537.36`），部分接口需要先访问首页获取 cookie。

---

## 目录

1. [雪球 - 股票行情 API](#1-雪球---股票行情-api)
2. [雪球 - K 线图 API](#2-雪球---k-线图-api)
3. [雪球 - 分时图 API](#3-雪球---分时图-api)
4. [雪球 - 7×24 实时快讯 API](#4-雪球---7x24-实时快讯-api)
5. [雪球 - 搜索 API（热搜话题、内容搜索）](#5-雪球---搜索-api)
6. [雪球 - 盘口/逐笔成交 API](#6-雪球---盘口逐笔成交-api)
7. [雪球 - F10 财务数据 API](#7-雪球---f10-财务数据-api)
8. [雪球 - 龙虎榜 API](#8-雪球---龙虎榜-api)
9. [雪球 - 股票筛选器（板块资金流）API](#9-雪球---股票筛选器板块资金流-api)
10. [雪球 - 相关资讯/文章 API](#10-雪球---相关资讯文章-api)
11. [雪球 - 热门股票 API](#11-雪球---热门股票-api)
12. [蛋卷基金 - 基金 API](#12-蛋卷基金---基金-api)
    - 12.1 核心详情（fund）
    - 12.2 基金持仓股/行业（detail）
    - 12.3 基金绩效归因分析（achievement/analysis）
    - 12.4 同类排名走势（achievement/rank）
    - 12.5 其它 fundx 子接口（业绩走势、定投收益率、净值增长走势）
13. [蛋卷基金 - 需登录 API](#13-蛋卷基金---需登录-api)
    - 13.1 基金净值
    - 13.2 基金持仓
    - 13.3 基金费率
    - 13.4 其他需登录 API
14. [通用参数说明](#14-通用参数说明)

---

## 多标的批量查询规则

雪球多个 API 支持批量查询，**逗号分隔**多个 symbol：

```
symbol=SH000001,SZ399001,SZ399006,SH600519,SZ000858
```

### 标的代码格式

| 市场 | 格式 | 示例 |
|------|------|------|
| 上海 A 股 | `SH{6位代码}` | `SH600519`（贵州茅台）、`SH000001`（上证指数） |
| 深圳 A 股 | `SZ{6位代码}` | `SZ000858`（五粮液）、`SZ399001`（深证成指） |
| 港股 | `HK{5位代码}` | `HK00700`（腾讯控股） |
| 美股 | 直接使用代码 | `AAPL`、`TSLA`、`MSFT` |

---

## 1. 雪球 - 股票行情 API

### 1.1 单只股票行情

```
GET https://stock.xueqiu.com/v5/stock/quote.json?symbol={symbol}&extend=detail
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | string | 是 | 股票代码，如 `SH000001`、`SH600519` |
| `extend` | string | 否 | 默认 `detail`，获取详细数据 |

**响应结构：**

```json
{
  "data": {
    "market": {
      "status_id": 7,           // 市场状态ID
      "region": "CN",           // 地区
      "status": "已收盘",        // 市场状态
      "time_zone": "Asia/Shanghai",
      "delay_tag": 0,           // 0=实时 1=延迟
      "daylight_savings": true
    },
    "quote": {
      "symbol": "SH000001",       // 代码
      "name": "上证指数",         // 名称
      "code": "000001",
      "exchange": "SH",           // 交易所
      "type": 12,                 // 类型(11=股票,12=指数)
      "current": 4145.37,         // 当前价/最新点数
      "percent": -0.17,           // 涨跌幅(%)
      "chg": -7.2,                // 涨跌额
      "open": 4137.3196,          // 今开
      "high": 4150.2888,          // 最高
      "low": 4104.4593,           // 最低
      "last_close": 4152.5686,    // 昨收
      "avg_price": 4145.37,       // 均价
      "volume": 65477775600,      // 成交量
      "amount": 1461685377747.7,  // 成交额
      "volume_ratio": 1.03,       // 量比
      "turnover_rate": 1.42,      // 换手率(%)
      "amplitude": 1.1,           // 振幅(%)
      "high52w": 4258.86,         // 52周最高
      "low52w": 3332.49,          // 52周最低
      "current_year_percent": 4.45, // 今年以来涨跌幅(%)
      "float_shares": 4595397837119,  // 流通股本
      "total_shares": 16684814142,    // 总股本
      "float_market_capital": 25239885076364.88,  // 流通市值
      "market_capital": 69164728000000.0,          // 总市值
      "currency": "CNY",          // 币种
      "lot_size": 100,            // 每手股数
      "timestamp": 1779778800000, // 时间戳(ms)
      "time": 1779778800000,
      "status": 1,                // 状态(1=交易中)
      "rise_count": 522,          // 上涨家数(指数特有)
      "fall_count": 1182,         // 下跌家数(指数特有)
      "flat_count": 42,           // 平盘家数(指数特有)
      "issue_date": 661536000000, // 上市日期
      "tick_size": 0.01           // 最小变动单位
    },
    "tags": []
  },
  "error_code": 0,
  "error_description": ""
}
```

### 1.2 批量股票行情

```
GET https://stock.xueqiu.com/v5/stock/batch/quote.json?symbol={symbol1},{symbol2},...
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | string | 是 | 逗号分隔多个代码，如 `SH000001,SZ399001,SH600519` |

**响应结构：** 返回 `data.items[]` 数组，每项结构与 `quote.json` 一致。

### 1.3 实时报价（压缩格式）

```
GET https://stock.xueqiu.com/v5/stock/realtime/quotec.json?symbol={symbol1},{symbol2}
```

**参数：** 同上

**响应：** 返回精简字段数组。

```json
{
  "data": [
    {
      "symbol": "SH000001",
      "current": 4145.37,
      "percent": -0.17,
      "chg": -7.2,
      "timestamp": 1779778800000,
      "volume": 65477775600,
      "amount": 1461685377747.7,
      "market_capital": 69192923363973.78,
      "float_market_capital": 25239885076364.88,
      "turnover_rate": 1.42,
      "amplitude": 1.1,
      "open": 4137.32,
      "last_close": 4152.57,
      "high": 4150.29,
      "low": 4104.46,
      "avg_price": 4145.37,
      "current_year_percent": 4.45,
      "type": 12,
      "trade_volume": null,
      "side": null
    }
  ]
}
```

---

## 2. 雪球 - K 线图 API

```
GET https://stock.xueqiu.com/v5/stock/chart/kline.json?symbol={symbol}&begin={timestamp}&period=day&count={n}
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | string | 是 | 股票代码 |
| `begin` | number | 是 | 起始时间戳(毫秒) |
| `period` | string | 是 | 周期: `day`(日), `week`(周), `month`(月) |
| `count` | number | 否 | 条数，默认 30 |

**响应结构：**

```json
{
  "data": {
    "symbol": "SH000001",
    "column": ["timestamp", "volume", "open", "high", "low", "close", "chg", "percent", "turnoverrate", "amount", "volume_post", "amount_post"],
    "item": [
      [1779206400000, 62415203500, 4152.7, 4169.85, 4139.97, 4162.18, -7.36, -0.18, 1.35, 1358926939220.2, null, null]
    ]
  }
}
```

**column 映射表：**

| 索引 | 字段 | 说明 |
|------|------|------|
| 0 | `timestamp` | 时间戳(ms) |
| 1 | `volume` | 成交量 |
| 2 | `open` | 开盘价 |
| 3 | `high` | 最高价 |
| 4 | `low` | 最低价 |
| 5 | `close` | 收盘价 |
| 6 | `chg` | 涨跌额 |
| 7 | `percent` | 涨跌幅(%) |
| 8 | `turnoverrate` | 换手率 |
| 9 | `amount` | 成交额 |
| 10 | `volume_post` | 盘后成交量 |
| 11 | `amount_post` | 盘后成交额 |

---

## 3. 雪球 - 分时图 API

```
GET https://stock.xueqiu.com/v5/stock/chart/minute.json?symbol={symbol}
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | string | 是 | 股票代码 |

**响应结构：**

```json
{
  "data": {
    "after": [],
    "items": [],
    "items_size": 0
  }
}
```

> 盘中交易时段返回分时数据，非交易时段（如收盘后）返回空数组。

---

## 4. 雪球 - 7×24 实时快讯 API

```
GET https://xueqiu.com/statuses/livenews/list.json
GET https://xueqiu.com/statuses/livenews/list.json?max_id={max_id}&count=15
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `max_id` | number | 否 | 分页游标，上次返回的 `next_max_id` |
| `count` | number | 否 | 每页条数，默认 10 |

**响应结构：**

```json
{
  "next_max_id": 4670161,
  "items": [
    {
      "id": 4670197,
      "text": "【卢伟冰：小米不久前刚刚发布两款新车...】",
      "mark": 0,
      "target": "http://xueqiu.com/5124430882/391051304",
      "created_at": 1779792761000,
      "view_count": 0,
      "status_id": 391051304,
      "reply_count": 1,
      "share_count": 0,
      "sub_type": 0
    }
  ]
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `items[].id` | number | 快讯 ID |
| `items[].text` | string | 快讯正文 |
| `items[].mark` | number | 重要度标记（1=重要，0=普通） |
| `items[].target` | string | 跳转链接 |
| `items[].created_at` | number | 创建时间戳(ms) |
| `items[].status_id` | number | 对应帖子 ID |
| `items[].reply_count` | number | 回复数 |
| `items[].share_count` | number | 分享数 |

---

## 5. 雪球 - 搜索 API

### 5.1 热搜话题（热门事件标签）

```
GET https://xueqiu.com/query/v1/hot_event/tag.json
GET https://xueqiu.com/query/v1/hot_event/tag.json?count=5
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `count` | number | 否 | 返回条数，默认 10 |

**响应结构：**

```json
{
  "code": 200,
  "data": [
    {
      "content": "有色·铝概念午后活跃，中国铝业逼近涨停...",
      "id": 484002,
      "img_url": "https://xqimg.imedao.com/xxx.png",
      "percentage": 7.08,
      "reason": "热度值 71.6万",
      "statusCount": 50,
      "stocks": [
        {
          "code": "SH601600",
          "current": "12.09",
          "indId": 691954,
          "name": "中国铝业",
          "percentage": 10.01,
          "sort": 0,
          "type": 11
        }
      ],
      "title": "#有色铝概念活跃，中国铝业涨停#",
      "url": "https://xueqiu.com/hashtag/xxx"
    }
  ]
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `data[].title` | string | 话题标题（带 `#` 号） |
| `data[].content` | string | 话题描述 |
| `data[].reason` | string | 热度值文字，如"热度值 71.6万" |
| `data[].percentage` | number | 热度百分比 |
| `data[].statusCount` | number | 相关帖子数 |
| `data[].stocks[]` | array | 关联股票列表 |
| `data[].stocks[].name` | string | 股票名称 |
| `data[].stocks[].code` | string | 股票代码（如 `SH601600`） |
| `data[].stocks[].current` | string | 当前价 |
| `data[].stocks[].percentage` | number | 涨跌幅(%) |
| `data[].img_url` | string | 话题配图链接 |

> ✅ 此接口 **不需要登录**，直接返回热搜话题数据。

### 5.2 内容搜索（帖子/动态）

```
GET https://xueqiu.com/query/v1/search/status.json?q={keyword}&count=10
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `q` | string | 是 | 搜索关键词 |
| `count` | number | 否 | 返回条数 |

### 5.3 股票搜索

```
GET https://xueqiu.com/query/v1/search/stock.json?q={keyword}
```

> ⚠️ 需登录或额外参数

### 5.4 相关标的搜索

```
GET https://xueqiu.com/query/v1/symbol/search/status.json?symbol={symbol}
```

返回指定股票代码的相关动态。

---

## 6. 雪球 - 盘口/逐笔成交 API

### 6.1 盘口五档

```
GET https://stock.xueqiu.com/v5/stock/realtime/pankou.json?symbol={symbol}
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | string | 是 | 股票代码 |

**响应：** 返回买卖五档数据（盘中交易时段有值）。

### 6.2 逐笔成交

```
GET https://stock.xueqiu.com/v5/stock/history/trade.json?symbol={symbol}
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | string | 是 | 股票代码 |

**响应结构：**

```json
{
  "data": {
    "symbol": "SH600519",
    "items": [
      {
        "symbol": "SH600519",
        "timestamp": 1779778474320,
        "current": 1273.33,
        "chg": -12.55,
        "percent": -0.98,
        "trade_volume": 340,
        "side": 0,
        "level": 1,
        "trade_session": null,
        "trade_type": null,
        "trade_unique_id": "4511562"
      }
    ]
  }
}
```

---

## 7. 雪球 - F10 财务数据 API

### 7.1 十大股东

```
GET https://stock.xueqiu.com/v5/stock/f10/cn/top_holders.json?symbol={symbol}
```

**响应结构：**

```json
{
  "data": {
    "times": [
      {"name": "2026一季报", "value": 1774886400000},
      {"name": "2025年报", "value": 1767110400000}
    ],
    "total": {"chg": -1.88, "held_num": 858059278, "held_ratio": 68.5202},
    "items": [
      {
        "holder_name": "中国工商银行股份有限公司...",
        "held_num": 7377868,
        "held_ratio": 0.5892,
        "holder_rank": 9,
        "chg": -1.88,
        "chg_ratio": -0.83
      }
    ],
    "quit": [/* 退出的股东 */],
    "new": [/* 新进的股东 */]
  }
}
```

### 7.2 机构持仓详情

```
GET https://stock.xueqiu.com/v5/stock/f10/cn/org_holding/detail.json?symbol={symbol}
```

**示例响应：** 返回机构持仓列表，包含基金名称、持仓数量、占流通股比例等。

### 7.3 股本变动

```
GET https://stock.xueqiu.com/v5/stock/f10/cn/shareschg.json?symbol={symbol}
```

```json
{
  "data": {
    "restricts": [],
    "items": [
      {"float_shares": 1252270215, "chg_date": 1756656000000, "chg_reason": "注销回购股份", "total_shares": 1252270215}
    ]
  }
}
```

### 7.4 分红配股

```
GET https://stock.xueqiu.com/v5/stock/f10/cn/bonus.json?symbol={symbol}
```

```json
{
  "data": {
    "items": [
      {"dividend_year": "2025年报", "ashare_ex_dividend_date": null, "plan_explain": "10派279.930元(董事会预案)"}
    ],
    "allots": [],
    "addtions": []
  }
}
```

### 7.5 利润表

```
GET https://stock.xueqiu.com/v5/stock/finance/cn/income.json?symbol={symbol}&count=5&type=all
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | string | 是 | 股票代码 |
| `count` | number | 否 | 报告的期数，默认 5 |
| `type` | string | 否 | `all`（全部） |

```json
{
  "data": {
    "quote_name": "贵州茅台",
    "currency_name": "人民币",
    "currency": "CNY",
    "list": [
      {
        "report_date": 1774886400000,
        "report_name": "2026一季报",
        "net_profit": [27242512886.45, 0.01471],
        "net_profit_atsopc": [27242512886.45, 0.01471],
        "total_revenue": [54702912385.23, 0.06336],
        "op": [37537008686.42, 0.01351]
      }
    ]
  }
}
```

> 财务数据中的数组格式为 `[当前值, 同比变化]`。

### 7.6 资产负债表

```
GET https://stock.xueqiu.com/v5/stock/finance/cn/balance.json?symbol={symbol}&count=5&type=all
```

```json
{
  "data": {
    "list": [
      {
        "report_date": 1774886400000,
        "report_name": "2026一季报",
        "total_assets": [319918844905.58, 0.02417],
        "total_liab": [38782958469.89, -0.12213],
        "asset_liab_ratio": [0.12123, -0.14285]
      }
    ]
  }
}
```

### 7.7 现金流量表

```
GET https://stock.xueqiu.com/v5/stock/finance/cn/cash_flow.json?symbol={symbol}&count=5&type=all
```

### 7.8 财务指标

```
GET https://stock.xueqiu.com/v5/stock/finance/cn/indicator.json?symbol={symbol}&count=5
```

```json
{
  "data": {
    "list": [
      {
        "report_date": 1774886400000,
        "report_name": "2026一季报",
        "avg_roe": [10.57, -0.032],
        "np_per_share": [216.3223, 0.0518],
        "operate_cash_flow_ps": [21.4889, 2.064],
        "basic_eps": [21.76, 0.0178],
        "undistri_profit_ps": [175.0003, 0.0487],
        "gross_sell": [92.24, 0.00316],
        "net_interest_of_total_assets": [9.0272, -0.0066]
      }
    ]
  }
}
```

---

## 8. 雪球 - 龙虎榜 API

```
GET https://stock.xueqiu.com/v5/stock/capital/longhu.json?symbol={symbol}&count=5
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | string | 是 | 股票代码 |
| `count` | number | 否 | 返回条数 |

**响应结构：**

```json
{
  "data": {
    "items": [
      [
        {
          "seq": 20141147,
          "td_date": 1359302400000,
          "rank_type": 1,
          "info_type_name": "日跌幅偏离值达7%的证券",
          "trans_amt": 2857092951.0,
          "branches": [
            {
              "branch_id": "00218065",
              "branch_name": "海通证券杭州环城西路",
              "buy_amt": 73528206.54,
              "sell_amt": 0.0,
              "ratio": 2.57,
              "net_amt": 73528206.54,
              "branch_tag": null
            }
          ]
        }
      ]
    ]
  }
}
```

---

## 9. 雪球 - 股票筛选器（板块资金流）API

### 9.1 筛选股票列表

```
GET https://stock.xueqiu.com/v5/stock/screener/quote/list.json?market=CN&type=sh&order_by=percent&order=desc&count=5&page=1
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `market` | string | 是 | `CN`（A股）、`US`（美股）、`HK`（港股） |
| `type` | string | 是 | `sh`（沪市）、`sz`（深市）、`all`（全部） |
| `order_by` | string | 是 | 排序字段：`percent`(涨幅)、`change`(涨跌额)、`volume`(成交量)、`amount`(成交额)、`turnover_rate`(换手率) 等 |
| `order` | string | 否 | `desc`(降序) / `asc`(升序) |
| `count` | number | 否 | 每页条数 |
| `page` | number | 否 | 页码 |

**响应结构：**

```json
{
  "data": {
    "count": 5000,
    "list": [
      {
        "symbol": "SZ301591",
        "current": 58.68,
        "percent": 20.0,
        "chg": 9.78,
        "name": "股票名称",
        "type": 11,
        "amplitude": 19.14,
        "turnover_rate": 38.62,
        "volume": 13277048,
        "amount": 723019345.59,
        "volume_ratio": 4.24,
        "market_capital": 4936161600.0,
        "float_market_capital": 2017452141.0,
        "pb": 6.977,
        "pb_ttm": 5.367,
        "eps": 0.73,
        "roe_ttm": 6.74,
        "ps": 11.29,
        "pcf": 88.79,
        "dividend_yield": 0.324,
        "followers": 5280,
        "issue_date_ts": 1709049600000,
        "main_net_inflows": 68117134.0
      }
    ]
  }
}
```

### 9.2 行业列表

```
GET https://stock.xueqiu.com/v5/stock/screener/industries.json?category=CN
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `category` | string | 是 | `CN`（A股）、`US`（美股）、`HK`（港股） |

---

## 10. 雪球 - 相关资讯/文章 API

```
GET https://stock.xueqiu.com/v5/stock/article/relevant.json?symbols={symbol}&count=5
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbols` | string | 是 | 股票代码（**注意是 `symbols` 复数**） |
| `count` | number | 否 | 条数 |

**响应：** 返回相关标的的近期收盘价走势和资讯列表。

```
GET https://stock.xueqiu.com/v5/stock/bar/relation.json?symbol={symbol}
```

返回与该标的相关联的其他标的（板块联动等）。

---

## 11. 雪球 - 热门股票 API

```
GET https://stock.xueqiu.com/v5/stock/hot_stock/list.json?type={type}&count=10
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | number | 是 | 类型（`0`=涨幅榜, `1`=跌幅榜, `2`=成交量榜, `3`=换手率榜等，需实际测试确认） |
| `count` | number | 否 | 条数 |

---

## 12. 蛋卷基金 - 基金 API

> 基础域名：`https://danjuanfunds.com` | 以下所有接口 **无需登录**（除非特别标注）

### 12.1 基金核心信息

```
GET /djapi/fund/{fund_code}
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `fund_code` | path | 是 | 基金代码，如 `002771` |

**响应：** 返回基金名称、类型、成立日期、基金经理、基金公司、阶段涨幅、年度收益、排名、最新净值等。

```json
{
  "data": {
    "fd_code": "002771",
    "fd_name": "安信新回报混合C",
    "fd_full_name": "安信新回报灵活配置混合型证券投资基金",
    "found_date": "2016-05-09",
    "keeper_name": "安信基金管理有限责任公司",
    "manager_name": "陈鹏",
    "fund_derived": {
      "end_date": "2026-05-25",
      "unit_nav": "7.5501",
      "nav_grtd": "3.7287",
      "nav_grl1m": "25.9946",
      "nav_grl3m": "55.7203",
      "nav_grlty": "64.4651",
      "nav_grl1y": "222.1445",
      "annual_performance_list": [
        {"period": "成立以来", "nav": "689.91", "rank": "34/2140"},
        {"period": "今年以来", "nav": "64.47", "rank": "56/2140"}
      ]
    }
  },
  "result_code": 0
}
```

### 12.2 基金持仓（股票/债券/现金比例）

```
GET /djapi/fundx/base/fund/record/asset/percent?fund_code={fund_code}
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `fund_code` | query | 是 | 基金代码 |

**响应：**

```json
{
  "data": {
    "source": "2026-03-31",
    "stock_percent": 91.82,
    "cash_percent": 1.92,
    "bond_percent": 5.3,
    "other_percent": 2.94,
    "stock_list": [
      {
        "name": "新易盛",
        "code": "300502",
        "percent": 9.92,
        "current_price": 700,
        "change_percentage": 6.22,
        "xq_symbol": "SZ300502",
        "xq_url": "https://xueqiu.com/S/SZ300502",
        "change_of_pre_quarter": "0.26%",
        "industry_label": "通信"
      }
    ],
    "bond_list": []
  }
}
```

### 12.3 基金绩效归因分析

```
GET /djapi/fundx/base/fund/achievement/analysis?fund_code={fund_code}
```

逐年分析基金收益中市场贡献、择时贡献、选股贡献各占多少。

```json
{
  "data": {
    "fund_code": "002771",
    "annual_analysis_list": [
      {
        "period_time": "2025",
        "total_data": {"data": 111.44, "desc": "2025全年"},
        "market_data": {"data": 16.51, "desc": "市场贡献"},
        "time_data": {"data": 0.09, "desc": "择时贡献"},
        "stock_data": {"data": 94.83, "desc": "选股贡献"}
      }
    ]
  }
}
```

### 12.4 定投收益率

```
GET /djapi/fundx/autoinvest/quote/yield/list?fd_code={fund_code}
```

模拟定投收益率数据（不同持有期的定投收益）。

```json
{
  "data": {
    "duration": "3Y",
    "fd_code": "002771",
    "base_invest_amount": "100",
    "recent_yields": [
      {"duration": "近1年", "normal": "83.0300", "max_itg": "94.4900"},
      {"duration": "近2年", "normal": "167.1100", "max_itg": "244.8000"},
      {"duration": "近3年", "normal": "197.2200", "max_itg": "259.9000"},
      {"duration": "近5年", "normal": "184.8000", "max_itg": "222.8800"}
    ]
  }
}
```

### 12.5 净值增长走势

```
GET /djapi/fund/growth/{fund_code}?day={period}
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `fund_code` | path | 是 | 基金代码 |
| `day` | string | 是 | 周期：`ty`(今年以来)、`1m`(近1月)、`3m`(近3月)、`1y`(近1年)、`3y`(近3年) |

**响应：** 返回每日净值及累计涨跌幅走势。

```json
{
  "data": {
    "fund_nav_growth": [
      {
        "date": "2025-12-31",
        "nav": "4.5907",
        "percentage": "-2.2611",
        "value": "0.0",
        "than_value": "0.0",
        "performance_value": "0.0"
      },
      {
        "date": "2026-01-05",
        "nav": "4.6965",
        "percentage": "2.3047",
        "value": "0.023047",
        "than_value": "0.018966",
        "performance_value": "0.009328"
      }
    ],
    "growth_lines": [],   // 基准线数据
    "tip": "数据来源：...",
    "performance_remark": "业绩比较基准：50%*沪深300指数收益率+50%*中债总指数（全价）收益率"
  }
}
```

> 字段说明：`percentage`=当日涨跌幅(%)，`value`=累计收益率，`than_value`=相对基准累计超额收益，`performance_value`=相对业绩比较基准的超额收益

---

## 13. 蛋卷基金 - 需登录 API

以下接口需要携带登录后的 Cookie 才能访问，未登录返回 `300001`：

### 13.1 基金净值

```
GET https://danjuanfunds.com/djapi/fund/nav/{fund_code}
GET https://danjuanfunds.com/djapi/fund/nav/{fund_code}?page=1&size=20
```

### 13.2 基金持仓

```
GET https://danjuanfunds.com/djapi/fund/hold/{fund_code}
```

### 13.3 基金费率

```
GET https://danjuanfunds.com/djapi/fund/rate/{fund_code}
```

### 13.4 其他需登录 API

| API | 说明 |
|-----|------|
| `GET https://danjuanfunds.com/djapi/fund/industry/{code}` | 行业配置 |
| `GET https://danjuanfunds.com/djapi/fund/nav/latest/{code}` | 最新净值 |
| `GET https://danjuanfunds.com/djapi/fund/nav/growth/{code}` | 净值增长率 |

> ⚠️ 全部需要登录 Cookie，未登录返回 `{"result_code":300001,"message":"请重新登录"}`

---

## 14. 通用参数说明

### 请求头

大多数 API 需要以下请求头：

```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
Cookie: (从首页获取的 cookie)
```

### Cookie 获取方式

先访问首页获取 cookie，再请求 API：

```bash
# 雪球
curl -s -c cookies.txt "https://xueqiu.com/" -A "Mozilla/5.0" -L > /dev/null
curl -s -b cookies.txt "https://stock.xueqiu.com/v5/stock/quote.json?symbol=SH000001" -A "Mozilla/5.0"

# 蛋卷基金
curl -s -c dj_cookies.txt "https://danjuanfunds.com/funding/002771" -A "Mozilla/5.0" -L > /dev/null
curl -s -b dj_cookies.txt "https://danjuanfunds.com/djapi/fund/002771" -A "Mozilla/5.0"
```

### 错误码说明

| 错误码 | 说明 |
|--------|------|
| `0` | 成功 |
| `10022` | 用户未登录（需携带有效 Cookie） |
| `10027` | 无权限或参数错误 |
| `100002` | 缺少必需参数 |
| `300001` | 登录过期/需重新登录（蛋卷基金） |

---

### 补充说明

1. **热搜话题**：`/query/v1/hot_event/tag.json` 无需登录即可获取实时热搜话题，每条包含话题标题、热度值、关联股票列表。配合 7×24 快讯 API（`/statuses/livenews/list.json`）可覆盖雪球实时内容。

2. **蛋卷基金的净值/持仓/费率** 等接口（`/djapi/fund/nav/{code}`、`/djapi/fund/hold/{code}`、`/djapi/fund/rate/{code}`）需要登录后方可访问，未登录返回 `300001`。但以下接口**无需登录**即可访问：
   - `GET /djapi/fund/{code}` — 基金核心详情（净值、阶段涨幅、排名、年度收益）
   - `GET /djapi/fund/detail/{code}` — 基金持仓股、行业配置、费率、基金经理
   - `GET /djapi/fundx/base/fund/achievement/analysis?fund_code={code}` — 绩效归因分析（市场/择时/选股贡献）
   - `GET /djapi/fundx/base/fund/achievement/rank?fund_code={code}` — 同类排名走势

3. **时间戳** 均为毫秒级 Unix 时间戳，需除以 1000 转换为秒。

4. **财务数据数组格式**：财务接口中数值字段多为 `[currentValue, yoyChange]`（当前值，同比变化）。
