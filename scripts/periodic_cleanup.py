#!/usr/bin/env python3
"""
Periodic cleanup script for EC2 instances.

Run this as a cron job to prevent disk space issues:
    # Run every 6 hours
    0 */6 * * * cd /path/to/deploymind && python scripts/periodic_cleanup.py

Cleans up:
- Old Trivy cache files (>7 days)
- Temporary repository clones (>24 hours)
- Docker dangling images and build cache
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.cleanup import get_cleanup_manager
from shared.secure_logging import get_logger

logger = get_logger(__name__)


def main():
    """Run periodic cleanup tasks."""
    print("=" * 70)
    print("DEPLOYMIND PERIODIC CLEANUP")
    print("=" * 70)
    print()

    cleanup_manager = get_cleanup_manager()

    # Get disk usage before cleanup
    print("📊 Current disk usage:")
    disk_usage = cleanup_manager.get_disk_usage()
    if disk_usage:
        print(f"   Total: {disk_usage['total_gb']} GB")
        print(f"   Used:  {disk_usage['used_gb']} GB ({disk_usage['percent_used']}%)")
        print(f"   Free:  {disk_usage['free_gb']} GB")
        print()

        # Warn if disk is >80% full
        if disk_usage['percent_used'] > 80:
            print("⚠️  WARNING: Disk usage is above 80%!")
            print()

    # Run comprehensive cleanup
    print("🧹 Running cleanup tasks...")
    print()

    stats = cleanup_manager.cleanup_all(
        trivy_cache_max_age_days=7,      # Keep cache for 7 days
        temp_repos_max_age_hours=24,     # Clean repos older than 24 hours
        cleanup_docker=True               # Clean Docker build cache
    )

    # Print results
    print("✅ Cleanup complete!")
    print()
    print("Results:")
    print(f"   Trivy cache:")
    print(f"     - Files deleted: {stats['trivy_cache'].get('files_deleted', 0)}")
    print(f"     - Space freed: {round(stats['trivy_cache'].get('space_freed_mb', 0), 2)} MB")
    print()
    print(f"   Temp repositories:")
    print(f"     - Repos deleted: {stats['temp_repos'].get('repos_deleted', 0)}")
    print(f"     - Space freed: {round(stats['temp_repos'].get('space_freed_mb', 0), 2)} MB")
    print()
    print(f"   Docker:")
    print(f"     - Images removed: {stats['docker'].get('images_removed', 0)}")
    print(f"     - Space freed: {round(stats['docker'].get('space_freed_mb', 0), 2)} MB")
    print()
    print(f"   📦 Total space freed: {round(stats['total_space_freed_mb'], 2)} MB")
    print()

    # Get disk usage after cleanup
    if disk_usage:
        disk_usage_after = cleanup_manager.get_disk_usage()
        if disk_usage_after:
            print("📊 Disk usage after cleanup:")
            print(f"   Used:  {disk_usage_after['used_gb']} GB ({disk_usage_after['percent_used']}%)")
            print(f"   Free:  {disk_usage_after['free_gb']} GB")
            print()

    print("=" * 70)

    logger.info("Periodic cleanup completed", stats=stats)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ ERROR: {e}")
        logger.error("Periodic cleanup failed", error=str(e), exc_info=True)
        sys.exit(1)
