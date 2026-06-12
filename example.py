from lottery_service import LotteryService, Prize


def basic_usage():
    print("=== 基础抽奖示例 ===")

    prizes = [
        Prize("特等奖", 0.01, is_guaranteed=True),
        Prize("一等奖", 0.04),
        Prize("二等奖", 0.15),
        Prize("三等奖", 0.30),
        Prize("谢谢参与", 0.50, is_win=False),
    ]

    service = LotteryService(prizes, guaranteed_threshold=10)

    print(f"保底奖品: {service.guaranteed_prize.name}")
    print(f"保底阈值: {service.guaranteed_threshold} 次")
    print()

    user_id = "player_001"
    print(f"用户 {user_id} 开始抽奖：")
    for i in range(15):
        prize = service.draw(user_id)
        state = service.get_user_state(user_id)
        status = "中奖!" if prize.is_win else "未中奖"
        print(f"  第 {i + 1:2d} 次: {prize.name:8} {status:5} | 连续未中: {state.consecutive_losses}")

    print()


def guaranteed_demo():
    print("=== 保底机制演示 ===")

    import random
    random.seed(0)

    prizes = [
        Prize("稀有道具", 0.001, is_guaranteed=True, data={"id": "item_001", "rarity": "SSR"}),
        Prize("普通道具", 0.099, data={"id": "item_002", "rarity": "R"}),
        Prize("谢谢参与", 0.90, is_win=False),
    ]

    threshold = 5
    service = LotteryService(prizes, guaranteed_threshold=threshold)

    user_id = "lucky_player"
    print(f"设置: {threshold} 次未中必中稀有道具")
    print(f"稀有道具概率: 0.1%")
    print()

    for i in range(threshold - 1):
        prize = service.draw(user_id)
        state = service.get_user_state(user_id)
        print(f"第 {i + 1} 次: {prize.name:8} | 连续未中: {state.consecutive_losses}")

    prize = service.draw(user_id)
    state = service.get_user_state(user_id)
    guaranteed_triggered = prize.is_guaranteed and state.consecutive_losses == 0
    trigger_msg = " (保底触发!)" if guaranteed_triggered else ""
    print(f"第 {threshold} 次: {prize.name:8} | 连续未中: {state.consecutive_losses}{trigger_msg}")
    if prize.data:
        print(f"  奖品数据: {prize.data}")

    print()


def multi_user_demo():
    print("=== 多用户独立状态演示 ===")

    prizes = [
        Prize("大奖", 0.1, is_guaranteed=True),
        Prize("谢谢参与", 0.9, is_win=False),
    ]

    service = LotteryService(prizes, guaranteed_threshold=3)

    users = ["Alice", "Bob", "Charlie"]
    for user_id in users:
        print(f"\n用户 {user_id}:")
        for i in range(4):
            prize = service.draw(user_id)
            state = service.get_user_state(user_id)
            status = "★" if prize.is_win else " "
            print(f"  第{i+1}次: {prize.name:6} {status} 连续未中:{state.consecutive_losses}")

    print()


if __name__ == "__main__":
    basic_usage()
    guaranteed_demo()
    multi_user_demo()
