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


class TestNormalizeSelector(unittest.TestCase):
    """测试选择器规范化（修正 DrissionPage 复合 CSS 退化为文本匹配的隐患）"""

    def test_explicit_prefixes_passthrough(self):
        from rpa_core.browser.adapter import normalize_selector
        for s in ["css:.a.b", "xpath://div", "x://div", "text:登录", "tx:登录",
                  "tag:button", "@id=foo", "c:.x", "t:div"]:
            self.assertEqual(normalize_selector(s), s)

    def test_bare_css_gets_css_prefix(self):
        from rpa_core.browser.adapter import normalize_selector
        # 复合 CSS / 多类 / id / 单类：统一显式标注为 CSS
        self.assertEqual(normalize_selector("h1.title"), "css:h1.title")
        self.assertEqual(normalize_selector("div > span:nth-of-type(2)"), "css:div > span:nth-of-type(2)")
        self.assertEqual(normalize_selector(".a.b"), "css:.a.b")
        self.assertEqual(normalize_selector("#kw"), "css:#kw")

    def test_bare_xpath_gets_xpath_prefix(self):
        from rpa_core.browser.adapter import normalize_selector
        self.assertEqual(normalize_selector("//div[@id='x']"), "xpath://div[@id='x']")
        self.assertEqual(normalize_selector("(//a)[1]"), "xpath:(//a)[1]")


class TestSelfHealingFind(unittest.TestCase):
    """测试候选选择器自愈回退（_find_element），用假 page 避免真实浏览器"""

    def _make_adapter(self, resolvable):
        """resolvable: 一组「规范化后能命中」的选择器集合"""
        from rpa_core.browser.adapter import BrowserAdapter

        class FakeEle:
            text = "ok"
            def click(self): pass

        class FakePage:
            def ele(self, sel, timeout=10):
                return FakeEle() if sel in resolvable else None

        adapter = BrowserAdapter()
        adapter._page = FakePage()
        return adapter

    def test_primary_hit(self):
        adapter = self._make_adapter({"css:#main"})
        ele, used, idx = adapter._find_element(["#main", "css:.fallback"], timeout=1)
        self.assertEqual(used, "#main")
        self.assertEqual(idx, 0)

    def test_fallback_when_primary_misses(self):
        # 主选择器失效，回退到第二候选
        adapter = self._make_adapter({"css:.fallback"})
        ele, used, idx = adapter._find_element(["#gone", ".fallback"], timeout=1)
        self.assertEqual(used, ".fallback")
        self.assertEqual(idx, 1)

    def test_all_miss_raises(self):
        from rpa_core.browser.adapter import ElementNotFoundError
        adapter = self._make_adapter(set())
        with self.assertRaises(ElementNotFoundError):
            adapter._find_element(["#a", "#b"], timeout=1)

    def test_single_string_backward_compatible(self):
        adapter = self._make_adapter({"css:#solo"})
        ele, used, idx = adapter._find_element("#solo", timeout=1)
        self.assertEqual(used, "#solo")


if __name__ == "__main__":
    unittest.main()
