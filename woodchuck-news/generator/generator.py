"""
Woodchuck News - Static Site Generator

Fetches headlines from TrendRadar MCP API and generates static HTML pages
organized by date, region, and language.
"""

import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from jinja2 import Environment, FileSystemLoader
from slugify import slugify

# Configuration
MCP_API_URL = os.getenv("MCP_API_URL", "http://localhost:3333")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/app/output"))
TEMPLATES_DIR = Path(os.getenv("TEMPLATES_DIR", "/app/templates"))
STATIC_DIR = Path(os.getenv("STATIC_DIR", "/app/static"))

# Region mapping based on platform origins
REGION_MAPPING = {
    # Europe
    "spiegel": "europe",
    "taz": "europe",
    "heise": "europe",
    "golem": "europe",
    "bbc": "europe",
    "guardian": "europe",
    "telegraph": "europe",
    "elpais": "europe",
    "elpais_mexico": "americas",  # México override
    "reuters": "europe",  # HQ in London
    
    # Eurasia (Russia, Israel, Turkey, etc.)
    "timesofisrael": "eurasia",
    "rt": "eurasia",
    "tass": "eurasia",
    "ria": "eurasia",
    "interfax": "eurasia",
    "dailysabah": "eurasia",
    "hurriyetdailynews": "eurasia",
    
    # Asia
    "china_daily": "asia",
    "xinhua": "asia",
    "peoples_daily": "asia",
    "scmp": "asia",
    "asahi": "asia",
    "nikkei": "asia",
    "japantimes": "asia",
    "yomiuri": "asia",
    "chosun": "asia",
    "joongang": "asia",
    "koreaherald": "asia",
    "koreatimes": "asia",
    "channelnewsasia": "asia",
    "straitstimes": "asia",
    
    # Middle East
    "aljazeera": "middle_east",
    
    # Americas
    "nytimes": "americas",
    "washingtonpost": "americas",
    "cnn": "americas",
    "fox": "americas",
    "latimes": "americas",
    "abcnews": "americas",
    
    # Oceania
    "abc_au": "oceania",
    "smh": "oceania",
}

# Region display names
REGION_NAMES = {
    "europe": "Europe",
    "eurasia": "Eurasia",
    "asia": "Asia-Pacific",
    "middle_east": "Middle East",
    "americas": "Americas",
    "oceania": "Oceania",
    "africa": "Africa",
}

# Language display names
LANGUAGE_NAMES = {
    "zh": "中文 (Chinese)",
    "en": "English",
    "de": "Deutsch (German)",
    "ja": "日本語 (Japanese)",
    "ko": "한국어 (Korean)",
    "es": "Español (Spanish)",
    "ar": "العربية (Arabic)",
}


class WoodchuckGenerator:
    """Generates static HTML pages from TrendRadar headlines."""
    
    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True
        )
        self.headlines: list[dict] = []
        
    def fetch_headlines(self, date: str | None = None) -> list[dict]:
        """Fetch headlines from MCP API."""
        try:
            params = {}
            if date:
                params["date"] = date
                
            response = requests.get(
                f"{MCP_API_URL}/api/headlines",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get("headlines", [])
        except requests.RequestException as e:
            print(f"Error fetching headlines: {e}")
            return []
    
    def fetch_output_folder(self, date_folder: str) -> list[dict]:
        """
        Alternative: Read headlines directly from TrendRadar output folder.
        Parses the txt files which contain platform headlines.
        """
        # Try multiple possible paths
        possible_paths = [
            Path("/trendradar/output") / date_folder,  # Docker volume mount
            Path(os.getenv("TRENDRADAR_OUTPUT", "")) / date_folder,
            Path(__file__).parent.parent.parent / "output" / date_folder,  # Local dev
        ]
        
        output_path = None
        for p in possible_paths:
            if p.exists():
                output_path = p
                break
        
        headlines = []
        
        if not output_path:
            print(f"Output folder not found for: {date_folder}")
            return headlines
        
        print(f"Reading from: {output_path}")
        
        # Read from txt subfolder
        txt_path = output_path / "txt"
        if txt_path.exists():
            for txt_file in txt_path.glob("*.txt"):
                try:
                    headlines.extend(self._parse_txt_file(txt_file, date_folder))
                except Exception as e:
                    print(f"Error reading {txt_file}: {e}")
        
        return headlines
    
    def _parse_txt_file(self, filepath: Path, date_str: str) -> list[dict]:
        """Parse a TrendRadar txt output file into headline dicts."""
        headlines = []
        current_platform = None
        current_platform_name = None
        
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        lines = content.strip().split("\n")
        headline_id = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Platform header: "heise | Heise Online"
            if "|" in line and not line[0].isdigit():
                parts = line.split("|", 1)
                current_platform = parts[0].strip().lower().replace(" ", "_")
                current_platform_name = parts[1].strip() if len(parts) > 1 else current_platform
                continue
            
            # Headline: "1. Title [URL:http://...]"
            if line[0].isdigit() and ". " in line:
                # Extract rank
                rank_end = line.index(". ")
                rank = int(line[:rank_end])
                rest = line[rank_end + 2:]
                
                # Extract URL if present
                url = ""
                title = rest
                if "[URL:" in rest:
                    url_start = rest.index("[URL:")
                    url_end = rest.rindex("]")
                    url = rest[url_start + 5:url_end]
                    title = rest[:url_start].strip()
                
                headline_id += 1
                headlines.append({
                    "id": headline_id,
                    "title": title,
                    "url": url,
                    "platform": current_platform or "unknown",
                    "platform_name": current_platform_name or "Unknown",
                    "rank": rank,
                    "timestamp": f"{date_str}T00:00:00Z",
                    "language": self._detect_language(current_platform),
                })
        
        return headlines
    
    def _detect_language(self, platform: str) -> str:
        """Detect language based on platform."""
        lang_map = {
            # German
            "spiegel": "de", "taz": "de", "heise": "de", "golem": "de",
            # Chinese
            "china_daily": "zh", "xinhua": "zh", "peoples_daily": "zh", "scmp": "en",
            # Japanese
            "asahi": "ja", "nikkei": "ja", "japantimes": "en", "yomiuri": "ja",
            # Korean
            "chosun": "ko", "joongang": "ko", "koreaherald": "en", "koreatimes": "en",
            # Spanish
            "elpais": "es", "elpais_mexico": "es",
            # Arabic
            "aljazeera": "ar",
        }
        return lang_map.get(platform, "en")
    
    def enrich_headline(self, headline: dict) -> dict:
        """Add computed fields to headline."""
        platform = headline.get("platform", "unknown")
        title = headline.get("title", "Untitled")
        
        # Generate slug from title
        headline["slug"] = slugify(title, max_length=60)
        
        # Add region
        headline["region"] = REGION_MAPPING.get(platform, "other")
        headline["region_name"] = REGION_NAMES.get(headline["region"], "Other")
        
        # Add language display name
        lang = headline.get("language", "en")
        headline["language_name"] = LANGUAGE_NAMES.get(lang, lang.upper())
        
        # Parse timestamp
        timestamp = headline.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                headline["date"] = dt.strftime("%Y-%m-%d")
                headline["time"] = dt.strftime("%H:%M")
                headline["datetime_display"] = dt.strftime("%B %d, %Y at %H:%M UTC")
            except ValueError:
                headline["date"] = datetime.now().strftime("%Y-%m-%d")
                headline["time"] = "00:00"
        
        return headline
    
    def group_headlines(self, headlines: list[dict]) -> dict:
        """Group headlines by various criteria."""
        grouped = {
            "by_date": {},
            "by_region": {},
            "by_language": {},
            "by_platform": {},
        }
        
        for h in headlines:
            # By date
            date = h.get("date", "unknown")
            if date not in grouped["by_date"]:
                grouped["by_date"][date] = []
            grouped["by_date"][date].append(h)
            
            # By region
            region = h.get("region", "other")
            if region not in grouped["by_region"]:
                grouped["by_region"][region] = []
            grouped["by_region"][region].append(h)
            
            # By language
            lang = h.get("language", "en")
            if lang not in grouped["by_language"]:
                grouped["by_language"][lang] = []
            grouped["by_language"][lang].append(h)
            
            # By platform
            platform = h.get("platform", "unknown")
            if platform not in grouped["by_platform"]:
                grouped["by_platform"][platform] = []
            grouped["by_platform"][platform].append(h)
            
        return grouped
    
    def generate_index(self, headlines: list[dict], grouped: dict):
        """Generate main index page."""
        template = self.env.get_template("index.html")
        
        # Get recent headlines (last 50)
        recent = sorted(
            headlines,
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )[:50]
        
        html = template.render(
            headlines=recent,
            grouped=grouped,
            regions=REGION_NAMES,
            languages=LANGUAGE_NAMES,
            generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        )
        
        output_file = OUTPUT_DIR / "index.html"
        output_file.write_text(html, encoding="utf-8")
        print(f"Generated: {output_file}")
    
    def generate_date_pages(self, grouped: dict):
        """Generate pages for each date."""
        template = self.env.get_template("date.html")
        
        for date, headlines in grouped["by_date"].items():
            # Sort by timestamp
            headlines = sorted(
                headlines,
                key=lambda x: x.get("timestamp", ""),
                reverse=True
            )
            
            html = template.render(
                date=date,
                headlines=headlines,
                total_count=len(headlines),
                regions=REGION_NAMES,
                generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            )
            
            # Create date directory
            date_dir = OUTPUT_DIR / "news" / date
            date_dir.mkdir(parents=True, exist_ok=True)
            
            output_file = date_dir / "index.html"
            output_file.write_text(html, encoding="utf-8")
            print(f"Generated: {output_file}")
            
            # Generate individual article pages
            self.generate_article_pages(headlines, date_dir)
    
    def generate_article_pages(self, headlines: list[dict], date_dir: Path):
        """Generate individual article pages."""
        template = self.env.get_template("article.html")
        
        for h in headlines:
            slug = h.get("slug", "untitled")
            headline_id = h.get("id", hash(h.get("title", "")))
            
            html = template.render(
                headline=h,
                generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            )
            
            # Create article page: /news/2025-11-29/slug-id.html
            output_file = date_dir / f"{slug}-{headline_id}.html"
            output_file.write_text(html, encoding="utf-8")
    
    def generate_region_pages(self, grouped: dict):
        """Generate pages for each region."""
        template = self.env.get_template("region.html")
        
        for region, headlines in grouped["by_region"].items():
            headlines = sorted(
                headlines,
                key=lambda x: x.get("timestamp", ""),
                reverse=True
            )
            
            html = template.render(
                region=region,
                region_name=REGION_NAMES.get(region, region.title()),
                headlines=headlines,
                total_count=len(headlines),
                generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            )
            
            region_dir = OUTPUT_DIR / "region" / region
            region_dir.mkdir(parents=True, exist_ok=True)
            
            output_file = region_dir / "index.html"
            output_file.write_text(html, encoding="utf-8")
            print(f"Generated: {output_file}")
    
    def generate_language_pages(self, grouped: dict):
        """Generate pages for each language."""
        template = self.env.get_template("language.html")
        
        for lang, headlines in grouped["by_language"].items():
            headlines = sorted(
                headlines,
                key=lambda x: x.get("timestamp", ""),
                reverse=True
            )
            
            html = template.render(
                language=lang,
                language_name=LANGUAGE_NAMES.get(lang, lang.upper()),
                headlines=headlines,
                total_count=len(headlines),
                generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            )
            
            lang_dir = OUTPUT_DIR / "language" / lang
            lang_dir.mkdir(parents=True, exist_ok=True)
            
            output_file = lang_dir / "index.html"
            output_file.write_text(html, encoding="utf-8")
            print(f"Generated: {output_file}")
    
    def generate_source_pages(self, grouped: dict):
        """Generate pages for each source/platform and a source index."""
        # Generate source index page
        source_index_template = self.env.get_template("sources_index.html")
        
        # Group sources by region for the tree view
        sources_by_region = {}
        for platform, headlines in grouped["by_platform"].items():
            if headlines:
                region = headlines[0].get("region", "other")
                if region not in sources_by_region:
                    sources_by_region[region] = []
                sources_by_region[region].append({
                    "id": platform,
                    "name": headlines[0].get("platform_name", platform),
                    "count": len(headlines),
                    "language": headlines[0].get("language", "en"),
                })
        
        # Sort sources within each region by count
        for region in sources_by_region:
            sources_by_region[region].sort(key=lambda x: x["count"], reverse=True)
        
        html = source_index_template.render(
            sources_by_region=sources_by_region,
            regions=REGION_NAMES,
            total_sources=len(grouped["by_platform"]),
            generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        )
        
        source_dir = OUTPUT_DIR / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = source_dir / "index.html"
        output_file.write_text(html, encoding="utf-8")
        print(f"Generated: {output_file}")
        
        # Generate individual source pages
        source_template = self.env.get_template("source.html")
        
        for platform, headlines in grouped["by_platform"].items():
            headlines = sorted(
                headlines,
                key=lambda x: x.get("timestamp", ""),
                reverse=True
            )
            
            platform_name = headlines[0].get("platform_name", platform) if headlines else platform
            region = headlines[0].get("region", "other") if headlines else "other"
            language = headlines[0].get("language", "en") if headlines else "en"
            
            html = source_template.render(
                source_id=platform,
                source_name=platform_name,
                region=region,
                region_name=REGION_NAMES.get(region, region.title()),
                language=language,
                language_name=LANGUAGE_NAMES.get(language, language.upper()),
                headlines=headlines,
                total_count=len(headlines),
                generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            )
            
            platform_dir = source_dir / platform
            platform_dir.mkdir(parents=True, exist_ok=True)
            
            output_file = platform_dir / "index.html"
            output_file.write_text(html, encoding="utf-8")
    
    def copy_static_assets(self):
        """Copy static assets to output directory."""
        if STATIC_DIR.exists():
            dest = OUTPUT_DIR / "static"
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(STATIC_DIR, dest)
            print(f"Copied static assets to: {dest}")
    
    def generate(self, date: str | None = None):
        """Main generation method."""
        print(f"🦫 Woodchuck News Generator starting...")
        print(f"   MCP API: {MCP_API_URL}")
        print(f"   Output:  {OUTPUT_DIR}")
        
        # Ensure output directory exists
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        # Determine dates to process
        if date:
            dates_to_process = [date]
        else:
            # Process last 7 days
            today = datetime.now()
            dates_to_process = [
                (today - timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(7)
            ]
        
        # Fetch headlines from all dates
        all_headlines = []
        for d in dates_to_process:
            print(f"📅 Processing date: {d}")
            
            # Try API first
            headlines = self.fetch_headlines(d)
            
            # Fallback to output folder if API returns nothing
            if not headlines:
                print(f"   API returned no data, trying output folder...")
                headlines = self.fetch_output_folder(d)
            
            if headlines:
                print(f"   Found {len(headlines)} headlines")
                all_headlines.extend(headlines)
            else:
                print(f"   No headlines found")
        
        self.headlines = all_headlines
        print(f"📰 Total: {len(self.headlines)} headlines")
        
        if not self.headlines:
            print("❌ No headlines available. Exiting.")
            return
        
        # Enrich headlines
        self.headlines = [self.enrich_headline(h) for h in self.headlines]
        
        # Group headlines
        grouped = self.group_headlines(self.headlines)
        
        # Generate pages
        print("🔨 Generating static pages...")
        self.generate_index(self.headlines, grouped)
        self.generate_date_pages(grouped)
        self.generate_region_pages(grouped)
        self.generate_language_pages(grouped)
        self.generate_source_pages(grouped)
        
        # Copy static assets
        self.copy_static_assets()
        
        print(f"✅ Generation complete! Output: {OUTPUT_DIR}")


def main():
    """Entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Woodchuck News Static Site Generator"
    )
    parser.add_argument(
        "--date",
        help="Generate for specific date (YYYY-MM-DD)",
        default=None
    )
    parser.add_argument(
        "--output",
        help="Output directory",
        default=None
    )
    
    args = parser.parse_args()
    
    if args.output:
        global OUTPUT_DIR
        OUTPUT_DIR = Path(args.output)
    
    generator = WoodchuckGenerator()
    generator.generate(date=args.date)


if __name__ == "__main__":
    main()
