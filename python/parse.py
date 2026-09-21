import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

# ============================================================
# 解析 / 驗證設定
# ============================================================

SOURCE_PAGE = (
    "http://47.96.230.2:5147/qqyx/downloadScript.html"
)

KNOWN_DOWNLOAD_API = (
    "http://47.96.230.2:9997/version/getDownloUrl"
)

BROWSER_RETRIES = 10
PAGE_LOAD_TIMEOUT = 20000
ELEMENT_TIMEOUT = 30000

OUTPUT_FILE = Path.cwd() / "apk_url.txt"

session = requests.Session()

# ============================================================
# 取得 5147 入口頁
# ============================================================

def get_source_page():

    print()
    print("=" * 60)
    print("① 請求 5147 入口頁面")
    print("=" * 60)

    print(f"URL: {SOURCE_PAGE}")

    response = session.get(
        SOURCE_PAGE,
        timeout=20,
        allow_redirects=True,
    )

    print(f"HTTP : {response.status_code}")
    print(f"Final: {response.url}")
    print(
        "Type : "
        f"{response.headers.get('Content-Type')}"
    )
    print(
        f"Size : {len(response.content)} bytes"
    )

    response.raise_for_status()

    return response.text


# ============================================================
# 找到 9997 API
# ============================================================

def find_download_api(html):

    print()
    print("=" * 60)
    print("② 尋找 9997 API")
    print("=" * 60)

    if "9997/version/getDownloUrl" in html:

        print(
            "✅ 找到 API："
            f"{KNOWN_DOWNLOAD_API}"
        )

        return KNOWN_DOWNLOAD_API

    patterns = [
        r"""['"]([^'"]*9997[^'"]*)['"]""",
        r"""['"]([^'"]*getDownloUrl[^'"]*)['"]""",
        r"""['"]([^'"]*getDownloadUrl[^'"]*)['"]""",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.IGNORECASE,
        )

        if not match:
            continue

        found = match.group(1)

        if (
            found.startswith("http://")
            or found.startswith("https://")
        ):
            api_url = found
        else:
            api_url = urljoin(
                SOURCE_PAGE,
                found,
            )

        print(
            "✅ 找到 API："
            f"{api_url}"
        )

        return api_url

    print("⚠️ HTML 中沒有找到 API")
    print(
        "➡️ 使用已知 API："
        f"{KNOWN_DOWNLOAD_API}"
    )

    return KNOWN_DOWNLOAD_API


# ============================================================
# 取得 dmpdmp URL
# ============================================================

def get_lanzou_url(api_url):

    print()
    print("=" * 60)
    print("③ 請求 9997 取得最新下載 URL")
    print("=" * 60)

    print(f"URL: {api_url}")

    response = session.get(
        api_url,
        timeout=30,
        allow_redirects=True,
    )

    print(f"HTTP : {response.status_code}")
    print(f"Final: {response.url}")
    print(
        "Type : "
        f"{response.headers.get('Content-Type')}"
    )

    response.raise_for_status()

    text = response.text.strip()

    print(
        f"Response length: {len(text)}"
    )

    if not text:
        raise RuntimeError(
            "9997 API 回傳空內容"
        )

    text = text.strip(
        "\"' \r\n\t"
    )

    urls = re.findall(
        r'https?://[^\s"\'<>]+',
        text,
    )

    if urls:
        download_url = urls[0]
    else:
        download_url = text

    if not (
        download_url.startswith("http://")
        or download_url.startswith("https://")
    ):
        raise RuntimeError(
            "9997 回傳內容不像 URL：\n"
            + download_url[:500]
        )

    print()
    print("✅ 成功取得下載 URL")

    try:
        print(
            "🌐 網域："
            f"{download_url.split('/')[2]}"
        )
    except Exception:
        pass

    return download_url

# ============================================================
# 從頁面取得 APK URL
# ============================================================

def get_apk_href(page):

    print()
    print("=" * 60)
    print("⑥ 等待「立即下载」")
    print("=" * 60)

    go_link = page.locator("#go a")

    go_link.wait_for(
        state="visible",
        timeout=ELEMENT_TIMEOUT,
    )

    print("✅ 驗證成功！")
    print("✅ 找到「立即下载」連結")

    href = go_link.get_attribute(
        "href"
    )

    if not href:
        raise RuntimeError(
            "「立即下载」沒有 href"
        )

    href = urljoin(
        page.url,
        href,
    )

    print()
    print("✅ 已取得 APK 下載連結")

    try:
        print(
            "🌐 APK 網域："
            f"{href.split('/')[2]}"
        )
    except Exception:
        pass

    print(
        "🔗 APK URL："
        f"{href[:200]}"
    )

    return href

# ============================================================
# Chromium 正常驗證
# ============================================================

def save_page_debug(page, attempt, stage):
    """保存目前 Chromium 頁面的 HTML、URL 與截圖，方便 GitHub Actions 診斷。"""
    debug_dir = Path.cwd() / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    prefix = debug_dir / f"dmpdmp_{attempt}_{stage}"

    try:
        (prefix.with_suffix(".txt")).write_text(
            f"URL: {page.url}\n"
            f"TITLE: {page.title()}\n",
            encoding="utf-8",
        )
    except Exception:
        pass

    try:
        (prefix.with_suffix(".html")).write_text(
            page.content(),
            encoding="utf-8",
        )
    except Exception:
        pass

    try:
        page.screenshot(
            path=str(prefix.with_suffix(".png")),
            full_page=True,
            timeout=15000,
        )
    except Exception:
        pass


def find_working_page(context, preferred_page=None):
    """
    在目前 BrowserContext 中尋找真正的下載頁。
    優先尋找包含 #sub 或 #go a 的頁面。
    避免把 about:blank 當成下載頁。
    """

    pages = list(context.pages)

    # 先找真正已經出現下載 DOM 的頁面。
    for candidate in pages:
        try:
            if (
                candidate.locator("#go a").count() > 0
                or candidate.locator("#sub").count() > 0
            ):
                return candidate
        except Exception:
            continue

    # 再找非 about:blank 的頁面。
    for candidate in pages:
        try:
            if candidate.url and candidate.url != "about:blank":
                return candidate
        except Exception:
            continue

    # 最後才回傳原本的 page，讓呼叫端決定是否失敗。
    return preferred_page


def wait_for_download_page(context, page, timeout=30000):
    """
    等待 dmpdmp 頁面真正可用。
    會同時檢查 context 中新開出的分頁。
    """

    deadline = time.monotonic() + (timeout / 1000)

    while time.monotonic() < deadline:

        candidate = find_working_page(
            context,
            preferred_page=page,
        )

        if candidate is not None:
            try:
                # #sub 出現代表驗證頁已經載入。
                if candidate.locator("#sub").count() > 0:
                    candidate.locator("#sub").wait_for(
                        state="visible",
                        timeout=10000,
                    )
                    return candidate

                # #go a 出現代表甚至已經完成驗證。
                if candidate.locator("#go a").count() > 0:
                    return candidate
            except Exception:
                pass

        time.sleep(0.5)

    return None


def get_verified_apk_url(download_url):

    print()
    print("=" * 60)
    print("④ 啟動 Chromium")
    print("=" * 60)

    with sync_playwright() as p:

        print("🚀 啟動 Chromium...")

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            accept_downloads=True,
            viewport={
                "width": 1280,
                "height": 900,
            },
            locale="zh-TW",
            timezone_id="Asia/Taipei",
        )

        for attempt in range(
            1,
            BROWSER_RETRIES + 1,
        ):

            page = context.new_page()

            print()
            print("=" * 60)
            print(
                f"🌐 dmpdmp 第 "
                f"{attempt}/{BROWSER_RETRIES} 次嘗試"
            )
            print("=" * 60)

            try:

                print("🌐 開啟下載頁面...")

                goto_timed_out = False

                try:
                    response = page.goto(
                        download_url,
                        wait_until="commit",
                        timeout=15000,
                    )

                    if response:
                        print(
                            f"HTTP：{response.status}"
                        )

                except PlaywrightTimeoutError:
                    goto_timed_out = True
                    print(
                        "⚠️ page.goto 等待超時，"
                        "繼續檢查 BrowserContext 中的頁面..."
                    )

                # 給 redirect / popup / JS 一點時間完成。
                time.sleep(2)

                working_page = wait_for_download_page(
                    context,
                    page,
                    timeout=30000,
                )

                if working_page is None:
                    print()
                    print("❌ 找不到可用的 dmpdmp 頁面")

                    for index, candidate in enumerate(
                        context.pages,
                        start=1,
                    ):
                        try:
                            print(
                                f"📄 Page {index}: "
                                f"{candidate.url}"
                            )
                        except Exception:
                            pass

                    save_page_debug(
                        page,
                        attempt,
                        "no_working_page",
                    )

                    raise RuntimeError(
                        "dmpdmp 頁面沒有正常載入；"
                        "BrowserContext 中沒有找到 #sub 或 #go a"
                    )

                page = working_page

                print()
                print("目前頁面：")
                print(page.url)

                if goto_timed_out:
                    print(
                        "ℹ️ 原始 goto 曾超時，"
                        "但已找到實際可用頁面。"
                    )

                # 明確禁止把 about:blank 當成正常下載頁。
                if page.url == "about:blank":
                    if page.locator("#sub").count() == 0:
                        save_page_debug(
                            page,
                            attempt,
                            "about_blank",
                        )

                        raise RuntimeError(
                            "目前仍是 about:blank，"
                            "且沒有 #sub"
                        )

                    print(
                        "⚠️ URL 仍為 about:blank，"
                        "但頁面內已有 #sub；"
                        "繼續檢查 DOM。"
                    )

                print()
                print("=" * 60)
                print("⑤ 等待「验证并下载」")
                print("=" * 60)

                sub_button = page.locator(
                    "#sub"
                )

                # 如果驗證連結已經直接出現，就不用再次點擊。
                if page.locator("#go a").count() > 0:
                    print(
                        "✅ 已經找到「立即下载」，"
                        "跳過「验证并下载」"
                    )
                else:
                    sub_button.wait_for(
                        state="visible",
                        timeout=ELEMENT_TIMEOUT,
                    )

                    print(
                        "✅ 找到「验证并下载」"
                    )

                    try:
                        print(
                            "按鈕文字："
                            f"{sub_button.inner_text()}"
                        )
                    except Exception:
                        pass

                    print()
                    print(
                        "🖱️ 點擊「验证并下载」..."
                    )

                    # 正常點擊網站自己的驗證按鈕。
                    sub_button.click(
                        no_wait_after=True
                    )

                    print(
                        "✅ 已點擊"
                        "「验证并下载」"
                    )

                print()
                print("=" * 60)
                print("⑥ 等待「立即下载」")
                print("=" * 60)

                # 點擊後可能同頁更新，也可能開新分頁。
                deadline = time.monotonic() + (
                    ELEMENT_TIMEOUT / 1000
                )

                apk_page = None

                while time.monotonic() < deadline:

                    for candidate in context.pages:

                        try:
                            link = candidate.locator(
                                "#go a"
                            )

                            if link.count() > 0:
                                link.wait_for(
                                    state="visible",
                                    timeout=1000,
                                )

                                apk_page = candidate
                                break

                        except Exception:
                            continue

                    if apk_page is not None:
                        break

                    time.sleep(0.5)

                if apk_page is None:
                    print()
                    print(
                        "❌ 30 秒內沒有出現 "
                        "#go a"
                    )

                    print()
                    print("目前所有 Page：")

                    for index, candidate in enumerate(
                        context.pages,
                        start=1,
                    ):
                        try:
                            print(
                                f"📄 Page {index}: "
                                f"{candidate.url}"
                            )
                        except Exception:
                            pass

                    # 保存每個目前分頁的診斷資料。
                    for index, candidate in enumerate(
                        context.pages,
                        start=1,
                    ):
                        try:
                            save_page_debug(
                                candidate,
                                attempt,
                                f"after_click_{index}",
                            )
                        except Exception:
                            pass

                    raise RuntimeError(
                        "點擊「验证并下载」後，"
                        "沒有出現「立即下载」(#go a)"
                    )

                page = apk_page

                print(
                    "✅ 找到「立即下载」所在頁面"
                )

                apk_url = get_apk_href(
                    page
                )

                browser.close()

                return apk_url

            except Exception as e:

                print()
                print(
                    f"❌ 第 {attempt} 次失敗"
                )

                print(
                    f"{type(e).__name__}: {e}"
                )

                # 額外列出所有分頁狀態。
                print()
                print("📄 Browser Pages：")

                for index, candidate in enumerate(
                    context.pages,
                    start=1,
                ):
                    try:
                        print(
                            f"  Page {index}: "
                            f"{candidate.url}"
                        )
                    except Exception:
                        pass

                if attempt < BROWSER_RETRIES:

                    print()
                    print(
                        "⏳ 5 秒後重新建立 Chromium Page..."
                    )

                    time.sleep(5)

                    # 關閉本次所有分頁，
                    # 下一輪重新建立乾淨 page。
                    for candidate in list(
                        context.pages
                    ):
                        try:
                            candidate.close()
                        except Exception:
                            pass

                else:

                    browser.close()

                    raise



# ============================================================
# Main
# ============================================================

def main():
    print()
    print("=" * 60)
    print("🔎 QQYX APK URL 解析 / 驗證")
    print("=" * 60)

    html = get_source_page()
    api_url = find_download_api(html)
    download_url = get_lanzou_url(api_url)
    apk_url = get_verified_apk_url(download_url)

    OUTPUT_FILE.write_text(apk_url.strip(), encoding="utf-8")

    print()
    print("=" * 60)
    print("🎉 解析完成")
    print("=" * 60)
    print(f"📄 URL 已寫入：{OUTPUT_FILE}")

if __name__ == "__main__":
    main()
