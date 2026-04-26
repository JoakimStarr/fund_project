from typing import Any

from pydantic import BaseModel


class TaskInfo(BaseModel):
    task_id: str
    fund_code: str
    status: str
    progress: int
    stage: str
    message: str
    error_code: str | None = None
    error_message: str | None = None
    details: dict[str, Any] | None = None
