"""强化学习代理：用 DQN 替代手工规则做决策。

核心能力：
1. 状态表示：将任务上下文编码为状态向量
2. 动作空间：选择策略参数（提权幅度、衰减率等）
3. 奖励设计：基于任务完成质量和用户反馈
4. Q-Network：简单的神经网络近似 Q 值
5. 经验回放：存储和重用历史经验
6. ε-贪心：平衡探索与利用

边缘处理：
- 训练数据不足 → 使用默认策略
- 网络未初始化 → 随机初始化
- 梯度爆炸 → 梯度裁剪
"""
import logging
import math
import random
from collections import deque
from typing import Any

from evolution_core.safe_ops import clamp_value

logger = logging.getLogger(__name__)

# ── 配置 ──
RL_CONFIG = {
    "state_dim": 8,                 # 状态向量维度
    "hidden_dim": 32,               # 隐藏层维度
    "action_dim": 5,                # 动作数量
    "learning_rate": 0.01,
    "gamma": 0.95,                  # 折扣因子
    "epsilon_start": 1.0,           # 探索率初始值
    "epsilon_end": 0.1,             # 探索率最小值
    "epsilon_decay": 0.995,         # 探索率衰减
    "batch_size": 16,               # 训练批次大小
    "memory_size": 1000,            # 经验回放缓冲区大小
    "target_update_freq": 50,       # 目标网络更新频率
    "min_experiences": 20,          # 最少经验数才开始训练
}

# 动作定义：不同的策略参数组合
ACTIONS = [
    {"name": "conservative", "boost": 0.3, "decay": 0.05, "threshold": 65},   # 保守
    {"name": "balanced", "boost": 0.5, "decay": 0.1, "threshold": 60},        # 平衡
    {"name": "aggressive", "boost": 0.8, "decay": 0.15, "threshold": 55},     # 激进
    {"name": "quality_focus", "boost": 0.6, "decay": 0.08, "threshold": 70},  # 质量优先
    {"name": "speed_focus", "boost": 0.4, "decay": 0.12, "threshold": 50},    # 速度优先
]


class SimpleNN:
    """简单的全连接神经网络（纯 Python 实现，无依赖）。

    架构：state_dim → hidden_dim → action_dim
    激活函数：ReLU
    """

    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim

        # Xavier 初始化
        self.w1 = [[self._init_weight(input_dim) for _ in range(input_dim)] for _ in range(hidden_dim)]
        self.b1 = [0.0] * hidden_dim
        self.w2 = [[self._init_weight(hidden_dim) for _ in range(hidden_dim)] for _ in range(output_dim)]
        self.b2 = [0.0] * output_dim

    def _init_weight(self, fan_in: int) -> float:
        """Xavier 初始化。"""
        limit = math.sqrt(6.0 / (fan_in + self.hidden_dim))
        return random.uniform(-limit, limit)

    def forward(self, x: list[float]) -> list[float]:
        """前向传播。"""
        # 隐藏层：z = W1·x + b1, h = ReLU(z)
        h = [0.0] * self.hidden_dim
        for j in range(self.hidden_dim):
            z = self.b1[j]
            for i in range(min(len(x), self.input_dim)):
                z += self.w1[j][i] * x[i]
            h[j] = max(0.0, z)  # ReLU

        # 输出层：out = W2·h + b2
        out = [0.0] * self.output_dim
        for k in range(self.output_dim):
            z = self.b2[k]
            for j in range(self.hidden_dim):
                z += self.w2[k][j] * h[j]
            out[k] = z

        return out

    def train_batch(self, states: list[list[float]], targets: list[list[float]], lr: float = 0.01) -> float:
        """训练一批数据（简化版 SGD）。

        使用数值梯度（避免手动求导）。
        """
        total_loss = 0.0

        for state, target in zip(states, targets):
            # 前向传播
            pred = self.forward(state)

            # 计算损失 (MSE)
            loss = sum((p - t) ** 2 for p, t in zip(pred, target)) / len(pred)
            total_loss += loss

            # 数值梯度更新（简化）
            self._numerical_gradient_update(state, target, lr)

        return total_loss / max(len(states), 1)

    def _numerical_gradient_update(self, state: list[float], target: list[float], lr: float) -> None:
        """数值梯度更新（有限差分法，小网络可用）。"""
        epsilon = 1e-3

        # 只更新输出层（简化训练）
        for k in range(self.output_dim):
            for j in range(self.hidden_dim):
                # 正向扰动
                self.w2[k][j] += epsilon
                pred_plus = self.forward(state)
                loss_plus = sum((p - t) ** 2 for p, t in zip(pred_plus, target))

                # 负向扰动
                self.w2[k][j] -= 2 * epsilon
                pred_minus = self.forward(state)
                loss_minus = sum((p - t) ** 2 for p, t in zip(pred_minus, target))

                # 恢复
                self.w2[k][j] += epsilon

                # 梯度
                grad = (loss_plus - loss_minus) / (2 * epsilon)
                self.w2[k][j] -= lr * clamp_value(grad, -1, 1)

    def copy_from(self, other: 'SimpleNN') -> None:
        """复制网络权重（用于目标网络更新）。"""
        for j in range(self.hidden_dim):
            for i in range(self.input_dim):
                self.w1[j][i] = other.w1[j][i]
            self.b1[j] = other.b1[j]
        for k in range(self.output_dim):
            for j in range(self.hidden_dim):
                self.w2[k][j] = other.w2[k][j]
            self.b2[k] = other.b2[k]


class ReplayBuffer:
    """经验回放缓冲区。"""

    def __init__(self, capacity: int):
        self.buffer = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done) -> None:
        """存储经验。"""
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int) -> list:
        """随机采样。"""
        if len(self.buffer) < batch_size:
            return list(self.buffer)
        return random.sample(list(self.buffer), batch_size)

    def __len__(self) -> int:
        return len(self.buffer)


class DQNAgent:
    """DQN 代理（纯 Python 实现）。

    用于学习最优的权重调整策略。
    """

    def __init__(self):
        self.state_dim = RL_CONFIG["state_dim"]
        self.action_dim = RL_CONFIG["action_dim"]
        self.hidden_dim = RL_CONFIG["hidden_dim"]

        # Q 网络和目标网络
        self.q_network = SimpleNN(self.state_dim, self.hidden_dim, self.action_dim)
        self.target_network = SimpleNN(self.state_dim, self.hidden_dim, self.action_dim)
        self.target_network.copy_from(self.q_network)

        # 经验回放
        self.memory = ReplayBuffer(RL_CONFIG["memory_size"])

        # 超参数
        self.gamma = RL_CONFIG["gamma"]
        self.epsilon = RL_CONFIG["epsilon_start"]
        self.epsilon_end = RL_CONFIG["epsilon_end"]
        self.epsilon_decay = RL_CONFIG["epsilon_decay"]
        self.batch_size = RL_CONFIG["batch_size"]
        self.lr = RL_CONFIG["learning_rate"]
        self.target_update_freq = RL_CONFIG["target_update_freq"]
        self.min_experiences = RL_CONFIG["min_experiences"]

        # 训练计数
        self.train_step = 0

    def select_action(self, state: list[float]) -> int:
        """ε-贪心策略选择动作。"""
        if random.random() < self.epsilon:
            return random.randint(0, self.action_dim - 1)

        q_values = self.q_network.forward(state)
        return q_values.index(max(q_values))

    def store_experience(self, state, action, reward, next_state, done) -> None:
        """存储经验。"""
        self.memory.push(state, action, reward, next_state, done)

    def train(self) -> float:
        """训练一步。"""
        if len(self.memory) < self.min_experiences:
            return 0.0

        # 采样
        batch = self.memory.sample(self.batch_size)
        states = []
        targets = []

        for state, action, reward, next_state, done in batch:
            # 当前 Q 值
            current_q = self.q_network.forward(state)

            # 目标 Q 值
            if done:
                target_q = reward
            else:
                next_q = self.target_network.forward(next_state)
                target_q = reward + self.gamma * max(next_q)

            # 构建目标向量
            target = list(current_q)
            target[action] = target_q

            # 梯度裁剪
            target[action] = clamp_value(target[action], -10, 10)

            states.append(state)
            targets.append(target)

        # 训练
        loss = self.q_network.train_batch(states, targets, self.lr)

        # 更新目标网络
        self.train_step += 1
        if self.train_step % self.target_update_freq == 0:
            self.target_network.copy_from(self.q_network)

        # 衰减探索率
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)

        return loss

    def get_action_config(self, action_idx: int) -> dict:
        """获取动作对应的策略配置。"""
        if 0 <= action_idx < len(ACTIONS):
            return ACTIONS[action_idx]
        return ACTIONS[1]  # 默认平衡


class EvolutionStateEncoder:
    """状态编码器：将任务上下文编码为状态向量。"""

    @staticmethod
    def encode(task_text: str, task_type: str, task_count: int,
               avg_score: float, avg_duration: float, recent_scores: list[float]) -> list[float]:
        """编码状态向量（8 维）。

        维度：
        0: 任务类型编码 (work=0.3, life=0.6, health=0.9)
        1: 任务数量（归一化）
        2: 历史平均分（归一化）
        3: 平均耗时（归一化）
        4: 最近得分趋势（上升/下降）
        5: 任务文本长度（归一化）
        6: 反馈满意度（归一化）
        7: 使用频率（归一化）
        """
        # 任务类型编码
        type_encoding = {"work": 0.3, "life": 0.6, "health": 0.9, "mix": 0.5}
        type_val = type_encoding.get(task_type, 0.5)

        # 任务数量（对数归一化）
        count_val = clamp_value(math.log(max(task_count, 1) + 1) / 5, 0, 1)

        # 平均分
        score_val = clamp_value(avg_score / 100, 0, 1)

        # 平均耗时（假设合理范围 5-120 秒）
        duration_val = clamp_value((avg_duration - 5) / 115, 0, 1)

        # 最近趋势（最近 3 次 vs 之前 3 次）
        trend_val = 0.5
        if len(recent_scores) >= 6:
            recent_avg = sum(recent_scores[:3]) / 3
            older_avg = sum(recent_scores[3:6]) / 3
            trend_val = clamp_value(0.5 + (recent_avg - older_avg) / 100, 0, 1)

        # 文本长度
        text_len_val = clamp_value(len(task_text) / 100, 0, 1)

        # 反馈满意度（默认 0.5）
        satisfaction_val = 0.5

        # 使用频率
        freq_val = clamp_value(task_count / 50, 0, 1)

        return [type_val, count_val, score_val, duration_val, trend_val, text_len_val, satisfaction_val, freq_val]


class RLEvolutionAgent:
    """RL 驱动的演化代理。

    使用 DQN 学习最优的权重调整策略，替代手工规则。
    """

    def __init__(self):
        self.dqn = DQNAgent()
        self.state_encoder = EvolutionStateEncoder()
        self.last_state = None
        self.last_action = None

    def decide(self, task_text: str, task_type: str = "") -> dict:
        """决定策略参数。

        Returns:
            策略配置 {"boost": float, "decay": float, "threshold": float}
        """
        # 获取上下文
        task_count = self._get_task_count(task_type)
        avg_score = self._get_avg_score(task_type)
        avg_duration = self._get_avg_duration(task_type)
        recent_scores = self._get_recent_scores(task_type)

        # 编码状态
        state = self.state_encoder.encode(task_text, task_type, task_count, avg_score, avg_duration, recent_scores)

        # 选择动作
        action_idx = self.dqn.select_action(state)
        config = self.dqn.get_action_config(action_idx)

        # 存储状态用于后续训练
        self.last_state = state
        self.last_action = action_idx

        logger.debug("RL 决策: action=%s, config=%s", action_idx, config.get("name"))
        return config

    def learn(self, reward: float, done: bool = False) -> float:
        """从结果中学习。

        Args:
            reward: 奖励值（基于任务质量和用户反馈）
            done: 是否结束

        Returns:
            训练损失
        """
        if self.last_state is None or self.last_action is None:
            return 0.0

        # 编码当前状态（用于计算 next_state）
        next_state = list(self.last_state)  # 简化：使用相同状态

        # 存储经验
        self.dqn.store_experience(self.last_state, self.last_action, reward, next_state, done)

        # 训练
        loss = self.dqn.train()

        # 重置
        self.last_state = None
        self.last_action = None

        return loss

    def calculate_reward(self, score: float, duration: float, feedback_type: str = "") -> float:
        """计算奖励。

        奖励设计：
        - 基础分：任务得分 / 10
        - 效率奖励：快速完成 +1
        - 用户反馈：点赞 +2，修改 -0.5，驳回 -2
        """
        reward = score / 10.0

        # 效率奖励（30 秒内完成）
        if 0 < duration < 30:
            reward += 1.0

        # 用户反馈
        if feedback_type == "praise":
            reward += 2.0
        elif feedback_type == "modify":
            reward -= 0.5
        elif feedback_type == "reject":
            reward -= 2.0

        return reward

    def get_stats(self) -> dict:
        """获取代理统计。"""
        return {
            "epsilon": round(self.dqn.epsilon, 3),
            "experiences": len(self.dqn.memory),
            "train_steps": self.dqn.train_step,
            "exploration_rate": f"{self.dqn.epsilon:.1%}",
        }

    # ── 数据获取 ──

    def _get_task_count(self, task_type: str = "") -> int:
        """获取任务数量。"""
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            if task_type:
                return conn.execute("SELECT COUNT(*) FROM task_list WHERE task_type = ?", (task_type,)).fetchone()[0]
            return conn.execute("SELECT COUNT(*) FROM task_list").fetchone()[0]
        except Exception:
            return 0
        finally:
            conn.close()

    def _get_avg_score(self, task_type: str = "") -> float:
        """获取平均分。"""
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            if task_type:
                row = conn.execute("SELECT AVG(work_score) FROM task_list WHERE task_type = ? AND work_score > 0", (task_type,)).fetchone()
            else:
                row = conn.execute("SELECT AVG(work_score) FROM task_list WHERE work_score > 0").fetchone()
            return row[0] if row and row[0] else 50.0
        except Exception:
            return 50.0
        finally:
            conn.close()

    def _get_avg_duration(self, task_type: str = "") -> float:
        """获取平均耗时。"""
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            if task_type:
                row = conn.execute("SELECT AVG(cost_time) FROM task_list WHERE task_type = ? AND cost_time > 0", (task_type,)).fetchone()
            else:
                row = conn.execute("SELECT AVG(cost_time) FROM task_list WHERE cost_time > 0").fetchone()
            return row[0] if row and row[0] else 30.0
        except Exception:
            return 30.0
        finally:
            conn.close()

    def _get_recent_scores(self, task_type: str = "", limit: int = 10) -> list[float]:
        """获取最近分数。"""
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            if task_type:
                rows = conn.execute(
                    "SELECT work_score FROM task_list WHERE task_type = ? AND work_score > 0 ORDER BY create_time DESC LIMIT ?",
                    (task_type, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT work_score FROM task_list WHERE work_score > 0 ORDER BY create_time DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [r[0] for r in rows]
        except Exception:
            return []
        finally:
            conn.close()


# ── 全局实例 ──

_rl_agent = None


def get_rl_agent() -> RLEvolutionAgent:
    """获取全局 RL 代理。"""
    global _rl_agent
    if _rl_agent is None:
        _rl_agent = RLEvolutionAgent()
    return _rl_agent


def decide_with_rl(task_text: str, task_type: str = "") -> dict:
    """使用 RL 决策（便捷函数）。"""
    agent = get_rl_agent()
    return agent.decide(task_text, task_type)


def learn_from_result(score: float, duration: float, feedback_type: str = "") -> float:
    """从结果中学习（便捷函数）。"""
    agent = get_rl_agent()
    reward = agent.calculate_reward(score, duration, feedback_type)
    return agent.learn(reward, done=True)
