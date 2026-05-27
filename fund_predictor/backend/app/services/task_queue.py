import logging
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from functools import partial
from queue import Empty, PriorityQueue
from typing import Any, Callable

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Priority(int, Enum):
    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0


@dataclass(order=True)
class _TaskItem:
    priority: int
    task_id: str = field(compare=False)
    task_fn: Callable = field(compare=False)
    args: tuple = field(compare=False)
    kwargs: dict = field(compare=False)
    retry_count: int = field(default=0, compare=False)
    max_retries: int = field(default=2, compare=False)
    submitted_at: float = field(default_factory=time.time, compare=False)


@dataclass
class TaskInfo:
    task_id: str
    status: TaskStatus
    priority: Priority
    created_at: float
    started_at: float | None = None
    completed_at: float | None = None
    result: Any = None
    error: str | None = None
    retry_count: int = 0
    worker_thread: str | None = None


class LocalTaskQueue:
    """
    轻量级本地异步任务队列。

    基于 threading + PriorityQueue 实现，不依赖Celery/Redis。
    支持功能：
    - 并发限制（默认max_concurrent=3）
    - 优先级队列（CRITICAL > HIGH > NORMAL > LOW）
    - 任务取消
    - 自动重试（默认最多重试2次）
    - 状态查询

    用法示例：
        tq = LocalTaskQueue(max_concurrent=3)
        task_id = tq.submit(my_function, arg1, arg2, kwarg=value)
        status = tq.get_status(task_id)
        tq.cancel(task_id)
    """

    def __init__(self, max_concurrent: int = 3):
        self._queue: PriorityQueue[_TaskItem] = PriorityQueue()
        self._tasks: dict[str, TaskInfo] = {}
        self._lock = threading.RLock()
        self._max_concurrent = max_concurrent
        self._running_count = 0
        self._stop_event = threading.Event()
        self._workers: list[threading.Thread] = []

        for i in range(max_concurrent):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"task_worker_{i}",
                daemon=True,
            )
            worker.start()
            self._workers.append(worker)

        logger.info("task_queue_initialized workers=%s max_concurrent=%s", max_concurrent, max_concurrent)

    def submit(self, task_fn: Callable, *args,
               priority: Priority = Priority.NORMAL,
               max_retries: int = 2,
               **kwargs) -> str:
        """
        提交任务到队列。

        Args:
            task_fn: 要执行的可调用对象
            *args: 位置参数
            priority: 任务优先级（默认NORMAL）
            max_retries: 最大重试次数（默认2）
            **kwargs: 关键字参数

        Returns:
            task_id: 唯一任务标识符
        """
        task_id = uuid.uuid4().hex[:16]

        item = _TaskItem(
            priority=priority.value,
            task_id=task_id,
            task_fn=task_fn,
            args=args,
            kwargs=kwargs,
            max_retries=max_retries,
        )

        info = TaskInfo(
            task_id=task_id,
            status=TaskStatus.PENDING,
            priority=priority,
            created_at=time.time(),
        )

        with self._lock:
            self._tasks[task_id] = info
            self._queue.put(item)

        logger.info(
            "task_submitted task_id=%s fn=%s priority=%s retries=%s",
            task_id, getattr(task_fn, '__name__', str(task_fn)), priority.name, max_retries,
        )
        return task_id

    def get_status(self, task_id: str) -> dict:
        """
        获取任务状态。

        Returns:
            包含status、result、error等信息的字典，如果任务不存在则返回None
        """
        with self._lock:
            info = self._tasks.get(task_id)
            if info is None:
                return {"exists": False}

            return {
                "exists": True,
                "task_id": info.task_id,
                "status": info.status.value,
                "priority": info.priority.name,
                "created_at": info.created_at,
                "started_at": info.started_at,
                "completed_at": info.completed_at,
                "has_result": info.result is not None,
                "error": info.error,
                "retry_count": info.retry_count,
                "worker_thread": info.worker_thread,
            }

    def cancel(self, task_id: str) -> bool:
        """
        取消任务。

        只能取消PENDING状态的任务。
        已运行或已完成的任务无法取消。

        Returns:
            是否成功取消
        """
        with self._lock:
            info = self._tasks.get(task_id)
            if info is None:
                logger.warning("task_cancel_not_found task_id=%s", task_id)
                return False

            if info.status != TaskStatus.PENDING:
                logger.warning(
                    "task_cancel_not_pending task_id=%s status=%s",
                    task_id, info.status.value,
                )
                return False

            info.status = TaskStatus.CANCELLED
            info.completed_at = time.time()
            logger.info("task_cancelled task_id=%s", task_id)
            return True

    def get_result(self, task_id: str, timeout: float | None = None) -> Any:
        """
        阻塞等待任务结果。

        Args:
            task_id: 任务ID
            timeout: 超时时间（秒），None表示无限等待

        Returns:
            任务返回值

        Raises:
            TimeoutError: 超时
            RuntimeError: 任务失败或被取消
        """
        deadline = time.time() + (timeout or 86400)
        while time.time() < deadline:
            with self._lock:
                info = self._tasks.get(task_id)
                if info is None:
                    raise RuntimeError(f"任务不存在: {task_id}")

                if info.status == TaskStatus.COMPLETED:
                    return info.result
                elif info.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
                    raise RuntimeError(
                        f"任务{info.status.value}: {info.error or 'unknown'}"
                    )

            time.sleep(0.1)

        raise TimeoutError(f"等待任务结果超时: {task_id}")

    def shutdown(self, wait: bool = True):
        """关闭任务队列，停止所有worker线程"""
        self._stop_event.set()
        for _ in range(self._max_concurrent + 10):
            self._queue.put(_TaskItem(
                priority=999, task_id="_shutdown_sentinel_",
                task_fn=lambda: None, args=(), kwargs={},
            ))
        if wait:
            for w in self._workers:
                w.join(timeout=5.0)
        logger.info("task_queue_shutdown")

    @property
    def pending_count(self) -> int:
        """当前待处理任务数"""
        with self._lock:
            return sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING)

    @property
    def running_count(self) -> int:
        """当前运行中任务数"""
        return self._running_count

    @property
    def all_tasks(self) -> dict[str, dict]:
        """获取所有任务的状态快照"""
        with self._lock:
            return {
                tid: self.get_status(tid)
                for tid in self._tasks
            }

    def _worker_loop(self):
        """工作线程主循环：从优先级队列取任务并执行"""
        thread_name = threading.current_thread().name
        logger.debug("task_worker_started name=%s", thread_name)

        while not self._stop_event.is_set():
            try:
                item: _TaskItem = self._queue.get(timeout=1.0)
            except Empty:
                continue

            if item.task_id == "_shutdown_sentinel_":
                break

            with self._lock:
                info = self._tasks.get(item.task_id)
                if info is None or info.status == TaskStatus.CANCELLED:
                    continue

                info.status = TaskStatus.RUNNING
                info.started_at = time.time()
                info.worker_thread = thread_name
                self._running_count += 1

            try:
                logger.debug(
                    "task_executing task_id=%s worker=%s retry=%s/%s",
                    item.task_id, thread_name, item.retry_count, item.max_retries,
                )
                result = item.task_fn(*item.args, **item.kwargs)

                with self._lock:
                    info.status = TaskStatus.COMPLETED
                    info.result = result
                    info.completed_at = time.time()
                    self._running_count -= 1

                logger.info("task_completed task_id=%s", item.task_id)

            except Exception as e:
                with self._lock:
                    self._running_count -= 1
                    should_retry = item.retry_count < item.max_retries

                    if should_retry:
                        item.retry_count += 1
                        info.retry_count = item.retry_count
                        info.status = TaskStatus.PENDING
                        info.started_at = None
                        self._queue.put(item)
                        logger.warning(
                            "task_retrying task_id=%s attempt=%s/%s error=%s",
                            item.task_id, item.retry_count, item.max_retries, e,
                        )
                    else:
                        info.status = TaskStatus.FAILED
                        info.error = str(e)
                        info.completed_at = time.time()
                        logger.error(
                            "task_failed task_id=%s retries_exhausted error=%s",
                            item.task_id, e,
                        )


_global_task_queue: LocalTaskQueue | None = None
_global_queue_lock = threading.Lock()


def get_task_queue() -> LocalTaskQueue:
    """获取全局单例任务队列实例（懒初始化）"""
    global _global_task_queue
    with _global_queue_lock:
        if _global_task_queue is None:
            _global_task_queue = LocalTaskQueue(max_concurrent=3)
        return _global_task_queue


def submit_task(task_fn: Callable, *args,
                priority: Priority = Priority.NORMAL,
                max_retries: int = 2,
                **kwargs) -> str:
    """
    便捷函数：向全局任务队列提交任务。

    等效于 get_task_queue().submit(...)
    """
    return get_task_queue().submit(task_fn, *args, priority=priority, max_retries=max_retries, **kwargs)
