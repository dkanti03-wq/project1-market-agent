"""Data Cleaner and Normalization Module for NovaFactory AI Market Intelligence."""

import os
import re
import html
import logging
import datetime
from typing import Dict, Any, Tuple
import pandas as pd
from bs4 import BeautifulSoup

# 로깅 설정
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "cleaner_run.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DataCleaner")


def clean_text(raw_text: Any) -> str:
    """HTML 태그, HTML 엔티티, 불필요한 공백을 제거하고 정규화."""
    if pd.isna(raw_text) or raw_text is None:
        return ""
    text = str(raw_text)
    # HTML 파싱 및 태그 제거
    soup = BeautifulSoup(text, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    # HTML 엔티티 언이스케이프 (&quot; -> ", &amp; -> & 등)
    text = html.unescape(text)
    # 연속 공백 / 탭 / 줄바꿈 정규화
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_title_for_dedup(title: str) -> str:
    """중복 비교를 위해 특수문자 및 공백을 최소화한 정규화 타이틀 생성."""
    if not title:
        return ""
    # 영문/한글/숫자만 남기고 소문자화
    t = re.sub(r"[^\w\s가-힣a-zA-Z0-9]", "", title.lower())
    t = re.sub(r"\s+", "", t)
    return t


def normalize_date(date_val: Any, default_date: str = "") -> str:
    """날짜를 YYYY-MM-DD 형식으로 정규화."""
    if not default_date:
        default_date = datetime.date.today().isoformat()
    if pd.isna(date_val) or date_val is None or str(date_val).strip() == "":
        return default_date
    
    date_str = str(date_val).strip()
    # 1. 정규식 추출
    match = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", date_str)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        # 유효 범위 검사
        if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"
    
    # 2. pd.to_datetime 시도
    try:
        dt = pd.to_datetime(date_str, errors="coerce")
        if not pd.isna(dt):
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    return default_date


class DataCleaner:
    def __init__(
        self,
        input_csv: str = "data/raw/crawled_market_news.csv",
        output_csv: str = "data/processed/cleaned_market_news.csv"
    ):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.input_csv = os.path.join(self.base_dir, input_csv)
        self.output_csv = os.path.join(self.base_dir, output_csv)
        os.makedirs(os.path.dirname(self.output_csv), exist_ok=True)

    def run(self) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        logger.info(f"Starting Data Cleaning on: {self.input_csv}")
        
        if not os.path.exists(self.input_csv):
            raise FileNotFoundError(f"Input file not found at: {self.input_csv}")

        df_raw = pd.read_csv(self.input_csv, encoding="utf-8-sig")
        initial_count = len(df_raw)
        logger.info(f"Loaded raw dataset with {initial_count} rows, {df_raw.shape[1]} columns.")

        # 1. 텍스트 정제 (HTML 태그 및 공백 정규화)
        text_columns = ["title", "content", "summary", "source_name", "category", "keywords"]
        for col in text_columns:
            if col in df_raw.columns:
                df_raw[col] = df_raw[col].apply(clean_text)

        # 2. 결측치 및 비정상 데이터 필터링
        # title 결측 또는 5자 미만 제거
        valid_title_mask = df_raw["title"].str.strip().str.len() >= 5
        missing_title_count = (~valid_title_mask).sum()
        df_filtered = df_raw[valid_title_mask].copy()
        
        # source_url 결측 또는 빈값 제거
        if "source_url" in df_filtered.columns:
            valid_url_mask = df_filtered["source_url"].str.strip().str.len() > 0
            missing_url_count = (~valid_url_mask).sum()
            df_filtered = df_filtered[valid_url_mask].copy()
        else:
            missing_url_count = 0

        total_missing_filtered = missing_title_count + missing_url_count
        logger.info(f"Filtered out {missing_title_count} rows with invalid/short title and {missing_url_count} rows with invalid URL.")

        # 3. 날짜 정규화
        today_iso = datetime.date.today().isoformat()
        df_filtered["date"] = df_filtered["date"].apply(lambda d: normalize_date(d, today_iso))

        # 4. 중복 제거
        before_dedup_count = len(df_filtered)
        
        # 4.1 URL 기준 중복 제거
        df_filtered = df_filtered.drop_duplicates(subset=["source_url"], keep="first")
        url_dedup_count = before_dedup_count - len(df_filtered)

        # 4.2 정규화된 제목 기준 중복 제거
        df_filtered["_norm_title"] = df_filtered["title"].apply(normalize_title_for_dedup)
        before_title_dedup = len(df_filtered)
        df_filtered = df_filtered.drop_duplicates(subset=["_norm_title"], keep="first")
        title_dedup_count = before_title_dedup - len(df_filtered)
        df_filtered = df_filtered.drop(columns=["_norm_title"])

        total_duplicates_removed = url_dedup_count + title_dedup_count
        logger.info(f"Removed duplicates: {url_dedup_count} by URL, {title_dedup_count} by Title. Total duplicates removed: {total_duplicates_removed}")

        # 5. article_id 고유값 재부여 및 메타데이터 정비
        df_filtered = df_filtered.reset_index(drop=True)
        df_filtered["article_id"] = [f"CLN-{i+1:05d}" for i in range(len(df_filtered))]
        df_filtered["has_null"] = df_filtered[["title", "source_url", "source_name"]].isna().any(axis=1)
        df_filtered["is_duplicate_seed"] = False
        
        # company_tag NaN 처리 (빈 문자열)
        if "company_tag" in df_filtered.columns:
            df_filtered["company_tag"] = df_filtered["company_tag"].fillna("")

        # 6. 정제 결과 CSV 저장
        df_filtered.to_csv(self.output_csv, index=False, encoding="utf-8-sig")
        final_count = len(df_filtered)
        logger.info(f"Successfully saved {final_count} cleaned records to: {self.output_csv}")

        summary = {
            "initial_count": initial_count,
            "final_count": final_count,
            "missing_filtered": total_missing_filtered,
            "duplicates_removed": total_duplicates_removed,
            "output_csv": self.output_csv
        }
        return df_filtered, summary


if __name__ == "__main__":
    cleaner = DataCleaner()
    df_clean, summary = cleaner.run()
    print("\n" + "="*50)
    print(" [DATA CLEANING EXECUTION SUMMARY] ")
    print("="*50)
    print(f"Original Raw Rows   : {summary['initial_count']}")
    print(f"Missing/Short Filter: {summary['missing_filtered']}")
    print(f"Duplicates Removed  : {summary['duplicates_removed']}")
    print(f"Final Cleaned Rows  : {summary['final_count']}")
    print(f"Output File Path    : {summary['output_csv']}")
    print("="*50)
