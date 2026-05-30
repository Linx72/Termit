import sqlite3
from datetime import date
from pathlib import Path
from threading import Lock
from typing import Optional


class QuotaStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = str(Path(db_path).resolve())
        self._lock = Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_usage (
                    api_key TEXT NOT NULL,
                    usage_day TEXT NOT NULL,
                    request_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (api_key, usage_day)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS team_usage (
                    team TEXT NOT NULL,
                    usage_day TEXT NOT NULL,
                    request_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (team, usage_day)
                )
                """
            )
            conn.commit()

    def _today(self) -> str:
        return date.today().isoformat()

    def get_usage(self, api_key: str) -> int:
        usage_day = self._today()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT request_count FROM api_usage WHERE api_key = ? AND usage_day = ?",
                (api_key, usage_day),
            ).fetchone()
        return int(row["request_count"]) if row else 0

    def consume(self, api_key: str, daily_limit: int) -> tuple[bool, int, int]:
        usage_day = self._today()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT request_count FROM api_usage WHERE api_key = ? AND usage_day = ?",
                (api_key, usage_day),
            ).fetchone()
            current = int(row["request_count"]) if row else 0
            if current >= daily_limit:
                return False, current, daily_limit

            if row:
                conn.execute(
                    "UPDATE api_usage SET request_count = request_count + 1 "
                    "WHERE api_key = ? AND usage_day = ?",
                    (api_key, usage_day),
                )
            else:
                conn.execute(
                    "INSERT INTO api_usage(api_key, usage_day, request_count) VALUES (?, ?, 1)",
                    (api_key, usage_day),
                )
            conn.commit()
            new_count = current + 1
        return True, new_count, daily_limit

    def reset_usage(self, api_key: str, usage_day: Optional[str] = None) -> bool:
        day = usage_day or self._today()
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM api_usage WHERE api_key = ? AND usage_day = ?",
                (api_key, day),
            )
            conn.commit()
        return cursor.rowcount > 0

    def list_usage_for_day(self, usage_day: Optional[str] = None) -> dict[str, int]:
        day = usage_day or self._today()
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT api_key, request_count FROM api_usage WHERE usage_day = ?",
                (day,),
            ).fetchall()
        return {str(row["api_key"]): int(row["request_count"]) for row in rows}

    def get_team_usage(self, team: str) -> int:
        usage_day = self._today()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT request_count FROM team_usage WHERE team = ? AND usage_day = ?",
                (team, usage_day),
            ).fetchone()
        return int(row["request_count"]) if row else 0

    def list_team_usage_for_day(self, usage_day: Optional[str] = None) -> dict[str, int]:
        day = usage_day or self._today()
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT team, request_count FROM team_usage WHERE usage_day = ?",
                (day,),
            ).fetchall()
        return {str(row["team"]): int(row["request_count"]) for row in rows}

    def reset_team_usage(self, team: str, usage_day: Optional[str] = None) -> bool:
        day = usage_day or self._today()
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM team_usage WHERE team = ? AND usage_day = ?",
                (team, day),
            )
            conn.commit()
        return cursor.rowcount > 0

    def consume_with_team(
        self,
        api_key: str,
        daily_limit: int,
        team: Optional[str],
        team_daily_limit: Optional[int],
    ) -> tuple[bool, int, int, Optional[int], Optional[int]]:
        usage_day = self._today()
        with self._lock, self._connect() as conn:
            key_row = conn.execute(
                "SELECT request_count FROM api_usage WHERE api_key = ? AND usage_day = ?",
                (api_key, usage_day),
            ).fetchone()
            key_current = int(key_row["request_count"]) if key_row else 0
            if key_current >= daily_limit:
                return False, key_current, daily_limit, None, None

            team_used: Optional[int] = None
            team_limit: Optional[int] = None
            if team and team_daily_limit is not None:
                team_row = conn.execute(
                    "SELECT request_count FROM team_usage WHERE team = ? AND usage_day = ?",
                    (team, usage_day),
                ).fetchone()
                team_current = int(team_row["request_count"]) if team_row else 0
                if team_current >= team_daily_limit:
                    return (
                        False,
                        key_current,
                        daily_limit,
                        team_current,
                        team_daily_limit,
                    )
                team_used = team_current + 1
                team_limit = team_daily_limit
                if team_row:
                    conn.execute(
                        "UPDATE team_usage SET request_count = request_count + 1 "
                        "WHERE team = ? AND usage_day = ?",
                        (team, usage_day),
                    )
                else:
                    conn.execute(
                        "INSERT INTO team_usage(team, usage_day, request_count) VALUES (?, ?, 1)",
                        (team, usage_day),
                    )

            if key_row:
                conn.execute(
                    "UPDATE api_usage SET request_count = request_count + 1 "
                    "WHERE api_key = ? AND usage_day = ?",
                    (api_key, usage_day),
                )
            else:
                conn.execute(
                    "INSERT INTO api_usage(api_key, usage_day, request_count) VALUES (?, ?, 1)",
                    (api_key, usage_day),
                )
            conn.commit()
            key_used = key_current + 1
        return True, key_used, daily_limit, team_used, team_limit
