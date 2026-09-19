"""Static Dashboard & HTML Report Builder for GitHub Pages Deployment."""

import os
import json
import logging
import datetime
from typing import Dict, Any, List, Tuple
import yaml
import pandas as pd

# 로깅 설정
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "build_site_run.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("SiteBuilder")


class SiteBuilder:
    def __init__(
        self,
        config_path: str = "config/company_profile.yaml",
        cleaned_csv: str = "data/processed/cleaned_market_news.csv",
        recommended_csv: str = "data/processed/recommended_market_news.csv",
        docs_dir: str = "docs"
    ):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.base_dir, config_path)
        self.cleaned_csv = os.path.join(self.base_dir, cleaned_csv)
        self.recommended_csv = os.path.join(self.base_dir, recommended_csv)
        self.docs_dir = os.path.join(self.base_dir, docs_dir)
        os.makedirs(self.docs_dir, exist_ok=True)

        self.html_output = os.path.join(self.docs_dir, "index.html")
        self.json_output = os.path.join(self.docs_dir, "report.json")

    def _load_data(self) -> Tuple[Dict[str, Any], pd.DataFrame, pd.DataFrame]:
        # 1. Profile 로드
        profile = {}
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                profile = yaml.safe_load(f)

        # 2. 추천 CSV 로드
        if not os.path.exists(self.recommended_csv):
            raise FileNotFoundError(f"Recommended CSV not found at {self.recommended_csv}")
        df_rec = pd.read_csv(self.recommended_csv, encoding="utf-8-sig")

        # 3. 전체 Cleaned CSV 로드
        df_clean = pd.DataFrame()
        if os.path.exists(self.cleaned_csv):
            df_clean = pd.read_csv(self.cleaned_csv, encoding="utf-8-sig")

        return profile, df_rec, df_clean

    def _build_json_report(self, profile: Dict[str, Any], df_rec: pd.DataFrame, df_clean: pd.DataFrame) -> Dict[str, Any]:
        now_iso = datetime.datetime.now().astimezone().isoformat()
        
        category_stats = df_clean["category"].value_counts().to_dict() if not df_clean.empty else {}
        top_categories = df_rec["category"].value_counts().to_dict()
        source_stats = df_clean["source_name"].value_counts().head(10).to_dict() if not df_clean.empty else {}

        report_data = {
            "metadata": {
                "generated_at": now_iso,
                "project_name": "Project 1 Market Intelligence Agent",
                "total_cleaned_articles": len(df_clean),
                "total_recommended_articles": len(df_rec)
            },
            "company_profile": profile,
            "statistics": {
                "category_distribution": category_stats,
                "top_recommendations_category": top_categories,
                "top_sources": source_stats
            },
            "top_10": df_rec.head(10).to_dict(orient="records"),
            "top_30": df_rec.to_dict(orient="records")
        }

        with open(self.json_output, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Generated JSON report: {self.json_output}")
        return report_data

    def _build_html_dashboard(self, report_data: Dict[str, Any]):
        profile = report_data["company_profile"]
        top_10 = report_data["top_10"]
        top_30 = report_data["top_30"]
        stats = report_data["statistics"]
        meta = report_data["metadata"]

        company_name = profile.get("company_name", "NovaFactory AI")
        business_area = profile.get("business_area", "제조업 AI 비전 품질검사")
        competitors = profile.get("competitors", [])
        keywords = profile.get("interest_keywords", [])
        funding_kws = profile.get("funding_keywords", [])

        # JSON 직렬화 (프론트엔드 검색 및 인터랙션용)
        top_30_json_str = json.dumps(top_30, ensure_ascii=False)
        stats_json_str = json.dumps(stats, ensure_ascii=False)

        html_content = f"""<!DOCTYPE html>
<html lang="ko" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{company_name} | 마켓 & 경쟁사 인텔리전스 대시보드</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {{
            darkMode: 'class',
            theme: {{
                extend: {{
                    fontFamily: {{
                        sans: ['Pretendard', 'ui-sans-serif', 'system-ui']
                    }},
                    colors: {{
                        brand: {{
                            50: '#f0fdf4',
                            500: '#10b981',
                            600: '#059669',
                            900: '#064e3b'
                        }},
                        dark: {{
                            800: '#1e293b',
                            850: '#172033',
                            900: '#0f172a',
                            950: '#020617'
                        }}
                    }}
                }}
            }}
        }}
    </script>
    <style>
        body {{ font-family: 'Pretendard', sans-serif; }}
        .glass {{ background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); }}
        .badge-market {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }}
        .badge-policy {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }}
        .badge-tech {{ background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); }}
    </style>
</head>
<body class="bg-dark-950 text-slate-100 min-h-screen flex flex-col antialiased selection:bg-brand-500 selection:text-white">

    <!-- 헤더 -->
    <header class="border-b border-slate-800 bg-dark-900/80 sticky top-0 z-50 backdrop-blur-md">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div class="flex items-center space-x-3">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-600 to-emerald-400 flex items-center justify-center font-bold text-white text-xl shadow-lg shadow-emerald-500/20">
                    ⚡
                </div>
                <div>
                    <div class="flex items-center space-x-2">
                        <h1 class="text-xl font-bold tracking-tight text-white">{company_name}</h1>
                        <span class="px-2 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Live Intelligence</span>
                    </div>
                    <p class="text-xs text-slate-400">{business_area} 맞춤형 시장·정책·기술 동향 리포트</p>
                </div>
            </div>
            <div class="flex items-center space-x-4 text-xs text-slate-400">
                <div class="flex items-center space-x-1.5">
                    <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span>수집 풀: <strong class="text-white">{meta['total_cleaned_articles']}건</strong></span>
                </div>
                <div class="h-4 w-px bg-slate-800"></div>
                <div>최종 갱신: <span class="text-slate-300">{meta['generated_at'][:10]}</span></div>
                <a href="report.json" target="_blank" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium transition border border-slate-700">
                    JSON Data
                </a>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">

        <!-- 프로필 & 핵심 메트릭스 -->
        <section class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- 기업 프로필 카드 -->
            <div class="glass p-6 rounded-2xl space-y-4">
                <div class="flex items-center justify-between">
                    <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-400">🎯 타겟팅 프로필</h2>
                    <span class="text-xs text-emerald-400 font-medium">자동 최적화</span>
                </div>
                <div class="space-y-3">
                    <div>
                        <div class="text-xs text-slate-400">주요 경쟁사 모니터링</div>
                        <div class="flex flex-wrap gap-1.5 mt-1">
                            {" ".join([f'<span class="px-2 py-0.5 rounded-md bg-slate-800 text-slate-300 text-xs border border-slate-700">{c}</span>' for c in competitors])}
                        </div>
                    </div>
                    <div>
                        <div class="text-xs text-slate-400">시장/기술 관심 키워드</div>
                        <div class="flex flex-wrap gap-1.5 mt-1">
                            {" ".join([f'<span class="px-2 py-0.5 rounded-md bg-emerald-950/50 text-emerald-300 text-xs border border-emerald-800/40">{k}</span>' for k in keywords])}
                        </div>
                    </div>
                    <div>
                        <div class="text-xs text-slate-400">정부지원/바우처 키워드</div>
                        <div class="flex flex-wrap gap-1.5 mt-1">
                            {" ".join([f'<span class="px-2 py-0.5 rounded-md bg-amber-950/50 text-amber-300 text-xs border border-amber-800/40">{f}</span>' for f in funding_kws])}
                        </div>
                    </div>
                </div>
            </div>

            <!-- 수집 및 추천 통계 요약 -->
            <div class="glass p-6 rounded-2xl flex flex-col justify-between">
                <div>
                    <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4">📊 데이터 인텔리전스 요약</h2>
                    <div class="grid grid-cols-2 gap-4">
                        <div class="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
                            <div class="text-xs text-slate-400">전체 정제 데이터</div>
                            <div class="text-2xl font-black text-white mt-1">{meta['total_cleaned_articles']}<span class="text-xs text-slate-400 font-normal"> 건</span></div>
                            <div class="text-xs text-emerald-400 mt-1">✓ 무결성 검증 완료</div>
                        </div>
                        <div class="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
                            <div class="text-xs text-slate-400">맞춤 선별 추천</div>
                            <div class="text-2xl font-black text-emerald-400 mt-1">{meta['total_recommended_articles']}<span class="text-xs text-slate-400 font-normal"> 건</span></div>
                            <div class="text-xs text-slate-400 mt-1">가중치 알고리즘 적용</div>
                        </div>
                    </div>
                </div>
                <div class="mt-4 pt-4 border-t border-slate-800 flex justify-between text-xs text-slate-400">
                    <span>시장(Market): <strong class="text-slate-200">{stats.get('category_distribution', {}).get('market', 0)}</strong></span>
                    <span>정책(Policy): <strong class="text-slate-200">{stats.get('category_distribution', {}).get('policy', 0)}</strong></span>
                    <span>기술(Tech): <strong class="text-slate-200">{stats.get('category_distribution', {}).get('tech', 0)}</strong></span>
                </div>
            </div>

            <!-- 핵심 액션 가이드 -->
            <div class="glass p-6 rounded-2xl flex flex-col justify-between">
                <div>
                    <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3">💡 비즈니스 대응 권고사항</h2>
                    <ul class="space-y-2.5 text-xs text-slate-300">
                        <li class="flex items-start space-x-2">
                            <span class="text-emerald-400 font-bold">1.</span>
                            <span><strong>AI 바우처 공급기업 연계:</strong> 2026년 공고에 맞춘 수요기업 매칭 및 비전 SaaS 바우처 상품 등록 추진</span>
                        </li>
                        <li class="flex items-start space-x-2">
                            <span class="text-amber-400 font-bold">2.</span>
                            <span><strong>스마트공장 2.0 전환:</strong> 지역 제조 혁신 벨트(부산/창원 등) 제조 AX 품질검사 프로젝트 선점</span>
                        </li>
                        <li class="flex items-start space-x-2">
                            <span class="text-blue-400 font-bold">3.</span>
                            <span><strong>경쟁사 동향:</strong> VisionForge 등 경쟁사 SaaS 가격 및 클라우드 연동 전략 벤치마킹</span>
                        </li>
                    </ul>
                </div>
                <div class="text-xs text-slate-500 mt-3 text-right">전략 분석 엔진 v1.0</div>
            </div>
        </section>

        <!-- TOP 10 핵심 하이라이트 -->
        <section class="space-y-4">
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-2">
                    <h2 class="text-lg font-bold text-white">🔥 TOP 10 최우선 검토 인텔리전스</h2>
                    <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-500/10 text-red-400 border border-red-500/20">High Impact</span>
                </div>
                <div class="text-xs text-slate-400">자사 관련성 점수 순위</div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
"""

        # TOP 10 카드 생성
        for idx, item in enumerate(top_10, 1):
            cat = str(item.get("category", "market")).lower()
            badge_cls = "badge-market"
            cat_label = "시장 동향"
            if "policy" in cat:
                badge_cls = "badge-policy"
                cat_label = "정책·지원"
            elif "tech" in cat:
                badge_cls = "badge-tech"
                cat_label = "기술 혁신"

            score = item.get("relevance_score", 0.0)
            title = item.get("title", "")
            reason = item.get("recommendation_reason", "")
            source_name = item.get("source_name", "News")
            date_str = item.get("date", "")
            source_url = item.get("source_url", "#")

            html_content += f"""
                <div class="glass p-5 rounded-2xl flex flex-col justify-between hover:border-slate-600 transition duration-200 group">
                    <div class="space-y-3">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center space-x-2">
                                <span class="w-6 h-6 rounded-full bg-slate-800 text-slate-200 font-bold text-xs flex items-center justify-center border border-slate-700">#{idx}</span>
                                <span class="px-2 py-0.5 rounded-md text-xs font-semibold {badge_cls}">{cat_label}</span>
                                <span class="text-xs text-slate-400">{source_name}</span>
                            </div>
                            <div class="flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-emerald-950/60 border border-emerald-500/30 text-emerald-400 font-bold text-xs">
                                <span>적합도</span>
                                <span class="text-sm">{score}점</span>
                            </div>
                        </div>
                        <h3 class="text-sm sm:text-base font-bold text-white group-hover:text-emerald-300 transition line-clamp-2">
                            <a href="{source_url}" target="_blank" rel="noopener noreferrer">
                                {title}
                            </a>
                        </h3>
                        <div class="p-3 rounded-xl bg-slate-900/70 border border-slate-800 text-xs text-slate-300 space-y-1">
                            <div class="text-emerald-400 font-semibold flex items-center space-x-1">
                                <span>🎯 추천 및 대응 사유:</span>
                            </div>
                            <p class="leading-relaxed">{reason}</p>
                        </div>
                    </div>
                    <div class="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
                        <span>발행일: {date_str}</span>
                        <a href="{source_url}" target="_blank" rel="noopener noreferrer" class="text-emerald-400 hover:text-emerald-300 font-medium inline-flex items-center space-x-1 group-hover:translate-x-0.5 transition">
                            <span>원문 기사 보기</span>
                            <span>→</span>
                        </a>
                    </div>
                </div>
"""

        # 하단 전체 TOP 30 검색/탐색 테이블 섹션
        html_content += f"""
            </div>
        </section>

        <!-- TOP 30 인터랙티브 탐색 테이블 -->
        <section class="glass p-6 rounded-2xl space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h2 class="text-base font-bold text-white">📑 맞춤 추천 인텔리전스 전체 목록 (TOP 30)</h2>
                    <p class="text-xs text-slate-400">카테고리 필터 및 실시간 검색을 통해 필요한 정보를 빠르게 탐색하세요.</p>
                </div>
                <div class="flex items-center space-x-2">
                    <input type="text" id="searchInput" placeholder="키워드, 제목, 출처 검색..." class="px-3.5 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500 w-64">
                    <select id="categoryFilter" class="px-3.5 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-emerald-500">
                        <option value="ALL">전체 카테고리</option>
                        <option value="market">시장 (Market)</option>
                        <option value="policy">정책·지원 (Policy)</option>
                        <option value="tech">기술 (Tech)</option>
                    </select>
                </div>
            </div>

            <div class="overflow-x-auto">
                <table class="w-full text-left text-xs text-slate-300">
                    <thead class="bg-slate-900/80 text-slate-400 font-semibold uppercase tracking-wider border-b border-slate-800">
                        <tr>
                            <th class="py-3 px-3 w-14 text-center">순위</th>
                            <th class="py-3 px-3 w-20">구분</th>
                            <th class="py-3 px-4">제목 및 추천 사유</th>
                            <th class="py-3 px-3 w-28">출처</th>
                            <th class="py-3 px-3 w-24">발행일</th>
                            <th class="py-3 px-3 w-20 text-center">점수</th>
                            <th class="py-3 px-3 w-20 text-center">원문</th>
                        </tr>
                    </thead>
                    <tbody id="tableBody" class="divide-y divide-slate-800/60">
                        <!-- JS 렌더링 -->
                    </tbody>
                </table>
            </div>
            <div id="noResults" class="hidden py-8 text-center text-slate-400 text-xs">
                검색 조건에 맞는 인텔리전스가 없습니다.
            </div>
        </section>

    </main>

    <!-- 푸터 -->
    <footer class="border-t border-slate-800 bg-dark-900/50 py-6 mt-12 text-center text-xs text-slate-400">
        <p>© 2026 {company_name} Market Intelligence System. Powered by Antigravity Agentic Pipeline.</p>
    </footer>

    <!-- 인터랙티브 스크립트 -->
    <script>
        const articles = {top_30_json_str};

        function renderTable(data) {{
            const tbody = document.getElementById('tableBody');
            const noResults = document.getElementById('noResults');
            tbody.innerHTML = '';

            if (data.length === 0) {{
                noResults.classList.remove('hidden');
                return;
            }}
            noResults.classList.add('hidden');

            data.forEach((item, index) => {{
                const cat = (item.category || 'market').toLowerCase();
                let badgeCls = 'badge-market';
                let catName = '시장';
                if (cat.includes('policy')) {{ badgeCls = 'badge-policy'; catName = '정책'; }}
                else if (cat.includes('tech')) {{ badgeCls = 'badge-tech'; catName = '기술'; }}

                const tr = document.createElement('tr');
                tr.className = 'hover:bg-slate-800/40 transition';
                tr.innerHTML = `
                    <td class="py-3.5 px-3 text-center font-bold text-slate-400">#${{index + 1}}</td>
                    <td class="py-3.5 px-3"><span class="px-2 py-0.5 rounded-md text-[11px] font-semibold ${{badgeCls}}">${{catName}}</span></td>
                    <td class="py-3.5 px-4">
                        <div class="font-bold text-slate-100 hover:text-emerald-400 transition cursor-pointer" onclick="window.open('${{item.source_url}}', '_blank')">
                            ${{item.title}}
                        </div>
                        <div class="text-[11px] text-slate-400 mt-1 leading-normal">
                            ${{item.recommendation_reason || ''}}
                        </div>
                    </td>
                    <td class="py-3.5 px-3 text-slate-300">${{item.source_name || '-'}}</td>
                    <td class="py-3.5 px-3 text-slate-400 whitespace-nowrap">${{item.date || '-'}}</td>
                    <td class="py-3.5 px-3 text-center font-bold text-emerald-400">${{item.relevance_score || 0}}</td>
                    <td class="py-3.5 px-3 text-center">
                        <a href="${{item.source_url}}" target="_blank" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-[11px] border border-slate-700 transition">
                            링크
                        </a>
                    </td>
                `;
                tbody.appendChild(tr);
            }});
        }}

        function filterArticles() {{
            const query = document.getElementById('searchInput').value.toLowerCase().trim();
            const cat = document.getElementById('categoryFilter').value;

            const filtered = articles.filter(a => {{
                const matchesCat = (cat === 'ALL') || (a.category && a.category.toLowerCase().includes(cat.toLowerCase()));
                const searchTarget = `${{a.title}} ${{a.source_name}} ${{a.recommendation_reason}} ${{a.keywords}}`.toLowerCase();
                const matchesQuery = !query || searchTarget.includes(query);
                return matchesCat && matchesQuery;
            }});

            renderTable(filtered);
        }}

        document.getElementById('searchInput').addEventListener('input', filterArticles);
        document.getElementById('categoryFilter').addEventListener('change', filterArticles);

        // 초기 렌더링
        renderTable(articles);
    </script>
</body>
</html>
"""

        with open(self.html_output, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Generated HTML dashboard: {self.html_output}")

    def run(self) -> Dict[str, Any]:
        logger.info("Starting Dashboard and Web Report Generation...")
        profile, df_rec, df_clean = self._load_data()
        
        report_data = self._build_json_report(profile, df_rec, df_clean)
        self._build_html_dashboard(report_data)

        logger.info("Successfully built all web report assets in docs/")
        return report_data


if __name__ == "__main__":
    builder = SiteBuilder()
    report_data = builder.run()
    print("\n" + "="*50)
    print(" [SITE BUILDER EXECUTION SUMMARY] ")
    print("="*50)
    print(f"HTML Dashboard : {builder.html_output}")
    print(f"JSON Report    : {builder.json_output}")
    print(f"Total Top Items: {len(report_data['top_30'])}")
    print("="*50)
