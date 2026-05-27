import logging

from app.services.predict.intraday_service import estimate_t_day

logger = logging.getLogger(__name__)


async def predict(fund_code: str, session, save_result: bool = False) -> dict:
    try:
        result = await estimate_t_day(fund_code, session=session, mode="auto", save_result=save_result)
    except ValueError as e:
        logger.warning("prediction_failed fund=%s error=%s", fund_code, e)
        raise
    except Exception as e:
        logger.error("prediction_error fund=%s error=%s", fund_code, e, exc_info=True)
        raise
    return result


async def batch_predict(fund_codes: list, session, save_result: bool = False) -> list:
    results = []
    for code in fund_codes:
        try:
            result = await predict(code, session, save_result=save_result)
            results.append({"fund_code": code, "success": True, "data": result})
        except Exception as e:
            logger.warning("batch_predict_failed fund=%s error=%s", code, e)
            results.append({"fund_code": code, "success": False, "error": str(e)})
    return results
