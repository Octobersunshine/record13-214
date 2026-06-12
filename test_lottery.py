import random
import unittest
from collections import Counter
from lottery_service import LotteryService, Prize, DrawAlgorithm


class TestLotteryService(unittest.TestCase):
    def setUp(self):
        random.seed(42)

    def test_prize_validation(self):
        with self.assertRaises(ValueError):
            Prize("Test", 1.5)

        with self.assertRaises(ValueError):
            Prize("Test", -0.1)

        with self.assertRaises(ValueError):
            Prize("Test", 0.1, is_win=False, is_guaranteed=True)

    def test_service_validation(self):
        with self.assertRaises(ValueError):
            LotteryService([])

        prizes = [
            Prize("A", 0.5),
            Prize("B", 0.3),
        ]
        with self.assertRaises(ValueError):
            LotteryService(prizes)

        prizes = [
            Prize("A", 0.5, is_guaranteed=True),
            Prize("B", 0.3, is_guaranteed=True),
            Prize("C", 0.2),
        ]
        with self.assertRaises(ValueError):
            LotteryService(prizes)

    def test_probability_distribution(self):
        prizes = [
            Prize("一等奖", 0.05),
            Prize("二等奖", 0.15),
            Prize("三等奖", 0.30),
            Prize("谢谢参与", 0.50, is_win=False),
        ]
        service = LotteryService(prizes, guaranteed_threshold=100)

        num_draws = 100000
        results = []
        for i in range(num_draws):
            prize = service.draw(f"user_{i % 1000}")
            results.append(prize.name)

        counts = Counter(results)

        for prize in prizes:
            expected = prize.probability
            actual = counts[prize.name] / num_draws
            self.assertAlmostEqual(actual, expected, delta=0.01,
                                   msg=f"{prize.name}: expected {expected}, got {actual}")

    def test_guaranteed_mechanism(self):
        prizes = [
            Prize("稀有奖品", 0.01, is_guaranteed=True),
            Prize("普通奖品", 0.09),
            Prize("谢谢参与", 0.90, is_win=False),
        ]
        threshold = 10
        service = LotteryService(prizes, guaranteed_threshold=threshold)

        user_id = "test_user"

        for i in range(threshold - 1):
            prize = service.draw(user_id)
            state = service.get_user_state(user_id)
            if prize.name == "稀有奖品" or prize.name == "普通奖品":
                self.assertEqual(state.consecutive_losses, 0)
                break
            self.assertEqual(state.consecutive_losses, i + 1)
        else:
            prize = service.draw(user_id)
            self.assertEqual(prize.name, "稀有奖品",
                             f"Expected guaranteed prize on draw {threshold}, got {prize.name}")
            state = service.get_user_state(user_id)
            self.assertEqual(state.consecutive_losses, 0)

    def test_guaranteed_reset_on_win(self):
        prizes = [
            Prize("稀有奖品", 0.01, is_guaranteed=True),
            Prize("普通奖品", 0.50),
            Prize("谢谢参与", 0.49, is_win=False),
        ]
        threshold = 10
        service = LotteryService(prizes, guaranteed_threshold=threshold)

        user_id = "test_user_2"
        random.seed(123)

        for _ in range(100):
            prize = service.draw(user_id)
            state = service.get_user_state(user_id)
            if prize.is_win:
                self.assertEqual(state.consecutive_losses, 0)
            self.assertLess(state.consecutive_losses, threshold)

    def test_guaranteed_multiple_users(self):
        prizes = [
            Prize("稀有奖品", 0.001, is_guaranteed=True),
            Prize("谢谢参与", 0.999, is_win=False),
        ]
        threshold = 5
        service = LotteryService(prizes, guaranteed_threshold=threshold)

        for user_idx in range(10):
            user_id = f"user_{user_idx}"
            for i in range(threshold - 1):
                prize = service.draw(user_id)
                self.assertEqual(prize.name, "谢谢参与")

            prize = service.draw(user_id)
            self.assertEqual(prize.name, "稀有奖品",
                             f"User {user_id}: expected guaranteed prize")

    def test_user_state_tracking(self):
        prizes = [
            Prize("中奖", 0.001, is_guaranteed=True),
            Prize("未中奖", 0.999, is_win=False),
        ]
        threshold = 5
        service = LotteryService(prizes, guaranteed_threshold=threshold)

        user_id = "state_test"
        random.seed(999)

        for i in range(threshold - 1):
            prize = service.draw(user_id)
            self.assertEqual(prize.name, "未中奖")

        prize = service.draw(user_id)
        self.assertEqual(prize.name, "中奖")

        state = service.get_user_state(user_id)
        self.assertEqual(state.total_draws, threshold)
        self.assertEqual(state.total_wins, 1)
        self.assertEqual(state.consecutive_losses, 0)
        self.assertEqual(len(state.prize_history), threshold)
        self.assertEqual(state.prize_history[-1], "中奖")
        self.assertEqual(state.prize_history[0], "未中奖")

    def test_reset_user(self):
        prizes = [
            Prize("中奖", 1.0, is_guaranteed=True),
        ]
        service = LotteryService(prizes)

        user_id = "reset_test"
        service.draw(user_id)
        state = service.get_user_state(user_id)
        self.assertEqual(state.total_draws, 1)

        service.reset_user(user_id)
        state = service.get_user_state(user_id)
        self.assertEqual(state.total_draws, 0)

    def test_no_guaranteed_prize(self):
        prizes = [
            Prize("A", 0.3),
            Prize("B", 0.7),
        ]
        service = LotteryService(prizes)

        self.assertIsNone(service.guaranteed_prize)

        for i in range(100):
            prize = service.draw(f"user_{i}")
            self.assertIn(prize.name, ["A", "B"])

    def test_prize_with_data(self):
        prizes = [
            Prize("金币", 0.5, data={"amount": 100}),
            Prize("钻石", 0.5, data={"amount": 10}),
        ]
        service = LotteryService(prizes)

        prize = service.draw("test")
        self.assertIsNotNone(prize.data)
        self.assertIn("amount", prize.data)

    def test_period_expired_resets_counter(self):
        prizes = [
            Prize("稀有奖品", 0.001, is_guaranteed=True),
            Prize("谢谢参与", 0.999, is_win=False),
        ]
        threshold = 10
        period_days = 3
        now = 1000000.0
        service = LotteryService(
            prizes,
            guaranteed_threshold=threshold,
            guaranteed_period_days=period_days,
            time_func=lambda: now,
        )

        user_id = "period_user"
        for i in range(5):
            service.draw(user_id)

        state = service.get_user_state(user_id)
        self.assertEqual(state.consecutive_losses, 5)
        self.assertIsNotNone(state.cycle_start_time)

        now += period_days * 86400 + 1

        service.draw(user_id)
        state = service.get_user_state(user_id)
        self.assertEqual(state.consecutive_losses, 1)
        self.assertEqual(state.total_draws, 6)

    def test_period_not_expired_keeps_counter(self):
        prizes = [
            Prize("稀有奖品", 0.001, is_guaranteed=True),
            Prize("谢谢参与", 0.999, is_win=False),
        ]
        threshold = 10
        period_days = 3
        now = 1000000.0
        service = LotteryService(
            prizes,
            guaranteed_threshold=threshold,
            guaranteed_period_days=period_days,
            time_func=lambda: now,
        )

        user_id = "within_period_user"
        for i in range(5):
            service.draw(user_id)

        now += period_days * 86400 - 1

        service.draw(user_id)
        state = service.get_user_state(user_id)
        self.assertEqual(state.consecutive_losses, 6)

    def test_period_resets_after_win(self):
        prizes = [
            Prize("稀有奖品", 0.5, is_guaranteed=True),
            Prize("谢谢参与", 0.5, is_win=False),
        ]
        period_days = 3
        now = 1000000.0
        service = LotteryService(
            prizes,
            guaranteed_threshold=10,
            guaranteed_period_days=period_days,
            time_func=lambda: now,
        )

        user_id = "win_reset_user"
        random.seed(77)
        service.draw(user_id)
        service.draw(user_id)
        state = service.get_user_state(user_id)
        if state.consecutive_losses == 0:
            self.assertIsNone(state.cycle_start_time)

        now += 100

        for _ in range(3):
            service.draw(user_id)
        state_after = service.get_user_state(user_id)
        if state_after.consecutive_losses > 0:
            self.assertIsNotNone(state_after.cycle_start_time)

    def test_backward_compatible_no_period(self):
        prizes = [
            Prize("稀有奖品", 0.001, is_guaranteed=True),
            Prize("谢谢参与", 0.999, is_win=False),
        ]
        service = LotteryService(prizes, guaranteed_threshold=5)
        self.assertIsNone(service.guaranteed_period_days)

        user_id = "compat_user"
        for i in range(4):
            service.draw(user_id)
        state = service.get_user_state(user_id)
        self.assertEqual(state.consecutive_losses, 4)

        prize = service.draw(user_id)
        self.assertEqual(prize.name, "稀有奖品")

    def test_period_expired_then_guaranteed_works_in_new_cycle(self):
        prizes = [
            Prize("稀有奖品", 0.001, is_guaranteed=True),
            Prize("谢谢参与", 0.999, is_win=False),
        ]
        threshold = 3
        period_days = 1
        now = 1000000.0
        service = LotteryService(
            prizes,
            guaranteed_threshold=threshold,
            guaranteed_period_days=period_days,
            time_func=lambda: now,
        )

        user_id = "new_cycle_user"
        service.draw(user_id)
        service.draw(user_id)
        state = service.get_user_state(user_id)
        self.assertEqual(state.consecutive_losses, 2)

        now += period_days * 86400 + 1

        service.draw(user_id)
        state = service.get_user_state(user_id)
        self.assertEqual(state.consecutive_losses, 1)
        self.assertIsNotNone(state.cycle_start_time)

        now += 10
        service.draw(user_id)
        state = service.get_user_state(user_id)
        self.assertEqual(state.consecutive_losses, 2)

        now += 10
        prize = service.draw(user_id)
        self.assertEqual(prize.name, "稀有奖品")
        state = service.get_user_state(user_id)
        self.assertEqual(state.consecutive_losses, 0)
        self.assertIsNone(state.cycle_start_time)

    def test_prd_distribution_accuracy(self):
        prizes = [
            Prize("一等奖", 0.05),
            Prize("二等奖", 0.15),
            Prize("三等奖", 0.30),
            Prize("谢谢参与", 0.50, is_win=False),
        ]
        service = LotteryService(
            prizes,
            guaranteed_threshold=1000,
            algorithm=DrawAlgorithm.PRD,
        )

        num_draws = 100000
        results = []
        for i in range(num_draws):
            prize = service.draw(f"user_{i % 1000}")
            results.append(prize.name)

        counts = Counter(results)

        actual_win_rate = sum(counts[p.name] for p in prizes if p.is_win) / num_draws
        expected_win_rate = sum(p.probability for p in prizes if p.is_win)
        self.assertAlmostEqual(actual_win_rate, expected_win_rate, delta=0.02,
                               msg=f"Win rate: expected {expected_win_rate}, got {actual_win_rate}")

    def test_prd_c_value(self):
        prizes = [
            Prize("中奖", 0.5),
            Prize("未中奖", 0.5, is_win=False),
        ]
        service = LotteryService(prizes, guaranteed_threshold=100, algorithm=DrawAlgorithm.PRD)
        self.assertGreater(service.prd_c, 0)
        self.assertLess(service.prd_c, 0.5)

    def test_prd_reduces_long_losing_streaks(self):
        prizes = [
            Prize("中奖", 0.1),
            Prize("未中奖", 0.9, is_win=False),
        ]
        threshold = 100
        num_draws = 50000
        num_users = 100

        def measure_streaks(algo: DrawAlgorithm) -> list[int]:
            random.seed(42)
            service = LotteryService(
                prizes,
                guaranteed_threshold=threshold,
                algorithm=algo,
            )
            streaks = []
            for u in range(num_users):
                current = 0
                for _ in range(num_draws // num_users):
                    prize = service.draw(f"u_{algo.value}_{u}")
                    if prize.is_win:
                        streaks.append(current)
                        current = 0
                    else:
                        current += 1
                streaks.append(current)
            return streaks

        flat_streaks = measure_streaks(DrawAlgorithm.FLAT)
        prd_streaks = measure_streaks(DrawAlgorithm.PRD)

        flat_max = max(flat_streaks)
        prd_max = max(prd_streaks)
        self.assertLess(prd_max, flat_max,
                        msg=f"PRD max streak {prd_max} should be < Flat max streak {flat_max}")

        flat_p99 = sorted(flat_streaks)[int(len(flat_streaks) * 0.99)]
        prd_p99 = sorted(prd_streaks)[int(len(prd_streaks) * 0.99)]
        self.assertLess(prd_p99, flat_p99,
                        msg=f"PRD p99 streak {prd_p99} should be < Flat p99 {flat_p99}")

    def test_prd_streak_resets_on_win(self):
        prizes = [
            Prize("中奖", 0.0001),
            Prize("未中奖", 0.9999, is_win=False),
        ]
        service = LotteryService(
            prizes,
            guaranteed_threshold=1000,
            algorithm=DrawAlgorithm.PRD,
        )
        user_id = "reset_check"
        random.seed(0)

        for _ in range(5):
            service.draw(user_id)
        state = service.get_user_state(user_id)
        self.assertEqual(state.prd_streak, 5)

        for _ in range(10000):
            prize = service.draw(user_id)
            state = service.get_user_state(user_id)
            if prize.is_win:
                self.assertEqual(state.prd_streak, 0)
                break
        else:
            self.fail("Expected a win within 10000 draws with PRD")

    def test_prd_backward_compatible_default_flat(self):
        prizes = [
            Prize("A", 0.5),
            Prize("B", 0.5),
        ]
        service = LotteryService(prizes)
        self.assertEqual(service.algorithm, DrawAlgorithm.FLAT)
        self.assertEqual(service.prd_c, 0.0)

    def test_prd_and_guaranteed_coexist(self):
        prizes = [
            Prize("稀有", 0.01, is_guaranteed=True),
            Prize("普通", 0.09),
            Prize("谢谢", 0.90, is_win=False),
        ]
        threshold = 8
        service = LotteryService(
            prizes,
            guaranteed_threshold=threshold,
            algorithm=DrawAlgorithm.PRD,
        )

        user_id = "mixed_user"
        random.seed(12345)
        max_loss = 0
        for _ in range(200):
            prize = service.draw(user_id)
            state = service.get_user_state(user_id)
            if state.consecutive_losses > max_loss:
                max_loss = state.consecutive_losses
            self.assertLessEqual(state.consecutive_losses, threshold - 1)
            if prize.is_guaranteed:
                self.assertEqual(state.consecutive_losses, 0)

    def test_thread_safety(self):
        import threading

        prizes = [
            Prize("稀有", 0.01, is_guaranteed=True),
            Prize("普通", 0.09),
            Prize("谢谢", 0.90, is_win=False),
        ]
        service = LotteryService(prizes, guaranteed_threshold=10)

        results = []
        lock = threading.Lock()

        def draw_many(user_id, count):
            local_results = []
            for _ in range(count):
                prize = service.draw(user_id)
                local_results.append(prize.name)
            with lock:
                results.extend(local_results)

        threads = []
        for i in range(10):
            t = threading.Thread(target=draw_many, args=(f"thread_user_{i}", 100))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(len(results), 1000)


if __name__ == "__main__":
    unittest.main()
