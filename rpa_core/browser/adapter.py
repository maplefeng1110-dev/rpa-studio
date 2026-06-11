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
    
    def __init__(self, headless: bool = False):
        """
        初始化浏览器适配器
        
        Args:
            headless: 是否使用无头模式
        """
        self._page: Optional[ChromiumPage] = None
        self._headless = headless
    
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
            page = self._ensure_page()
            page.get(url, timeout=timeout)
        except Exception as e:
            raise PageLoadTimeoutError(f"页面加载超时或失败: {url}, 错误: {str(e)}")
    
    def _find_element(
        self,
        selector: Union[str, List[str]],
        timeout: int = 10,
    ) -> Tuple[object, str, int]:
        """
        按候选选择器顺序定位元素，实现「选择器自愈」：
        依次尝试每个候选，命中即返回。若主选择器（第 0 个）失效而靠后续候选命中，
        会打 warning 日志作为页面漂移的信号。

        Args:
            selector: 单个选择器或候选选择器列表（按优先级排序）
            timeout: 首选选择器的超时时间；后续候选用较短超时避免叠加等待

        Returns:
            (元素, 命中的原始选择器, 命中候选的下标)

        Raises:
            ElementNotFoundError: 所有候选都未命中
        """
        candidates = _as_candidates(selector)
        if not candidates:
            raise ElementNotFoundError("未提供任何选择器")

        page = self._ensure_page()
        last_error: Optional[str] = None

        for idx, raw in enumerate(candidates):
            normalized = normalize_selector(raw)
            # 首选用完整 timeout，后备候选用较短超时（最多 3s）
            attempt_timeout = timeout if idx == 0 else min(timeout, 3)
            try:
                element = page.ele(normalized, timeout=attempt_timeout)
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

    def click(self, selector: Union[str, List[str]], timeout: int = 10) -> str:
        """
        点击元素。selector 可为单个选择器或候选列表（自愈回退）。

        Returns:
            实际命中的选择器
        """
        element, used, _ = self._find_element(selector, timeout=timeout)
        try:
            element.click()
        except Exception as e:
            raise ElementNotFoundError(f"点击元素失败: {used}, 错误: {str(e)}")
        return used

    def input(self, selector: Union[str, List[str]], text: str, timeout: int = 10, clear: bool = True) -> str:
        """
        输入文本。selector 可为单个选择器或候选列表（自愈回退）。

        Returns:
            实际命中的选择器
        """
        element, used, _ = self._find_element(selector, timeout=timeout)
        try:
            if clear:
                element.clear()
            element.input(text)
        except Exception as e:
            raise ElementNotFoundError(f"输入文本失败: {used}, 错误: {str(e)}")
        return used

    def exists(self, selector: Union[str, List[str]], timeout: int = 3) -> bool:
        """判断元素是否存在（任一候选命中即为存在）。"""
        try:
            self._find_element(selector, timeout=timeout)
            return True
        except ElementNotFoundError:
            return False

    def text(self, selector: Union[str, List[str]], timeout: int = 10) -> str:
        """
        获取元素文本内容。selector 可为单个选择器或候选列表（自愈回退）。
        """
        element, used, _ = self._find_element(selector, timeout=timeout)
        try:
            return element.text
        except Exception as e:
            raise ElementNotFoundError(f"获取元素文本失败: {used}, 错误: {str(e)}")
    
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
        page = self._ensure_page()
        page.get_screenshot(path=path)
    
    def pick_element_start(self) -> None:
        """
        向当前页面注入 JS，进入元素拾取模式。
        鼠标悬停会高亮元素，点击后将 CSS 选择器写入 window.__picked_selector。
        """
        page = self._ensure_page()
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
        page = self._ensure_page()
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
