import random
import time
import threading
from enum import Enum
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field


class DrawAlgorithm(str, Enum):
    FLAT = "flat"
    PRD = "prd"


@dataclass
class Prize:
    name: str
    probability: float
    is_win: bool = True
    is_guaranteed: bool = False
    data: Any = None

    def __post_init__(self):
        if not (0 <= self.probability <= 1):
            raise ValueError(f"Probability must be between 0 and 1, got {self.probability}")
        if self.is_guaranteed and not self.is_win:
            raise ValueError("Guaranteed prize must be a winning prize")


@dataclass
class UserState:
    total_draws: int = 0
    total_wins: int = 0
    consecutive_losses: int = 0
    cycle_start_time: Optional[float] = None
    prd_streak: int = 0
    prize_history: List[str] = field(default_factory=list)


class LotteryService:
    def __init__(
        self,
        prizes: List[Prize],
        guaranteed_threshold: int = 10,
        guaranteed_period_days: Optional[int] = None,
        time_func: Callable[[], float] = time.time,
        algorithm: DrawAlgorithm = DrawAlgorithm.FLAT,
    ):
        self._validate_prizes(prizes)
        self._prizes = prizes
        self._guaranteed_threshold = guaranteed_threshold
        self._guaranteed_period_days = guaranteed_period_days
        self._time_func = time_func
        self._algorithm = algorithm
        self._user_states: Dict[str, UserState] = {}
        self._lock = threading.Lock()

        self._guaranteed_prize = self._find_guaranteed_prize()
        self._cumulative_probs = self._build_cumulative_probs()

        self._win_prizes, self._win_cumulative = self._build_win_distribution()
        self._total_win_prob = sum(p.probability for p in self._win_prizes)
        self._prd_c = self._compute_prd_c(self._total_win_prob) if algorithm == DrawAlgorithm.PRD else 0.0

    def _build_win_distribution(self) -> tuple[List[Prize], List[float]]:
        win_prizes = [p for p in self._prizes if p.is_win]
        total = sum(p.probability for p in win_prizes)
        if total <= 0:
            return [], []
        cumulative = []
        acc = 0.0
        for p in win_prizes:
            acc += p.probability / total
            cumulative.append(acc)
        return win_prizes, cumulative

    def _sample_win_prize(self) -> Prize:
        r = random.random()
        for i, cum in enumerate(self._win_cumulative):
            if r <= cum:
                return self._win_prizes[i]
        return self._win_prizes[-1]

    def _compute_prd_c(self, target_p: float, max_iter: int = 100) -> float:
        if target_p <= 0:
            return 0.0
        if target_p >= 1:
            return 1.0

        lo = 0.0
        hi = target_p

        def simulate(c: float) -> float:
            p_acc = 0.0
            p_last = 0.0
            n = 1
            while True:
                p_n = min(c * n, 1.0)
                prob_n_hit = (1.0 - p_last) * p_n
                p_acc += prob_n_hit * n
                p_last += prob_n_hit
                n += 1
                if p_last >= 1.0 - 1e-15 or n > 100000:
                    break
            return 1.0 / p_acc if p_acc > 0 else 0.0

        for _ in range(max_iter):
            mid = (lo + hi) / 2
            actual = simulate(mid)
            if abs(actual - target_p) < 1e-8:
                return mid
            if actual < target_p:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    def _validate_prizes(self, prizes: List[Prize]) -> None:
        if not prizes:
            raise ValueError("Prize list cannot be empty")

        total_prob = sum(p.probability for p in prizes)
        if abs(total_prob - 1.0) > 1e-9:
            raise ValueError(f"Total probability must sum to 1, got {total_prob}")

        guaranteed_count = sum(1 for p in prizes if p.is_guaranteed)
        if guaranteed_count > 1:
            raise ValueError("Only one prize can be marked as guaranteed")

    def _find_guaranteed_prize(self) -> Optional[Prize]:
        for prize in self._prizes:
            if prize.is_guaranteed:
                return prize
        return None

    def _build_cumulative_probs(self) -> List[float]:
        cumulative = []
        total = 0.0
        for prize in self._prizes:
            total += prize.probability
            cumulative.append(total)
        return cumulative

    def _get_or_create_user_state(self, user_id: str) -> UserState:
        if user_id not in self._user_states:
            self._user_states[user_id] = UserState()
        return self._user_states[user_id]

    def _should_guarantee(self, user_state: UserState) -> bool:
        if self._guaranteed_prize is None:
            return False
        return user_state.consecutive_losses >= self._guaranteed_threshold - 1

    def _is_period_expired(self, user_state: UserState) -> bool:
        if self._guaranteed_period_days is None:
            return False
        if user_state.cycle_start_time is None:
            return False
        elapsed = self._time_func() - user_state.cycle_start_time
        return elapsed > self._guaranteed_period_days * 86400

    def _reset_cycle(self, user_state: UserState) -> None:
        user_state.consecutive_losses = 0
        user_state.cycle_start_time = None
        user_state.prd_streak = 0

    def _draw_flat(self) -> Prize:
        r = random.random()
        for i, cum_prob in enumerate(self._cumulative_probs):
            if r <= cum_prob:
                return self._prizes[i]
        return self._prizes[-1]

    def _draw_prd(self, user_state: UserState) -> Prize:
        if self._total_win_prob <= 0 or not self._win_prizes:
            return self._draw_flat()

        user_state.prd_streak += 1
        current_p = min(self._prd_c * user_state.prd_streak, 1.0)

        r = random.random()
        if r <= current_p:
            user_state.prd_streak = 0
            return self._sample_win_prize()
        else:
            for p in self._prizes:
                if not p.is_win:
                    return p
            return self._prizes[-1]

    def _draw_by_probability(self, user_state: UserState) -> Prize:
        if self._algorithm == DrawAlgorithm.PRD:
            return self._draw_prd(user_state)
        return self._draw_flat()

    def draw(self, user_id: str) -> Prize:
        with self._lock:
            user_state = self._get_or_create_user_state(user_id)
            user_state.total_draws += 1

            if self._is_period_expired(user_state):
                self._reset_cycle(user_state)

            if self._should_guarantee(user_state):
                prize = self._guaranteed_prize
                user_state.consecutive_losses = 0
                user_state.cycle_start_time = None
                user_state.prd_streak = 0
                user_state.total_wins += 1
            else:
                prize = self._draw_by_probability(user_state)
                if prize.is_win:
                    user_state.consecutive_losses = 0
                    user_state.cycle_start_time = None
                    user_state.prd_streak = 0
                    user_state.total_wins += 1
                else:
                    user_state.consecutive_losses += 1
                    if user_state.consecutive_losses == 1:
                        user_state.cycle_start_time = self._time_func()

            user_state.prize_history.append(prize.name)
            return prize

    def get_user_state(self, user_id: str) -> UserState:
        with self._lock:
            return self._get_or_create_user_state(user_id)

    def reset_user(self, user_id: str) -> None:
        with self._lock:
            if user_id in self._user_states:
                del self._user_states[user_id]

    def get_prizes(self) -> List[Prize]:
        return self._prizes.copy()

    @property
    def guaranteed_threshold(self) -> int:
        return self._guaranteed_threshold

    @property
    def guaranteed_period_days(self) -> Optional[int]:
        return self._guaranteed_period_days

    @property
    def guaranteed_prize(self) -> Optional[Prize]:
        return self._guaranteed_prize

    @property
    def algorithm(self) -> DrawAlgorithm:
        return self._algorithm

    @property
    def prd_c(self) -> float:
        return self._prd_c
