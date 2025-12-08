"""Tests for memory monitoring and management functionality."""

import gc
import time
from unittest.mock import Mock, patch

import pytest

from src.talk2me_ui.memory_monitor import (
    MemoryMonitor,
    check_memory_leaks,
    get_memory_stats,
    optimize_memory,
)


class TestMemoryMonitor:
    """Test cases for MemoryMonitor class."""

    def test_memory_monitor_initialization(self):
        """Test MemoryMonitor initialization."""
        monitor = MemoryMonitor(check_interval=1.0, leak_threshold=1000)
        assert monitor.check_interval == 1.0
        assert monitor.leak_threshold == 1000
        assert not monitor.monitoring
        assert monitor.monitor_thread is None

    def test_get_memory_stats(self):
        """Test getting memory statistics."""
        monitor = MemoryMonitor()
        stats = monitor.get_memory_stats()

        # Check that all expected fields are present
        expected_fields = [
            'total_memory', 'available_memory', 'used_memory', 'memory_percent',
            'process_memory', 'process_memory_percent', 'gc_stats', 'object_counts'
        ]

        for field in expected_fields:
            assert hasattr(stats, field), f"Missing field: {field}"

        # Check that values are reasonable
        assert stats.total_memory > 0
        assert stats.used_memory >= 0
        assert 0 <= stats.memory_percent <= 100
        assert stats.process_memory >= 0
        assert isinstance(stats.gc_stats, dict)
        assert isinstance(stats.object_counts, dict)

    def test_force_garbage_collection(self):
        """Test garbage collection functionality."""
        monitor = MemoryMonitor()

        # Create some garbage
        garbage = [object() for _ in range(1000)]
        del garbage

        # Force GC
        collected = monitor.force_garbage_collection()

        assert isinstance(collected, dict)
        assert len(collected) == 3  # Three GC generations

    def test_memory_leak_detection(self):
        """Test memory leak detection."""
        monitor = MemoryMonitor(leak_threshold=10)

        # Initially no leaks
        leaks = monitor.check_for_memory_leaks()
        assert isinstance(leaks, list)

        # Simulate leak by modifying baseline
        monitor.baseline_objects = {'test_object': 0}
        monitor._get_object_counts = Mock(return_value={'test_object': 100})

        leaks = monitor.check_for_memory_leaks()
        assert len(leaks) > 0
        assert 'test_object' in leaks[0]

    @patch('src.talk2me_ui.memory_monitor.time.sleep')
    def test_monitoring_loop(self, mock_sleep):
        """Test the monitoring loop."""
        monitor = MemoryMonitor(check_interval=0.1)

        # Start monitoring
        monitor.start_monitoring()
        assert monitor.monitoring

        # Let it run for a short time
        time.sleep(0.2)

        # Stop monitoring
        monitor.stop_monitoring()
        assert not monitor.monitoring

        # Check that stats were collected
        assert len(monitor.memory_history) > 0

    def test_memory_optimization(self):
        """Test memory optimization."""
        monitor = MemoryMonitor()

        # Should not raise any exceptions
        monitor.optimize_memory()

        # Check that GC was called
        # (This is implicit - if no exception, test passes)


class TestMemoryMonitorFunctions:
    """Test standalone memory monitor functions."""

    def test_get_memory_stats_function(self):
        """Test get_memory_stats function."""
        stats = get_memory_stats()

        expected_fields = [
            'total_memory', 'available_memory', 'used_memory', 'memory_percent',
            'process_memory', 'process_memory_percent', 'gc_stats', 'object_counts'
        ]

        for field in expected_fields:
            assert hasattr(stats, field), f"Missing field: {field}"

    def test_check_memory_leaks_function(self):
        """Test check_memory_leaks function."""
        leaks = check_memory_leaks()
        assert isinstance(leaks, list)

    def test_optimize_memory_function(self):
        """Test optimize_memory function."""
        # Should not raise any exceptions
        optimize_memory()


class TestMemoryTracker:
    """Test memory tracker context manager."""

    @patch('src.talk2me_ui.memory_monitor.MemoryMonitor')
    def test_memory_tracker_context(self, mock_monitor_class):
        """Test memory tracker context manager."""
        mock_monitor = Mock()
        # Create mock MemoryStats objects
        mock_start_stats = Mock()
        mock_start_stats.process_memory = 1000000
        mock_end_stats = Mock()
        mock_end_stats.process_memory = 1100000

        mock_monitor.get_memory_stats.side_effect = [mock_start_stats, mock_end_stats]
        mock_monitor_class.return_value = mock_monitor

        from src.talk2me_ui.memory_monitor import memory_tracker

        with memory_tracker("test_operation"):
            pass

        # Check that monitor methods were called
        assert mock_monitor.get_memory_stats.call_count == 2
        # Note: logger.info would be called but we can't easily test that
