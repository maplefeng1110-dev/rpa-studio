"""
Browser Adapter 模块
封装浏览器操作能力，隔离 RPA 内核与 DrissionPage 实现
任何上层模块禁止直接使用 DrissionPage API
"""
import time
from typing import List, Optional, Tuple, Union
from DrissionPage import ChromiumPage, ChromiumOptions

from ..utils import setup_logger

logger = setup_logger("BrowserAdapter")

# DrissionPage 原生识别的定位前缀。带这些前缀的选择器原样透传。
_KNOWN_PREFIXES = (
    "xpath:", "xpath=", "x:", "x=",
    "css:", "css=", "c:", "c=",
    "text:", "text=", "text^", "text$", "tx:", "tx=", "tx^", "tx$",
    "tag:", "tag=", "tag^", "tag$", "t:", "t=",
    "@",
)


def normalize_selector(selector: str) -> str:
    """
    将选择器规范化为 DrissionPage 能正确解析的形式。

    背景：DrissionPage 的 ele() 对「无前缀」字符串的处理是——只有 #id / .class（单类）
    会被当定位符，其余（如 h1.title、div > span、.a.b 复合 CSS）会退化成「文本模糊匹配」，
    并不会按 CSS 解析。这里统一把无前缀的串显式标注为 CSS（或裸 XPath 标注为 xpath），
    既修正了复合 CSS 失效的隐患，也让多类选择器（.a.b）正确工作。

    - 已带前缀（css:/xpath:/text:/@... 等）：原样返回
    - 裸 XPath（以 / 或 ( 开头）：加 xpath: 前缀
    - 其余一律按 CSS 处理：加 css: 前缀
    """
    if not selector:
        return selector
    s = selector.strip()
    if s.startswith(_KNOWN_PREFIXES):
        return s
    if s.startswith(("/", "(")):
        return f"xpath:{s}"
    return f"css:{s}"


def _as_candidates(selector: Union[str, List[str], None]) -> List[str]:
    """把单个选择器或候选列表统一成非空候选列表。"""
    if selector is None:
        return []
    if isinstance(selector, (list, tuple)):
        return [s for s in selector if s]
    return [selector] if selector else []


class BrowserAdapter:
    """
    浏览器适配器
    - 封装 DrissionPage ChromiumPage 操作
    - 提供统一的浏览器操作接口
    - 支持有头/无头模式切换
    """
    
    def __init__(self, headless: bool = False, ai_locator=None):
        """
        初始化浏览器适配器

        Args:
            headless: 是否使用无头模式
            ai_locator: 可选的 AI 兜底定位器（AILocator）。DOM 候选全部失效时启用。
        """
        self._page: Optional[ChromiumPage] = None
        self._headless = headless
        self._ai_locator = ai_locator
        # 当前操作目标：可被 switch_tab/new_tab 切换为某个标签页对象；None 表示主页面
        self._active = None

    def _ai_resolve(self, candidates: List[str], intent: Optional[str], allow_coordinates: bool):
        """
        DOM 失败后的 AI 兜底。返回：
          ("element", 元素, 选择器) —— LLM 给出可解析的修复选择器
          ("coords", (x, y), None) —— LLM 给出点击坐标（仅 allow_coordinates 时）
          None —— 不可用或无法定位
        """
        if not (self._ai_locator and self._ai_locator.available):
            return None
        target = self._target()
        # 捕获截图 + 精简 DOM + 视口尺寸，任何一步失败都不应中断（降级为可用的部分）
        screenshot = html = viewport = None
        try:
            screenshot = target.get_screenshot(as_bytes="png")
        except Exception:
            pass
        try:
            html = target.html
        except Exception:
            pass
        try:
            viewport = {
                "width": int(target._run_js("return window.innerWidth;")),
                "height": int(target._run_js("return window.innerHeight;")),
            }
        except Exception:
            pass

        result = self._ai_locator.locate(
            intent=intent, failed_selectors=candidates, html=html,
            screenshot_png=screenshot, viewport=viewport, allow_coordinates=allow_coordinates,
        )
        if not result:
            return None

        if result["strategy"] == "selector":
            sel = result["selector"]
            try:
                element = target.ele(normalize_selector(sel), timeout=5)
            except Exception:
                element = None
            if element:
                logger.warning(f"AI 选择器修复：DOM 候选全失效，改用 LLM 给出的 '{sel}'")
                return ("element", element, sel)
            return None

        if result["strategy"] == "coordinates":
            logger.warning(f"AI 视觉兜底：DOM 无法定位，改用坐标点击 ({result['x']},{result['y']})")
            return ("coords", (result["x"], result["y"]), None)
        return None

    def _target(self):
        """返回当前操作目标（激活的标签页或主页面）。所有元素/页面操作都走它。"""
        self._ensure_page()
        return self._active or self._page

    def _ensure_page(self) -> ChromiumPage:
        """确保页面实例存在"""
        if self._page is None:
            options = ChromiumOptions()
            options.headless(self._headless)
            
            # 使用自动分配的端口，避免与用户正在运行的 Chrome (9222) 端口冲突导致连接断开
            options.auto_port()
            
            # macOS 下默认 Chrome 路径防备
            import sys
            import os
            if sys.platform == "darwin":
                mac_chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
                if os.path.exists(mac_chrome):
                    options.set_browser_path(mac_chrome)
                    
            self._page = ChromiumPage(addr_or_opts=options)
        return self._page
    
    def open(self, url: str, timeout: int = 10) -> None:
        """
        打开指定 URL
        
        Args:
            url: 目标网址
            timeout: 超时时间（秒）
        """
        try:
            target = self._target()
            target.get(url, timeout=timeout)
        except Exception as e:
            raise PageLoadTimeoutError(f"页面加载超时或失败: {url}, 错误: {str(e)}")

    def _find_element(
        self,
        selector: Union[str, List[str]],
        timeout: int = 10,
        frame: Union[str, int, None] = None,
    ) -> Tuple[object, str, int]:
        """
        按候选选择器顺序定位元素，实现「选择器自愈」：
        依次尝试每个候选，命中即返回。若主选择器（第 0 个）失效而靠后续候选命中，
        会打 warning 日志作为页面漂移的信号。

        Args:
            selector: 单个选择器或候选选择器列表（按优先级排序）
            timeout: 首选选择器的超时时间；后续候选用较短超时避免叠加等待
            frame: 可选 iframe 定位（选择器或下标），在该 iframe 内查找元素

        Returns:
            (元素, 命中的原始选择器, 命中候选的下标)

        Raises:
            ElementNotFoundError: 所有候选都未命中
        """
        candidates = _as_candidates(selector)
        if not candidates:
            raise ElementNotFoundError("未提供任何选择器")

        # 确定查找容器：iframe（若指定）或当前激活目标
        container = self._target()
        if frame is not None and frame != "":
            try:
                frame_loc = frame if isinstance(frame, int) else normalize_selector(str(frame))
                container = self._target().get_frame(frame_loc, timeout=timeout)
                if not container:
                    raise ElementNotFoundError(f"iframe 未找到: {frame}")
            except ElementNotFoundError:
                raise
            except Exception as e:
                raise ElementNotFoundError(f"切换 iframe 失败: {frame}, 错误: {str(e)}")

        last_error: Optional[str] = None

        for idx, raw in enumerate(candidates):
            normalized = normalize_selector(raw)
            # 首选用完整 timeout，后备候选用较短超时（最多 3s）
            attempt_timeout = timeout if idx == 0 else min(timeout, 3)
            try:
                element = container.ele(normalized, timeout=attempt_timeout)
            except Exception as e:
                last_error = str(e)
                element = None

            if element:
                if idx > 0:
                    logger.warning(
                        f"选择器自愈：主选择器 '{candidates[0]}' 失效，"
                        f"已回退到候选 #{idx} '{raw}'"
                    )
                return element, raw, idx

        detail = f"，最后错误: {last_error}" if last_error else ""
        raise ElementNotFoundError(f"元素未找到（已尝试 {len(candidates)} 个候选）: {candidates}{detail}")

    def click(self, selector: Union[str, List[str]], timeout: int = 10, frame: Union[str, int, None] = None,
              intent: Optional[str] = None) -> str:
        """
        点击元素。DOM 候选全失效时走 AI 兜底（修复选择器或坐标点击）。

        Returns:
            实际命中的选择器（坐标点击时返回 'ai:coordinates'）
        """
        try:
            element, used, _ = self._find_element(selector, timeout=timeout, frame=frame)
        except ElementNotFoundError:
            resolved = self._ai_resolve(_as_candidates(selector), intent, allow_coordinates=True)
            if resolved is None:
                raise
            kind, payload, used = resolved
            if kind == "coords":
                try:
                    self._target().actions.move_to(payload).click()
                except Exception as e:
                    raise ElementNotFoundError(f"坐标点击失败 {payload}, 错误: {str(e)}")
                return "ai:coordinates"
            element = payload  # kind == "element"
        try:
            element.click()
        except Exception as e:
            raise ElementNotFoundError(f"点击元素失败: {used}, 错误: {str(e)}")
        return used

    def input(self, selector: Union[str, List[str]], text: str, timeout: int = 10, clear: bool = True,
              frame: Union[str, int, None] = None, intent: Optional[str] = None) -> str:
        """
        输入文本。DOM 候选全失效时走 AI 选择器修复（输入需要真实元素，不用坐标）。

        Returns:
            实际命中的选择器
        """
        element, used = self._resolve_for_value_op(selector, timeout, frame, intent, "输入文本")
        try:
            if clear:
                element.clear()
            element.input(text)
        except Exception as e:
            raise ElementNotFoundError(f"输入文本失败: {used}, 错误: {str(e)}")
        return used

    def exists(self, selector: Union[str, List[str]], timeout: int = 3, frame: Union[str, int, None] = None) -> bool:
        """判断元素是否存在（任一候选命中即为存在）。不触发 AI 兜底。"""
        try:
            self._find_element(selector, timeout=timeout, frame=frame)
            return True
        except ElementNotFoundError:
            return False

    def text(self, selector: Union[str, List[str]], timeout: int = 10, frame: Union[str, int, None] = None,
             intent: Optional[str] = None) -> str:
        """获取元素文本内容。DOM 候选全失效时走 AI 选择器修复。"""
        element, used = self._resolve_for_value_op(selector, timeout, frame, intent, "获取元素文本")
        try:
            return element.text
        except Exception as e:
            raise ElementNotFoundError(f"获取元素文本失败: {used}, 错误: {str(e)}")

    def select_option(self, selector: Union[str, List[str]], by: str, value: Union[str, int],
                      timeout: int = 10, frame: Union[str, int, None] = None, intent: Optional[str] = None) -> str:
        """
        操作 <select> 下拉框。DOM 候选全失效时走 AI 选择器修复。

        Args:
            by: 'text' | 'value' | 'index'
            value: 对应的选项文本/值/下标
        """
        element, used = self._resolve_for_value_op(selector, timeout, frame, intent, "下拉选择")
        try:
            sel = element.select
            if by == "text":
                sel.by_text(str(value))
            elif by == "value":
                sel.by_value(str(value))
            elif by == "index":
                sel.by_index(int(value))
            else:
                raise ElementNotFoundError(f"未知的下拉选择方式: {by}（应为 text/value/index）")
        except ElementNotFoundError:
            raise
        except Exception as e:
            raise ElementNotFoundError(f"下拉选择失败: {used} by={by} value={value}, 错误: {str(e)}")
        return used

    def _resolve_for_value_op(self, selector, timeout, frame, intent, op_label):
        """
        为 input/text/select 等「需要真实元素」的操作定位元素：
        先走 DOM 自愈，全失败再走 AI 选择器修复（不接受坐标）。返回 (元素, 命中选择器)。
        """
        try:
            element, used, _ = self._find_element(selector, timeout=timeout, frame=frame)
            return element, used
        except ElementNotFoundError:
            resolved = self._ai_resolve(_as_candidates(selector), intent, allow_coordinates=False)
            if resolved is None or resolved[0] != "element":
                raise
            return resolved[1], resolved[2]

    def switch_tab(self, target: Union[str, int]) -> None:
        """
        切换当前操作的标签页。

        Args:
            target: 'latest'（最新打开的标签页）或整数下标（从 0 开始）
        """
        page = self._ensure_page()
        try:
            if isinstance(target, str) and target.strip().lower() in ("latest", "new", "last"):
                self._active = page.latest_tab
            else:
                self._active = page.get_tab(int(target))
        except Exception as e:
            raise ElementNotFoundError(f"切换标签页失败: {target}, 错误: {str(e)}")

    def new_tab(self, url: Optional[str] = None) -> None:
        """打开一个新标签页并切换为当前操作目标。"""
        page = self._ensure_page()
        try:
            self._active = page.new_tab(url=url) if url else page.new_tab()
        except Exception as e:
            raise PageLoadTimeoutError(f"打开新标签页失败: {url}, 错误: {str(e)}")

    def set_download_path(self, path: str) -> None:
        """设置后续下载的保存目录。"""
        page = self._ensure_page()
        page.set.download_path(path)

    def wait_download(self, timeout: int = 30) -> bool:
        """等待下载完成。返回是否在超时内完成。"""
        page = self._ensure_page()
        try:
            return bool(page.wait.downloads_done(timeout=timeout))
        except Exception:
            return False
    
    def wait(self, seconds: float) -> None:
        """
        等待指定时间
        
        Args:
            seconds: 等待秒数
        """
        time.sleep(seconds)
    
    def screenshot(self, path: str) -> None:
        """
        页面截图
        
        Args:
            path: 截图保存路径
        """
        self._target().get_screenshot(path=path)
    
    def pick_element_start(self) -> None:
        """
        向当前页面注入 JS，进入元素拾取模式。
        鼠标悬停会高亮元素，点击后将 CSS 选择器写入 window.__picked_selector。
        """
        page = self._target()
        js = """
(function() {
    // 清除旧结果
    window.__picked_selector = null;

    // 避免重复注入
    if (window.__rpa_picker_active) return;
    window.__rpa_picker_active = true;

    // 创建高亮遮罩
    var overlay = document.createElement('div');
    overlay.id = '__rpa_picker_overlay';
    overlay.style.cssText = [
        'position:fixed','top:0','left:0','width:100%','height:100%',
        'z-index:2147483646','pointer-events:none',
        'box-sizing:border-box'
    ].join(';');
    document.body.appendChild(overlay);

    // 高亮提示 banner
    var banner = document.createElement('div');
    banner.style.cssText = [
        'position:fixed','top:0','left:0','width:100%','padding:8px',
        'background:rgba(220,38,38,0.9)','color:#fff',
        'font-size:14px','font-family:monospace','text-align:center',
        'z-index:2147483647','pointer-events:none'
    ].join(';');
    banner.textContent = '🎯 RPA 元素拾取模式 — 点击目标元素以捕获选择器（ESC 取消）';
    document.body.appendChild(banner);

    var lastEl = null;

    function cssPath(el) {
        if (!el || el === document.body) return 'body';
        if (el.id) return '#' + CSS.escape(el.id);
        var parts = [];
        while (el && el !== document.body) {
            var seg = el.tagName.toLowerCase();
            if (el.id) { seg = '#' + CSS.escape(el.id); parts.unshift(seg); break; }
            if (el.className && typeof el.className === 'string') {
                var cls = Array.from(el.classList).slice(0, 2).map(function(c){ return '.' + CSS.escape(c); }).join('');
                seg += cls;
            }
            var siblings = Array.from(el.parentNode ? el.parentNode.children : []);
            var sameTag = siblings.filter(function(s){ return s.tagName === el.tagName; });
            if (sameTag.length > 1) seg += ':nth-of-type(' + (sameTag.indexOf(el) + 1) + ')';
            parts.unshift(seg);
            el = el.parentNode;
        }
        return parts.join(' > ');
    }

    // 生成一组按稳定性排序的候选选择器，供运行时自愈回退
    function buildCandidates(el) {
        var out = [];
        var tag = el.tagName.toLowerCase();
        function push(s) { if (s && out.indexOf(s) === -1) out.push(s); }

        // 1) id 最稳定
        if (el.id) push('#' + CSS.escape(el.id));
        // 2) 测试/语义属性
        ['data-testid', 'data-test', 'data-id', 'name', 'aria-label'].forEach(function(a) {
            var v = el.getAttribute && el.getAttribute(a);
            if (v) push('css:' + tag + '[' + a + '="' + v.replace(/"/g, '\\"') + '"]');
        });
        // 3) 完整 CSS 路径
        push('css:' + cssPath(el));
        // 4) 文本定位（按钮/链接等短文本元素）
        var txt = (el.textContent || '').trim();
        if (txt && txt.length <= 30 && (tag === 'a' || tag === 'button' || el.getAttribute('role') === 'button')) {
            push('text:' + txt);
        }
        return out;
    }

    function onMouseOver(e) {
        if (lastEl) lastEl.style.outline = '';
        lastEl = e.target;
        lastEl.style.outline = '2px solid #ef4444';
    }

    function onClick(e) {
        e.preventDefault();
        e.stopPropagation();
        var candidates = buildCandidates(e.target);
        window.__picked_selectors = candidates;
        window.__picked_selector = candidates[0] || null;  // 向后兼容
        cleanup();
    }

    function onKeydown(e) {
        if (e.key === 'Escape') cleanup();
    }

    function cleanup() {
        if (lastEl) lastEl.style.outline = '';
        document.removeEventListener('mouseover', onMouseOver, true);
        document.removeEventListener('click', onClick, true);
        document.removeEventListener('keydown', onKeydown, true);
        if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
        if (banner.parentNode) banner.parentNode.removeChild(banner);
        window.__rpa_picker_active = false;
    }

    document.addEventListener('mouseover', onMouseOver, true);
    document.addEventListener('click', onClick, true);
    document.addEventListener('keydown', onKeydown, true);
})();
"""
        page.run_js(js)

    def pick_element_result(self) -> Optional[dict]:
        """
        读取页面上已拾取的元素选择器候选列表。
        有结果则清除并返回 {"selector": 首选, "selectors": [候选...]}，否则返回 None。
        """
        page = self._target()
        result = page.run_js("return window.__picked_selectors || null;")
        if result:
            page.run_js("window.__picked_selectors = null; window.__picked_selector = null;")
            selectors = [str(s) for s in result if s]
            if not selectors:
                return None
            return {"selector": selectors[0], "selectors": selectors}
        return None

    def close(self) -> None:
        """关闭浏览器"""
        if self._page is not None:
            self._page.quit()
            self._page = None
        self._active = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class ElementNotFoundError(Exception):
    """元素未找到异常"""
    pass


class PageLoadTimeoutError(Exception):
    """页面加载超时异常"""
    pass
