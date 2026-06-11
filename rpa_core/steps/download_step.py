"""
Download Step 模块
设置下载目录，点击触发下载的元素，并等待下载完成。
"""
from typing import Any, Dict

from .base import BaseStep, StepResult, StepError
from ..browser import BrowserAdapter, ElementNotFoundError
from ..utils import RuntimeContext, safe_output_path


class DownloadStep(BaseStep):
    """
    文件下载 Step
    - selector / selectors: 触发下载的元素（如下载按钮/链接）
    - save_path: 下载目录（受输出沙箱约束），默认 downloads
    - frame: 可选 iframe
    - timeout: 等待下载完成的超时（秒）
    """

    step_type = "download"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.save_path = config.get("save_path", "downloads")

    def execute(self, browser: BrowserAdapter, context: RuntimeContext) -> StepResult:
        candidates = self._candidate_selectors(context)
        save_path = self._render_value(self.save_path, context) or "downloads"

        if not candidates:
            raise StepError(self.step_type, "selector 不能为空（触发下载的元素）")

        try:
            download_dir = safe_output_path(save_path)
        except ValueError as e:
            raise StepError(self.step_type, str(e))

        try:
            download_dir.mkdir(parents=True, exist_ok=True)
            browser.set_download_path(str(download_dir))
            used = browser.click(candidates, timeout=self.timeout, frame=self.frame)
            done = browser.wait_download(timeout=self.timeout)
            if not done:
                raise StepError(self.step_type, f"下载未在 {self.timeout}s 内完成")
            return StepResult(
                success=True,
                message=f"下载完成，保存目录: {download_dir}",
                data={"download_dir": str(download_dir)}
            )
        except StepError:
            raise
        except ElementNotFoundError as e:
            raise StepError(self.step_type, str(e))
        except Exception as e:
            raise StepError(self.step_type, f"下载失败: {candidates}, 错误: {str(e)}")
