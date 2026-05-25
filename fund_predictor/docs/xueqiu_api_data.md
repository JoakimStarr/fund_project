# 雪球网 API 接口文档

**测试日期**: 2026-05-25  
**测试状态**: ✅ 已验证可用  
**Cookie 状态**: 有效（需定期更新）

---

## 📌 API 总览

| 分类 | API | URL | 状态 | 认证 |
|------|-----|-----|------|------|
| **基金数据** | 历史净值 | `/djapi/fund/nav/history/{code}` | ✅ 可用 | 无需 |
| **基金数据** | 基础信息 | `/djapi/fundx/autoinvest/quote/fund/info` | ✅ 可用 | 无需 |
| **基金数据** | 业绩曲线 | `/djapi/fund/growth/{code}` | ✅ 可用 | 无需 |
| **基金数据** | 风险收益分析 | `/djapi/fund/base/quote/data/index/analysis/{code}` | ✅ 可用 | 无需 |
| **基金数据** | 年度/阶段业绩 | `/djapi/fundx/base/fund/achievement/{code}` | ✅ 可用 | 无需 |
| **基金数据** | 选股行业贡献 | `/djapi/fundx/base/fund/achievement/analysis/stock` | ✅ 可用 | 无需 |
| **基金数据** | 基金经理 | `/djapi/fundx/base/fund/record/manager/list` | ✅ 可用 | 无需 |
| **基金数据** | 盈利概率 | `/djapi/fundx/base/fund/profit/ratio/{code}` | ✅ 可用 | 无需 |
| **基金数据** | 交易日期 | `/djapi/fund/order/v2/trade_date` | ✅ 可用 | 无需 |
| **股票/指数** | 实时行情 | `/v5/stock/quote.json?symbol={symbol}&extend=detail` | ✅ **已验证** | ⚠️ **需要Cookie** |
| **股票/指数** | 分时数据 | `/v5/stock/chart/minute.json?symbol={symbol}&period=1d` | ✅ **已验证** | ⚠️ **需要Cookie** |
| **股票/指数** | K线数据 | `/v5/stock/chart/kline.json?symbol={symbol}&begin={ts}&...` | ✅ **已验证** | ⚠️ **需要Cookie** |

---

## 🔐 Cookie 配置说明

### 获取方式
1. 浏览器打开 https://xueqiu.com 并登录账号
2. 按 `F12` 打开开发者工具 → `Application` → `Cookies`
3. 复制以下字段值：
   - `xq_a_token`
   - `xqat`

### 当前有效 Cookie（2026-05-25）
```
xq_a_token=20458f74230aee45906ecb90d8c70ff43daa3837
xqat=20458f74230aee45906ecb90d8c70ff43daa3837
```

### 配置位置
```yaml
# config.yaml (或环境变量)
data:
  xueqiu:
    cookie: "xq_a_token=xxx; xqat=xxx"
    base_url: "https://stock.xueqiu.com"
```

### 注意事项
- Cookie 有效期约 **30天**
- 过期后需要重新获取
- 建议配置自动刷新机制或监控告警

---

## 📊 一、基金数据API（danjuanfunds.com）

> **无需认证**，可直接访问

### 1.1 历史净值

**接口**: `GET /djapi/fund/nav/history/{fund_code}?page={page}&size={size}`

**请求参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| fund_code | string | ✅ | - | 基金代码（6位数字） |
| page | int | ❌ | 1 | 页码 |
| size | int | ❌ | 20 | 每页条数 |

**返回结构**:
```json
{
  "data": {
    "items": [
      {
        "date": "2026-05-25",        // 交易日期 (YYYY-MM-DD)
        "nav": "7.5501",           // 单位净值 (string)
        "percentage": null,         // 日涨跌幅% (string, 当日可能为空)
        "value": "7.5501"           // 累计净值 (string)
      },
      {
        "date": "2026-05-22",
        "nav": "7.2787",
        "percentage": "5.37",     // 日涨跌幅%
        "value": "7.2787"
      }
    ],
    "current_page": 1,
    "size": 5,
    "total_items": 2441,
    "total_pages": 489
  },
  "result_code": 0
}
```

**字段映射**:
| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| date | string | 交易日期 | `"2026-05-22"` |
| nav | string | 单位净值 | `"7.2787"` |
| percentage | string | 日涨跌幅% | `"5.37"` 或 `null` |
| value | string | 累计净值 | `"7.2787"` |

**分页说明**:
- 默认每页返回20条记录
- 通过循环请求所有页面可获取完整历史数据
- 示例：2441条记录 / 20 = 123页

---

### 1.2 基金基础信息

**接口**: `GET /djapi/fundx/autoinvest/quote/fund/info?fd_codes={fund_code}`

**返回结构**:
```json
{
  "data": [{
    "fd_code": "002771",                    // 基金代码
    "fd_type": "3",                         // 类型编号
    "fd_name": "安信新回报混合C",            // 基金简称
    "fd_full_name": "安信新回报灵活配置混合型证券投资基金",  // 全称
    "can_invest": true,                     // 是否可申购
    "fd_type_desc": "混合型"                // 类型描述
  }],
  "result_code": 0,
  "error_type": 0
}
```

**类型映射表**:
| fd_type_desc | 系统标准类型 |
|--------------|-------------|
| 股票型 | equity |
| 混合型 | hybrid_equity |
| 债券型 | bond |
| 指数型 | index |
| QDII | qdii |
| FOF | fof |
| 货币型 | money_market |
| 商品型 | commodity |

---

### 1.3 业绩曲线

**接口**: `GET /djapi/fund/growth/{fund_code}?day=ty`

**返回结构**:
```json
{
  "data": {
    "fund_nav_growth": [
      {
        "date": "2026-05-22",
        "nav": "7.2787",
        "percentage": "5.3723",
        "value": "0.585532",              // 本产品累计收益率
        "than_value": "0.046471",          // 基准(沪深300)收益率
        "performance_value": "0.026418"   // 超额收益
      }
    ],
    "growth_lines": [
      {"line_name": "本产品", "line_key": "value", "line_color": "#FFA100"},
      {"line_name": "沪深300指数", "line_key": "than_value", "line_color": "#797C86"}
    ],
    "tip": [...],
    "performance_remark": "当前基金的业绩比较基准公式:50%*沪深300指数收益率+50%*中债总指数（全价）收益率。"
  }
}
```

**关键字段说明**:
- `value`: 本产品累计收益率（从基准日至今）
- `than_value`: 基准指数（如沪深300）同期收益率
- `performance_value`: 超额收益 = value - than_value

---

### 1.4 风险收益分析

**接口**: `GET /djapi/fund/base/quote/data/index/analysis/{fund_code}`

**返回结构**:
```json
{
  "data": {
    "fund_code": "002771",
    "index_data_list": [
      {
        "investment_cost_performance": "99%",  // 性价比排名
        "risk_control": "14%",               // 抗风险能力
        "index_time_period": "近1年",         // 时间段
        "range": "1y",
        "self_index": {
          "volatility_rank": 0.3936,       // 波动率排名
          "sharpe_rank": 5.29,             // 夏普比率排名
          "max_draw_down": 0.1682          // 最大回撤
        },
        "average_index": {                  // 同类平均
          "volatility_rank": 0.1996,
          "sharpe_rank": 1.83,
          "max_draw_down": 0.132
        }
      },
      {
        "investment_cost_performance": "98%",
        "risk_control": "30%",
        "index_time_period": "近3年",
        ...
      }
    ]
  }
}
```

**指标含义**:
| 指标 | 说明 | 数值范围 | 越好 |
|------|------|----------|------|
| volatility_rank | 年化波动率 | 0~1+ | 越低越好 |
| sharpe_rank | 夏普比率 | 0~10+ | 越高越好 |
| max_draw_down | 最大回撤 | 0~1 | 越小越好 |

---

### 1.5 年度与阶段业绩

**接口**: `GET /djapi/fundx/base/fund/achievement/{fund_code}`

**返回结构**:
```json
{
  "data": {
    "annual_performance_list": [        // 年度业绩
      {
        "period_time": "成立以来",        // 时间段
        "self_nav": "661.5116",          // 本产品收益率%
        "self_max_draw_down": "52.71%",  // 本产品最大回撤
        "standard_index_nav": "58.0466",  // 基准收益率%
        "standard_index_max_draw_down": "45.60%",
        "self_nav_rank": "36/2140"        // 同类排名
      },
      {
        "period_time": "2025",
        "self_nav": "111.44",
        ...
      }
    ],
    "stage_performance_list": [          // 阶段业绩
      {
        "period_time": "近1年",
        "self_nav": "209.8637718819",
        "self_max_draw_down": "16.82%",
        "standard_index_nav": "23.7931",
        "self_nav_rank": "27/2106"
      },
      {
        "period_time": "近3月",
        "self_nav": "55.6841216268",
        ...
      }
    ]
  }
}
```

---

### 1.6 选股与行业贡献

**接口**: `GET /djapi/fundx/base/fund/achievement/analysis/stock?fund_code={code}&period_time=2025`

**返回结构**:
```json
{
  "data": {
    "fund_code": "002771",
    "industry_analysis_list": {             // 行业贡献排名
      "top_list": [                          // 正贡献TOP
        {"name": "通信", "data": 66.28},    // +66.28%
        {"name": "电子", "data": 36.7},
        {"name": "传媒", "data": 5.45}
      ],
      "tail_list": [                          // 负贡献TOP
        {"name": "医药生物", "data": -2.38},  // -2.38%
        {"name": "纺织服饰", "data": -1.79},
        {"name": "电力设备", "data": -0.76}
      ]
    },
    "stock_analysis_list": {                 // 个股贡献排名
      "top_list": [
        {"name": "中际旭创", "data": 32.7},   // +32.7%
        {"name": "新易盛", "data": 28.18},
        {"name": "胜宏科技", "data": 20.6}
      ],
      "tail_list": [
        {"name": "一品红", "data": -2.99},
        {"name": "莱绅通灵", "data": -1.16},
        {"name": "潮宏基", "data": -0.63}
      ]
    }
  }
}
```

**使用场景**：
- 分析基金经理的选股能力
- 识别主要持仓行业
- 发现拖累业绩的行业/个股

---

### 1.7 基金经理信息

**接口**: `GET /djapi/fundx/base/fund/record/manager/list?fund_code={code}&post_status=1`

**返回结构**:
```json
{
  "data": {
    "items": [{
      "indi_id": "101001233",             // 经理ID
      "name": "陈鹏",                    // 姓名
      "work_year": "23",                // 从业年限
      "post_date": 1562688000000,      // 任职时间戳(ms)
      "post_status": 1,                // 在任状态(1=在任)
      "cp_term": "6年322天",           // 任职时长
      "cp_rate": 399.6703,            // 任职以来收益率%
      "post_name": 1,                 // 职位(1=基金经理)
      "performance_year": 26.35,      // 近一年收益率%
      "fund_total_nav": 25.45         // 管理规模(亿)
    }]
  }
}
```

---

### 1.8 盈利概率

**接口**: `GET /djapi/fundx/base/fund/profit/ratio/{fund_code}`

**返回结构**:
```json
{
  "data": {
    "fund_code": "002771",
    "profit_desc": "历史任意时点买入，持有满 %s 年，盈利概率 %s",
    "holding_year": "3",                   // 推荐持有年数
    "profit_ratio_desc": "70%",            // 盈利概率
    "data_list": [
      {
        "holding_time": "满6个月",         // 持有期限
        "profit_ratio": "70%",             // 盈利概率
        "average_income": "10.86%",       // 平均收益
        "average_income_data": "10.8600"  // 平均收益数值
      },
      {
        "holding_time": "满1年",
        "profit_ratio": "72%",
        "average_income": "23.19%",
        "average_income_data": "23.1900"
      },
      {
        "holding_time": "满2年",
        "profit_ratio": "68%",
        "average_income": "44.49%",
        "average_income_data": "44.4900"
      },
      {
        "holding_time": "满3年",
        "profit_ratio": "70%",
        "average_income": "68.44%",
        "average_income_data": "68.4400"
      }
    ]
  }
}
```

---

### 1.9 交易日期

**接口**: `GET /djapi/fund/order/v2/trade_date?fd_code={fund_code}`

**返回结构**:
```json
{
  "data": {
    "buy_query_date": "05-28",             // 申购查询日(MM-DD)
    "buy_confirm_date": "05-27",          // 申购确认日
    "sale_confirm_date": "05-27",          // 赎回确认日
    "sale_query_date": "06-01 12:00前",    // 赎回查询日
    "sale_to_cash_query_date": "05-28 18:00前", // 赎回现金到账日
    "withdraw_date": 0,                    // 提现到账日
    "if_can_pay_xjb": true,               // 是否可用现金宝
    "if_can_sale_xjb": true,              // 是否可快速赎回
    "if_can_transition": true,            // 是否支持转换
    "if_can_sale_to_cash": true          // 是否可转货币基金
  }
}
```

---

## 📈 二、股票/指数API（stock.xueqiu.com）

> ⚠️ **需要Cookie认证**

### 2.1 实时行情 ✅ **已验证通过**

**接口**: `GET /v5/stock/quote.json?symbol={symbol}&extend=detail`

**请求头要求**:
```http
Cookie: xq_a_token=xxx; xqat=xxx
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
Referer: https://xueqiu.com/
Origin: https://xueqiu.com
```

**参数说明**:
| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| symbol | string | ✅ | 股票/指数代码 | `SH000001`, `SZ399006`, `SH600519` |
| extend | string | ❌ | 扩展信息 | `detail` |

**代码格式**:
- 上海市场: `SH` + 6位代码（如 `SH600519`）
- 深圳市场: `SZ` + 6位代码（如 `SZ000001`）
- 指数: `SH` + 6位代码（如 `SH000300`）

**实际返回示例**（上证指数 SH000001）:
```json
{
  "data": {
    "market": {
      "status_id": 7,
      "region": "CN",
      "status": "已收盘",
      "time_zone": "Asia/Shanghai",
      "time_zone_desc": null,
      "delay_tag": 0,
      "downgrade_night_session": false,
      "daylight_savings": true
    },
    "quote": {
      "symbol": "SH000001",
      "code": "000001",
      "name": "上证指数",
      "current": 4152.57,                  // 最新价
      "percent": 0.96,                    // 涨跌幅%
      "high": 4153.8788,                  // 最高价
      "low": 4119.7996,                   // 最低价
      "open": 4126.3376,                  // 开盘价
      "last_close": 4112.8996,             // 昨收价
      "volume": 61593086100,               // 成交量(股)
      "amount": 1445655378392.4,            // 成交额(元)
      "timestamp": 1779692400000,           // 时间戳(毫秒)
      "chg": 39.67,                       // 涨跌额
      "market_capital": 69313103000000.0,   // 总市值(元)
      "float_market_capital": 25239885076364.88, // 流通市值(元)
      "turnover_rate": 1.34,                // 换手率(%)
      "high52w": 4258.86,                  // 52周最高
      "low52w": 3332.49,                   // 52周最低
      "current_year_percent": 4.63,         // 今年以来涨跌%
      "exchange": "SH",                   // 交易所
      "currency": "CNY",                 // 货币
      "type": 12,                        // 类型(12=指数)
      "status": 1                        // 状态(1=正常交易)
    },
    "others": {},
    "tags": []
  },
  "error_code": 0,
  "error_description": ""
}
```

**完整字段列表**:
| 字段 | 类型 | 说明 |
|------|------|------|
| symbol | string | 完整代码 (SH000001) |
| code | string | 纯数字代码 (000001) |
| name | string | 名称 (上证指数) |
| current | float | 最新价 |
| percent | float | 涨跌幅% (正数=上涨) |
| chg | float | 涨跌额 |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| last_close | float | 昨收价 |
| volume | int | 成交量(股) |
| amount | float | 成交额(元) |
| timestamp | int | 时间戳(毫秒) |
| market_capital | float | 总市值(元) |
| float_market_capital | float | 流通市值(元) |
| turnover_rate | float | 换手率(%) |
| high52w | float | 52周最高价 |
| low52w | float | 52周最低价 |
| current_year_percent | float | 今年以来涨跌% |
| exchange | string | 交易所 (SH/SZ) |
| currency | string | 货币 (CNY) |
| type | int | 类型 (12=指数, 1=股票等) |
| status | int | 状态 (1=正常) |

---

### 2.2 分时数据 ✅ **已验证通过**

**接口**: `GET /v5/stock/chart/minute.json?symbol={symbol}&period={period}`

**参数说明**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| symbol | string | ✅ | - | 股票/指数代码 |
| period | string | ❌ | `1d` | 周期 (`1d`=当天, `5d`=5天, `...`) |

**实际返回示例**（上证指数 SH000001）:
```json
{
  "data": {
    "last_close": 4112.8996,              // 昨收价
    "after": [],
    "items": [
      {
        "timestamp": 1779672600000,           // 时间戳(毫秒)
        "current": 4124.86,                  // 当前价格
        "volume": 2457609500,               // 成交量(股)
        "avg_price": 4124.86,               // 均价
        "chg": 11.96,                      // 涨跌额
        "percent": 0.29,                    // 涨跌幅%
        "amount": 51064237616.0,             // 成交额(元)
        "high": 4128.34,                    // 最高价
        "low": 4112.7,                     // 最低价
        "amount_total": 51064237616.0,      // 累计成交额
        "volume_total": 2457609500,         // 累计成交量
        "macd": {                            // MACD指标
          "dif": 0.0,
          "dea": 0.0,
          "macd": 0.0
        },
        "kdj": {                             // KDJ指标
          "k": 100.0,
          "d": 100.0,
          "j": 100.0
        },
        "ratio": {"ratio": 0.0},
        "capital": null,
        "volume_compare": {                 // 成交量对比
          "volume_sum": 2457609500,          // 今日成交量
          "volume_sum_last": 1970877600    // 昨日成交量
        }
      },
      // ... 更多时间点数据
    ],
    "items_size": 242                      // 数据点数量
  }
}
```

**完整字段列表**:
| 字段 | 类型 | 说明 |
|------|------|------|
| timestamp | int | 时间戳(毫秒)，可用于转换为 datetime |
| current | float | 当前价格 |
| volume | int | 该时间点成交量(股) |
| avg_price | float | 该时间段均价 |
| chg | float | 涨跌额 |
| percent | float | 涨跌幅% |
| amount | float | 成交额(元) |
| high | float | 该时间段最高价 |
| low | float | 该时间段最低价 |
| amount_total | float | 累计成交额(从开盘起) |
| volume_total | int | 累计成交量(从开盘起) |
| macd.dif/dea/macd | float | MACD指标 |
| kdj.k/d/j | float | KDJ指标 |
| ratio.ratio | float | 量比 |
| capital | object/null | 资金流向 |
| volume_compare.volume_sum | int | 今日总成交量 |
| volume_compare.volume_sum_last | int | 昨日成交量 |

**数据点频率**:
- `period=1d`: 约242个数据点（每分钟一个）
- `period=5d`: 约1200个数据点（5分钟一个）

---

### 2.3 K线数据 ✅ **已验证（2026-05-25）**

**接口**: `GET /v5/stock/chart/kline.json`

**完整URL格式**:
```
https://stock.xueqiu.com/v5/stock/chart/kline.json?
  symbol=SH600519&                    # 股票代码
  &begin=1779713095082               # 开始时间戳(毫秒，13位)
  &period=day                        # K线周期
  &type=before                       # 复权类型
  &count=-284                        # 数量(负=往前取)
  &indicator=kline,pe,pb,ps,pcf,market_capital  # 返回指标
```

**参数详解**:

#### symbol（股票代码）
- 格式：`{交易所}{6位代码}`
- 示例：`SH600519`（贵州茅台）、`SZ000001`（平安银行）
- 指数示例：`SH000001`（上证指数）、`SZ399006`（创业板指）

#### begin（开始时间戳）
- 类型：整数，单位：**毫秒**
- 格式：13位时间戳
- 含义：K线数据的起始时间点
- 示例：`1779713095082`（2026-05-25 某时刻）

#### period（周期）
| 值 | 说明 | 适用场景 |
|----|------|----------|
| `day` | 日K线 | 技术分析、短期趋势 |
| `week` | 周K线 | 中期趋势判断 |
| `month` | 月K线 | 长期趋势分析 |
| `quarter` | 季度K线 | 季度报告 |
| `year` | 年K线 | 年度总结 |

#### type（复权类型）⭐ 重要
| 值 | 中文名 | 英文名 | 使用场景 | 公式 |
|----|--------|--------|----------|------|
| `before` | **前复权** | Forward Adjusted | **推荐：技术分析** | 价格 = 复权价格 × (1 + 前次分红率) |
| `after` | **后复权** | Backward Adjusted | 长期趋势分析 | 价格 = 除权价格 × ∏(1 + 所有历史分红率) |
| `normal` | **不复权** | Raw Price | 原始价格查看 | 价格 = 实际成交价格 |

**选择建议**:
- **日常技术分析** → `before`（前复权）：保持价格连续性，适合均线、MACD等技术指标
- **长期投资分析** → `after`（后复权）：反映真实长期收益
- **查看原始数据** → `normal`（不复权）：看到实际交易价格

#### count（数量）
- 正数：从 `begin` 往**后**取 N 条
- 负数：从 `begin` 往**前**取 N 条
- 示例：`count=-284` = 取最近284个交易日（约1年）

#### indicator（返回指标）
可多选，逗号分隔：

| 指标 | 参数名 | 说明 | 单位 |
|------|--------|------|------|
| OHLCV基础 | `kline` | 开高低收成交量 | - |
| 市盈率 | `pe` | 市盈率(TTM) | 倍 |
| 市净率 | `pb` | 市净率 | 倍 |
| 市销率 | `ps` | 市销率 | 倍 |
| 市现率 | `pcf` | 市现率 | 倍 |
| 总市值 | `market_capital` | 总市值 | 元 |
| 其他 | `agt,ggt,balance` | 待验证 | - |

**✅ 实际返回格式**（2026-05-25 验证通过）:
```json
{
  "data": {
    "symbol": "SH000001",
    "column": [
      "timestamp", "volume", "open", "high", "low", "close",
      "chg", "percent", "turnoverrate", "amount",
      "volume_post", "amount_post", "pe", "pb", "ps", "pcf",
      "market_capital", "balance",
      "hold_volume_cn", "hold_ratio_cn", "net_volume_cn",
      "hold_volume_hk", "hold_ratio_hk", "net_volume_hk"
    ],
    "item": [
      [1742486400000, 52086263000, 3401.76, 3414.71, 3355.84, 3364.83, -44.12, -1.29, 1.14, 623164007297.2, null, null, null, null, null, null, null, null, null, null, null, null, null, null],
      // ... 更多数据
    ]
  },
  "error_code": 0,
  "error_description": ""
}
```

**字段说明**（按 column 顺序）:

| 序号 | 字段名 | 类型 | 说明 | 示例值 |
|------|--------|------|------|--------|
| 0 | `timestamp` | int | 时间戳(毫秒) | `1742486400000` |
| 1 | `volume` | int | 成交量(股) | `52086263000` |
| 2 | `open` | float | 开盘价 | `3401.76` |
| 3 | `high` | float | 最高价 | `3414.71` |
| 4 | `low` | float | 最低价 | `3355.84` |
| 5 | `close` | float | 收盘价 | `3364.83` |
| 6 | `chg` | float | 涨跌额 | `-44.12` |
| 7 | `percent` | float | 涨跌幅(%) | `-1.29` |
| 8 | `turnoverrate` | float | 换手率(%) | `1.14` |
| 9 | `amount` | float | 成交额(元) | `623164007297.2` |
| 10-11 | `volume_post/amount_post` | - | 复权后成交量/成交额 | - |
| 12 | `pe` | float | 市盈率(TTM) | `20.0493`（个股有值，指数为null） |
| 13 | `pb` | float | 市净率 | - |
| 14 | `ps` | float | 市销率 | - |
| 15 | `pcf` | float | 市现率 | - |
| 16 | `market_capital` | float | 总市值(元) | - |
| 17 | `balance` | - | 待确认 | - |
| 18-23 | `hold_*/net_*` | - | 沪深港通持股数据 | - |

**⚠️ 关键发现**：
- ✅ **begin参数必须是当前时间的毫秒时间戳**（不是过去的时间）
- ✅ 返回格式是 `column`(字段名数组) + `item`(数据数组)，**不是** `items`
- ✅ 指数数据（如SH000001）的pe/pb等字段为null
- ✅ 个股数据（如SH600519）包含完整的估值指标

**测试结果**（2026-05-25）:
- SH000001（上证指数）: ✅ 获取284条日K线数据
- SH600519（贵州茅台）: ✅ 获取284条日K线数据，PE=20.0493

---

## 🔧 三、使用示例

### Python 代码示例

```python
import requests
from datetime import datetime

# === 基金数据（无需认证）===
def get_fund_nav(fund_code):
    url = f"https://danjuanfunds.com/djapi/fund/nav/history/{fund_code}"
    resp = requests.get(url, params={"page": 1, "size": 20})
    return resp.json()

# === 股票数据（需要Cookie）===
XUEQIU_COOKIE = "xq_a_token=20458f74230aee45906ecb90d8c70ff43daa3837; xqat=20458f74230aee45906ecb90d8c70ff43daa3837"

def get_stock_quote(symbol):
    url = f"https://stock.xueqiu.com/v5/stock/quote.json"
    headers = {
        "Cookie": XUEQIU_COOKIE,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    resp = requests.get(url, params={"symbol": symbol, "extend": "detail"}, headers=headers)
    data = resp.json()["data"]["quote"]
    
    return {
        "name": data["name"],
        "price": data["current"],
        "change_pct": data["percent"],
        "volume": data["volume"],
        "timestamp": datetime.fromtimestamp(data["timestamp"] / 1000)
    }

# 使用示例
nav_data = get_fund_nav("002771")
print(f"最新净值: {nav_data['data']['items'][0]['nav']}")

quote = get_stock_quote("SH000001")
print(f"上证指数: {quote['name']} 最新价: {quote['price']}")
```

---

## 📝 四、错误码说明

| error_code | 说明 | 处理方式 |
|------------|------|----------|
| 0 | 成功 | 正常处理数据 |
| 400016 | 认证失败 | 检查Cookie是否有效，提示用户重新登录 |
| 100002 | 缺少必填参数 | 检查请求参数是否完整 |
| 其他 | 服务端错误 | 记录日志并重试 |

---

## 🔄 五、版本更新记录

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v1.0 | 2026-05-25 | 初始版本，包含基金数据API文档 |
| v1.1 | 2026-05-25 | 新增股票/指数API测试结果（行情✅ 分时✅ K线⚠️） |
| v1.2 | 2026-05-25 | 补充详细字段说明和使用示例 |
| v1.3 | 2026-05-25 | ✅ **K线API验证通过**，更新实际返回格式、字段映射、关键发现（begin必须用当前时间戳、column+item格式） |

---

## 💡 六、注意事项

1. **频率限制**：建议单IP请求间隔 ≥200ms，避免触发限流
2. **缓存策略**：基金数据可缓存1小时，股票行情建议缓存≤5分钟
3. **Cookie安全**：不要将Cookie提交到公开仓库，使用环境变量存储
4. **数据延迟**：行情数据可能有15分钟延迟，非实时
5. **交易日历**：注意区分交易日和非交易日，非交易日数据可能不更新
6. **异常处理**：网络超时设置合理阈值（建议5-10秒），失败后重试2-3次
