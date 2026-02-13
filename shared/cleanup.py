"""
Cleanup utilities for managing temporary files, cache, and build artifacts.

Prevents disk space issues on EC2 instances by cleaning up:
- Cloned repositories (temp directories)
- Trivy vulnerability scan cache
- Docker build cache and dangling images
- Old log files
"""

import os
import shutil
import time
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
from shared.secure_logging import get_logger

logger = get_logger(__name__)


class CleanupManager:
    """Manages cleanup of temporary files and caches to prevent disk space issues."""

    def __init__(self):
        """Initialize cleanup manager."""
        self.project_root = Path(__file__).parent.parent
        self.trivy_cache_dir = self.project_root / ".trivy-cache"
        self.temp_repos_base = Path(os.path.join(os.path.expanduser("~"), ".deploymind", "temp_repos"))

    def cleanup_temp_repository(self, clone_path: str) -> bool:
        """
        Remove a cloned repository directory.

        Args:
            clone_path: Path to the cloned repository

        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            if os.path.exists(clone_path):
                shutil.rmtree(clone_path, ignore_errors=True)
                logger.info("Cleaned up temporary repository", path=clone_path)
                return True
            return True
        except Exception as e:
            logger.warning("Failed to cleanup repository", path=clone_path, error=str(e))
            return False

    def cleanup_trivy_cache(self, max_age_days: int = 7) -> dict:
        """
        Clean up old Trivy vulnerability scan cache files.

        Args:
            max_age_days: Delete cache files older than this many days

        Returns:
            Dict with cleanup stats (files_deleted, space_freed_mb)
        """
        stats = {"files_deleted": 0, "space_freed_mb": 0}

        try:
            if not self.trivy_cache_dir.exists():
                return stats

            cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)

            for root, dirs, files in os.walk(self.trivy_cache_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_stat = os.stat(file_path)
                        if file_stat.st_mtime < cutoff_time:
                            file_size_mb = file_stat.st_size / (1024 * 1024)
                            os.remove(file_path)
                            stats["files_deleted"] += 1
                            stats["space_freed_mb"] += file_size_mb
                    except Exception as e:
                        logger.warning("Failed to delete cache file", file=file_path, error=str(e))

            logger.info("Trivy cache cleanup complete", stats=stats)
            return stats

        except Exception as e:
            logger.error("Failed to cleanup Trivy cache", error=str(e))
            return stats

    def cleanup_docker_build_cache(self) -> dict:
        """
        Clean up Docker build cache and dangling images.

        Returns:
            Dict with cleanup stats (images_removed, space_freed_mb)
        """
        stats = {"images_removed": 0, "space_freed_mb": 0}

        try:
            import docker
            client = docker.from_env()

            # Remove dangling images (not tagged, not in use)
            dangling_images = client.images.list(filters={"dangling": True})
            for image in dangling_images:
                try:
                    size_mb = image.attrs.get("Size", 0) / (1024 * 1024)
                    client.images.remove(image.id, force=True)
                    stats["images_removed"] += 1
                    stats["space_freed_mb"] += size_mb
                except Exception as e:
                    logger.warning("Failed to remove dangling image", image_id=image.id, error=str(e))

            # Prune build cache
            client.images.prune(filters={"dangling": True})

            logger.info("Docker cleanup complete", stats=stats)
            return stats

        except Exception as e:
            logger.warning("Failed to cleanup Docker cache", error=str(e))
            return stats

    def cleanup_old_temp_repos(self, max_age_hours: int = 24) -> dict:
        """
        Clean up all temporary repository clones older than specified hours.

        Args:
            max_age_hours: Delete repos older than this many hours

        Returns:
            Dict with cleanup stats (repos_deleted, space_freed_mb)
        """
        stats = {"repos_deleted": 0, "space_freed_mb": 0}

        try:
            # Check common temp locations
            temp_locations = [
                self.temp_repos_base,
                Path(os.path.join(os.path.expanduser("~"), ".deploymind", "repos")),
                Path(os.path.join(os.path.expanduser("~"), "temp", "deploymind")),
            ]

            cutoff_time = time.time() - (max_age_hours * 60 * 60)

            for temp_location in temp_locations:
                if not temp_location.exists():
                    continue

                for repo_dir in temp_location.iterdir():
                    if not repo_dir.is_dir():
                        continue

                    try:
                        dir_stat = os.stat(repo_dir)
                        if dir_stat.st_mtime < cutoff_time:
                            # Calculate size
                            size_mb = sum(
                                f.stat().st_size for f in repo_dir.rglob("*") if f.is_file()
                            ) / (1024 * 1024)

                            shutil.rmtree(repo_dir, ignore_errors=True)
                            stats["repos_deleted"] += 1
                            stats["space_freed_mb"] += size_mb
                    except Exception as e:
                        logger.warning("Failed to cleanup repo", repo=str(repo_dir), error=str(e))

            logger.info("Temp repos cleanup complete", stats=stats)
            return stats

        except Exception as e:
            logger.error("Failed to cleanup temp repos", error=str(e))
            return stats

    def cleanup_all(
        self,
        trivy_cache_max_age_days: int = 7,
        temp_repos_max_age_hours: int = 24,
        cleanup_docker: bool = True
    ) -> dict:
        """
        Run all cleanup tasks.

        Args:
            trivy_cache_max_age_days: Max age for Trivy cache files
            temp_repos_max_age_hours: Max age for temp repository clones
            cleanup_docker: Whether to cleanup Docker build cache

        Returns:
            Combined stats from all cleanup operations
        """
        logger.info("Starting comprehensive cleanup")

        total_stats = {
            "trivy_cache": {},
            "temp_repos": {},
            "docker": {},
            "total_space_freed_mb": 0
        }

        # Cleanup Trivy cache
        total_stats["trivy_cache"] = self.cleanup_trivy_cache(trivy_cache_max_age_days)
        total_stats["total_space_freed_mb"] += total_stats["trivy_cache"].get("space_freed_mb", 0)

        # Cleanup temp repos
        total_stats["temp_repos"] = self.cleanup_old_temp_repos(temp_repos_max_age_hours)
        total_stats["total_space_freed_mb"] += total_stats["temp_repos"].get("space_freed_mb", 0)

        # Cleanup Docker (optional)
        if cleanup_docker:
            total_stats["docker"] = self.cleanup_docker_build_cache()
            total_stats["total_space_freed_mb"] += total_stats["docker"].get("space_freed_mb", 0)

        logger.info(
            "Comprehensive cleanup complete",
            total_space_freed_mb=round(total_stats["total_space_freed_mb"], 2)
        )

        return total_stats

    def get_disk_usage(self) -> dict:
        """
        Get current disk usage statistics.

        Returns:
            Dict with disk usage info
        """
        try:
            import psutil
            disk = psutil.disk_usage('/')

            return {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent_used": disk.percent
            }
        except ImportError:
            logger.warning("psutil not available, cannot get disk usage")
            return {}


# Global singleton
_cleanup_manager = None


def get_cleanup_manager() -> CleanupManager:
    """Get or create global CleanupManager instance."""
    global _cleanup_manager
    if _cleanup_manager is None:
        _cleanup_manager = CleanupManager()
    return _cleanup_manager
