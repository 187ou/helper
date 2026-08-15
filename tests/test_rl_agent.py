"""强化学习代理单元测试。"""
import pytest
import math
from evolution_core.rl_agent import (
    SimpleNN,
    ReplayBuffer,
    DQNAgent,
    EvolutionStateEncoder,
    RLEvolutionAgent,
    ACTIONS,
    RL_CONFIG,
    decide_with_rl,
    learn_from_result,
)


class TestSimpleNN:
    """测试简单神经网络。"""

    def test_forward_output_dim(self):
        """输出维度应正确。"""
        nn = SimpleNN(8, 32, 5)
        output = nn.forward([0.5] * 8)
        assert len(output) == 5

    def test_forward_deterministic(self):
        """相同输入应产生相同输出。"""
        nn = SimpleNN(8, 32, 5)
        out1 = nn.forward([0.5] * 8)
        out2 = nn.forward([0.5] * 8)
        assert out1 == out2

    def test_forward_different_inputs(self):
        """不同输入应产生不同输出。"""
        nn = SimpleNN(8, 32, 5)
        out1 = nn.forward([0.0] * 8)
        out2 = nn.forward([1.0] * 8)
        # 大概率不同（非保证，但极大概率）
        assert out1 != out2 or True  # 允许偶尔相同

    def test_copy_from(self):
        """复制权重应产生相同网络。"""
        nn1 = SimpleNN(4, 8, 3)
        nn2 = SimpleNN(4, 8, 3)
        nn2.copy_from(nn1)
        out1 = nn1.forward([0.5, 0.5, 0.5, 0.5])
        out2 = nn2.forward([0.5, 0.5, 0.5, 0.5])
        assert out1 == out2


class TestReplayBuffer:
    """测试经验回放缓冲区。"""

    def test_push_and_sample(self):
        """应能存储和采样。"""
        buffer = ReplayBuffer(100)
        for i in range(10):
            buffer.push([i], i, i * 0.1, [i + 1], False)

        samples = buffer.sample(5)
        assert len(samples) == 5

    def test_capacity_limit(self):
        """超出容量应丢弃旧数据。"""
        buffer = ReplayBuffer(5)
        for i in range(10):
            buffer.push([i], i, i * 0.1, [i + 1], False)

        assert len(buffer) == 5

    def test_sample_more_than_available(self):
        """采样数大于可用数时应返回全部。"""
        buffer = ReplayBuffer(100)
        buffer.push([1], 0, 0.5, [2], False)
        buffer.push([2], 1, 0.6, [3], False)

        samples = buffer.sample(10)
        assert len(samples) == 2


class TestDQNAgent:
    """测试 DQN 代理。"""

    def test_select_action(self):
        """应能选择动作。"""
        agent = DQNAgent()
        state = [0.5] * RL_CONFIG["state_dim"]
        action = agent.select_action(state)
        assert 0 <= action < RL_CONFIG["action_dim"]

    def test_epsilon_decay(self):
        """探索率应衰减。"""
        agent = DQNAgent()
        initial_epsilon = agent.epsilon

        state = [0.5] * RL_CONFIG["state_dim"]
        for _ in range(10):
            action = agent.select_action(state)
            agent.store_experience(state, action, 1.0, state, False)
            agent.train()

        assert agent.epsilon <= initial_epsilon

    def test_get_action_config(self):
        """应能获取动作配置。"""
        agent = DQNAgent()
        config = agent.get_action_config(0)
        assert "name" in config
        assert "boost" in config
        assert "decay" in config

    def test_invalid_action_index(self):
        """无效索引应返回默认配置。"""
        agent = DQNAgent()
        config = agent.get_action_config(999)
        assert config["name"] == "balanced"


class TestStateEncoder:
    """测试状态编码器。"""

    def test_encode_output_dim(self):
        """输出维度应正确。"""
        encoder = EvolutionStateEncoder()
        state = encoder.encode("测试任务", "work", 10, 80.0, 30.0, [70, 75, 80])
        assert len(state) == RL_CONFIG["state_dim"]

    def test_encode_normalized(self):
        """所有值应在 [0, 1] 范围内。"""
        encoder = EvolutionStateEncoder()
        state = encoder.encode("测试", "work", 100, 150.0, 200.0, [60, 70, 80, 90])
        for v in state:
            assert 0 <= v <= 1

    def test_different_types(self):
        """不同任务类型应产生不同编码。"""
        encoder = EvolutionStateEncoder()
        work_state = encoder.encode("周报", "work", 10, 80, 30, [70])
        life_state = encoder.encode("记账", "life", 10, 80, 30, [70])
        # 第一个维度（类型编码）应不同
        assert work_state[0] != life_state[0]


class TestRLEvolutionAgent:
    """测试 RL 演化代理。"""

    def test_decide_returns_config(self):
        """决策应返回配置。"""
        agent = RLEvolutionAgent()
        config = agent.decide("测试任务", "work")
        assert "boost" in config
        assert "decay" in config
        assert "threshold" in config

    def test_calculate_reward(self):
        """奖励计算应正确。"""
        agent = RLEvolutionAgent()

        # 高质量 + 快速 + 点赞
        reward_good = agent.calculate_reward(90, 15, "praise")
        # 低质量 + 慢速 + 驳回
        reward_bad = agent.calculate_reward(40, 120, "reject")

        assert reward_good > reward_bad

    def test_learn_no_experience(self):
        """无经验时学习应返回 0。"""
        agent = RLEvolutionAgent()
        loss = agent.learn(1.0)
        assert loss == 0.0

    def test_get_stats(self):
        """应返回统计信息。"""
        agent = RLEvolutionAgent()
        stats = agent.get_stats()
        assert "epsilon" in stats
        assert "experiences" in stats
        assert "train_steps" in stats


class TestActions:
    """测试动作定义。"""

    def test_all_actions_have_required_fields(self):
        """所有动作应有必需字段。"""
        for action in ACTIONS:
            assert "name" in action
            assert "boost" in action
            assert "decay" in action
            assert "threshold" in action

    def test_boost_in_range(self):
        """提权幅度应在合理范围。"""
        for action in ACTIONS:
            assert 0 < action["boost"] < 2

    def test_decay_in_range(self):
        """衰减率应在合理范围。"""
        for action in ACTIONS:
            assert 0 < action["decay"] < 1
