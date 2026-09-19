"""Market Intelligence Recommender Module for NovaFactory AI."""

import os
import re
import json
import logging
import datetime
from typing import List, Dict, Any, Tuple
import yaml
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# 로깅 설정
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "recommender_run.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Recommender")


class MarketRecommender:
    def __init__(
        self,
        config_path: str = "config/company_profile.yaml",
        input_csv: str = "data/processed/cleaned_market_news.csv",
        output_csv: str = "data/processed/recommended_market_news.csv"
    ):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.base_dir, config_path)
        self.input_csv = os.path.join(self.base_dir, input_csv)
        self.output_csv = os.path.join(self.base_dir, output_csv)
        os.makedirs(os.path.dirname(self.output_csv), exist_ok=True)

        self.profile = self._load_profile()
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    def _load_profile(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            logger.warning("Profile not found, using default fallback profile.")
            return {
                "company_name": "NovaFactory AI",
                "business_area": "제조업 AI 비전 품질검사",
                "competitors": ["VisionForge", "InspectAI", "FactoryMind", "QualiBot", "SmartSensorix"],
                "interest_keywords": ["AI", "스마트팩토리", "품질검사", "머신비전", "자동화", "클라우드", "제조 AX"],
                "funding_keywords": ["창업지원", "AI 바우처", "스마트공장", "R&D", "사업화 자금", "기술개발 지원"]
            }
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _calculate_relevance_score(self, row: pd.Series) -> Tuple[float, Dict[str, Any]]:
        """기업 프로필 기반 규칙 기반 관련성 점수 및 매칭 근거 산출."""
        text = f"{row.get('title', '')} {row.get('summary', '')} {row.get('content', '')}".lower()
        title_text = str(row.get("title", "")).lower()

        score = 0.0
        reasons = []
        matched_competitors = []
        matched_keywords = []
        matched_funding = []

        # 1. 자사명 및 제품군 매칭 (+30점)
        company_name = self.profile.get("company_name", "NovaFactory AI").lower()
        if company_name in text:
            score += 30.0
            reasons.append("자사명 직접 언급")

        for prod in self.profile.get("products", []):
            if prod.lower() in text:
                score += 20.0
                reasons.append(f"주요 제품군({prod}) 매칭")

        # 2. 경쟁사 매칭 (+25점)
        for comp in self.profile.get("competitors", []):
            if comp.lower() in text:
                score += 25.0
                matched_competitors.append(comp)
        if matched_competitors:
            reasons.append(f"경쟁사({', '.join(matched_competitors)}) 동향 포착")

        # 3. 비즈니스 관심 키워드 매칭 (제목 매칭 가중치 1.5배)
        for kw in self.profile.get("interest_keywords", []):
            kw_low = kw.lower()
            if kw_low in title_text:
                score += 15.0
                matched_keywords.append(kw)
            elif kw_low in text:
                score += 8.0
                matched_keywords.append(kw)
        if matched_keywords:
            reasons.append(f"핵심 키워드({', '.join(list(set(matched_keywords))[:3])}) 부합")

        # 4. 정책/지원사업 키워드 매칭
        for fkw in self.profile.get("funding_keywords", []):
            fkw_low = fkw.lower()
            if fkw_low in title_text:
                score += 18.0
                matched_funding.append(fkw)
            elif fkw_low in text:
                score += 10.0
                matched_funding.append(fkw)
        if matched_funding:
            reasons.append(f"정부지원/바우처({', '.join(list(set(matched_funding))[:2])}) 연계 가능")

        # 5. 카테고리 가중치
        cat = str(row.get("category", "")).lower()
        if cat in ["policy", "정부지원"]:
            score += 10.0
        elif cat in ["market", "시장"]:
            score += 8.0
        elif cat in ["tech", "기술"]:
            score += 6.0

        # 6. 최신성 점수 (최대 10점)
        date_str = str(row.get("date", ""))
        try:
            pub_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            delta_days = (datetime.date.today() - pub_date).days
            if delta_days <= 7:
                score += 10.0
            elif delta_days <= 30:
                score += 6.0
            elif delta_days <= 90:
                score += 3.0
        except Exception:
            score += 5.0

        # 100점 만점으로 정규화 (스케일링)
        final_score = min(round(score, 1), 99.5)
        
        # 추천 사유 텍스트 조합
        if not reasons:
            recommendation_reason = "제조업 및 스마트 인프라 전반의 산업 동향 모니터링 가치 보유."
        else:
            recommendation_reason = " · ".join(reasons) + "에 따른 맞춤형 추천."

        meta = {
            "matched_competitors": matched_competitors,
            "matched_keywords": list(set(matched_keywords)),
            "matched_funding": list(set(matched_funding)),
            "raw_reasons": reasons
        }

        return final_score, {"reason": recommendation_reason, "meta": meta}

    def _call_gemini_llm(self, top_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Gemini API를 활용한 심층 분석 및 정밀 추천 이유 생성 (API Key 있을 경우)."""
        logger.info("Evaluating top candidates with Gemini API...")
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            
            # 최신 지원 모델 리스트 순차 적용
            model = None
            for model_name in ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-flash-latest"]:
                try:
                    model = genai.GenerativeModel(model_name)
                    logger.info(f"Using Gemini model: {model_name}")
                    break
                except Exception:
                    continue

            if not model:
                model = genai.GenerativeModel("gemini-3.6-flash")

            for i, rec in enumerate(top_records[:10]):  # 상위 10건에 대해 LLM 심층 평가
                try:
                    prompt = (
                        f"기업명: {self.profile.get('company_name', 'NovaFactory AI')}\n"
                        f"사업분야: {self.profile.get('business_area', '제조업 AI 비전 품질검사 SaaS')}\n"
                        f"뉴스 제목: {rec.get('title', '')}\n"
                        f"뉴스 요약: {rec.get('summary', '')}\n"
                        f"카테고리: {rec.get('category', 'market')}\n\n"
                        "위 뉴스가 우리 기업의 제조 AI 비전 품질검사 사업 및 시장 전략(정부지원사업 수주, 경쟁사 대응, 판로 개척 등)에 어떤 실질적 가치가 있는지 1~2문장의 전문 추천 사유로 간결하게 작성해줘. (한국어로 작성)"
                    )
                    response = model.generate_content(prompt)
                    if response and response.text:
                        rec["recommendation_reason"] = response.text.strip().replace("\n", " ")
                        logger.info(f"LLM reason generated for item #{i+1}")
                except Exception as item_err:
                    logger.warning(f"Failed LLM generation for item #{i+1}: {item_err}")
                    continue

            logger.info("Successfully completed Gemini LLM deep analysis.")
        except Exception as e:
            logger.warning(f"LLM evaluation encountered an error ({e}). Keeping rule-based analysis.")
        
        return top_records

    def run(self, top_n: int = 30) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        logger.info(f"Loading cleaned data from: {self.input_csv}")
        if not os.path.exists(self.input_csv):
            raise FileNotFoundError(f"Cleaned CSV not found at: {self.input_csv}")

        df = pd.read_csv(self.input_csv, encoding="utf-8-sig")
        logger.info(f"Scoring {len(df)} cleaned items against company profile...")

        scores = []
        reasons = []
        business_impacts = []

        for _, row in df.iterrows():
            score, res = self._calculate_relevance_score(row)
            scores.append(score)
            reasons.append(res["reason"])
            
            # 사업 중요도 등급 매핑
            if score >= 60:
                impact = "High"
            elif score >= 40:
                impact = "Medium"
            else:
                impact = "Low"
            business_impacts.append(impact)

        df["relevance_score"] = scores
        df["recommendation_reason"] = reasons
        df["business_impact"] = business_impacts

        # 점수 기준 내림차순 정렬 및 상위 N개 추출
        df_sorted = df.sort_values(by=["relevance_score", "date"], ascending=[False, False]).reset_index(drop=True)
        df_top = df_sorted.head(top_n).copy()

        # LLM 평가 적용 여부
        llm_used = False
        if self.api_key:
            logger.info("Gemini API Key detected. Performing LLM evaluation...")
            records = df_top.to_dict(orient="records")
            records = self._call_gemini_llm(records)
            df_top = pd.DataFrame(records)
            llm_used = True
        else:
            logger.info("No Gemini API Key provided. Successfully applied advanced rule-based recommendation logic.")

        # 저장
        df_top.to_csv(self.output_csv, index=False, encoding="utf-8-sig")
        logger.info(f"Saved TOP {len(df_top)} recommendations to: {self.output_csv}")

        summary = {
            "total_evaluated": len(df),
            "top_n_saved": len(df_top),
            "llm_used": llm_used,
            "output_csv": self.output_csv,
            "top_10": df_top.head(10)[["article_id", "title", "relevance_score", "category", "source_name", "recommendation_reason", "source_url"]].to_dict(orient="records")
        }
        return df_top, summary


if __name__ == "__main__":
    import sys
    # Windows 콘솔 인코딩 대응
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    recommender = MarketRecommender()
    df_top, summary = recommender.run(top_n=30)
    print("\n" + "="*50)
    print(" [RECOMMENDER EXECUTION SUMMARY] ")
    print("="*50)
    print(f"Total Evaluated  : {summary['total_evaluated']}")
    print(f"TOP Saved Count  : {summary['top_n_saved']}")
    print(f"LLM Used (Gemini): {summary['llm_used']}")
    print(f"Output File      : {summary['output_csv']}")
    print("\n[TOP 5 RECOMMENDATIONS]")
    for i, row in enumerate(summary['top_10'][:5], 1):
        safe_title = str(row['title']).encode("ascii", "replace").decode("ascii") if not hasattr(sys.stdout, "reconfigure") else str(row['title'])
        print(f"{i}. [{row['relevance_score']}점][{row['category']}] {row['title']}")
        print(f"   - 이유: {row['recommendation_reason']}")
        print(f"   - 출처: {row['source_name']} ({str(row['source_url'])[:60]}...)")
    print("="*50)
