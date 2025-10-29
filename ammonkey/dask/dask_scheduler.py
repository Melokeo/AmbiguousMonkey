"""dask scheduler with resource-aware orchestration (keeps public interface)

This class intentionally avoids re-implementing Dask's scheduler logic.
It:
  • logs worker resources (no client-side tagging)
  • wires dependencies via `depends_on` (no pre-wait)
  • passes priority/resources to the scheduler
  • tracks timings and basic stats
  • provides the same methods/attributes as before
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict

import dask
from dask.distributed import Client, as_completed

from .dask_task import DaskTask, DaskType

logger = logging.getLogger(__name__)


@dataclass
class TaskStats:
    """statistics for a task type"""
    submitted: int = 0
    completed: int = 0
    failed: int = 0
    total_time: float = 0.0

    @property
    def success_rate(self) -> float:
        total = self.completed + self.failed
        return (self.completed / total) if total else 0.0

    @property
    def avg_time(self) -> float:
        return (self.total_time / self.completed) if self.completed else 0.0


class DaskScheduler:
    """manages task submission and monitoring (orchestrator/submitter)

    Public:
      - __init__(scheduler_address: str = 'tcp://localhost:8786', auto_setup: bool = True)
      - setup_workers() -> None
      - submit_task(task: DaskTask) -> str
      - submit_tasks(tasks: list[DaskTask]) -> dict[str, Any]
      - monitor_progress(...)
      - get_status() -> dict
      - cancel_pending() -> int
      - cleanup() -> None
    """

    def __init__(self, scheduler_address: str = 'tcp://localhost:8786', auto_setup: bool = True):
        with dask.config.set({'distributed.comm.timeouts.tcp': '11s', 'distributed.comm.timeouts.connect': '10s'}): #type:ignore
            self.client = Client(scheduler_address)
        
        self.pending_tasks: dict[str, DaskTask] = {}
        self.completed_tasks: dict[str, dict] = {}
        self.futures: dict[str, Any] = {}
        self.stats: dict[DaskType, TaskStats] = defaultdict(TaskStats)
        self._start_times: dict[str, float] = {}  # task_id -> submit time

        if auto_setup:
            self.setup_workers()

    # ----------------------------- resource discovery -----------------------------
    def setup_workers(self) -> None:
        """Log available worker resources; handle both direct and nested resource formats."""
        info = self.client.scheduler_info().get('workers', {})
        gpu_workers = 0
        cpu_workers = 0

        for addr, w in info.items():
            res = w.get('resources', {})
            
            # Check if resources are nested (LocalCluster format)
            if any(isinstance(v, dict) for v in res.values()):
                # Flatten nested resources: {0: {'cpu': 1}, 1: {'gpu': 1}} -> {'cpu': 1, 'gpu': 1}
                flat_res = {}
                for nested in res.values():
                    if isinstance(nested, dict):
                        flat_res.update(nested)
                res = flat_res
                logger.debug(res)
            
            if res.get('gpu', 0) >= 1:
                gpu_workers += 1
                logger.debug(f"Worker {addr} has GPU resources")
            elif res.get('cpu', 0) >= 1:
                cpu_workers += 1
                logger.debug(f"Worker {addr} has CPU resources")
            else:
                logger.debug(f"Worker {addr} has resources {w.get('resources')} (unclassified)")

        logger.info(f"Detected: {gpu_workers} GPU workers, {cpu_workers} CPU workers")

    def _has_resource(self, key: str) -> bool:
        """Check if any worker has the specified resource"""
        info = self.client.scheduler_info().get('workers', {})
        for w in info.values():
            res = w.get('resources', {})
            
            # Handle nested resources
            if any(isinstance(v, dict) for v in res.values()):
                for nested in res.values():
                    if isinstance(nested, dict) and nested.get(key, 0) >= 1:
                        return True
            
            # Check direct resources
            if res.get(key, 0) >= 1:
                return True
        
        return False
    # ---------------------------------- submit -----------------------------------
    def submit_task(self, task: DaskTask) -> str:
        """submit single task (thin wrapper)"""
        return self.submit_tasks([task])[task.id]

    def submit_tasks(self, tasks: list[DaskTask]) -> dict[str, Any]:
        """submit multiple tasks with dependency wiring (no pre-waiting)

        - Uses `depends_on` to express dependencies without serializing execution.
        - Passes `priority` and `resources` into the scheduler.
        - Keeps `key=task.id` for stable identification.
        """
        logger.debug(tasks)
        from .dask_executors import execute_task  # local import to avoid worker-side imports here
        def _after(*_deps, task):
            return execute_task(task)

        submitted_futures: dict[str, Any] = {}

        # optional safety: fail fast when GPU tasks exist but no gpu workers are present
        if any(t.requires_gpu for t in tasks) and not self._has_resource('gpu'):
            logger.error("No workers with 'gpu' resource available; GPU tasks will fail to run.")

        # create a quick lookup for tasks that arrive in this batch
        remaining = {t.id: t for t in tasks}

        # keep looping until all submit or no progress (topological-like submit)
        while remaining:
            progressed = False
            for task_id, task in list(remaining.items()):
                # ensure all dependencies either already have futures or are completed
                unknown = [d for d in task.dependencies if d not in self.futures and d not in self.completed_tasks]
                if unknown:
                    continue

                dep_futs = [self.futures[d] for d in task.dependencies if d in self.futures]

                resources = {('gpu' if task.requires_gpu else 'cpu'): 1}

                submit_kwargs = {
                    'key': task.id,
                    'resources': resources,
                    'retries': 1,
                    'priority': getattr(task, 'priority', 0),
                    'pure': False,
                }

                fut = self.client.submit(
                    _after, *dep_futs,
                    task=task,  
                    **submit_kwargs
                )
                logger.debug(f'{fut=}, {submit_kwargs=}')

                self.futures[task.id] = fut
                self.pending_tasks[task.id] = task
                submitted_futures[task.id] = fut
                self.stats[task.type].submitted += 1
                self._start_times[task.id] = time.time()

                del remaining[task_id]
                progressed = True

            if not progressed:
                # still have tasks, but none could be submitted -> unresolved deps
                dangling = {tid: [d for d in t.dependencies if d not in self.futures and d not in self.completed_tasks]
                            for tid, t in remaining.items()}
                logger.error(f"Unresolvable dependencies for tasks: {dangling}")
                break

        return submitted_futures

    # --------------------------------- monitor -----------------------------------
    def monitor_progress(
        self,
        futures: dict[str, Any] | None = None,
        callback: Callable[[str, dict], None] | None = None,
        timeout: float | None = None,
    ) -> list[dict]:
        """monitor task completion with optional callback"""
        futures = futures or self.futures
        results: list[dict] = []

        for future in as_completed(futures.values(), timeout=timeout):
            task_id = getattr(future, "key", None)
            try:
                result = future.result()
                if isinstance(result, dict):
                    # prefer task_id from result if present
                    result_tid = result.get("task_id") or task_id
                else:
                    result_tid = task_id
                    result = {"task_id": task_id, "status": "success", "result": result}

                if result_tid:
                    task = self.pending_tasks.pop(result_tid, None)
                    self.completed_tasks[result_tid] = result  # store raw executor payload

                    # stats update
                    if task:
                        elapsed = time.time() - self._start_times.get(result_tid, time.time())
                        self.stats[task.type].total_time += max(0.0, elapsed)
                        if result.get("status") == "success":
                            self.stats[task.type].completed += 1
                        else:
                            self.stats[task.type].failed += 1

                    results.append(result)
                    if callback:
                        callback(result_tid, result)

            except Exception as e:  # execution failure uncaught by executor
                msg = str(e)
                logger.error(f"Task {task_id} failed: {msg}")
                # synthesize a failure record
                fail_id = task_id or "<unknown>"
                result = {"task_id": fail_id, "status": "error", "message": msg}
                self.completed_tasks[fail_id] = result
                task = self.pending_tasks.pop(fail_id, None)
                if task:
                    elapsed = time.time() - self._start_times.get(fail_id, time.time())
                    self.stats[task.type].total_time += max(0.0, elapsed)
                    self.stats[task.type].failed += 1
                results.append(result)
                if callback and fail_id:
                    callback(fail_id, result)

        return results

    # --------------------------------- status ------------------------------------
    def get_status(self) -> dict:
        """get current scheduler status"""
        try:
            n_workers = len(self.client.scheduler_info().get('workers', {}))
        except Exception:
            n_workers = 0

        return {
            'workers': n_workers,
            'pending': len(self.pending_tasks),
            'completed': len(self.completed_tasks),
            'stats': {
                task_type.value: {
                    'submitted': stats.submitted,
                    'completed': stats.completed,
                    'failed': stats.failed,
                    'success_rate': f"{stats.success_rate:.1%}",
                    'avg_time': f"{stats.avg_time:.1f}s",
                }
                for task_type, stats in self.stats.items()
                if stats.submitted > 0
            },
        }

    # --------------------------------- control -----------------------------------
    def cancel_pending(self) -> int:
        """cancel all pending tasks"""
        cancelled = 0
        for task_id, future in list(self.futures.items()):
            if task_id in self.pending_tasks:
                try:
                    future.cancel()
                    cancelled += 1
                except Exception:
                    pass
        self.pending_tasks.clear()
        return cancelled

    def cleanup(self) -> None:
        """cleanup resources"""
        try:
            self.cancel_pending()
        finally:
            try:
                self.client.close()
            except Exception:
                pass
