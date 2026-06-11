from DrissionPage import ChromiumPage, ChromiumOptions
try:
    opts = ChromiumOptions()
    opts.set_browser_path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    # Setting an auto port or setting headless to avoid conflicting with an active UI Chrome
    opts.auto_port() 
    page = ChromiumPage(addr_or_opts=opts)
    page.get("https://www.baidu.com")
    print("Success:", page.title)
    page.quit()
except Exception as e:
    print("Error:", repr(e))
