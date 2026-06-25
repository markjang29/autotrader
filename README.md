# Auto-Trader (자동매매 시스템)

> 알고리즘 / 자동매매 트레이딩 시스템 프로젝트.
> 전략 수립 → 백테스트 → 실거래 연동을 목표로 한다.

## 상태

- 초기 세팅 (2026-06-25)
- 기술스택 미확정 (아래 결정 항목 참고)

## 결정해야 할 것

- [ ] 언어/런타임: **Python(권장)** vs Node.js
- [ ] 대상 시장: 암호화폐(ccxt) / 주식 / 선물
- [ ] 백테스트 프레임워크: backtrader / vectorbt / 자체
- [ ] 실거래 연동: REST / WebSocket, 테스트넷 우선
- [ ] 데이터 저장: SQLite / PostgreSQL / Parquet

## 협업 규칙 (중요)

이 프로젝트는 **여러 환경의 에이전트가 함께 작업**한다:

- Linux 서버 (Claude Code)
- Windows 머신 (별도 에이전트)

원칙:

1. 작업 전 반드시 `git pull`, 작업 후 즉시 `git push`.
2. 커밋 메시지는 변경 내용을 명확히 서술한다 (한국어 OK).
3. 중요 결정/변경은 이 README 또는 `docs/` 에 문서화.
4. 전반적인 작업 맥락과 일일 진행은 `notes` 저장소(`github.com/markjang29/notes`)에 기록.
5. 비밀키/API 키는 절대 커밋 금지 (`.env` 사용, `.gitignore`에 포함됨).

## 구조 (예정)

```
autotrader/
├── README.md
├── .gitignore
├── docs/          # 설계/결정 문서
├── src/           # 소스코드
├── tests/         # 테스트
└── data/          # 시장 데이터 (git 제외)
```
