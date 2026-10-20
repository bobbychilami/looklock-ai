# Application-level SerpApi search quota guard (testable, deterministic)
from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
GUARD_STATE_FILE = Path(__file__).resolve().parents[2] / '.serpapi_guard_state.json'
@dataclass
class _State:
    month_key: str
    count: int = 0
class SerpApiSearchGuard:
    def __init__(self, monthly_limit: int = 100, state_file: Path = GUARD_STATE_FILE) -> None:
        self._monthly_limit = monthly_limit
        self._state_file = state_file
        self._lock = Lock()
        self._state = self._load_state()
    def _month_key(self, now: datetime | None = None) -> str:
        now = now or datetime.now(timezone.utc)
        return f'{now.year}-{now.month:02d}'
    def _load_state(self) -> _State:
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text(encoding='utf-8'))
                mk = data.get('month_key') or self._month_key()
                cnt = int(data.get('count', 0))
                return _State(month_key=mk, count=cnt)
        except Exception:
            pass
        return _State(month_key=self._month_key(), count=0)
    def _save_state(self) -> None:
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(json.dumps({'month_key': self._state.month_key, 'count': self._state.count}), encoding='utf-8')
        except Exception:
            pass
    def _rollover_if_needed(self, now: datetime | None = None) -> None:
        mk = self._month_key(now)
        if self._state.month_key != mk:
            self._state.month_key = mk
            self._state.count = 0
            self._save_state()
    def reset(self) -> None:
        with self._lock:
            self._state = _State(month_key=self._month_key(), count=0)
            self._save_state()
    @property
    def count(self) -> int:
        with self._lock:
            self._rollover_if_needed()
            return self._state.count
    @property
    def limit(self) -> int:
        return self._monthly_limit
    @property
    def remaining(self) -> int:
        return max(0, self._monthly_limit - self.count)
    def can_perform_search(self) -> tuple[bool, str]:
        with self._lock:
            self._rollover_if_needed()
            if self._state.count >= self._monthly_limit:
                return False, f'SerpApi monthly search limit reached. ({self._state.count}/{self._monthly_limit} this month).'
            return True, ''
    def record_search(self) -> None:
        with self._lock:
            self._rollover_if_needed()
            self._state.count += 1
            self._save_state()
