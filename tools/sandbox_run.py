"""安全沙箱运行脚本：受限 Python 代码执行。"""
import ast
import builtins
import logging
import multiprocessing
from typing import Any

# 预先提取 __import__，避免 spawn 模式下丢失
_BUILTIN_IMPORT = builtins.__import__

logger = logging.getLogger(__name__)

# 危险的内置函数/模块黑名单
FORBIDDEN_NAMES = {
    "exec", "eval", "compile", "__import__", "open", "input",
    "globals", "locals", "vars", "dir", "getattr", "setattr", "delattr",
    "breakpoint", "exit", "quit",
}

FORBIDDEN_MODULES = {
    "os", "sys", "subprocess", "shutil", "socket", "http", "urllib",
    "ftplib", "smtplib", "ctypes", "importlib", "pickle", "marshal",
}


def check_safety(code: str) -> tuple[bool, str]:
    """AST 静态检查代码安全性。"""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"语法错误: {e}"

    for node in ast.walk(tree):
        # 检查危险名称
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            return False, f"禁用标识符: {node.id}"

        # 检查 import 黑名单模块
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in FORBIDDEN_MODULES:
                    return False, f"禁用模块: {root}"
        if isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in FORBIDDEN_MODULES:
                return False, f"禁用模块: {root}"

        # 检查 __import__ 调用
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                return False, "禁止 __import__"

    return True, "安全检查通过"


def _run_in_process(code: str, result_queue):
    """在子进程中运行代码。"""
    try:
        # 受限的内置函数
        safe_builtins = {
            name: getattr(builtins, name)
            for name in dir(builtins)
            if name not in FORBIDDEN_NAMES and not name.startswith("_")
        }
        # 移除 open，但保留 __import__
        safe_builtins.pop("open", None)
        safe_builtins["__import__"] = _BUILTIN_IMPORT

        safe_globals = {
            "__builtins__": safe_builtins,
            "__name__": "__main__",
            "__import__": _BUILTIN_IMPORT,
        }

        # 允许的安全模块
        import math, random, datetime, itertools, collections, json, re, string, statistics
        safe_globals.update({
            "math": math, "random": random, "datetime": datetime,
            "itertools": itertools, "collections": collections,
            "json": json, "re": re, "string": string, "statistics": statistics,
        })

        # 捕获输出
        import io
        from contextlib import redirect_stdout, redirect_stderr
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exec(compile(code, "<sandbox>", "exec"), safe_globals)

        output = stdout.getvalue()
        result_queue.put(("ok", output if output else "执行完成（无输出）"))
    except Exception as e:
        result_queue.put(("error", f"{type(e).__name__}: {e}"))


def run_script(code: str, timeout: int = 10) -> str:
    """在沙箱中运行 Python 代码。

    1. AST 静态检查
    2. 子进程隔离执行
    3. 超时控制
    """
    # 静态安全检查
    safe, msg = check_safety(code)
    if not safe:
        return f"[安全拦截] {msg}"

    # 子进程执行
    result_queue = multiprocessing.Queue()
    proc = multiprocessing.Process(target=_run_in_process, args=(code, result_queue))
    proc.start()
    proc.join(timeout)

    if proc.is_alive():
        proc.terminate()
        proc.join(1)
        if proc.is_alive():
            proc.kill()
        return f"[超时] 执行超过 {timeout} 秒被终止"

    if not result_queue.empty():
        status, output = result_queue.get()
        if status == "ok":
            return output
        return f"[执行错误] {output}"

    return "[未知错误] 无执行结果"


if __name__ == "__main__":
    # 测试
    test_code = """
import math, json
data = [1, 2, 3, 4, 5]
result = {"sum": sum(data), "avg": sum(data)/len(data), "sqrt_2": math.sqrt(2)}
print(json.dumps(result, indent=2))
"""
    print(run_script(test_code))

    # 测试危险代码
    print(run_script("import os; os.system('ls')"))
    print(run_script("open('test.txt', 'w')"))
