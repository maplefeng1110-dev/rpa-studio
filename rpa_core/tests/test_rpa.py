"""
RPA Core Unit Tests
"""
import unittest
import sys
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rpa_core.utils.context import RuntimeContext
from rpa_core.browser.adapter import BrowserAdapter


class TestRuntimeContext(unittest.TestCase):
    """测试运行时上下文变量解析"""

    def setUp(self):
        self.context = RuntimeContext({
            "str_val": "hello",
            "int_val": 42,
            "list_val": [1, 2, 3],
            "dict_val": {"a": 1}
        })

    def test_string_interpolation(self):
        # 普通字符串插值
        self.assertEqual(self.context.render("value is {{str_val}}"), "value is hello")
        self.assertEqual(self.context.render("value is {{int_val}}"), "value is 42")

    def test_exact_type_preservation(self):
        # 精确变量替换保留原始类型
        self.assertEqual(self.context.render("{{list_val}}"), [1, 2, 3])
        self.assertEqual(self.context.render("{{dict_val}}"), {"a": 1})
        self.assertEqual(self.context.render("{{int_val}}"), 42)

    def test_missing_variable(self):
        # 变量不存在时保留原字符串
        self.assertEqual(self.context.render("{{missing_val}}"), "{{missing_val}}")
        self.assertEqual(self.context.render("hello {{missing_val}}"), "hello {{missing_val}}")


class TestBrowserAdapterInstantiation(unittest.TestCase):
    """测试浏览器适配器初始化配置"""

    def test_init_headless(self):
        # 验证能够正确初始化并包含 headless 参数
        adapter = BrowserAdapter(headless=True)
        self.assertTrue(adapter._headless)
        self.assertIsNone(adapter._page)


class TestEvalCondition(unittest.TestCase):
    """测试条件解析函数"""

    def setUp(self):
        self.context = RuntimeContext({
            "status": "success",
            "count": 10,
            "threshold": 5.5,
            "flag": True
        })

    def test_equality(self):
        from rpa_core.engine.flow_engine import eval_condition
        self.assertTrue(eval_condition("{{status}} == success", self.context))
        self.assertFalse(eval_condition("{{status}} != success", self.context))
        self.assertTrue(eval_condition("{{status}} != fail", self.context))

    def test_comparison(self):
        from rpa_core.engine.flow_engine import eval_condition
        self.assertTrue(eval_condition("{{count}} > 5", self.context))
        self.assertTrue(eval_condition("{{count}} >= 10", self.context))
        self.assertFalse(eval_condition("{{count}} < 5", self.context))
        self.assertTrue(eval_condition("{{threshold}} > 5.0", self.context))

    def test_contains(self):
        from rpa_core.engine.flow_engine import eval_condition
        self.assertTrue(eval_condition("{{status}} contains ucc", self.context))
        self.assertFalse(eval_condition("{{status}} contains fail", self.context))

    def test_boolean_fallback(self):
        from rpa_core.engine.flow_engine import eval_condition
        self.assertTrue(eval_condition("{{flag}}", self.context))
        self.assertTrue(eval_condition("True", self.context))
        self.assertFalse(eval_condition("False", self.context))


class TestFlowEngineControlFlow(unittest.TestCase):
    """测试流程引擎控制流执行"""

    def setUp(self):
        from rpa_core.engine.flow_engine import FlowEngine
        self.engine = FlowEngine()

    def test_if_step_then_branch(self):
        # 测试 if 条件为真，走向 then 分支
        flow = {
            "name": "test_if",
            "steps": [
                {
                    "type": "if",
                    "condition": "1 == 1",
                    "then": [
                        {"type": "wait", "value": 0.01}
                    ],
                    "else": [
                        {"type": "wait", "value": 100.0}
                    ]
                }
            ]
        }
        res = self.engine.execute(flow)
        self.assertTrue(res.success)
        self.assertEqual(res.executed_steps, 2)  # then里面的wait步骤(1) + if步骤本身(1) = 2
        self.assertEqual(len(res.execution_log), 2)
        self.assertEqual(res.execution_log[0]["step_type"], "wait")
        self.assertEqual(res.execution_log[1]["step_type"], "if")

    def test_if_step_else_branch(self):
        # 测试 if 条件为假，走向 else 分支
        flow = {
            "name": "test_if_else",
            "steps": [
                {
                    "type": "if",
                    "condition": "1 == 2",
                    "then": [
                        {"type": "wait", "value": 100.0}
                    ],
                    "else": [
                        {"type": "wait", "value": 0.01}
                    ]
                }
            ]
        }
        res = self.engine.execute(flow)
        self.assertTrue(res.success)
        self.assertEqual(res.executed_steps, 2)
        self.assertEqual(res.execution_log[0]["step_type"], "wait")
        self.assertEqual(res.execution_log[1]["step_type"], "if")

    def test_loop_count(self):
        # 测试次数循环
        flow = {
            "name": "test_loop_count",
            "steps": [
                {
                    "type": "loop",
                    "loop_type": "count",
                    "value": 3,
                    "steps": [
                        {"type": "wait", "value": 0.01}
                    ]
                }
            ]
        }
        res = self.engine.execute(flow)
        self.assertTrue(res.success)
        self.assertEqual(res.executed_steps, 4)  # 3次wait(3) + loop步骤本身(1) = 4
        self.assertEqual(len(res.execution_log), 4)


if __name__ == "__main__":
    unittest.main()
