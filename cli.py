"""CLI 终端界面：Rich 美化 · 全局快捷键唤起。"""
import sys
import os
import logging
from typing import Callable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich.layout import Layout
from rich.text import Text
from rich import box
from rich.markdown import Markdown
from rich.align import Align

from config.settings import load_config, is_llm_configured
from config.app_const import RunMode
from agent_core.task_scheduler import run as run_task
from service.schedule_service import get_today_schedule, add_schedule
from evolution_core.evo_log import get_stats, list_logs
from evolution_core.weight_evolve import get_top_habits

logger = logging.getLogger(__name__)
console = Console()


# ── 样式常量 ──
ACCENT = "bold cyan"
MUTED = "dim"
SUCCESS = "bold green"
WARNING = "bold yellow"
DANGER = "bold red"


def header():
    """打印标题头."""
    console.print()
    console.print(Panel(
        Align.center("[bold cyan]桌面智能助手[/]  [dim]CLI v1.0[/]\n"
                     "[dim]输入指令执行 AI 任务 · 输入 help 查看命令[/]"),
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 4)
    ))


def run_ai_task(text: str):
    """执行 AI 任务并显示日志."""
    if not is_llm_configured():
        console.print(f"[{DANGER}]⚠ 请先在「设置」配置 API Key[/]")
        return

    console.print(f"\n[{ACCENT}]▸ 任务: {text}[/]")
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("[cyan]执行中...", total=None)
        result = run_task(text)

    # 显示日志
    logs = result.get("logs", [])
    if logs:
        from rich import box as rich_box
        log_panel = Panel(
            "\n".join(f"  › {lg}" for lg in logs[:20]),
            title="[dim]执行日志[/]",
            border_style="dim",
            box=rich_box.SIMPLE,
            padding=(0, 2),
        )
        console.print(log_panel)

    # 结果
    cost = result.get("cost_time", 0)
    console.print(f"\n[{SUCCESS}]✓ 完成 · {cost:.1f}s[/]")
    console.print()


def cmd_dashboard():
    """看板页."""
    console.print()
    console.print(Panel("[bold]今日看板[/]", border_style="blue", box=box.ROUNDED))

    items = get_today_schedule()
    work_items = [i for i in items if i.get("category") == "work"]
    life_items = [i for i in items if i.get("category") != "work"]

    table = Table(box=box.SIMPLE_HEAD, show_header=True, border_style="dim")
    table.add_column("💼 工作清单", style="cyan", ratio=1)
    table.add_column("🏠 生活待办", style="magenta", ratio=1)

    max_len = max(len(work_items), len(life_items), 1)
    for i in range(max_len):
        w = f"• [{work_items[i].get('schedule_time', '全天')}] {work_items[i]['title']}" if i < len(work_items) else ""
        l = f"• [{life_items[i].get('schedule_time', '全天')}] {life_items[i]['title']}" if i < len(life_items) else ""
        table.add_row(w, l)

    console.print(table)
    console.print()

    # 操作
    if Confirm.ask("[dim]添加待办?[/]", default=False):
        cat = Prompt.ask("分类", choices=["work", "life"], default="work")
        title = Prompt.ask("内容")
        if title.strip():
            add_schedule(title.strip(), schedule_time="", category=cat)
            console.print(f"[{SUCCESS}]✓ 已添加[/]")
    console.print()


def cmd_evolution():
    """进化中心."""
    console.print()
    console.print(Panel("[bold]进化中心[/]", border_style="magenta", box=box.ROUNDED))

    # 统计
    s = get_stats()
    stat_table = Table(box=box.SIMPLE, show_header=False, border_style="dim")
    stat_table.add_column(ratio=1)
    stat_table.add_column(ratio=1)
    stat_table.add_column(ratio=1)
    stat_table.add_row(
        Panel(f"[bold]{s.get('flow_optimizations', 0)}[/]\n[dim]流程优化[/]", border_style="blue"),
        Panel(f"[bold]{s.get('tool_count', 0)}[/]\n[dim]工具[/]", border_style="cyan"),
        Panel(f"[bold]{s.get('template_count', 0)}[/]\n[dim]模板[/]", border_style="green"),
    )
    console.print(stat_table)
    console.print()

    # 时间轴
    m = {"flow": "优化", "tool": "工具", "template": "模板", "weight": "权重"}
    logs = list_logs()
    if logs:
        tl_table = Table(title="[dim]时间轴[/]", box=box.SIMPLE, border_style="dim")
        tl_table.add_column("日期", style="dim")
        tl_table.add_column("类型")
        for log in logs[:15]:
            tl_table.add_row(log["evo_time"][:10], m.get(log["evo_type"], log["evo_type"]))
        console.print(tl_table)
    else:
        console.print("[dim]暂无记录[/]")

    console.print()

    # 权重
    habits = get_top_habits(8)
    if habits:
        w_table = Table(title="[dim]记忆权重[/]", box=box.SIMPLE, border_style="dim")
        w_table.add_column("key")
        w_table.add_column("权重", justify="right")
        for h in habits:
            bar = "█" * int(h["weight"])
            w_table.add_row(h["habit_key"], f"{bar} {h['weight']:.1f}")
        console.print(w_table)
    console.print()


def cmd_kb():
    """知识库."""
    from memory_store.chroma_kb import list_documents, search, delete_document, COLLECTIONS
    from config.app_const import KBCategory

    console.print()
    console.print(Panel("[bold]知识库[/]", border_style="green", box=box.ROUNDED))

    docs = list_documents()
    if docs:
        table = Table(box=box.SIMPLE_HEAD, border_style="dim")
        table.add_column("文件", style="cyan")
        table.add_column("分类")
        table.add_column("切片", justify="right", style="dim")
        for d in docs:
            table.add_row(
                d["file_name"],
                COLLECTIONS.get(d["category"], d["category"]),
                str(d["total_chunks"]),
            )
        console.print(table)
    else:
        console.print("[dim]暂无文档[/]")

    console.print(f"\n[dim]共 {len(docs)} 个文档[/]")

    # 搜索
    if Confirm.ask("[dim]搜索?[/]", default=False):
        q = Prompt.ask("关键词")
        if q.strip():
            results = search(q.strip(), top_k=5)
            if results:
                for r in results:
                    console.print(f"  [cyan]• [{r['file_name']}][/] {r['text'][:80]}...")
            else:
                console.print("[dim]无结果[/]")
    console.print()


def cmd_settings():
    """设置页."""
    from config.settings import set, get, get_run_mode, set_run_mode
    from agent_core.llm_client import reset_client

    console.print()
    console.print(Panel("[bold]设置[/]", border_style="yellow", box=box.ROUNDED))

    cfg = load_config()

    table = Table(box=box.SIMPLE, show_header=False, border_style="dim")
    table.add_column("key", style="dim")
    table.add_column("value")
    table.add_row("厂商", "自定义")
    table.add_row("Base URL", cfg.llm.base_url)
    table.add_row("API Key", "*" * 8 + cfg.llm.api_key[-6:] if cfg.llm.api_key else "[dim]未设置[/]")
    table.add_row("模型", cfg.llm.model_name)
    table.add_row("运行模式", get_run_mode())
    console.print(table)
    console.print()

    if Confirm.ask("[dim]修改配置?[/]", default=False):
        url = Prompt.ask("Base URL", default=cfg.llm.base_url)
        key = Prompt.ask("API Key", default=cfg.llm.api_key or "")
        model = Prompt.ask("模型", default=cfg.llm.model_name)
        if url and key and model:
            set("llm.base_url", url)
            set("llm.api_key", key)
            set("llm.model_name", model)
            reset_client()
            console.print(f"[{SUCCESS}]✓ 配置已保存[/]")
    console.print()


def cmd_help():
    """帮助信息."""
    console.print()
    table = Table(box=box.SIMPLE_HEAD, border_style="dim", title="[dim]可用命令[/]")
    table.add_column("命令", style="cyan")
    table.add_column("说明")
    table.add_row("help", "显示帮助")
    table.add_row("看板 / dashboard", "今日工作清单 · 生活待办")
    table.add_row("进化 / evolution", "系统自我优化记录")
    table.add_row("知识库 / kb", "文档管理 · 语义检索")
    table.add_row("设置 / settings", "大模型配置")
    table.add_row("清空 / clear", "清屏")
    table.add_row("退出 / exit / quit", "退出程序")
    table.add_row("──", "──")
    table.add_row("[dim]其他输入[/]", "[dim]当作 AI 指令执行[/]")
    console.print(table)
    console.print()


# ── 命令映射 ──
COMMANDS = {
    "help": cmd_help,
    "看板": cmd_dashboard,
    "dashboard": cmd_dashboard,
    "进化": cmd_evolution,
    "evolution": cmd_evolution,
    "知识库": cmd_kb,
    "kb": cmd_kb,
    "设置": cmd_settings,
    "settings": cmd_settings,
    "清空": lambda: console.clear(),
    "clear": lambda: console.clear(),
}


def cli_main():
    """CLI 主循环."""
    header()
    cmd_help()

    while True:
        try:
            text = Prompt.ask(f"\n[{ACCENT}]>[/]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print(f"\n[{MUTED}]再见[/]")
            break

        if not text:
            continue

        # 退出命令
        if text.lower() in ("退出", "exit", "quit", "q"):
            console.print(f"\n[{MUTED}]再见[/]")
            break

        # 内置命令
        cmd = COMMANDS.get(text.lower())
        if cmd:
            cmd()
        else:
            # AI 任务
            run_ai_task(text)


if __name__ == "__main__":
    cli_main()
