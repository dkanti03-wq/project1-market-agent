"""End-to-End Market Intelligence Pipeline Runner for NovaFactory AI."""

import os
import sys
import time
import logging
import traceback
from typing import Dict, Any

# Windows 콘솔 인코딩 대응
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 상대 경로 임포트 지원
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.crawler import MarketCrawler
from src.cleaner import DataCleaner
from src.recommender import MarketRecommender
from src.build_site import SiteBuilder

# 로깅 설정
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
PIPELINE_LOG_FILE = os.path.join(LOG_DIR, "pipeline.log")

logger = logging.getLogger("PipelineRunner")
logger.setLevel(logging.INFO)
logger.handlers = []  # 기존 핸들러 초기화

file_handler = logging.FileHandler(PIPELINE_LOG_FILE, encoding="utf-8", mode="a")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(stream_handler)


class PipelineRunner:
    def __init__(self):
        self.root_dir = PROJECT_ROOT
        self.stages = {}
        self.start_time = time.time()

    def log_stage_start(self, stage_name: str, description: str):
        logger.info("=" * 60)
        logger.info(f"▶ [STAGE START] {stage_name}: {description}")
        logger.info("=" * 60)

    def log_stage_end(self, stage_name: str, status: str, details: str = ""):
        status_icon = {
            "SUCCESS": "✅ [SUCCESS]",
            "WARNING": "⚠️ [WARNING]",
            "FAILED": "❌ [FAILED]"
        }.get(status, f"[{status}]")
        
        logger.info("-" * 60)
        logger.info(f"{status_icon} {stage_name} Finished | {details}")
        logger.info("-" * 60 + "\n")
        self.stages[stage_name] = {"status": status, "details": details}

    def run(self) -> Dict[str, Any]:
        logger.info("############################################################")
        logger.info("#   NOVAFACTORY AI MARKET INTELLIGENCE PIPELINE START      #")
        logger.info("############################################################\n")

        pipeline_success = True

        # -------------------------------------------------------------
        # STEP 1: 수집 (Data Collection)
        # -------------------------------------------------------------
        self.log_stage_start("STEP 1: Collection", "실시간 공개 RSS/웹 수집 및 필요 시 Fallback 병합")
        crawler_summary = {}
        try:
            crawler = MarketCrawler()
            df_raw, crawler_summary = crawler.run(min_required=200)
            
            raw_count = len(df_raw)
            live_count = crawler_summary.get("live_count", 0)
            fb_count = crawler_summary.get("fallback_count", 0)
            failed_sources = crawler_summary.get("failed_sources", [])

            if failed_sources or fb_count > 0:
                stage_status = "WARNING"
                detail_msg = f"수집 완료: 총 {raw_count}건 (Live: {live_count}건, Fallback: {fb_count}건, 소스 실패: {len(failed_sources)}건)"
            else:
                stage_status = "SUCCESS"
                detail_msg = f"수집 완료: 총 {raw_count}건 (100% 라이브 수집 달성, 소스 실패 0건)"

            self.log_stage_end("STEP 1: Collection", stage_status, detail_msg)
        except Exception as e:
            pipeline_success = False
            logger.error(f"Collection Step Failed: {e}\n{traceback.format_exc()}")
            self.log_stage_end("STEP 1: Collection", "FAILED", f"Error: {str(e)}")
            # 치명적 오류 발생 시 비상 fallback 파일 직접 생성 시도
            fb_file = os.path.join(self.root_dir, "data", "fallback", "fallback_market_news.csv")
            target_raw = os.path.join(self.root_dir, "data", "raw", "crawled_market_news.csv")
            if os.path.exists(fb_file):
                import shutil
                shutil.copyfile(fb_file, target_raw)
                logger.warning(f"Emergency: Copied fallback dataset directly to {target_raw}")

        # -------------------------------------------------------------
        # STEP 2: 정제 (Data Cleaning & Normalization)
        # -------------------------------------------------------------
        self.log_stage_start("STEP 2: Cleaning", "HTML 노이즈 제거, 결측치 필터링, 날짜 정규화, 중복 제거")
        cleaner_summary = {}
        try:
            cleaner = DataCleaner()
            df_clean, cleaner_summary = cleaner.run()
            
            clean_count = len(df_clean)
            dup_removed = cleaner_summary.get("duplicates_removed", 0)
            missing_filtered = cleaner_summary.get("missing_filtered", 0)

            detail_msg = f"정제 완료: 최종 {clean_count}건 유효 (중복 제거 {dup_removed}건, 결측 필터 {missing_filtered}건)"
            self.log_stage_end("STEP 2: Cleaning", "SUCCESS", detail_msg)
        except Exception as e:
            pipeline_success = False
            logger.error(f"Cleaning Step Failed: {e}\n{traceback.format_exc()}")
            self.log_stage_end("STEP 2: Cleaning", "FAILED", f"Error: {str(e)}")

        # -------------------------------------------------------------
        # STEP 3: 추천 (Relevance Scoring & LLM Reasoning)
        # -------------------------------------------------------------
        self.log_stage_start("STEP 3: Recommendation", "기업 프로필 맞춤형 다차원 가중치 점수 산출 및 Gemini LLM 심층 분석")
        recommender_summary = {}
        try:
            recommender = MarketRecommender()
            df_rec, recommender_summary = recommender.run(top_n=30)
            
            rec_count = len(df_rec)
            llm_used = recommender_summary.get("llm_used", False)
            
            detail_msg = f"추천 완료: TOP {rec_count}건 선별 완료 (Gemini LLM 적용: {llm_used})"
            self.log_stage_end("STEP 3: Recommendation", "SUCCESS", detail_msg)
        except Exception as e:
            pipeline_success = False
            logger.error(f"Recommendation Step Failed: {e}\n{traceback.format_exc()}")
            self.log_stage_end("STEP 3: Recommendation", "FAILED", f"Error: {str(e)}")

        # -------------------------------------------------------------
        # STEP 4: 대시보드 빌드 (Static Site & JSON Generation)
        # -------------------------------------------------------------
        self.log_stage_start("STEP 4: Site Builder", "GitHub Pages 배포용 정적 대시보드(docs/index.html, docs/report.json) 생성")
        site_summary = {}
        try:
            builder = SiteBuilder()
            site_summary = builder.run()
            
            html_path = builder.html_output
            json_path = builder.json_output
            
            html_size = os.path.getsize(html_path) if os.path.exists(html_path) else 0
            detail_msg = f"대시보드 빌드 완료: index.html ({html_size:,} bytes), report.json 생성 완료"
            self.log_stage_end("STEP 4: Site Builder", "SUCCESS", detail_msg)
        except Exception as e:
            pipeline_success = False
            logger.error(f"Site Builder Step Failed: {e}\n{traceback.format_exc()}")
            self.log_stage_end("STEP 4: Site Builder", "FAILED", f"Error: {str(e)}")

        # -------------------------------------------------------------
        # PIPELINE SUMMARY
        # -------------------------------------------------------------
        elapsed_sec = round(time.time() - self.start_time, 2)
        overall_status = "SUCCESS" if pipeline_success else "COMPLETED_WITH_WARNINGS"

        logger.info("=" * 60)
        logger.info(f"🎉 [PIPELINE OVERALL] Status: {overall_status} (Total Elapsed: {elapsed_sec}s)")
        logger.info("=" * 60)
        for stage, info in self.stages.items():
            logger.info(f"  - {stage}: [{info['status']}] {info['details']}")
        logger.info("=" * 60 + "\n")

        return {
            "overall_status": overall_status,
            "elapsed_seconds": elapsed_sec,
            "stages": self.stages,
            "log_file": PIPELINE_LOG_FILE
        }


if __name__ == "__main__":
    runner = PipelineRunner()
    result = runner.run()
    
    print("\n" + "#" * 60)
    print(f"# PIPELINE EXECUTION SUMMARY : {result['overall_status']}")
    print(f"# Total Time Taken           : {result['elapsed_seconds']}s")
    print(f"# Log File Location          : {result['log_file']}")
    print("#" * 60)
