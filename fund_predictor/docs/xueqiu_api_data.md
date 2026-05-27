# 002771 接口与返回结构

## 1. 历史净值

**接口**

`https://danjuanfunds.com/djapi/fund/nav/history/002771?page=1&size=20`

**返回结构**

```json
{
  "data": {
    "items": [
      {
        "date": "2026-05-22",
        "nav": "7.2787",
        "percentage": "5.37",
        "value": "7.2787"
      }
    ],
    "current_page": 1,
    "size": 20,
    "total_items": 2440,
    "total_pages": 122
  },
  "result_code": 0
}
```

## 2. 业绩曲线

**接口**

`https://danjuanfunds.com/djapi/fund/growth/002771?day=ty`

**返回结构**

```json
{
  "data": {
    "fund_nav_growth": [
      {
        "date": "2026-05-22",
        "nav": "7.2787",
        "percentage": "5.3723",
        "value": "0.585532",
        "than_value": "0.046471",
        "performance_value": "0.026418"
      }
    ],
    "growth_lines": [
      {
        "line_name": "本产品",
        "line_key": "value",
        "line_color": "#FFA100"
      },
      {
        "line_name": "沪深300指数",
        "line_key": "than_value",
        "line_color": "#797C86"
      }
    ],
    "tip": [
      {
        "title": "沪深300指数",
        "content": "由A股市值大、流动性最好的300家公司组成，代表A股各行业龙头的整体走势"
      }
    ],
    "performance_remark": "当前基金的业绩比较基准公式:50%*沪深300指数收益率+50%*中债总指数（全价）收益率。"
  },
  "result_code": 0
}
```

## 3. 风险收益分析

**接口**

`https://danjuanfunds.com/djapi/fund/base/quote/data/index/analysis/002771`

**返回结构**

```json
{
  "data": {
    "fund_code": "002771",
    "index_tip": [
      {
        "title": "风险收益比",
        "content": "综合统计基金承担风险获取收益的性价比..."
      }
    ],
    "index_data_list": [
      {
        "investment_cost_performance": "99%",
        "risk_control": "14%",
        "index_time_period": "近1年",
        "range": "1y",
        "self_index": {
          "volatility_rank": 0.3936,
          "sharpe_rank": 5.29,
          "max_draw_down": 0.1682
        },
        "average_index": {
          "volatility_rank": 0.1996,
          "sharpe_rank": 1.83,
          "max_draw_down": 0.132
        }
      }
    ]
  },
  "result_code": 0
}
```

## 4. 年度与阶段业绩

**接口**

`https://danjuanfunds.com/djapi/fundx/base/fund/achievement/002771`

**返回结构**

```json
{
  "data": {
    "fund_code": "002771",
    "annual_performance_list": [
      {
        "period_time": "成立以来",
        "self_nav": "661.5116",
        "self_max_draw_down": "52.71%",
        "standard_index_nav": "58.0466",
        "standard_index_max_draw_down": "45.60%",
        "self_nav_rank": "36/2140"
      }
    ],
    "stage_performance_list": [
      {
        "period_time": "近1年",
        "self_nav": "209.8637718819",
        "self_max_draw_down": "16.82%",
        "standard_index_nav": "23.7931",
        "standard_index_max_draw_down": "7.78%",
        "self_nav_rank": "27/2106"
      }
    ]
  },
  "result_code": 0
}
```

## 5. 选股与行业贡献

**接口**

`https://danjuanfunds.com/djapi/fundx/base/fund/achievement/analysis/stock?fund_code=002771&period_time=2025`

**返回结构**

```json
{
  "data": {
    "fund_code": "002771",
    "industry_analysis_list": {
      "top_list": [
        {
          "name": "通信",
          "data": 66.28
        }
      ],
      "tail_list": [
        {
          "name": "医药生物",
          "data": -2.38
        }
      ]
    },
    "stock_analysis_list": {
      "top_list": [
        {
          "name": "中际旭创",
          "data": 32.7
        }
      ],
      "tail_list": [
        {
          "name": "一品红",
          "data": -2.99
        }
      ]
    }
  },
  "result_code": 0
}
```

## 6. 基金基础信息

**接口**

`https://danjuanfunds.com/djapi/fundx/autoinvest/quote/fund/info?fd_codes=002771`

**返回结构**

```json
{
  "data": [
    {
      "fd_code": "002771",
      "fd_type": "3",
      "fd_name": "安信新回报混合C",
      "fd_full_name": "安信新回报灵活配置混合型证券投资基金",
      "can_invest": true,
      "fd_type_desc": "混合型"
    }
  ],
  "result_code": 0,
  "error_type": 0
}
```

## 11. 股票页示例

**页面**

`https://xueqiu.com/S/SH000001`

### 11.1 股票行情

**接口**

`https://stock.xueqiu.com/v5/stock/quote.json?symbol=SH000001&extend=detail`

**返回结构**

```json
{
  "data": {
    "quote": {
      "symbol": "SH000001",
      "name": "上证指数",
      "current": 4152.57,
      "percent": 0.96,
      "high": 4153.8788,
      "low": 4119.7996,
      "open": 4126.3376,
      "last_close": 4112.8996,
      "volume": 61593086100,
      "amount": 1445655378392.4,
      "timestamp": 1779692400000,
      "chg": 39.67
    },
    "market": {},
    "others": {},
    "tags": []
  },
  "error_code": 0,
  "error_description": ""
}
```

### 11.2 分时数据

**接口**

`https://stock.xueqiu.com/v5/stock/chart/minute.json?symbol=SH000001&period=1d`

**返回结构**

```json
{
  "data": {
    "last_close": 4112.8996,
    "after": {},
    "items": [
      {
        "current": 4124.86,
        "volume": 2457609500,
        "avg_price": 4124.86,
        "chg": 11.96,
        "percent": 0.29,
        "timestamp": 1779672600000,
        "amount": 51064237616,
        "high": 4128.34,
        "low": 4112.7,
        "amount_total": 51064237616,
        "volume_total": 2457609500,
        "volume_compare": {
          "volume_sum": 2457609500,
          "volume_sum_last": 1970877600
        }
      }
    ],
    "items_size": 242
  },
  "error_code": 0,
  "error_description": ""
}
```

### 11.3 相关标的

**接口**

`https://stock.xueqiu.com/v5/stock/quote/relevant.json?symbol=SH000001`

**返回结构**

```json
{
  "data": {
    "cubes": [],
    "items": [
      {
        "symbol": "SH688008",
        "name": "澜起科技",
        "current": 284.08,
        "percent": 4.51,
        "tick_size": 0.01,
        "type": 82,
        "has_follow": false,
        "list": []
      }
    ]
  },
  "error_code": 0,
  "error_description": ""
}
```

## 7. 基金经理

**接口**

`https://danjuanfunds.com/djapi/fundx/base/fund/record/manager/list?fund_code=002771&post_status=1`

**返回结构**

```json
{
  "data": {
    "items": [
      {
        "indi_id": "101001233",
        "name": "陈鹏",
        "work_year": "23",
        "post_date": 1562688000000,
        "post_status": 1,
        "cp_term": "6年322天",
        "cp_rate": 399.6703,
        "post_name": 1,
        "performance_year": 26.35,
        "fund_total_nav": 25.45
      }
    ],
    "current_page": 1,
    "size": 20,
    "total_items": 1,
    "total_pages": 1
  },
  "result_code": 0
}
```

## 8. 交易日期

**接口**

`https://danjuanfunds.com/djapi/fund/order/v2/trade_date?fd_code=002771`

**返回结构**

```json
{
  "data": {
    "buy_query_date": "05-28",
    "buy_confirm_date": "05-27",
    "sale_confirm_date": "05-27",
    "sale_query_date": "06-01 12:00前",
    "sale_to_cash_query_date": "05-28 18:00前",
    "withdraw_date": 0,
    "if_can_pay_xjb": true,
    "if_can_sale_xjb": true,
    "if_can_transition": true,
    "if_can_sale_to_cash": true
  },
  "result_code": 0
}
```

## 9. 盈利概率

**接口**

`https://danjuanfunds.com/djapi/fundx/base/fund/profit/ratio/002771`

**返回结构**

```json
{
  "data": {
    "fund_code": "002771",
    "profit_desc": "历史任意时点买入，持有满 %s 年，盈利概率 %s",
    "holding_year": "3",
    "profit_ratio_desc": "70%",
    "data_list": [
      {
        "holding_time": "满6个月",
        "profit_ratio": "70%",
        "average_income": "10.86%",
        "average_income_data": "10.8600"
      },
      {
        "holding_time": "满1年",
        "profit_ratio": "72%",
        "average_income": "23.19%",
        "average_income_data": "23.1900"
      }
    ]
  },
  "result_code": 0
}
```

## 10. 定投收益

**接口**

`https://danjuanfunds.com/djapi/fundx/autoinvest/quote/yield/list?fd_code=002771`

**返回结构**

```json
{
  "data": {
    "duration": "3Y",
    "fd_code": "002771",
    "buy_type1": "normal",
    "buy_type2": "mv",
    "cycle": "1",
    "base_invest_amount": "100",
    "recent_yields": [
      {
        "duration": "近1年",
        "normal": "78.0200",
        "max_itg": "87.8000"
      },
      {
        "duration": "近3年",
        "normal": "187.9100",
        "max_itg": "246.9900"
      }
    ]
  },
  "result_code": 0,
  "error_type": 0
}
```
