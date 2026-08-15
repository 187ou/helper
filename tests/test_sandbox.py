"""沙箱安全隔离模块单元测试。"""
import pytest
from tools.sandbox_run import check_safety, run_script


class TestCheckSafety:
    """测试 AST 静态安全检查。"""

    def test_safe_code_passes(self):
        """安全代码应通过检查。"""
        code = "import math\nresult = math.sqrt(16)"
        safe, msg = check_safety(code)
        assert safe is True

    def test_forbid_os_import(self):
        """os 模块应被拦截。"""
        code = "import os\nos.system('ls')"
        safe, msg = check_safety(code)
        assert safe is False
        assert "os" in msg

    def test_forbid_eval(self):
        """eval 应被拦截。"""
        code = "eval('1+1')"
        safe, msg = check_safety(code)
        assert safe is False
        assert "eval" in msg

    def test_forbid_open(self):
        """open 应被拦截。"""
        code = "open('test.txt', 'w')"
        safe, msg = check_safety(code)
        assert safe is False

    def test_forbid_subprocess(self):
        """subprocess 应被拦截。"""
        code = "import subprocess\nsubprocess.run(['ls'])"
        safe, msg = check_safety(code)
        assert safe is False
        assert "subprocess" in msg

    def test_forbid_dunder_import(self):
        """__import__ 应被拦截。"""
        code = "__import__('os')"
        safe, msg = check_safety(code)
        assert safe is False

    def test_syntax_error(self):
        """语法错误应返回失败。"""
        code = "def foo(:"
        safe, msg = check_safety(code)
        assert safe is False
        assert "语法错误" in msg


class TestRunScript:
    """测试沙箱执行。"""

    def test_execute_safe_code(self):
        """安全代码应正常执行。"""
        code = "import math\nprint(math.sqrt(16))"
        result = run_script(code, timeout=5)
        assert "4.0" in result

    def test_block_dangerous_code(self):
        """危险代码应被拦截。"""
        code = "import os\nos.system('ls')"
        result = run_script(code, timeout=5)
        assert "[安全拦截]" in result

    def test_timeout_protection(self):
        """超时代码应被终止。"""
        code = "import time\nwhile True:\n    time.sleep(1)"
        result = run_script(code, timeout=2)
        assert "[超时]" in result

    def test_math_operations(self):
        """数学运算应正常执行。"""
        code = "import math, json\nresult = {'sum': sum(range(10)), 'sqrt': math.sqrt(2)}\nprint(json.dumps(result))"
        result = run_script(code, timeout=5)
        assert "45" in result
