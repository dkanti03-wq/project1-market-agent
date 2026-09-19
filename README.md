# Project 1: Market & Competitor Intelligence Agent (`project1-market-agent`)

시장 및 경쟁사 동향, 정부 지원사업 정보를 수집·분석하여 의사결정용 인텔리전스 리포트 및 GitHub Pages 정적 사이트를 자동 생성하는 마켓 인텔리전스 에이전트입니다.

## 📁 프로젝트 구조

```text
day1/
├── .github/              # GitHub Actions 워크플로 및 Pages 배포 설정
├── config/               # 기업 프로필 및 수집 기준 설정
│   └── company_profile.yaml
├── data/                 # 수집 데이터 및 fallback 데이터셋
│   ├── fallback/
│   │   └── fallback_market_news.csv
│   └── raw/              # 수집된 원본 데이터 저장 위치
├── docs/                 # GitHub Pages 배포용 정적 웹 리포트 산출물
├── logs/                 # 에이전트 실행 및 수집 로그
├── src/                  # 에이전트 핵심 소스코드 모듈
├── .env.example          # 환경변수 예시 템플릿
├── .gitignore            # Git 관리 제외 항목
├── requirements.txt      # 프로젝트 의존성 패키지 목록
└── README.md             # 프로젝트 개요 및 가이드
```

## 🏢 대상 기업 프로필 (NovaFactory AI)

- **기업명**: NovaFactory AI
- **주요 사업 영역**: 제조업 AI 비전 품질검사
- **주요 제품/서비스**: 비전 기반 불량 탐지 SaaS, 제조 품질 리포트 자동화
- **목표 시장**: 중소·중견 제조기업, 스마트팩토리 구축 기업
- **주요 경쟁사**: VisionForge, InspectAI, FactoryMind, QualiBot, SmartSensorix
- **시장/기술 키워드**: AI, 스마트팩토리, 품질검사, 머신비전, 자동화, 클라우드, 제조 AX
- **지원사업/펀딩 키워드**: 창업지원, AI 바우처, 스마트공장, R&D, 사업화 자금, 기술개발 지원

## 🚀 빠른 시작

1. 의존성 설치:
   ```bash
   pip install -r requirements.txt
   ```
2. 환경 설정:
   ```bash
   cp .env.example .env
   ```
3. 에이전트 실행 (예시):
   ```bash
   python -m src.main
   ```
