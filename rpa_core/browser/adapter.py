"""
Browser Adapter 模块
封装浏览器操作能力，隔离 RPA 内核与 DrissionPage 实现
任何上层模块禁止直接使用 DrissionPage API
"""
import time
from typing import Optional
from DrissionPage import ChromiumPage, ChromiumOptions


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
    
    def click(self, selector: str, timeout: int = 10) -> None:
        """
        点击元素
        
        Args:
            selector: 元素选择器
            timeout: 超时时间（秒）
        """
        try:
            page = self._ensure_page()
            element = page.ele(selector, timeout=timeout)
            if element is None:
                raise ElementNotFoundError(f"元素未找到: {selector}")
            element.click()
        except Exception as e:
            if isinstance(e, ElementNotFoundError):
                raise
            raise ElementNotFoundError(f"点击元素失败: {selector}, 错误: {str(e)}")
    
    def input(self, selector: str, text: str, timeout: int = 10, clear: bool = True) -> None:
        """
        输入文本
        
        Args:
            selector: 元素选择器
            text: 要输入的文本
            timeout: 超时时间（秒）
            clear: 是否先清空输入框
        """
        try:
            page = self._ensure_page()
            element = page.ele(selector, timeout=timeout)
            if element is None:
                raise ElementNotFoundError(f"元素未找到: {selector}")
            if clear:
                element.clear()
            element.input(text)
        except Exception as e:
            if isinstance(e, ElementNotFoundError):
                raise
            raise ElementNotFoundError(f"输入文本失败: {selector}, 错误: {str(e)}")
    
    def exists(self, selector: str, timeout: int = 3) -> bool:
        """
        判断元素是否存在
        
        Args:
            selector: 元素选择器
            timeout: 超时时间（秒）
        
        Returns:
            元素是否存在
        """
        try:
            page = self._ensure_page()
            element = page.ele(selector, timeout=timeout)
            return element is not None
        except Exception:
            return False
    
    def text(self, selector: str, timeout: int = 10) -> str:
        """
        获取元素文本内容
        
        Args:
            selector: 元素选择器
            timeout: 超时时间（秒）
        
        Returns:
            元素的文本内容
        """
        try:
            page = self._ensure_page()
            element = page.ele(selector, timeout=timeout)
            if element is None:
                raise ElementNotFoundError(f"元素未找到: {selector}")
            return element.text
        except Exception as e:
            if isinstance(e, ElementNotFoundError):
                raise
            raise ElementNotFoundError(f"获取元素文本失败: {selector}, 错误: {str(e)}")
    
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

    function getCssSelector(el) {
        if (!el || el === document.body) return 'body';
        if (el.id) return '#' + CSS.escape(el.id);
        var parts = [];
        while (el && el !== document.body) {
            var seg = el.tagName.toLowerCase();
            if (el.id) { seg = '#' + CSS.escape(el.id); parts.unshift(seg); break; }
            if (el.className) {
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

    function onMouseOver(e) {
        if (lastEl) lastEl.style.outline = '';
        lastEl = e.target;
        lastEl.style.outline = '2px solid #ef4444';
    }

    function onClick(e) {
        e.preventDefault();
        e.stopPropagation();
        var sel = getCssSelector(e.target);
        window.__picked_selector = sel;
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

    def pick_element_result(self) -> Optional[str]:
        """
        读取页面上已拾取的元素选择器。
        有结果则清除并返回选择器字符串，否则返回 None。
        """
        page = self._ensure_page()
        result = page.run_js("return window.__picked_selector || null;")
        if result:
            page.run_js("window.__picked_selector = null;")
            return str(result)
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
