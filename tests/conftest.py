"""Pytest configuration and fixtures."""

import gc
import os
import tempfile
from collections.abc import Generator

import pytest

# Set default environment variables for testing
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("LOG_LEVEL", "INFO")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("HOST", "localhost")
os.environ.setdefault("PORT", "8000")
os.environ.setdefault("WORKERS", "1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-for-testing-only")

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# Memory limits (in MB)
MAX_MEMORY_PER_TEST = 100  # Skip test if memory > this before starting
MAX_SESSION_MEMORY = 500  # Fail session if memory > this
MEMORY_CLEANUP_THRESHOLD = 50  # Force cleanup if increase > this per test

# Use cross-platform temporary file for memory log
memory_log_path = os.path.join(tempfile.gettempdir(), "memory_log.txt")

with open(memory_log_path, "w") as f:
    f.write("conftest loaded\n")


def pytest_configure(config):
    """Configure pytest with memory monitoring."""
    config.addinivalue_line("markers", "memory_heavy: mark test as memory intensive")


@pytest.fixture(scope="session", autouse=True)
def memory_monitor() -> Generator[None, None, None]:
    """Monitor memory usage during test session."""
    if not HAS_PSUTIL:
        with open(memory_log_path, "a") as f:
            f.write("psutil not available, skipping memory monitoring\n")
        yield
        return

    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    with open(memory_log_path, "a") as f:
        f.write("\n=== Memory Monitor ===\n")
        f.write(f"Initial memory: {initial_memory:.1f} MB\n")

    yield

    # Force garbage collection
    gc.collect()

    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory

    with open(memory_log_path, "a") as f:
        f.write(f"Final memory: {final_memory:.1f} MB\n")
        f.write(f"Memory increase: {memory_increase:.1f} MB\n")
        f.write("===================\n")


@pytest.fixture(autouse=True)
def per_test_memory(request) -> Generator[None, None, None]:
    """Monitor memory per test and enforce limits."""
    if not HAS_PSUTIL:
        yield
        return

    process = psutil.Process(os.getpid())
    start_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Check if memory is already too high before starting test
    if start_memory > MAX_MEMORY_PER_TEST and not request.node.get_closest_marker("memory_heavy"):
        pytest.skip(f"Skipping test due to high memory usage: {start_memory:.1f} MB")

    yield

    end_memory = process.memory_info().rss / 1024 / 1024  # MB
    increase = end_memory - start_memory

    # Force cleanup if memory increase is too high
    if increase > MEMORY_CLEANUP_THRESHOLD:
        gc.collect()
        with open(memory_log_path, "a") as f:
            f.write(f"Forced GC after test {request.node.name}: {increase:.1f} MB increase\n")

    if increase > 10:  # Log if increase > 10MB
        with open(memory_log_path, "a") as f:
            f.write(f"Memory increase in test {request.node.name}: {increase:.1f} MB\n")


@pytest.fixture(autouse=True, scope="session")
def memory_limit_check():
    """Check total session memory and fail if exceeded."""
    if not HAS_PSUTIL:
        yield
        return

    process = psutil.Process(os.getpid())

    def check_memory():
        current = process.memory_info().rss / 1024 / 1024  # MB
        if current > MAX_SESSION_MEMORY:
            pytest.fail(
                f"Session memory limit exceeded: {current:.1f} MB > {MAX_SESSION_MEMORY} MB"
            )

    # Check at the end of session
    yield
    check_memory()
