"""
RPA Core Unit Tests
"""
import unittest
import sys
from datetime import datetime
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


class TestRunHistory(unittest.TestCase):
    """测试运行历史 SQLite 存储"""

    def setUp(self):
        import tempfile, os
        self.db = os.path.join(tempfile.gettempdir(), "rpa_hist_unittest.db")
        if os.path.exists(self.db):
            os.remove(self.db)
        from rpa_core.storage import RunHistory
        self.hist = RunHistory(db_path=self.db)

    def tearDown(self):
        import os
        if os.path.exists(self.db):
            os.remove(self.db)

    class _FakeResult:
        def __init__(self, run_id, success):
            self.run_id = run_id
            self.flow_name = "demo"
            self.success = success
            self.executed_steps = 1
            self.total_steps = 2
            self.error = None if success else "boom"
            self.started_at = "2026-06-11T10:00:00"
            self.finished_at = "2026-06-11T10:00:01"
            self.execution_log = [
                {"step_index": 0, "step_type": "click", "success": success,
                 "message": "x", "screenshot": None if success else "runs/r/step_1_fail.png"},
            ]

    def test_record_and_get(self):
        self.hist.record(self._FakeResult("r1", False))
        detail = self.hist.get_run("r1")
        self.assertEqual(detail["flow_name"], "demo")
        self.assertEqual(detail["success"], 0)
        self.assertEqual(detail["execution_log"][0]["screenshot"], "runs/r/step_1_fail.png")

    def test_list_orders_and_missing(self):
        self.hist.record(self._FakeResult("r1", True))
        self.hist.record(self._FakeResult("r2", False))
        runs = self.hist.list_runs()
        self.assertEqual(len(runs), 2)
        self.assertIsNone(self.hist.get_run("nope"))


class TestBrowserScenarios(unittest.TestCase):
    """测试下拉选择 / iframe 路由 / 标签页切换（用假 page，不启动真实浏览器）"""

    class FakeSelect:
        def __init__(self):
            self.calls = []
        def by_text(self, t, timeout=None):
            self.calls.append(("text", t))
        def by_value(self, v, timeout=None):
            self.calls.append(("value", v))
        def by_index(self, i, timeout=None):
            self.calls.append(("index", i))

    class FakeEle:
        def __init__(self, tag="main"):
            self.tag = tag
            self.select = TestBrowserScenarios.FakeSelect()
            self.text = "hi"
        def click(self):
            pass

    class FakeFrame:
        def __init__(self, ele):
            self._ele = ele
        def ele(self, sel, timeout=10):
            return self._ele

    class FakeTab:
        def __init__(self, name):
            self.name = name

    class FakePage:
        def __init__(self):
            self.main_ele = TestBrowserScenarios.FakeEle("main")
            self.frame_ele = TestBrowserScenarios.FakeEle("inframe")
            self.latest_tab = TestBrowserScenarios.FakeTab("latest")
            self._tabs = {0: TestBrowserScenarios.FakeTab("t0"), 1: TestBrowserScenarios.FakeTab("t1")}
            self.new_url = "unset"
        def ele(self, sel, timeout=10):
            return self.main_ele
        def get_frame(self, loc, timeout=None):
            return TestBrowserScenarios.FakeFrame(self.frame_ele)
        def get_tab(self, n):
            return self._tabs[n]
        def new_tab(self, url=None):
            self.new_url = url
            return TestBrowserScenarios.FakeTab("new")

    def _adapter(self):
        a = BrowserAdapter()
        a._page = TestBrowserScenarios.FakePage()
        return a

    def test_select_by_text(self):
        a = self._adapter()
        a.select_option("#sel", by="text", value="北京")
        self.assertIn(("text", "北京"), a._page.main_ele.select.calls)

    def test_select_by_index(self):
        a = self._adapter()
        a.select_option("#sel", by="index", value="2")
        self.assertIn(("index", 2), a._page.main_ele.select.calls)

    def test_iframe_routing(self):
        a = self._adapter()
        # 不带 frame -> 主文档元素；带 frame -> iframe 内元素
        ele_main, _, _ = a._find_element("#x")
        ele_frame, _, _ = a._find_element("#x", frame="#myframe")
        self.assertEqual(ele_main.tag, "main")
        self.assertEqual(ele_frame.tag, "inframe")

    def test_switch_tab_latest_and_index(self):
        a = self._adapter()
        a.switch_tab("latest")
        self.assertEqual(a._active.name, "latest")
        a.switch_tab(1)
        self.assertEqual(a._active.name, "t1")

    def test_new_tab_sets_active(self):
        a = self._adapter()
        a.new_tab("https://example.com")
        self.assertEqual(a._active.name, "new")
        self.assertEqual(a._page.new_url, "https://example.com")


class TestCron(unittest.TestCase):
    """测试零依赖 cron 解析器"""

    def test_wildcard_always_matches(self):
        from rpa_core.scheduler import cron
        self.assertTrue(cron.cron_match("* * * * *", datetime(2026, 6, 11, 3, 7)))

    def test_specific_time(self):
        from rpa_core.scheduler import cron
        self.assertTrue(cron.cron_match("0 9 * * *", datetime(2026, 6, 11, 9, 0)))
        self.assertFalse(cron.cron_match("0 9 * * *", datetime(2026, 6, 11, 9, 1)))

    def test_step(self):
        from rpa_core.scheduler import cron
        for m in (0, 15, 30, 45):
            self.assertTrue(cron.cron_match("*/15 * * * *", datetime(2026, 6, 11, 1, m)))
        self.assertFalse(cron.cron_match("*/15 * * * *", datetime(2026, 6, 11, 1, 7)))

    def test_dow_sunday(self):
        from rpa_core.scheduler import cron
        # 2026-06-14 是周日
        self.assertTrue(cron.cron_match("0 0 * * 0", datetime(2026, 6, 14, 0, 0)))
        self.assertTrue(cron.cron_match("0 0 * * 7", datetime(2026, 6, 14, 0, 0)))
        self.assertFalse(cron.cron_match("0 0 * * 1", datetime(2026, 6, 14, 0, 0)))

    def test_next_run(self):
        from rpa_core.scheduler import cron
        nxt = cron.next_run("0 9 * * *", datetime(2026, 6, 11, 10, 0))
        self.assertEqual((nxt.hour, nxt.minute, nxt.day), (9, 0, 12))

    def test_invalid(self):
        from rpa_core.scheduler import cron
        with self.assertRaises(ValueError):
            cron.parse_cron("* * *")
        with self.assertRaises(ValueError):
            cron.parse_cron("99 * * * *")


class TestScheduleStore(unittest.TestCase):
    def setUp(self):
        import tempfile, os
        self.db = os.path.join(tempfile.gettempdir(), "rpa_sched_unittest.db")
        if os.path.exists(self.db):
            os.remove(self.db)
        from rpa_core.scheduler import ScheduleStore
        self.store = ScheduleStore(db_path=self.db)

    def tearDown(self):
        import os
        if os.path.exists(self.db):
            os.remove(self.db)

    def test_crud(self):
        job = self.store.create({
            "name": "j1", "flow": {"name": "f", "steps": []},
            "schedule_type": "interval", "schedule_value": "60",
        })
        self.assertTrue(job["id"])
        self.assertEqual(job["flow"]["name"], "f")
        self.assertTrue(job["enabled"])
        self.store.update_fields(job["id"], enabled=0)
        self.assertFalse(self.store.get(job["id"])["enabled"])
        self.assertEqual(len(self.store.list()), 1)
        self.assertTrue(self.store.delete(job["id"]))
        self.assertIsNone(self.store.get(job["id"]))


class TestScheduler(unittest.TestCase):
    """测试调度引擎（不启动线程，用受控时钟 + 同步排空队列）"""

    def setUp(self):
        import tempfile, os
        self.db = os.path.join(tempfile.gettempdir(), "rpa_sched2_unittest.db")
        if os.path.exists(self.db):
            os.remove(self.db)
        from rpa_core.scheduler import Scheduler, ScheduleStore
        self.store = ScheduleStore(db_path=self.db)
        self.calls = []
        self.clock = {"t": datetime(2026, 6, 11, 10, 0, 0)}
        self.sched = Scheduler(
            run_callback=lambda flow, ctx: self.calls.append(flow),
            store=self.store,
            now_fn=lambda: self.clock["t"],
        )

    def tearDown(self):
        import os
        if os.path.exists(self.db):
            os.remove(self.db)

    def _make_interval_job(self, seconds=60, enabled=True):
        return self.store.create({
            "name": "j", "flow": {"name": "f", "steps": []},
            "schedule_type": "interval", "schedule_value": str(seconds),
            "enabled": enabled, "created_at": self.clock["t"].isoformat(),
        })

    def test_interval_fires_after_due(self):
        from datetime import timedelta
        self._make_interval_job(60)
        t0 = self.clock["t"]
        # 首次 poll：仅设置 next_run，不触发
        self.assertEqual(self.sched.poll(t0), 0)
        # 未到点
        self.assertEqual(self.sched.poll(t0 + timedelta(seconds=30)), 0)
        # 到点：入队
        self.assertEqual(self.sched.poll(t0 + timedelta(seconds=61)), 1)
        # 执行队列 -> 回调被调用
        self.assertEqual(self.sched.process_queue(), 1)
        self.assertEqual(len(self.calls), 1)

    def test_disabled_not_fired(self):
        from datetime import timedelta
        self._make_interval_job(60, enabled=False)
        t0 = self.clock["t"]
        self.sched.poll(t0)
        self.assertEqual(self.sched.poll(t0 + timedelta(seconds=120)), 0)

    def test_run_now(self):
        job = self._make_interval_job(60)
        self.assertTrue(self.sched.run_now(job["id"]))
        self.assertEqual(self.sched.process_queue(), 1)
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(self.sched.run_now("nope"))

    def test_callback_error_recorded(self):
        from rpa_core.scheduler import Scheduler
        def boom(flow, ctx):
            raise RuntimeError("kaboom")
        sched = Scheduler(run_callback=boom, store=self.store, now_fn=lambda: self.clock["t"])
        job = self._make_interval_job(60)
        sched.run_now(job["id"])
        sched.process_queue()  # 不应抛出
        self.assertTrue(self.store.get(job["id"])["last_status"].startswith("error"))


class TestSecretVault(unittest.TestCase):
    """测试加密凭据保险库"""

    def setUp(self):
        import tempfile, os
        from cryptography.fernet import Fernet
        from rpa_core.vault import SecretVault
        self.db = os.path.join(tempfile.gettempdir(), "rpa_vault_unittest.db")
        if os.path.exists(self.db):
            os.remove(self.db)
        self.key = Fernet.generate_key()
        self.vault = SecretVault(db_path=self.db, key=self.key)

    def tearDown(self):
        import os
        if os.path.exists(self.db):
            os.remove(self.db)

    def test_set_get_roundtrip(self):
        self.vault.set("login_pw", "s3cr3t!")
        self.assertEqual(self.vault.get("login_pw"), "s3cr3t!")

    def test_stored_ciphertext_is_not_plaintext(self):
        import sqlite3
        self.vault.set("api", "PLAINTEXT_VALUE")
        with sqlite3.connect(self.db) as c:
            blob = c.execute("SELECT ciphertext FROM secrets WHERE name='api'").fetchone()[0]
        self.assertNotIn(b"PLAINTEXT_VALUE", blob)

    def test_list_names_only(self):
        self.vault.set("a", "1")
        self.vault.set("b", "2")
        names = [s["name"] for s in self.vault.list_names()]
        self.assertEqual(sorted(names), ["a", "b"])

    def test_delete_and_missing(self):
        self.vault.set("x", "y")
        self.assertTrue(self.vault.delete("x"))
        self.assertIsNone(self.vault.get("x"))
        self.assertFalse(self.vault.delete("nope"))

    def test_wrong_key_fails(self):
        from cryptography.fernet import Fernet
        from rpa_core.vault import SecretVault
        self.vault.set("k", "v")
        other = SecretVault(db_path=self.db, key=Fernet.generate_key())
        with self.assertRaises(ValueError):
            other.get("k")


class TestSecretInContext(unittest.TestCase):
    """测试 {{secret:name}} 渲染，且明文不进入上下文快照"""

    def _ctx(self):
        secrets = {"pw": "TOPSECRET", "user": "alice"}
        return RuntimeContext(
            {"q": "hello"},
            secret_resolver=lambda name: secrets.get(name),
        )

    def test_exact_secret(self):
        self.assertEqual(self._ctx().render("{{secret:pw}}"), "TOPSECRET")

    def test_inline_secret_and_var(self):
        self.assertEqual(self._ctx().render("u={{secret:user}};q={{q}}"), "u=alice;q=hello")

    def test_missing_secret_keeps_template(self):
        self.assertEqual(self._ctx().render("{{secret:nope}}"), "{{secret:nope}}")

    def test_secret_not_in_snapshot(self):
        ctx = self._ctx()
        _ = ctx.render("{{secret:pw}}")
        # 明文绝不能出现在上下文快照里（即不会进入运行历史）
        self.assertNotIn("TOPSECRET", str(ctx.to_dict()))
        self.assertNotIn("pw", ctx.to_dict())


class TestAIFallback(unittest.TestCase):
    """测试 AI 视觉兜底定位（DOM 全失效后），用假 locator + 假 page，不联网"""

    class FakeEle:
        def __init__(self, tag): self.tag = tag; self.clicked = False; self.text = "ok"
        def click(self): self.clicked = True
        def clear(self): pass
        def input(self, t): self.typed = t

    class FakeActions:
        def __init__(self): self.moved = None; self.clicked = False
        def move_to(self, loc): self.moved = loc; return self
        def click(self): self.clicked = True

    class FakePage:
        def __init__(self, ai_selector_norm=None, ai_ele=None):
            self.ai_selector_norm = ai_selector_norm
            self.ai_ele = ai_ele
            self.actions = TestAIFallback.FakeActions()
            self.html = "<html></html>"
        def ele(self, sel, timeout=10):
            # 原 DOM 候选全部失败；只有 AI 修复后的选择器能命中
            if self.ai_selector_norm and sel == self.ai_selector_norm:
                return self.ai_ele
            return None
        def get_screenshot(self, as_bytes=None): return b"PNGDATA"
        def _run_js(self, js): return 1000

    class FakeLocator:
        def __init__(self, result): self._result = result; self.available = True
        def locate(self, **kwargs): self.last_kwargs = kwargs; return self._result

    def _adapter(self, page, result):
        from rpa_core.browser.adapter import BrowserAdapter
        a = BrowserAdapter(ai_locator=TestAIFallback.FakeLocator(result))
        a._page = page
        return a

    def test_click_ai_selector_repair(self):
        ele = TestAIFallback.FakeEle("fixed")
        page = TestAIFallback.FakePage(ai_selector_norm="css:#ai-fixed", ai_ele=ele)
        a = self._adapter(page, {"strategy": "selector", "selector": "#ai-fixed", "reason": "r"})
        used = a.click("#gone", timeout=1, intent="登录按钮")
        self.assertEqual(used, "#ai-fixed")
        self.assertTrue(ele.clicked)

    def test_click_ai_coordinates(self):
        page = TestAIFallback.FakePage()
        a = self._adapter(page, {"strategy": "coordinates", "x": 42, "y": 99, "reason": "canvas"})
        used = a.click("#gone", timeout=1)
        self.assertEqual(used, "ai:coordinates")
        self.assertEqual(page.actions.moved, (42, 99))
        self.assertTrue(page.actions.clicked)

    def test_input_rejects_coordinates(self):
        from rpa_core.browser.adapter import ElementNotFoundError
        page = TestAIFallback.FakePage()
        a = self._adapter(page, {"strategy": "coordinates", "x": 1, "y": 2})
        with self.assertRaises(ElementNotFoundError):
            a.input("#gone", "hi", timeout=1)

    def test_input_ai_selector_repair(self):
        ele = TestAIFallback.FakeEle("field")
        page = TestAIFallback.FakePage(ai_selector_norm="css:.ai-field", ai_ele=ele)
        a = self._adapter(page, {"strategy": "selector", "selector": ".ai-field"})
        used = a.input("#gone", "hello", timeout=1)
        self.assertEqual(used, ".ai-field")
        self.assertEqual(ele.typed, "hello")

    def test_no_locator_raises(self):
        from rpa_core.browser.adapter import BrowserAdapter, ElementNotFoundError
        a = BrowserAdapter()  # 无 AI locator
        a._page = TestAIFallback.FakePage()
        with self.assertRaises(ElementNotFoundError):
            a.click("#gone", timeout=1)


class TestAILocatorParsing(unittest.TestCase):
    """测试 AILocator 对 LLM 结构化响应的解析（注入假 client，不联网）"""

    class _Block:
        def __init__(self, text): self.type = "text"; self.text = text

    class _Resp:
        def __init__(self, text): self.content = [TestAILocatorParsing._Block(text)]

    class _FakeClient:
        def __init__(self, text): self._text = text
        class _Messages:
            def __init__(self, text): self._text = text
            def create(self, **kwargs): return TestAILocatorParsing._Resp(self._text)
        @property
        def messages(self): return TestAILocatorParsing._FakeClient._Messages(self._text)

    def _locator(self, text):
        from rpa_core.ai import AILocator
        loc = AILocator(enabled=True)
        loc._client = TestAILocatorParsing._FakeClient(text)
        return loc

    def test_parse_selector(self):
        loc = self._locator('{"strategy":"selector","selector":"css:.x","x":null,"y":null,"reason":"r"}')
        r = loc.locate(intent="x", failed_selectors=["#a"])
        self.assertEqual(r["strategy"], "selector")
        self.assertEqual(r["selector"], "css:.x")

    def test_parse_coordinates(self):
        loc = self._locator('{"strategy":"coordinates","selector":null,"x":10,"y":20,"reason":"r"}')
        r = loc.locate(failed_selectors=["#a"])
        self.assertEqual((r["x"], r["y"]), (10, 20))

    def test_coordinates_suppressed_when_not_allowed(self):
        loc = self._locator('{"strategy":"coordinates","selector":null,"x":10,"y":20,"reason":"r"}')
        self.assertIsNone(loc.locate(failed_selectors=["#a"], allow_coordinates=False))

    def test_parse_none(self):
        loc = self._locator('{"strategy":"none","selector":null,"x":null,"y":null,"reason":"r"}')
        self.assertIsNone(loc.locate(failed_selectors=["#a"]))


class TestFlowGen(unittest.TestCase):
    """测试 NL → Flow 生成：校验器 + 解析（注入假 client，不联网）"""

    def test_validator_ok(self):
        from rpa_core.ai import validate_flow_dict
        flow = {"name": "t", "steps": [
            {"type": "open", "value": "https://x.com"},
            {"type": "loop", "loop_type": "count", "value": "2", "steps": [
                {"type": "click", "selector": "#a"},
            ]},
        ]}
        self.assertEqual(validate_flow_dict(flow), [])

    def test_validator_catches_nested_and_missing(self):
        from rpa_core.ai import validate_flow_dict
        errs = validate_flow_dict({"steps": [
            {"type": "open"},  # 缺 value
            {"type": "if", "condition": "x", "then": [{"type": "bad"}]},
        ]})
        self.assertTrue(any("open" in e for e in errs))
        self.assertTrue(any("未知类型" in e for e in errs))

    def test_validator_top_level(self):
        from rpa_core.ai import validate_flow_dict
        self.assertTrue(validate_flow_dict({}))  # 缺 steps
        self.assertTrue(validate_flow_dict("nope"))

    class _Block:
        def __init__(self, text): self.type = "text"; self.text = text

    class _Resp:
        def __init__(self, text): self.content = [TestFlowGen._Block(text)]

    class _FakeClient:
        def __init__(self, text): self._text = text
        class _M:
            def __init__(self, text): self._text = text
            def create(self, **kw): return TestFlowGen._Resp(self._text)
        @property
        def messages(self): return TestFlowGen._FakeClient._M(self._text)

    def _gen(self, text):
        from rpa_core.ai import FlowGenerator
        g = FlowGenerator()
        g._client = TestFlowGen._FakeClient(text)
        return g

    def test_generate_parses_fenced_json(self):
        g = self._gen('```json\n{"name":"登录","steps":[{"type":"open","value":"https://x.com"}]}\n```')
        r = g.generate("打开 x.com")
        self.assertTrue(r["success"])
        self.assertEqual(r["flow"]["steps"][0]["type"], "open")

    def test_generate_rejects_invalid_flow(self):
        g = self._gen('{"steps":[{"type":"frobnicate"}]}')
        r = g.generate("做点什么")
        self.assertFalse(r["success"])
        self.assertTrue(r["errors"])

    def test_generate_handles_bad_json(self):
        g = self._gen('not json at all')
        r = g.generate("x")
        self.assertFalse(r["success"])
        self.assertIn("JSON", r["error"])


class TestBrowserPool(unittest.TestCase):
    """测试浏览器池：懒创建、借满返回 None、归还复用、close_all"""

    class FakeAdapter:
        def __init__(self): self.closed = False
        def close(self): self.closed = True

    def _pool(self, size):
        from rpa_core.browser import BrowserPool
        self.created = []
        def factory():
            a = TestBrowserPool.FakeAdapter()
            self.created.append(a)
            return a
        return BrowserPool(size, factory)

    def test_lazy_creation_and_exhaustion(self):
        pool = self._pool(2)
        self.assertEqual(len(self.created), 0)  # 懒创建：还没借就不创建
        a1 = pool.acquire(block=False)
        a2 = pool.acquire(block=False)
        self.assertEqual(len(self.created), 2)
        self.assertIsNotNone(a1)
        self.assertIsNotNone(a2)
        self.assertIsNot(a1, a2)
        # 池已满，非阻塞借取返回 None
        self.assertIsNone(pool.acquire(block=False))

    def test_release_allows_reacquire(self):
        pool = self._pool(1)
        a1 = pool.acquire(block=False)
        self.assertIsNone(pool.acquire(block=False))
        pool.release(a1)
        a2 = pool.acquire(block=False)
        self.assertIs(a1, a2)  # 复用归还的实例，未新建
        self.assertEqual(len(self.created), 1)

    def test_close_all(self):
        pool = self._pool(2)
        a1 = pool.acquire(block=False)
        a2 = pool.acquire(block=False)
        pool.close_all()
        self.assertTrue(a1.closed and a2.closed)

    def test_invalid_size(self):
        from rpa_core.browser import BrowserPool
        with self.assertRaises(ValueError):
            BrowserPool(0, lambda: None)


class TestAIConfigStore(unittest.TestCase):
    """测试 AI 配置存储：key 加密、非敏感项落 JSON、不回读 key、保留名不进凭据列表"""

    def setUp(self):
        import tempfile, os
        from cryptography.fernet import Fernet
        from rpa_core.vault import SecretVault
        from rpa_core.ai import AIConfigStore
        self.tmp = tempfile.mkdtemp()
        self.vault = SecretVault(db_path=os.path.join(self.tmp, "v.db"), key=Fernet.generate_key())
        self.store = AIConfigStore(self.vault, path=os.path.join(self.tmp, "ai.json"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_default_no_key(self):
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        pub = self.store.public()
        self.assertFalse(pub["has_key"])
        self.assertEqual(pub["model"], "claude-opus-4-8")

    def test_update_and_public(self):
        self.store.update(api_key="sk-test-123", base_url="https://proxy.example", model="m1", fallback_enabled=True)
        pub = self.store.public()
        self.assertTrue(pub["has_key"])
        self.assertEqual(pub["base_url"], "https://proxy.example")
        self.assertEqual(pub["model"], "m1")
        self.assertTrue(pub["fallback_enabled"])
        # public 绝不含明文 key
        self.assertNotIn("sk-test-123", str(pub))
        # 但内部能取到
        self.assertEqual(self.store.get_api_key(), "sk-test-123")

    def test_key_hidden_from_vault_list(self):
        self.store.update(api_key="sk-secret")
        names = [s["name"] for s in self.vault.list_names()]
        self.assertNotIn("__rpa_ai_key__", names)  # 保留名不展示给用户

    def test_clear_key(self):
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        self.store.update(api_key="sk-x")
        self.assertTrue(self.store.public()["has_key"])
        self.store.update(clear_key=True)
        self.assertFalse(self.store.public()["has_key"])

    def test_locator_uses_config(self):
        from rpa_core.ai import AILocator
        loc = AILocator(config_store=self.store)
        # 未配置 key 且未开兜底 -> 不可用
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        self.assertFalse(loc.available)


if __name__ == "__main__":
    unittest.main()
