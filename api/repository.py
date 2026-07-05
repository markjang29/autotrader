"""백테스트 결과 히스토리 저장 — Oracle (oracledb).

연결정보 환경변수 (서버 기동 시 export):
    ORACLE_DSN    (예: localhost:1521/FREEPDB1)
    ORACLE_USER   (예: system)
    ORACLE_PASSWORD  (~/.oracle-env 에서 로드 — 하드코딩/커밋 금지)
미설정·연결실패 시 NoopRepo(no-op)로 graceful fallback — API 동작은 영향 없음.

스키마(bt_runs): run_id · ts · strategy · target · start_date · end_date · params(CLOB) · metrics(CLOB)
  = 매니저 요구(전략명·파라미터·기간·메트릭·타임스탬프).
"""
import os
import json
import logging
import datetime
from typing import Optional

log = logging.getLogger("autotrader.repo")


def _creds():
    return (os.environ.get("ORACLE_DSN"),
            os.environ.get("ORACLE_USER"),
            os.environ.get("ORACLE_PASSWORD"))


class BacktestRepo:
    """저장 인터페이스."""

    def save_run(self, request: dict, result: dict) -> Optional[str]:
        raise NotImplementedError


class OracleRepo(BacktestRepo):
    def __init__(self):
        self.conn = None
        dsn, user, pwd = _creds()
        if not (dsn and user and pwd):
            log.warning("Oracle 연결정보 미설정 → no-op 모드")
            return
        try:
            import oracledb
            self.conn = oracledb.connect(user=user, password=pwd, dsn=dsn)
            self._ensure_table()
            log.info("Oracle 연결 성공: %s (v%s)", dsn, self.conn.version)
        except Exception as e:
            log.warning("Oracle 연결 실패(%s) → no-op", e)
            self.conn = None

    def _ensure_table(self):
        if not self.conn:
            return
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "CREATE TABLE bt_runs ("
                    " run_id VARCHAR2(64) PRIMARY KEY,"
                    " ts TIMESTAMP DEFAULT SYSTIMESTAMP,"
                    " strategy VARCHAR2(32),"
                    " target VARCHAR2(16),"
                    " start_date VARCHAR2(10),"
                    " end_date VARCHAR2(10),"
                    " params CLOB,"
                    " metrics CLOB)"
                )
                self.conn.commit()
            log.info("bt_runs 테이블 생성")
        except Exception as e:
            # 이미 존재하는 경우 무시
            log.info("bt_runs 테이블 존재 또는 생성 스킵: %s", e)

    def save_run(self, request, result):
        if not self.conn:
            return None
        run_id = f"bt_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        target = request.get("target") or (request.get("symbols") or ["?"])[0]
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO bt_runs"
                    "(run_id,strategy,target,start_date,end_date,params,metrics) "
                    "VALUES(:1,:2,:3,:4,:5,:6,:7)",
                    [run_id,
                     request.get("strategy"),
                     target,
                     str(request.get("start", "")),
                     str(request.get("end", "")),
                     json.dumps(request, default=str),
                     json.dumps(result.get("metrics", {}), default=str)])
            self.conn.commit()
            return run_id
        except Exception as e:
            log.warning("save 실패: %s", e)
            return None


class NoopRepo(BacktestRepo):
    def save_run(self, request, result):
        return None


def get_repo() -> BacktestRepo:
    dsn, user, pwd = _creds()
    if dsn and user and pwd:
        return OracleRepo()
    return NoopRepo()
