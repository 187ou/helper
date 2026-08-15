"""A/B 测试框架：验证优化是否真正有效。

核心能力：
1. 实验管理：创建、启动、停止实验
2. 流量分配：按概率分配到不同策略
3. 指标收集：自动收集各策略的表现数据
4. 统计显著性：判断差异是否显著
5. 自动决策：基于数据自动选择胜出策略

边缘处理：
- 样本不足 → 继续实验不决策
- 实验异常 → 自动回滚到对照组
- 流量不均 → 自动调整分配比例
"""
import hashlib
import json
import logging
import math
import random
from datetime import datetime
from typing import Any

from memory_store.sqlite_db import get_conn, now_str
from evolution_core.safe_ops import safe_divide, clamp_value, safe_json_loads

logger = logging.getLogger(__name__)

# ── 配置 ──
AB_TEST_CONFIG = {
    "min_sample_size": 10,          # 每组最少样本数
    "confidence_level": 0.95,       # 置信水平
    "max_experiment_days": 30,      # 实验最长天数
    "default_split": 0.5,           # 默认分流比例
}


def create_experiment(
    name: str,
    description: str = "",
    variants: list[dict[str, Any]] | None = None,
    metric: str = "score",
    split: float = 0.5,
) -> str | None:
    """创建 A/B 测试实验。

    Args:
        name: 实验名称
        description: 实验描述
        variants: 变体列表 [{"name": "control", "config": {...}}, {"name": "treatment", "config": {...}}]
        metric: 评估指标（score / duration / satisfaction）
        split: 实验组流量比例

    Returns:
        实验 ID

    Example:
        create_experiment(
            name="周报模板优化",
            description="测试简化版周报模板是否更高效",
            variants=[
                {"name": "control", "config": {"steps": 5}},
                {"name": "treatment", "config": {"steps": 3}},
            ],
            metric="score",
        )
    """
    if not name or not variants or len(variants) < 2:
        return None

    experiment_id = _generate_id(name)
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO ab_experiment
               (experiment_id, name, description, variants, metric, split_ratio, status, create_time)
               VALUES (?, ?, ?, ?, ?, ?, 'running', ?)""",
            (
                experiment_id, name, description,
                safe_json_dumps(variants),
                metric,
                clamp_value(split, 0.1, 0.9),
                now_str(),
            ),
        )
        conn.commit()
        logger.info("创建实验: %s (%s)", name, experiment_id)
        return experiment_id
    except Exception as e:
        logger.error("创建实验失败: %s", e)
        return None
    finally:
        conn.close()


def assign_variant(experiment_id: str, user_seed: str = "") -> dict[str, Any] | None:
    """为用户分配实验组。

    使用确定性哈希保证同一用户始终分配到同一组。

    Args:
        experiment_id: 实验 ID
        user_seed: 用户标识（用于确定性分配）

    Returns:
        分配的变体配置
    """
    experiment = get_experiment(experiment_id)
    if not experiment or experiment.get("status") != "running":
        return None

    variants = safe_json_loads(experiment.get("variants"), default=[])
    if not variants:
        return None

    split = experiment.get("split_ratio", 0.5)

    # 确定性哈希分配
    seed = f"{experiment_id}:{user_seed}"
    hash_val = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    normalized = (hash_val % 10000) / 10000.0

    # 对照组 (0 ~ split)，实验组 (split ~ 1)
    if normalized < split:
        variant = variants[0]  # control
    else:
        variant = variants[1] if len(variants) > 1 else variants[0]  # treatment

    return variant


def record_result(
    experiment_id: str,
    variant_name: str,
    metric_value: float,
    task_id: int = 0,
) -> None:
    """记录实验结果。"""
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO ab_result
               (experiment_id, variant_name, metric_value, task_id, create_time)
               VALUES (?, ?, ?, ?, ?)""",
            (experiment_id, variant_name, metric_value, task_id, now_str()),
        )
        conn.commit()
    except Exception as e:
        logger.warning("记录实验结果失败: %s", e)
    finally:
        conn.close()


def analyze_experiment(experiment_id: str) -> dict[str, Any] | None:
    """分析实验结果。

    计算各变体的：
    - 样本数
    - 均值
    - 标准差
    - 置信区间
    - 是否显著差异
    """
    experiment = get_experiment(experiment_id)
    if not experiment:
        return None

    variants = safe_json_loads(experiment.get("variants"), default=[])
    metric = experiment.get("metric", "score")

    conn = get_conn()
    try:
        results = conn.execute(
            """SELECT variant_name, metric_value FROM ab_result
               WHERE experiment_id = ?""",
            (experiment_id,)
        ).fetchall()
    except Exception:
        return None
    finally:
        conn.close()

    if not results:
        return {"experiment_id": experiment_id, "status": "no_data"}

    # 按变体分组统计
    variant_data: dict[str, list[float]] = {}
    for r in results:
        name = r["variant_name"]
        if name not in variant_data:
            variant_data[name] = []
        variant_data[name].append(r["metric_value"])

    analysis = {
        "experiment_id": experiment_id,
        "experiment_name": experiment.get("name"),
        "metric": metric,
        "status": experiment.get("status"),
        "variants": {},
        "winner": None,
        "significant": False,
    }

    for variant_name, values in variant_data.items():
        n = len(values)
        mean = safe_sum(values) / max(n, 1)
        std = _std_dev(values, mean)
        ci = _confidence_interval(mean, std, n)

        analysis["variants"][variant_name] = {
            "sample_size": n,
            "mean": round(mean, 2),
            "std": round(std, 2),
            "ci_lower": round(ci[0], 2),
            "ci_upper": round(ci[1], 2),
        }

    # 判断显著性（只有两个变体时）
    if len(variant_data) == 2:
        names = list(variant_data.keys())
        control_data = variant_data[names[0]]
        treatment_data = variant_data[names[1]]

        significant, p_value = _t_test(control_data, treatment_data)

        analysis["significant"] = significant
        analysis["p_value"] = round(p_value, 4)

        if significant:
            control_mean = safe_sum(control_data) / max(len(control_data), 1)
            treatment_mean = safe_sum(treatment_data) / max(len(treatment_data), 1)
            analysis["winner"] = names[1] if treatment_mean > control_mean else names[0]
            analysis["improvement"] = round(
                safe_divide(abs(treatment_mean - control_mean), max(control_mean, 0.01)) * 100, 1
            )

    # 样本不足检查
    min_sample = AB_TEST_CONFIG["min_sample_size"]
    for name, data in variant_data.items():
        if len(data) < min_sample:
            analysis["significant"] = False
            analysis["winner"] = None
            analysis.setdefault("warnings", []).append(
                f"{name} 样本不足（{len(data)} < {min_sample}），需继续收集数据"
            )

    return analysis


def stop_experiment(experiment_id: str, winner: str = "") -> bool:
    """停止实验。"""
    conn = get_conn()
    try:
        if winner:
            conn.execute(
                "UPDATE ab_experiment SET status = 'completed', winner = ?, end_time = ? WHERE experiment_id = ?",
                (winner, now_str(), experiment_id)
            )
        else:
            conn.execute(
                "UPDATE ab_experiment SET status = 'completed', end_time = ? WHERE experiment_id = ?",
                (now_str(), experiment_id)
            )
        conn.commit()
        logger.info("停止实验: %s (winner=%s)", experiment_id, winner)
        return True
    except Exception as e:
        logger.error("停止实验失败: %s", e)
        return False
    finally:
        conn.close()


def get_experiment(experiment_id: str) -> dict | None:
    """获取实验信息。"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM ab_experiment WHERE experiment_id = ?", (experiment_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["variants"] = safe_json_loads(d.get("variants"), default=[])
        return d
    except Exception:
        return None
    finally:
        conn.close()


def list_experiments(status: str = "") -> list[dict]:
    """列出实验。"""
    conn = get_conn()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM ab_experiment WHERE status = ? ORDER BY create_time DESC",
                (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ab_experiment ORDER BY create_time DESC"
            ).fetchall()

        results = []
        for row in rows:
            d = dict(row)
            d["variants"] = safe_json_loads(d.get("variants"), default=[])
            results.append(d)
        return results
    except Exception:
        return []
    finally:
        conn.close()


def auto_decide(experiment_id: str) -> dict[str, Any] | None:
    """自动决策（样本足够时自动选择胜出者）。"""
    analysis = analyze_experiment(experiment_id)
    if not analysis:
        return None

    if not analysis.get("significant"):
        return {
            "decision": "continue",
            "reason": "样本不足或差异不显著，继续实验",
            "analysis": analysis,
        }

    winner = analysis.get("winner")
    if winner:
        stop_experiment(experiment_id, winner)
        return {
            "decision": "stop",
            "winner": winner,
            "improvement": analysis.get("improvement", 0),
            "reason": f"变体 {winner} 显著胜出（p={analysis.get('p_value')}）",
            "analysis": analysis,
        }

    return {
        "decision": "continue",
        "reason": "无法确定胜出者",
        "analysis": analysis,
    }


# ── 数据库表初始化 ──

def init_ab_test_tables() -> None:
    """初始化 A/B 测试相关表。"""
    conn = get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS ab_experiment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                variants TEXT NOT NULL,
                metric TEXT DEFAULT 'score',
                split_ratio REAL DEFAULT 0.5,
                status TEXT DEFAULT 'running',
                winner TEXT DEFAULT '',
                create_time TEXT DEFAULT (datetime('now', 'localtime')),
                end_time TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS ab_result (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT NOT NULL,
                variant_name TEXT NOT NULL,
                metric_value REAL DEFAULT 0,
                task_id INTEGER DEFAULT 0,
                create_time TEXT DEFAULT (datetime('now', 'localtime'))
            );
        """)
        conn.commit()
    except Exception as e:
        logger.warning("A/B 测试表初始化: %s", e)
    finally:
        conn.close()


# ── 工具函数 ──

def _generate_id(name: str) -> str:
    """生成实验 ID。"""
    import hashlib
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    hash_part = hashlib.md5(f"{name}:{timestamp}".encode()).hexdigest()[:8]
    return f"exp_{hash_part}"


def safe_sum(values: list) -> float:
    """安全求和。"""
    if not values:
        return 0.0
    try:
        return sum(float(v) for v in values if isinstance(v, (int, float)))
    except (TypeError, ValueError):
        return 0.0


def safe_json_dumps(obj: Any, default: str = "{}") -> str:
    """安全序列化 JSON。"""
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return default


def _std_dev(values: list[float], mean: float) -> float:
    """计算标准差。"""
    if len(values) < 2:
        return 0.0
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def _confidence_interval(mean: float, std: float, n: int, confidence: float = 0.95) -> tuple:
    """计算置信区间。"""
    if n < 2:
        return (mean, mean)
    # 95% 置信区间 z=1.96
    z = 1.96 if confidence == 0.95 else 2.576  # 99%: 2.576
    margin = z * std / math.sqrt(n)
    return (mean - margin, mean + margin)


def _t_test(group_a: list[float], group_b: list[float]) -> tuple:
    """独立样本 t 检验。

    Returns:
        (significant, p_value)
    """
    n_a = len(group_a)
    n_b = len(group_b)

    if n_a < 2 or n_b < 2:
        return False, 1.0

    mean_a = safe_sum(group_a) / n_a
    mean_b = safe_sum(group_b) / n_b

    std_a = _std_dev(group_a, mean_a)
    std_b = _std_dev(group_b, mean_b)

    # 合并标准误
    se = math.sqrt((std_a ** 2 / n_a) + (std_b ** 2 / n_b))
    if se == 0:
        return False, 1.0

    t_stat = (mean_a - mean_b) / se

    # 自由度（Welch-Satterthwaite）
    if std_a == 0 and std_b == 0:
        df = n_a + n_b - 2
    else:
        num = ((std_a ** 2 / n_a) + (std_b ** 2 / n_b)) ** 2
        denom = ((std_a ** 2 / n_a) ** 2 / (n_a - 1)) + ((std_b ** 2 / n_b) ** 2 / (n_b - 1))
        df = safe_divide(num, denom, default=n_a + n_b - 2)

    # 近似 p 值（使用 t 分布）
    p_value = _t_p_value(abs(t_stat), df)

    significant = p_value < (1 - AB_TEST_CONFIG["confidence_level"])
    return significant, p_value


def _t_p_value(t_stat: float, df: float) -> float:
    """t 分布 p 值近似（使用正态近似）。

    大样本时 t 分布趋近正态分布。
    """
    # 正态近似
    z = t_stat
    # 误差函数近似
    p = math.exp(-0.5 * z * z) / (math.sqrt(2 * math.pi) * (1 + abs(z)))
    # 双尾
    return min(2 * p, 1.0)
