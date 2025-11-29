#!/usr/bin/env python3
"""
Warmup script for TrendRadar

Checks if cached output exists for today and optionally runs a minimal crawl
to populate the cache for the chat interface.
"""

import os
import sys
import yaml
from datetime import datetime
from pathlib import Path


def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent


def load_warmup_config() -> dict:
    """Load warmup configuration."""
    config_path = get_project_root() / "config" / "warmup_config.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {
        "warmup": {
            "enabled": True,
            "max_platforms": 5,
            "skip_if_cached": True,
            "timeout": 300
        },
        "priority_platforms": ["spiegel", "theguardian", "heise", "reuters", "bbc"]
    }


def get_today_output_dirs() -> list[Path]:
    """Get possible output directory names for today."""
    output_root = get_project_root() / "output"
    today = datetime.now()
    
    # Different date formats used by the system
    date_formats = [
        today.strftime("%Y-%m-%d"),           # 2025-11-29
        today.strftime("%Y年%m月%d日"),        # 2025年11月29日
    ]
    
    return [output_root / fmt for fmt in date_formats]


def check_cached_output() -> tuple[bool, str]:
    """
    Check if cached output exists for today.
    
    Returns:
        Tuple of (has_cache, message)
    """
    output_root = get_project_root() / "output"
    
    if not output_root.exists():
        return False, "Output directory does not exist"
    
    today_dirs = get_today_output_dirs()
    
    for dir_path in today_dirs:
        if dir_path.exists():
            # Check if directory has actual content (txt files in txt/ subdirectory)
            txt_dir = dir_path / "txt"
            if txt_dir.exists():
                txt_files = list(txt_dir.glob("*.txt"))
                if txt_files:
                    # Check if files have content
                    total_size = sum(f.stat().st_size for f in txt_files)
                    if total_size > 0:
                        return True, f"Found {len(txt_files)} cached file(s) in {dir_path.name}/txt ({total_size:,} bytes)"
            
            # Also check for JSON files (alternative format)
            json_files = list(dir_path.glob("*.json"))
            if json_files:
                return True, f"Found {len(json_files)} cached JSON file(s) in {dir_path.name}"
    
    return False, "No cached output for today"


def get_platforms_to_crawl(config: dict) -> list[str]:
    """
    Get list of platforms to crawl for warmup.
    
    Returns:
        List of platform IDs
    """
    warmup_config = config.get("warmup", {})
    max_platforms = warmup_config.get("max_platforms", 5)
    priority_platforms = config.get("priority_platforms", [])
    
    # Load main config to get all platforms
    main_config_path = get_project_root() / "config" / "config.yaml"
    if main_config_path.exists():
        with open(main_config_path, "r", encoding="utf-8") as f:
            main_config = yaml.safe_load(f)
        all_platforms = [p["id"] for p in main_config.get("platforms", [])]
    else:
        all_platforms = priority_platforms
    
    # Start with priority platforms
    platforms = []
    for p in priority_platforms:
        if p in all_platforms and p not in platforms:
            platforms.append(p)
    
    # Fill remaining slots with other platforms
    for p in all_platforms:
        if p not in platforms:
            platforms.append(p)
    
    # Limit to max_platforms (0 means all)
    if max_platforms > 0:
        platforms = platforms[:max_platforms]
    
    return platforms


def run_warmup_crawl(platforms: list[str], timeout: int = 300) -> bool:
    """
    Run the warmup crawl for specified platforms.
    
    Args:
        platforms: List of platform IDs to crawl
        timeout: Timeout in seconds
        
    Returns:
        True if successful
    """
    print(f"🔥 Running warmup crawl for {len(platforms)} platform(s)...")
    print(f"   Platforms: {', '.join(platforms)}")
    
    # Import and run the main crawler
    sys.path.insert(0, str(get_project_root()))
    
    try:
        from main import DataFetcher, CONFIG, save_titles_to_file, ensure_directory_exists
        
        # Filter platforms to only those in the warmup list
        all_platforms = CONFIG.get("PLATFORMS", [])
        warmup_platforms = [p for p in all_platforms if p.get("id") in platforms]
        
        if not warmup_platforms:
            print("   ⚠️ No matching platforms found in configuration")
            return False
        
        print(f"   Found {len(warmup_platforms)} platform(s) in configuration")
        
        # Create data fetcher
        fetcher = DataFetcher(proxy_url=None, debug_mode=False)
        
        # Build IDs list for crawling
        ids = []
        for platform in warmup_platforms:
            if "crawler" in platform:
                ids.append(platform)
            elif "name" in platform:
                ids.append((platform["id"], platform["name"]))
            else:
                ids.append(platform["id"])
        
        # Ensure output directory exists
        ensure_directory_exists("output")
        
        # Crawl websites
        print("\n📡 Starting data crawl...")
        results, id_to_name, failed_ids = fetcher.crawl_websites(
            ids, 
            request_interval=CONFIG.get("REQUEST_INTERVAL", 1000)
        )
        
        # Save results to file
        if results:
            title_file = save_titles_to_file(results, id_to_name, failed_ids)
            print(f"\n📁 Data saved to: {title_file}")
        
        # Report summary
        success_count = len(results)
        fail_count = len(failed_ids)
        total_items = sum(len(items) for items in results.values())
        
        print(f"\n✅ Warmup crawl completed")
        print(f"   Successful: {success_count} platform(s)")
        print(f"   Failed: {fail_count} platform(s)")
        print(f"   Total items: {total_items}")
        
        if failed_ids:
            print(f"   Failed platforms: {', '.join(failed_ids)}")
        
        return success_count > 0
        
    except Exception as e:
        print(f"\n❌ Warmup crawl failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="TrendRadar warmup utility")
    parser.add_argument(
        "--check", "-c",
        action="store_true",
        help="Only check cache status, don't run warmup"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force warmup even if cache exists"
    )
    parser.add_argument(
        "--platforms", "-p",
        type=int,
        default=None,
        help="Override number of platforms to crawl"
    )
    parser.add_argument(
        "--list-platforms",
        action="store_true",
        help="List available platforms and exit"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_warmup_config()
    warmup_config = config.get("warmup", {})
    
    print("=" * 60)
    print("🔍 TrendRadar Warmup Utility")
    print("=" * 60)
    
    # Check cache status
    has_cache, cache_msg = check_cached_output()
    print(f"\n📦 Cache Status: {'✅ CACHED' if has_cache else '❌ NOT CACHED'}")
    print(f"   {cache_msg}")
    
    if args.list_platforms:
        platforms = get_platforms_to_crawl(config)
        print(f"\n📋 Platforms for warmup ({len(platforms)}):")
        for i, p in enumerate(platforms, 1):
            print(f"   {i}. {p}")
        return 0
    
    if args.check:
        return 0 if has_cache else 1
    
    # Determine if warmup should run
    should_run = False
    
    if args.force:
        should_run = True
        print("\n⚡ Force mode: Running warmup regardless of cache")
    elif not warmup_config.get("enabled", True):
        print("\n⏸️ Warmup is disabled in configuration")
        return 0
    elif has_cache and warmup_config.get("skip_if_cached", True):
        print("\n✅ Cache exists, skipping warmup")
        return 0
    else:
        should_run = True
    
    if should_run:
        # Override max_platforms if specified
        if args.platforms is not None:
            config["warmup"]["max_platforms"] = args.platforms
        
        platforms = get_platforms_to_crawl(config)
        timeout = warmup_config.get("timeout", 300)
        
        success = run_warmup_crawl(platforms, timeout)
        return 0 if success else 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
