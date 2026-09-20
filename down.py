import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
import boto3
from botocore.config import Config
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ============================================================
# 設定
# ============================================================

SOURCE_PAGE = "http://47.96.230.2:5147/qqyx/downloadScript.html"
DOWNLOAD_API = "http://47.96.230.2:9997/version/getDownloUrl"

DOWNLOAD_DIR = Path.cwd() / "downloads"
APK_PATH = DOWNLOAD_DIR / "球球英雄脚本.apk"

# R2
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")

R2_BUCKET = "qqyx"
R2_OBJECT = "球球英雄脚本.apk"

R2_ENDPOINT = (
    f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    if R2_ACCOUNT_ID
    else None
)

# 等待瀏覽器下載的最長時間
DOWNLOAD_TIMEOUT = 180


# ============================================================
# HTTP Session
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
})


# ============================================================
# 檢查 R2 設定
# ============================================================

def check_r2_config():
    print("🔧 檢查 R2 設定...")

    missing = []

    if not R2_ACCOUNT_ID:
        missing.append("R2_ACCOUNT_ID")

    if not R2_ACCESS_KEY_ID:
        missing.append("R2_ACCESS_KEY_ID")

    if not R2_SECRET_ACCESS_KEY:
        missing.append("R2_SECRET_ACCESS_KEY")

    if missing:
        raise RuntimeError(
            "缺少 GitHub Secrets: " + ", ".join(missing)
        )

    print("✅ R2 Secrets 已設定")


# ============================================================
# 建立下載目錄
# ============================================================

def prepare_download_dir():
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # 清理舊 APK
    for file in DOWNLOAD_DIR.glob("*.apk"):
        try:
            file.unlink()
            print(f"🗑️ 清除舊 APK：{file}")
        except Exception as e:
            print(f"⚠️ 無法刪除舊檔案：{file} - {e}")


# ============================================================
# 取得入口頁面
# ============================================================

def get_source_page():
    print()
    print("=" * 60)
    print("① 請求 5147 入口頁面")
    print("=" * 60)

    print(f"URL: {SOURCE_PAGE}")

    response = session.get(
        SOURCE_PAGE,
        timeout=30,
        allow_redirects=True,
    )

    print(f"HTTP : {response.status_code}")
    print(f"Final: {response.url}")
    print(f"Type : {response.headers.get('Content-Type')}")
    print(f"Size : {len(response.content)} bytes")

    response.raise_for_status()

    return response.text


# ============================================================
# 從入口 HTML 找出 9997 API
# ============================================================

def find_download_api(html):
    print()
    print("=" * 60)
    print("② 尋找 9997 API")
    print("=" * 60)

    # 優先使用已知 API
    if "9997/version/getDownloUrl" in html:
        print(f"✅ 找到 API：{DOWNLOAD_API}")
        return DOWNLOAD_API

    # 嘗試尋找其他 XMLHttpRequest / fetch URL
    patterns = [
        r"""['"]([^'"]*9997[^'"]*)['"]""",
        r"""['"]([^'"]*getDownloUrl[^'"]*)['"]""",
        r"""['"]([^'"]*getDownloadUrl[^'"]*)['"]""",
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)

        if match:
            found = match.group(1)

            if found.startswith("http://") or found.startswith("https://"):
                api = found
            else:
                api = urljoin(SOURCE_PAGE, found)

            print(f"✅ 找到 API：{api}")
            return api

    print("⚠️ HTML 中沒有直接找到 API")
    print(f"➡️ 使用已知 API：{DOWNLOAD_API}")

    return DOWNLOAD_API


# ============================================================
# 請求 9997
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
    print(f"Type : {response.headers.get('Content-Type')}")

    response.raise_for_status()

    text = response.text.strip()

    print(f"Response length: {len(text)}")

    if not text:
        raise RuntimeError("9997 API 回傳空內容")

    # 有些 API 可能會把 URL 包在 JSON / 引號裡
    text = text.strip("\"' \r\n\t")

    # 直接找 http/https URL
    urls = re.findall(
        r'https?://[^\s"\'<>]+',
        text
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
            f"9997 回傳內容不像 URL：\n{download_url[:500]}"
        )

    print()
    print("✅ 取得下載 URL")
    print(download_url)

    return download_url


# ============================================================
# 設定 Playwright 下載監聽
# ============================================================

def attach_download_listener(context, state):
    def handle_page(page):
        print(f"🌐 新頁面：{page.url}")

        def handle_download(download):
            print()
            print("🎉 偵測到瀏覽器下載！")
            print(f"檔名：{download.suggested_filename}")

            state["download"] = download

        page.on("download", handle_download)

    context.on("page", handle_page)


# ============================================================
# Playwright 正常開啟下載頁面
# ============================================================

def browser_download(download_url):
    print()
    print("=" * 60)
    print("④ 啟動 Chromium")
    print("=" * 60)

    state = {
        "download": None
    }

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            accept_downloads=True,
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        attach_download_listener(context, state)

        page = context.new_page()

        # 目前這個 page 也需要監聽 download
        def handle_download(download):
            print()
            print("🎉 偵測到瀏覽器下載！")
            print(f"檔名：{download.suggested_filename}")

            state["download"] = download

        page.on("download", handle_download)

        print()
        print("🌐 開啟：")
        print(download_url)

        try:
            page.goto(
                download_url,
                wait_until="domcontentloaded",
                timeout=60000,
            )
        except PlaywrightTimeoutError:
            print("⚠️ 頁面載入超時，繼續等待下載...")
        except Exception as e:
            print(f"⚠️ page.goto 發生錯誤：{e}")

        print()
print()
print("目前頁面：")
print(page.url)

# ----------------------------------------------------
# 找到「驗證並下載」按鈕
# ----------------------------------------------------

print()
print("🔎 尋找「验证并下载」按鈕...")

try:
    button = page.locator("#sub")

    button.wait_for(
        state="visible",
        timeout=30000
    )

    print("✅ 找到驗證並下載按鈕")

    # 取得按鈕附近的文字
    try:
        print(
            "按鈕文字：",
            button.inner_text()
        )
    except Exception:
        pass

    print("🖱️ 正常點擊「验证并下载」...")

    button.click()

    print("✅ 已點擊")

except Exception as e:
    print(f"❌ 找不到或無法點擊驗證按鈕：{e}")

    try:
        html_path = Path.cwd() / "debug_button.html"
        screenshot_path = Path.cwd() / "debug_button.png"

        html_path.write_text(
            page.content(),
            encoding="utf-8"
        )

        page.screenshot(
            path=str(screenshot_path),
            full_page=True
        )

        print(f"📄 HTML：{html_path}")
        print(f"📸 Screenshot：{screenshot_path}")

    except Exception as debug_error:
        print(f"⚠️ 保存診斷資料失敗：{debug_error}")

    raise


# ----------------------------------------------------
# 等待網頁自己觸發下載
# ----------------------------------------------------

print()
print("⏳ 等待驗證完成並觸發下載...")

for i in range(DOWNLOAD_TIMEOUT):

    if state["download"] is not None:
        break

    if i % 10 == 0:
        print(
            f"⏳ 等待下載... "
            f"{i}/{DOWNLOAD_TIMEOUT} 秒"
        )

    try:
        page.wait_for_timeout(1000)
    except Exception:
        break

        # ----------------------------------------------------
        # 沒有下載
        # ----------------------------------------------------

        if state["download"] is None:

            print()
            print("❌ 等待時間內沒有偵測到 APK 下載")

            # 儲存診斷資訊
            try:
                html_path = Path.cwd() / "debug_page.html"
                screenshot_path = Path.cwd() / "debug_page.png"

                html_path.write_text(
                    page.content(),
                    encoding="utf-8",
                )

                page.screenshot(
                    path=str(screenshot_path),
                    full_page=True,
                )

                print(f"📄 HTML 已保存：{html_path}")
                print(f"📸 Screenshot 已保存：{screenshot_path}")

            except Exception as e:
                print(f"⚠️ 保存診斷資料失敗：{e}")

            print()
            print(
                "可能原因："
            )
            print(
                "1. 網頁仍在進行驗證"
            )
            print(
                "2. 網頁要求人工操作"
            )
            print(
                "3. 網頁沒有自動觸發下載"
            )

            browser.close()

            raise RuntimeError(
                "Chromium 沒有偵測到下載事件"
            )

        # ----------------------------------------------------
        # 保存下載
        # ----------------------------------------------------

        download = state["download"]

        print()
        print("💾 正在保存 APK...")

        download.save_as(str(APK_PATH))

        browser.close()

    # --------------------------------------------------------
    # 檢查 APK
    # --------------------------------------------------------

    if not APK_PATH.exists():
        raise RuntimeError(
            f"下載事件存在，但找不到 APK：{APK_PATH}"
        )

    size = APK_PATH.stat().st_size

    print()
    print(f"✅ APK 已下載")
    print(f"檔案：{APK_PATH}")
    print(f"大小：{size / 1024 / 1024:.2f} MB")

    if size < 100 * 1024:
        print("⚠️ APK 小於 100 KB，可能不是完整 APK")

    # APK 本質上是 ZIP
    with open(APK_PATH, "rb") as f:
        magic = f.read(4)

    if magic != b"PK\x03\x04":
        print()
        print(
            f"⚠️ 檔案不是標準 ZIP/APK Magic：{magic!r}"
        )

        raise RuntimeError(
            "下載到的檔案不是有效 APK"
        )

    print("✅ APK Magic 正確")

    return APK_PATH


# ============================================================
# 上傳 R2
# ============================================================

def upload_to_r2(apk_path):
    print()
    print("=" * 60)
    print("⑤ 上傳 Cloudflare R2")
    print("=" * 60)

    print(f"Bucket : {R2_BUCKET}")
    print(f"Object : {R2_OBJECT}")
    print(f"File   : {apk_path}")

    s3 = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(
            signature_version="s3v4"
        ),
    )

    s3.upload_file(
        str(apk_path),
        R2_BUCKET,
        R2_OBJECT,
        ExtraArgs={
            "ContentType": (
                "application/vnd.android.package-archive"
            )
        },
    )

    print()
    print("🎉 R2 上傳成功！")
    print()
    print(
        f"R2：{R2_BUCKET}/{R2_OBJECT}"
    )


# ============================================================
# 清理 APK
# ============================================================

def cleanup():
    print()
    print("=" * 60)
    print("⑥ 清理本地檔案")
    print("=" * 60)

    # 刪除主要 APK
    if APK_PATH.exists():
        try:
            APK_PATH.unlink()
            print(f"🗑️ 已刪除：{APK_PATH}")
        except Exception as e:
            print(
                f"⚠️ 刪除 APK 失敗：{e}"
            )
    else:
        print("ℹ️ 沒有需要刪除的 APK")

    # 清理其他可能殘留 APK
    if DOWNLOAD_DIR.exists():

        for file in DOWNLOAD_DIR.glob("*.apk"):
            try:
                file.unlink()
                print(f"🗑️ 已刪除：{file}")
            except Exception as e:
                print(
                    f"⚠️ 無法刪除：{file} - {e}"
                )


# ============================================================
# 主程式
# ============================================================

def main():

    print()
    print("=" * 60)
    print("🚀 QQYX APK 自動同步")
    print("=" * 60)

    success = False

    try:

        # ----------------------------------------------------
        # 1. 檢查 R2
        # ----------------------------------------------------

        check_r2_config()

        # ----------------------------------------------------
        # 2. 建立下載目錄
        # ----------------------------------------------------

        prepare_download_dir()

        # ----------------------------------------------------
        # 3. 取得 5147 頁面
        # ----------------------------------------------------

        html = get_source_page()

        # ----------------------------------------------------
        # 4. 找 9997 API
        # ----------------------------------------------------

        api_url = find_download_api(html)

        # ----------------------------------------------------
        # 5. 取得最新 dmpdmp URL
        # ----------------------------------------------------

        download_url = get_lanzou_url(api_url)

        # ----------------------------------------------------
        # 6. Chromium 正常開啟
        # ----------------------------------------------------

        apk_path = browser_download(download_url)

        # ----------------------------------------------------
        # 7. 上傳 R2
        # ----------------------------------------------------

        upload_to_r2(apk_path)

        success = True

        print()
        print("=" * 60)
        print("🎉 全部完成")
        print("=" * 60)

    except Exception as e:

        print()
        print("=" * 60)
        print("❌ 執行失敗")
        print("=" * 60)

        print(
            f"{type(e).__name__}: {e}"
        )

        # 讓 GitHub Actions 最後顯示失敗
        sys.exit(1)

    finally:

        # ----------------------------------------------------
        # 無論成功或失敗，都清理 APK
        # ----------------------------------------------------

        cleanup()

        print()

        if success:
            print("✅ 任務完成")
        else:
            print("⚠️ 任務失敗，但已執行清理")


# ============================================================
# 程式入口
# ============================================================

if __name__ == "__main__":
    main()
