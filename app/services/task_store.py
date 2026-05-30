from threading import Lock
from typing import Optional, Protocol

from app.domain.schemas import TaskStatusResponse


class TaskStore(Protocol):
    def put_task(self, task: TaskStatusResponse) -> None:
        ...

    def get_task(self, task_id: str) -> Optional[TaskStatusResponse]:
        ...

    def list_tasks(self, limit: int = 50) -> list[TaskStatusResponse]:
        ...


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskStatusResponse] = {}
        self._lock = Lock()

    def put_task(self, task: TaskStatusResponse) -> None:
        with self._lock:
            self._tasks[task.task_id] = TaskStatusResponse.model_validate(task.model_dump())

    def get_task(self, task_id: str) -> Optional[TaskStatusResponse]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            return TaskStatusResponse.model_validate(task.model_dump())

    def list_tasks(self, limit: int = 50) -> list[TaskStatusResponse]:
        with self._lock:
            tasks = list(self._tasks.values())
        tasks.sort(key=lambda item: item.updated_at, reverse=True)
        return [
            TaskStatusResponse.model_validate(task.model_dump())
            for task in tasks[:limit]
        ]
