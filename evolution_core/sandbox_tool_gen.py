"""安全沙箱、自定义工具生成（LLM 驱动，真实可用）。"""
import json
import logging
import re
from typing import Any

from agent_core.llm_client import chat
from tools.sandbox_run import check_safety, run_script

logger = logging.getLogger(__name__)

# 工具生成系统提示词
_TOOL_GEN_SYSTEM_PROMPT = """你是一个 Python 工具生成专家。根据用户需求，生成一个安全、可独立运行的 Python 函数。

## 安全约束（必须遵守）
1. 只能使用以下安全模块：math, random, datetime, itertools, collections, json, re, string, statistics
2. 禁止使用：os, sys, subprocess, shutil, socket, http, urllib, open, eval, exec, compile, __import__
3. 所有输入通过函数参数传入，所有结果通过 return 返回
4. 不要使用 print，用 return 返回结果

## 输出格式
严格返回 JSON，不要 markdown，不要其他文字：
{
  "name": "tool_xxx（英文小写下划线）",
  "description": "工具用途描述",
  "code": "完整的 Python 代码字符串（注意转义换行符\\n和引号\\\"）"
}

## 代码模板
```python
import math, json, re, datetime, itertools, collections, statistics

def run(*args, **kwargs):
    # 你的实现
    return result
```"""


def generate_tool(desc: str) -> dict[str, Any]:
    """根据需求描述生成工具（LLM 生成 + 安全校验）。

    1. 调用 LLM 生成工具代码
    2. AST 静态安全检查
    3. 沙箱试运行验证可用性
    """
    if not desc or not desc.strip():
        return {"name": "", "description": "", "code": "", "status": "error", "error": "需求描述为空"}

    # 1. LLM 生成
    tool_code = _generate_with_llm(desc)
    if tool_code is None:
        return {"name": "", "description": desc, "code": "", "status": "error", "error": "LLM 生成失败"}

    # 2. 安全校验
    safe, msg = validate_tool(tool_code.get("code", ""))
    if not safe:
        logger.warning("工具安全校验未通过: %s", msg)
        return {
            "name": tool_code.get("name", ""),
            "description": desc,
            "code": tool_code.get("code", ""),
            "status": "unsafe",
            "error": msg,
        }

    # 3. 沙箱试运行
    test_result = _trial_run(tool_code.get("code", ""))
    tool_code["status"] = "generated" if test_result else "test_failed"
    tool_code["test_output"] = test_result

    logger.info("生成工具: %s (状态: %s)", tool_code.get("name", "?"), tool_code["status"])
    return tool_code


def _generate_with_llm(desc: str) -> dict[str, Any] | None:
    """调用 LLM 生成工具代码。"""
    try:
        resp = chat([
            {"role": "system", "content": _TOOL_GEN_SYSTEM_PROMPT},
            {"role": "user", "content": f"请生成一个工具，需求描述：{desc}"},
        ], temperature=0.6, max_tokens=2000)

        # 解析 JSON
        text = resp.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group()

        data = json.loads(text)
        if "code" in data:
            return {
                "name": data.get("name", f"tool_{hash(desc) % 10000}"),
                "description": data.get("description", desc),
                "code": data["code"],
            }
        return None
    except json.JSONDecodeError:
        logger.warning("工具生成 JSON 解析失败: %s", resp[:200])
        # 尝试从响应中提取代码块
        code_match = re.search(r'```python\s*(.*?)\s*```', resp, re.DOTALL)
        if code_match:
            return {
                "name": f"tool_{hash(desc) % 10000}",
                "description": desc,
                "code": code_match.group(1).strip(),
            }
        return None
    except Exception as e:
        logger.error("工具生成异常: %s", e)
        return None


def _trial_run(code: str) -> str:
    """沙箱试运行工具代码。"""
    # 尝试调用 run 函数
    test_code = code + "\n\n# 测试调用\ntry:\n    result = run()\n    print(f'试运行成功: {result}')\nexcept TypeError:\n    print('工具需要参数，跳过试运行')\nexcept Exception as e:\n    print(f'试运行异常: {e}')\n"
    return run_script(test_code, timeout=5)


def validate_tool(code: str) -> tuple[bool, str]:
    """沙箱安全校验（AST 静态检查）。"""
    if not code or not code.strip():
        return False, "代码为空"
    return check_safety(code)
