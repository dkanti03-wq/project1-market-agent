"""Market & Competitor Intelligence Crawler Module for NovaFactory AI."""

import os
import re
import csv
import logging
import datetime
import urllib.parse
from typing import List, Dict, Any, Tuple
import yaml
import feedparser
import requests
from bs4 import BeautifulSoup
import pandas as pd

# 로그 설정
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "crawler_run.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MarketCrawler")


def clean_html(raw_html: str) -> str:
    """HTML 태그 제거 및 텍스트 정제."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_date(date_str: str) -> str:
    """날짜 문자열을 YYYY-MM-DD 형식으로 변환."""
    if not date_str:
        return datetime.date.today().isoformat()
    try:
        # RFC 2822 / ISO parsing fallback
        import email.utils
        parsed_tuple = email.utils.parsedate_tz(date_str)
        if parsed_tuple:
            dt = datetime.datetime.fromtimestamp(email.utils.mktime_tz(parsed_tuple))
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    
    # 정규식으로 YYYY-MM-DD 또는 YYYY.MM.DD 매칭
    match = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", date_str)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    
    return datetime.date.today().isoformat()


class MarketCrawler:
    def __init__(self, config_path: str = "config/company_profile.yaml", fallback_path: str = "data/fallback/fallback_market_news.csv"):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.base_dir, config_path)
        self.fallback_path = os.path.join(self.base_dir, fallback_path)
        self.raw_data_dir = os.path.join(self.base_dir, "data", "raw")
        os.makedirs(self.raw_data_dir, exist_ok=True)
        
        self.output_csv = os.path.join(self.raw_data_dir, "crawled_market_news.csv")
        self.profile = self._load_profile()
        self.failed_sources: List[Dict[str, str]] = []
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def _load_profile(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file not found at {self.config_path}. Using default profile.")
            return {
                "company_name": "NovaFactory AI",
                "interest_keywords": ["스마트팩토리", "품질검사", "AI", "머신비전", "자동화"],
                "competitors": ["VisionForge", "InspectAI", "FactoryMind"],
                "funding_keywords": ["AI 바우처", "스마트공장", "창업지원", "R&D"]
            }
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _build_feed_sources(self) -> List[Dict[str, Any]]:
        """수집 대상 RSS 및 소스 목록 구성."""
        sources = []
        
        # 1. Google News RSS: 관심 키워드 및 시장 동향
        for kw in self.profile.get("interest_keywords", ["스마트팩토리", "품질검사", "제조 AI"]):
            query = f"{kw} 제조업"
            encoded_q = urllib.parse.quote(query)
            sources.append({
                "name": f"Google News - {kw}",
                "category": "market",
                "type": "rss",
                "url": f"https://news.google.com/rss/search?q={encoded_q}&hl=ko&gl=KR&ceid=KR:ko",
                "default_keywords": kw
            })
            
        # 2. Google News RSS: 지원사업 및 정책
        for kw in self.profile.get("funding_keywords", ["AI 바우처", "스마트공장 지원"]):
            encoded_q = urllib.parse.quote(f"{kw} 지원사업")
            sources.append({
                "name": f"Google News Policy - {kw}",
                "category": "policy",
                "type": "rss",
                "url": f"https://news.google.com/rss/search?q={encoded_q}&hl=ko&gl=KR&ceid=KR:ko",
                "default_keywords": kw
            })

        # 3. Google News RSS: 경쟁사 동향
        for comp in self.profile.get("competitors", ["VisionForge", "InspectAI"]):
            encoded_q = urllib.parse.quote(comp)
            sources.append({
                "name": f"Google News Competitor - {comp}",
                "category": "competitor",
                "type": "rss",
                "url": f"https://news.google.com/rss/search?q={encoded_q}&hl=ko&gl=KR&ceid=KR:ko",
                "company_tag": comp,
                "default_keywords": f"경쟁사|{comp}"
            })

        # 4. 테크/산업 전문 RSS 피드
        sources.append({
            "name": "AI Times",
            "category": "tech",
            "type": "rss",
            "url": "https://www.aitimes.com/rss/allArticle.xml",
            "default_keywords": "AI|기술동향"
        })
        sources.append({
            "name": "로봇신문",
            "category": "tech",
            "type": "rss",
            "url": "http://www.irobotnews.com/rss/allArticle.xml",
            "default_keywords": "로봇|스마트제조|자동화"
        })

        return sources

    def _fetch_rss(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """개별 RSS 피드 수집."""
        url = source["url"]
        name = source["name"]
        items = []
        try:
            feed = feedparser.parse(url)
            if feed.bozo and not feed.entries:
                raise ValueError(f"Feed parsing error: {feed.bozo_exception}")

            for entry in feed.entries:
                title = clean_html(getattr(entry, "title", "")).strip()
                if not title:
                    continue

                link = getattr(entry, "link", "")
                raw_summary = getattr(entry, "summary", getattr(entry, "description", ""))
                summary = clean_html(raw_summary)
                published = getattr(entry, "published", getattr(entry, "updated", ""))
                date_str = parse_date(published)
                
                # 출처 이름 파싱 (Google News의 경우 타이틀 뒷부분 '- 출처' 분리)
                source_name = source["name"]
                if " - " in title and "Google News" in source["name"]:
                    parts = title.rsplit(" - ", 1)
                    title = parts[0].strip()
                    source_name = parts[1].strip()

                items.append({
                    "category": source.get("category", "market"),
                    "title": title,
                    "date": date_str,
                    "content": summary or title,
                    "summary": (summary[:200] + "...") if len(summary) > 200 else summary or title,
                    "source_url": link,
                    "source_name": source_name,
                    "company_tag": source.get("company_tag", ""),
                    "keywords": source.get("default_keywords", "스마트제조"),
                    "data_origin": "live"
                })
            logger.info(f"Successfully fetched {len(items)} items from [{name}]")
        except Exception as e:
            logger.warning(f"Failed to fetch from [{name}] ({url}): {e}")
            self.failed_sources.append({"source": name, "url": url, "error": str(e)})
        
        return items

    def _load_fallback_data(self) -> List[Dict[str, Any]]:
        """Fallback 데이터 로드."""
        if not os.path.exists(self.fallback_path):
            logger.error(f"Fallback file not found at {self.fallback_path}")
            return []
        
        try:
            df = pd.read_csv(self.fallback_path, encoding="utf-8-sig")
            # data_origin 컬럼 보장
            if "data_origin" not in df.columns or df["data_origin"].isna().all():
                df["data_origin"] = "fallback"
            else:
                df["data_origin"] = df["data_origin"].fillna("fallback")
            
            records = df.to_dict(orient="records")
            logger.info(f"Loaded {len(records)} fallback records from {self.fallback_path}")
            return records
        except Exception as e:
            logger.error(f"Error reading fallback CSV: {e}")
            return []

    def run(self, min_required: int = 200) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """전체 수집 프로세스 실행 및 fallback 보완."""
        logger.info("Starting Market Intelligence Data Collection...")
        all_items: List[Dict[str, Any]] = []
        sources = self._build_feed_sources()
        
        # 1. 라이브 소스 순회 수집
        for src in sources:
            if src["type"] == "rss":
                items = self._fetch_rss(src)
                all_items.extend(items)

        # 중복 URL 기반 중복 제거
        seen_urls = set()
        unique_live_items = []
        for it in all_items:
            url = it.get("source_url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_live_items.append(it)
            elif not url:
                unique_live_items.append(it)
        
        live_count = len(unique_live_items)
        logger.info(f"Total unique live items collected: {live_count}")
        
        fallback_count = 0
        final_items = []

        # 2. 200건 충족 여부 확인 및 Fallback 결합
        if live_count >= min_required:
            logger.info(f"Live collected count ({live_count}) satisfies minimum requirement ({min_required}).")
            final_items = unique_live_items
        else:
            needed = min_required - live_count
            logger.warning(f"Live collection ({live_count}) is below target ({min_required}). Merging fallback data...")
            fallback_records = self._load_fallback_data()
            fallback_count = len(fallback_records)
            
            final_items = unique_live_items + fallback_records
            logger.info(f"Merged {fallback_count} fallback records. Total items: {len(final_items)}")

        # 3. DataFrame 변환 및 표준 스키마 정렬
        df = pd.DataFrame(final_items)
        
        # 필수 컬럼 보장
        required_cols = [
            "article_id", "category", "title", "date", "content", 
            "summary", "source_url", "source_name", "company_tag", 
            "keywords", "collected_at", "has_null", "is_duplicate_seed", "data_origin"
        ]
        
        now_iso = datetime.datetime.now().astimezone().isoformat()
        
        if "article_id" not in df.columns or df["article_id"].isna().any():
            df["article_id"] = [f"ART-{i+1:05d}" for i in range(len(df))]
        if "collected_at" not in df.columns:
            df["collected_at"] = now_iso
        else:
            df["collected_at"] = df["collected_at"].fillna(now_iso)
        if "has_null" not in df.columns:
            df["has_null"] = df[["title", "source_url", "source_name"]].isna().any(axis=1)
        if "is_duplicate_seed" not in df.columns:
            df["is_duplicate_seed"] = False
        if "data_origin" not in df.columns:
            df["data_origin"] = "live"

        for col in required_cols:
            if col not in df.columns:
                df[col] = ""

        df = df[required_cols]

        # 4. CSV 파일 저장
        df.to_csv(self.output_csv, index=False, encoding="utf-8-sig")
        logger.info(f"Saved {len(df)} records to {self.output_csv}")

        summary = {
            "total_count": len(df),
            "live_count": live_count,
            "fallback_count": fallback_count,
            "sources_attempted": len(sources),
            "failed_sources": self.failed_sources,
            "output_file": self.output_csv
        }
        return df, summary


if __name__ == "__main__":
    crawler = MarketCrawler()
    df, summary = crawler.run(min_required=200)
    print("\n" + "="*50)
    print(" [CRAWLER EXECUTION SUMMARY] ")
    print("="*50)
    print(f"Total Rows Saved     : {summary['total_count']}")
    print(f"Live Collected Count : {summary['live_count']}")
    print(f"Fallback Used Count  : {summary['fallback_count']}")
    print(f"Sources Attempted    : {summary['sources_attempted']}")
    print(f"Failed Sources Count : {len(summary['failed_sources'])}")
    if summary['failed_sources']:
        for fs in summary['failed_sources']:
            print(f"  - {fs['source']}: {fs['error']}")
    print(f"Output Path          : {summary['output_file']}")
    print("="*50)
