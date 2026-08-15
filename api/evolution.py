"""进化中心 API + 模板库 API + 演化报告 API。"""
from fastapi import APIRouter

from evolution_core.evo_log import get_stats, list_logs
from evolution_core.weight_evolve import get_top_habits
from evolution_core.template_save import list_templates, get_template
from evolution_core.pattern_miner import get_top_patterns, mine_patterns
from evolution_core.evolution_report import generate_daily_report, generate_weekly_report, get_latest_report
from evolution_core.forgetting import run_forgetting_cycle
from evolution_core.cold_start import get_default_template, get_recommended_steps

router = APIRouter()


# ── 进化中心 ──


@router.get("/stats")
def stats():
    return get_stats()


@router.get("/logs")
def logs(evo_type: str = ""):
    return list_logs(evo_type=evo_type or "")


@router.get("/weights")
def weights(limit: int = 10):
    return get_top_habits(limit)


# ── 模板库 ──


@router.get("/templates")
def templates():
    """获取所有固化模板。"""
    return list_templates()


@router.get("/templates/recommend")
def recommend_template(task_text: str = "", task_type: str = ""):
    """推荐模板（冷启动感知）。"""
    steps, source = get_recommended_steps(task_text, task_type)
    return {"steps": steps, "source": source}


@router.get("/templates/defaults")
def default_templates():
    """获取默认模板库。"""
    from evolution_core.cold_start import get_all_default_templates
    return get_all_default_templates()


# ── 模式挖掘 ──


@router.get("/patterns")
def patterns(min_confidence: float = 0):
    """获取挖掘的模式。"""
    return get_top_patterns(n=20, min_confidence=min_confidence)


@router.post("/patterns/mine")
def mine():
    """触发模式挖掘。"""
    return mine_patterns()


# ── 演化报告 ──


@router.get("/report/daily")
def daily_report():
    """生成每日报告。"""
    return generate_daily_report()


@router.get("/report/weekly")
def weekly_report():
    """生成每周报告。"""
    return generate_weekly_report()


@router.get("/report/latest")
def latest_report(report_type: str = "daily"):
    """获取最新报告。"""
    return get_latest_report(report_type)


# ── 遗忘周期 ──


@router.post("/forgetting")
def forgetting():
    """执行遗忘周期。"""
    return run_forgetting_cycle()
