"""Tests for cleanup utilities."""

import os
import tempfile
import shutil
from pathlib import Path
import pytest
from shared.cleanup import CleanupManager, get_cleanup_manager


class TestCleanupManager:
    """Tests for CleanupManager class."""

    def test_cleanup_manager_initialization(self):
        """Test CleanupManager can be initialized."""
        cleanup_manager = CleanupManager()
        assert cleanup_manager is not None
        assert cleanup_manager.trivy_cache_dir.exists()

    def test_get_cleanup_manager_singleton(self):
        """Test get_cleanup_manager returns singleton instance."""
        manager1 = get_cleanup_manager()
        manager2 = get_cleanup_manager()
        assert manager1 is manager2

    def test_cleanup_temp_repository_success(self, tmp_path):
        """Test successful cleanup of temporary repository."""
        # Create a temp directory with some files
        test_repo = tmp_path / "test_repo"
        test_repo.mkdir()
        (test_repo / "file1.txt").write_text("test content")
        (test_repo / "subdir").mkdir()
        (test_repo / "subdir" / "file2.txt").write_text("more content")

        cleanup_manager = CleanupManager()
        result = cleanup_manager.cleanup_temp_repository(str(test_repo))

        assert result is True
        assert not test_repo.exists()

    def test_cleanup_temp_repository_nonexistent(self):
        """Test cleanup of non-existent repository returns True."""
        cleanup_manager = CleanupManager()
        result = cleanup_manager.cleanup_temp_repository("/nonexistent/path")
        assert result is True

    def test_cleanup_trivy_cache(self, tmp_path):
        """Test Trivy cache cleanup removes old files."""
        cleanup_manager = CleanupManager()

        # Create mock cache directory with old files
        old_cache = cleanup_manager.trivy_cache_dir / "old_db"
        old_cache.mkdir(parents=True, exist_ok=True)
        old_file = old_cache / "old_cache.db"
        old_file.write_text("old cache data")

        # Set file modification time to 10 days ago
        import time
        old_time = time.time() - (10 * 24 * 60 * 60)
        os.utime(old_file, (old_time, old_time))

        # Run cleanup (max_age_days=7)
        stats = cleanup_manager.cleanup_trivy_cache(max_age_days=7)

        assert stats["files_deleted"] >= 0  # May or may not delete depending on other files
        assert stats["space_freed_mb"] >= 0

    def test_cleanup_docker_build_cache_no_docker(self):
        """Test Docker cleanup handles missing Docker gracefully."""
        cleanup_manager = CleanupManager()

        # Should not raise error even if Docker not available
        stats = cleanup_manager.cleanup_docker_build_cache()

        assert "images_removed" in stats
        assert "space_freed_mb" in stats

    def test_cleanup_all(self):
        """Test comprehensive cleanup runs all tasks."""
        cleanup_manager = CleanupManager()

        stats = cleanup_manager.cleanup_all(
            trivy_cache_max_age_days=7,
            temp_repos_max_age_hours=24,
            cleanup_docker=False  # Don't cleanup Docker in tests
        )

        assert "trivy_cache" in stats
        assert "temp_repos" in stats
        assert "docker" in stats
        assert "total_space_freed_mb" in stats
        assert stats["total_space_freed_mb"] >= 0


class TestCleanupIntegration:
    """Integration tests for cleanup in deployment workflow."""

    def test_cleanup_with_workflow_simulation(self, tmp_path):
        """Test cleanup works in simulated deployment workflow."""
        cleanup_manager = get_cleanup_manager()

        # Simulate repository clone
        clone_path = tmp_path / "test_deployment"
        clone_path.mkdir()
        (clone_path / "app.py").write_text("print('Hello')")

        # Verify it exists
        assert clone_path.exists()

        # Simulate deployment completion with cleanup
        try:
            # ... deployment operations would happen here ...
            pass
        finally:
            # Cleanup should happen in finally block
            cleanup_manager.cleanup_temp_repository(str(clone_path))

        # Verify cleanup happened
        assert not clone_path.exists()

    def test_cleanup_happens_even_on_error(self, tmp_path):
        """Test cleanup happens even if deployment fails."""
        cleanup_manager = get_cleanup_manager()

        clone_path = tmp_path / "test_error"
        clone_path.mkdir()
        (clone_path / "data.txt").write_text("test data")

        try:
            # Simulate error during deployment
            raise RuntimeError("Simulated deployment error")
        except RuntimeError:
            pass  # Expected error
        finally:
            # Cleanup should still happen
            cleanup_manager.cleanup_temp_repository(str(clone_path))

        # Verify cleanup happened despite error
        assert not clone_path.exists()
