from fastapi import APIRouter, Query
from sqlalchemy import select, and_
from sqlalchemy.sql import func
from app.schemas.common import ApiResponse
from app.core.database import async_session
from app.models.prediction import Prediction
from app.models.fund_nav import FundNav
import math

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.get("/{code}")
async def run_backtest(
    code: str,
    start_date: str = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期 YYYY-MM-DD"),
    days: int = Query(90, description="最近N天")
) -> ApiResponse:
    """
    回测接口：获取基金的历史预测记录与实际收益对比
    """
    async with async_session() as session:
        # 构建查询条件
        filters = [Prediction.fund_code == code]
        if start_date:
            filters.append(Prediction.predict_date >= start_date)
        if end_date:
            filters.append(Prediction.predict_date <= end_date)
        
        # 如果没有指定日期范围，使用最近N天
        if not start_date and not end_date:
            # 获取最近N天的预测记录
            subquery = select(Prediction.predict_date).where(
                Prediction.fund_code == code
            ).order_by(Prediction.predict_date.desc()).limit(days).subquery()
            filters.append(Prediction.predict_date.in_(select(subquery)))
        
        # 只查询有实际收益数据的记录
        filters.append(Prediction.actual_return.isnot(None))
        
        result = await session.execute(
            select(Prediction).where(and_(*filters)).order_by(Prediction.predict_date)
        )
        predictions = result.scalars().all()
        
        if not predictions:
            return ApiResponse(ok=True, data={
                "summary": None,
                "records": [],
                "message": "暂无回测数据，请先进行预测并等待实际收益数据更新"
            })
        
        # 构建回测记录
        records = []
        for p in predictions:
            records.append({
                "date": p.predict_date,
                "actual_return": p.actual_return,
                "predicted_return": p.predicted_return,
                "confidence_lower": p.lower_bound,
                "confidence_upper": p.upper_bound,
                "direction_correct": bool(p.direction_correct) if p.direction_correct is not None else None,
                "interval_covered": bool(p.interval_covered) if p.interval_covered is not None else None,
                "model_version": p.model_version,
                "confidence_level": p.confidence_level,
            })
        
        # 计算汇总指标
        n = len(records)
        actual_returns = [r["actual_return"] for r in records]
        predicted_returns = [r["predicted_return"] for r in records]
        
        # MAE (Mean Absolute Error)
        mae = sum(abs(a - p) for a, p in zip(actual_returns, predicted_returns)) / n
        
        # RMSE (Root Mean Squared Error)
        rmse = math.sqrt(sum((a - p) ** 2 for a, p in zip(actual_returns, predicted_returns)) / n)
        
        # 方向准确率
        direction_correct_count = sum(1 for r in records if r["direction_correct"])
        direction_accuracy = direction_correct_count / n if n > 0 else 0
        
        # 区间覆盖率
        interval_covered_count = sum(1 for r in records if r["interval_covered"])
        interval_coverage = interval_covered_count / n if n > 0 else 0
        
        # Spearman 相关系数（简化计算）
        try:
            from scipy import stats
            spearman_corr, _ = stats.spearmanr(actual_returns, predicted_returns)
            if math.isnan(spearman_corr):
                spearman_corr = 0
        except:
            spearman_corr = 0
        
        summary = {
            "total_records": n,
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "direction_accuracy": round(direction_accuracy, 4),
            "interval_coverage_80": round(interval_coverage, 4) if any(r["confidence_level"] == 0.80 for r in records) else None,
            "interval_coverage_90": round(interval_coverage, 4) if any(r["confidence_level"] == 0.90 for r in records) else None,
            "spearman": round(spearman_corr, 3),
            "start_date": records[0]["date"],
            "end_date": records[-1]["date"],
        }
        
        return ApiResponse(ok=True, data={
            "summary": summary,
            "records": records
        })
