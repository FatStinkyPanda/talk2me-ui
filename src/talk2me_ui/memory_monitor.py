"""Memory monitoring and management utilities for Talk2Me UI.

This module provides comprehensive memory monitoring, leak detection,
and memory optimization features for the application.
"""

import gc
import logging
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from weakref import WeakSet

import prometheus_client as prom
import psutil

logger = logging.getLogger(__name__)

# Prometheus metrics for memory monitoring
memory_usage_gauge = prom.Gauge("memory_usage_bytes", "Current memory usage in bytes", ["type"])

memory_peak_gauge = prom.Gauge("memory_peak_bytes", "Peak memory usage in bytes", ["type"])

gc_collections_counter = prom.Counter(
    "gc_collections_total", "Total garbage collections by generation", ["generation"]
)

object_count_gauge = prom.Gauge(
    "python_object_count", "Number of Python objects by type", ["object_type"]
)

memory_leaks_detected = prom.Counter(
    "memory_leaks_detected_total", "Number of memory leaks detected"
)


@dataclass
class MemoryStats:
    """Memory statistics snapshot."""

    total_memory: int
    available_memory: int
    used_memory: int
    memory_percent: float
    process_memory: int
    process_memory_percent: float
    gc_stats: dict[int, int]
    object_counts: dict[str, int]


class MemoryMonitor:
    """Advanced memory monitoring and management system."""

    def __init__(self, check_interval: float = 60.0, leak_threshold: int = 1000000):
        self.check_interval = check_interval
        self.leak_threshold = leak_threshold
        self.monitoring = False
        self.monitor_thread: threading.Thread | None = None
        self.baseline_objects: dict[str, int] = {}
        self.object_trackers: WeakSet = WeakSet()
        self.memory_history: list[MemoryStats] = []
        self.max_history_size = 100

    def start_monitoring(self) -> None:
        """Start the memory monitoring system."""
        if self.monitoring:
            return

        self.monitoring = True
        self.baseline_objects = self._get_object_counts()
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="MemoryMonitor"
        )
        self.monitor_thread.start()
        logger.info("Memory monitoring started")

    def stop_monitoring(self) -> None:
        """Stop the memory monitoring system."""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        logger.info("Memory monitoring stopped")

    def get_memory_stats(self) -> MemoryStats:
        """Get current memory statistics."""
        # System memory
        mem = psutil.virtual_memory()
        total_memory = mem.total
        available_memory = mem.available
        used_memory = mem.used
        memory_percent = mem.percent

        # Process memory
        process = psutil.Process()
        process_memory = process.memory_info().rss
        process_memory_percent = (process_memory / total_memory) * 100

        # GC stats
        gc_stats = {}
        for gen in range(3):
            gc_stats[gen] = gc.get_stats()[gen]["collected"]

        # Object counts
        object_counts = self._get_object_counts()

        return MemoryStats(
            total_memory=total_memory,
            available_memory=available_memory,
            used_memory=used_memory,
            memory_percent=memory_percent,
            process_memory=process_memory,
            process_memory_percent=process_memory_percent,
            gc_stats=gc_stats,
            object_counts=object_counts,
        )

    def check_for_memory_leaks(self) -> list[str]:
        """Check for potential memory leaks by comparing object counts."""
        current_objects = self._get_object_counts()
        leaks = []

        for obj_type, current_count in current_objects.items():
            baseline_count = self.baseline_objects.get(obj_type, 0)
            if current_count - baseline_count > self.leak_threshold:
                leak_info = (
                    f"Potential leak in {obj_type}: {current_count - baseline_count} more objects"
                )
                leaks.append(leak_info)
                memory_leaks_detected.inc()

        return leaks

    def force_garbage_collection(self) -> dict[str, int]:
        """Force garbage collection and return collection statistics."""
        collected = {}
        for gen in range(3):
            collected[gen] = gc.collect(gen)
            gc_collections_counter.labels(generation=str(gen)).inc(collected[gen])

        logger.info(f"Garbage collection completed: {collected}")
        return collected

    def optimize_memory(self) -> None:
        """Perform memory optimization operations."""
        # Force garbage collection
        self.force_garbage_collection()

        # Clear any cached objects
        gc.collect()

        # Update Prometheus metrics
        stats = self.get_memory_stats()
        memory_usage_gauge.labels(type="system").set(stats.used_memory)
        memory_usage_gauge.labels(type="process").set(stats.process_memory)

        # Track peak memory usage
        if self.memory_history:
            peak_system = max(s.used_memory for s in self.memory_history)
            peak_process = max(s.process_memory for s in self.memory_history)
            memory_peak_gauge.labels(type="system").set(peak_system)
            memory_peak_gauge.labels(type="process").set(peak_process)

        logger.info("Memory optimization completed")

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self.monitoring:
            try:
                # Get current stats
                stats = self.get_memory_stats()
                self.memory_history.append(stats)

                # Keep history size manageable
                if len(self.memory_history) > self.max_history_size:
                    self.memory_history.pop(0)

                # Check for memory leaks periodically
                if len(self.memory_history) % 10 == 0:  # Every 10 minutes
                    leaks = self.check_for_memory_leaks()
                    if leaks:
                        logger.warning(f"Memory leaks detected: {leaks}")

                # Update Prometheus metrics
                memory_usage_gauge.labels(type="system").set(stats.used_memory)
                memory_usage_gauge.labels(type="process").set(stats.process_memory)

                # Update object count metrics
                for obj_type, count in stats.object_counts.items():
                    object_count_gauge.labels(object_type=obj_type).set(count)

            except Exception as e:
                logger.error(f"Error in memory monitoring loop: {e}")

            time.sleep(self.check_interval)

    def _get_object_counts(self) -> dict[str, int]:
        """Get counts of Python objects by type."""
        objects = defaultdict(int)
        for obj in gc.get_objects():
            obj_type = type(obj).__name__
            objects[obj_type] += 1
        return dict(objects)


@contextmanager
def memory_tracker(name: str = "operation"):
    """Context manager to track memory usage of operations."""
    monitor = MemoryMonitor()
    start_stats = monitor.get_memory_stats()

    try:
        yield
    finally:
        end_stats = monitor.get_memory_stats()
        memory_delta = end_stats.process_memory - start_stats.process_memory

        logger.info(
            f"Memory usage for {name}: "
            f"start={start_stats.process_memory}, "
            f"end={end_stats.process_memory}, "
            f"delta={memory_delta}"
        )


# Global memory monitor instance
memory_monitor = MemoryMonitor()


def get_memory_monitor() -> MemoryMonitor:
    """Get the global memory monitor instance."""
    return memory_monitor


def start_memory_monitoring() -> None:
    """Start the global memory monitoring system."""
    memory_monitor.start_monitoring()


def stop_memory_monitoring() -> None:
    """Stop the global memory monitoring system."""
    memory_monitor.stop_monitoring()


def get_memory_stats() -> MemoryStats:
    """Get current memory statistics."""
    return memory_monitor.get_memory_stats()


def check_memory_leaks() -> list[str]:
    """Check for memory leaks."""
    return memory_monitor.check_for_memory_leaks()


def optimize_memory() -> None:
    """Optimize memory usage."""
    memory_monitor.optimize_memory()
