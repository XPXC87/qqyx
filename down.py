import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
import boto3
from botocore.config import Config
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)


# ============================================================
# 基本設定
# ============================================================

SOURCE_PAGE = (
    "http://47.96.230.2:5147/qqyx/downloadScript.html"
)

KNOWN_DOWNLOAD_API = (
    "http://47.96.230.2:9997/version/getDownloUrl"
)

# 本地暫存目錄
DOWNLOAD_DIR = Path.cwd() / "downloads"

# 本地 APK 名稱
APK_PATH = DOWNLOAD_DIR / "球球英雄脚本.apk"

# 等待真正 APK 下載的最長時間
DOWNLOAD_TIMEOUT = 180


# ============================================================
# Cloudflare R2
# ============================================================

# 從 GitHub Secrets 取得
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")

# ★ 你指定的 R2 Bucket
R2_BUCKET = "qqyx"

# ★ 你指定的 R2 Object
R2_OBJECT = "球球英雄脚本.apk"

if R2_ACCOUNT_ID:
    R2_ENDPOINT = (
        f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    )
else:
    R2_ENDPOINT = None


# ============================================================
# HTTP Session
# ============================================================

session = requests.Session()

session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/124.0.0.0 "
            "Safari/537.36"
        ),
        "Accept": "*/*",
    }
)


# ============================================================
# 檢查 R2 設定
# ============================================================

def check_r2_config():
    print()
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
            "缺少 GitHub Secrets: "
            + ", ".join(missing)
        )

    print("✅ R2 Secrets 已設定")
    print(f"🪣 Bucket：{R2_BUCKET}")
    print(f"📄 Object：{R2_OBJECT}")


# ============================================================
# 建立下載目錄
# ============================================================

def prepare_download_dir():
    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # 清理舊 APK
    for file in DOWNLOAD_DIR.glob("*.apk"):
        try:
            file.unlink()
            print(
                f"🗑️ 清除舊 APK：{file}"
            )
        except Exception as e:
            print(
                f"⚠️ 無法刪除舊 APK："
                f"{file} - {e}"
            )


# ============================================================
# 取得 5147 入口頁面
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

    print(
        f"HTTP : {response.status_code}"
    )

    print(
        f"Final: {response.url}"
    )

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
# 從 HTML 找 9997 API
# ============================================================

def find_download_api(html):
    print()
    print("=" * 60)
    print("② 尋找 9997 API")
    print("=" * 60)

    # 已知 API
    if "9997/version/getDownloUrl" in html:
        print(
            f"✅ 找到 API："
            f"{KNOWN_DOWNLOAD_API}"
        )

        return KNOWN_DOWNLOAD_API

    # 備用搜尋
    patterns = [
        r"""['"]([^'"]*9997[^'"]*)['"]""",
        r"""['"]([^'"]*getDownloUrl[^'"]*)['"]""",
        r"""['"]([^'"]*getDownloadUrl[^'"]*)['"]""",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.IGNORECASE
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
                found
            )

        print(
            f"✅ 找到 API：{api_url}"
        )

        return api_url

    print(
        "⚠️ HTML 中沒有找到 API"
    )

    print(
        f"➡️ 使用已知 API："
        f"{KNOWN_DOWNLOAD_API}"
    )

    return KNOWN_DOWNLOAD_API


# ============================================================
# 請求 9997
# ============================================================

def get_lanzou_url(api_url):
    print()
    print("=" * 60)
    print("③ 請求 9997 取得最新下載 URL")
    print("=" * 60)

    print(
        f"URL: {api_url}"
    )

    response = session.get(
        api_url,
        timeout=30,
        allow_redirects=True,
    )

    print(
        f"HTTP : {response.status_code}"
    )

    print(
        f"Final: {response.url}"
    )

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

    # 去除可能的引號
    text = text.strip(
        "\"' \r\n\t"
    )

    # 嘗試找 URL
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
            "9997 回傳內容不像 URL：\n"
            + download_url[:500]
        )

    print()
    print("✅ 成功取得下載 URL")
    print(download_url)

    return download_url


# ============================================================
# 儲存瀏覽器診斷資料
# ============================================================

def save_debug(page, prefix):
    try:

        html_path = (
            Path.cwd()
            / f"{prefix}.html"
        )

        screenshot_path = (
            Path.cwd()
            / f"{prefix}.png"
        )

        html_path.write_text(
            page.content(),
            encoding="utf-8"
        )

        page.screenshot(
            path=str(screenshot_path),
            full_page=True
        )

        print(
            f"📄 HTML：{html_path}"
        )

        print(
            f"📸 Screenshot："
            f"{screenshot_path}"
        )

    except Exception as e:

        print(
            f"⚠️ 保存診斷資料失敗："
            f"{e}"
        )


# ============================================================
# Chromium 下載
# ============================================================

def browser_download(download_url):

    print()
    print("=" * 60)
    print("④ 啟動 Chromium")
    print("=" * 60)

    download_state = {
        "download": None
    }

    with sync_playwright() as p:

        print(
            "🚀 啟動 Chromium..."
        )

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            accept_downloads=True,
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/124.0.0.0 "
                "Safari/537.36"
            ),
        )

        page = context.new_page()

        # ----------------------------------------------------
        # 監聽下載事件
        # ----------------------------------------------------

        def handle_download(download):

            print()
            print(
                "🎉 偵測到瀏覽器下載！"
            )

            print(
                "檔名："
                f"{download.suggested_filename}"
            )

            download_state["download"] = (
                download
            )

        page.on(
            "download",
            handle_download
        )

        # ----------------------------------------------------
        # 開啟 dmpdmp
        # ----------------------------------------------------

        print()
        print(
            "🌐 開啟下載頁面："
        )

        print(
            download_url
        )

        try:

            page.goto(
                download_url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

        except PlaywrightTimeoutError:

            print(
                "⚠️ 頁面載入超時，"
                "繼續執行..."
            )

        except Exception as e:

            print(
                f"⚠️ page.goto 發生錯誤："
                f"{e}"
            )

        print()
        print(
            "目前頁面："
        )

        print(
            page.url
        )

        # ====================================================
        # 第一階段
        # 「验证并下载」
        # ====================================================

        print()
        print("=" * 60)
        print("⑤ 等待「验证并下载」")
        print("=" * 60)

        try:

            sub_button = page.locator(
                "#sub"
            )

            sub_button.wait_for(
                state="visible",
                timeout=30000
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

            sub_button.click()

            print(
                "✅ 已點擊「验证并下载」"
            )

        except Exception as e:

            print()
            print(
                "❌ 無法點擊"
                "「验证并下载」"
            )

            print(
                f"原因：{e}"
            )

            save_debug(
                page,
                "debug_sub"
            )

            browser.close()

            raise

        # ====================================================
        # 第二階段
        # 等待「立即下载」
        # ====================================================

        print()
        print("=" * 60)
        print("⑥ 等待「立即下载」")
        print("=" * 60)

        try:

            go_button = page.locator(
                "#go"
            )

            # 驗證完成後 #go 才會出現
            go_button.wait_for(
                state="visible",
                timeout=60000
            )

            print(
                "✅ 驗證成功！"
            )

            print(
                "✅ 找到「立即下载」"
            )

            # 顯示按鈕文字
            try:

                print(
                    "按鈕文字："
                    f"{go_button.inner_text()}"
                )

            except Exception:
                pass

            # 顯示 href
            try:

                href = page.locator(
                    "#go a"
                ).get_attribute(
                    "href"
                )

                print(
                    f"目前 href：{href}"
                )

            except Exception:
                pass

            # ------------------------------------------------
            # 點擊「立即下载」
            # ------------------------------------------------

            print()
            print(
                "🖱️ 點擊「立即下载」..."
            )

            go_button.click()

            print(
                "✅ 已點擊「立即下载」"
            )

        except Exception as e:

            print()
            print(
                "❌ 驗證後沒有出現"
                "「立即下载」"
            )

            print(
                f"原因：{e}"
            )

            print()
            print(
                "目前頁面："
            )

            print(
                page.url
            )

            save_debug(
                page,
                "debug_no_go"
            )

            browser.close()

            raise

        # ====================================================
        # 第三階段
        # 等待真正 APK 下載
        # ====================================================

        print()
        print("=" * 60)
        print("⑦ 等待 APK 下載")
        print("=" * 60)

        for i in range(
            DOWNLOAD_TIMEOUT
        ):

            if (
                download_state["download"]
                is not None
            ):
                break

            if i % 5 == 0:

                print(
                    "⏳ 等待 APK 下載..."
                    f" {i}/{DOWNLOAD_TIMEOUT} 秒"
                )

            try:

                page.wait_for_timeout(
                    1000
                )

            except Exception:

                break

        # ----------------------------------------------------
        # 沒有下載
        # ----------------------------------------------------

        if (
            download_state["download"]
            is None
        ):

            print()
            print(
                "❌ 點擊「立即下载」後"
            )

            print(
                "❌ 沒有偵測到 APK 下載"
            )

            print()
            print(
                "目前頁面："
            )

            print(
                page.url
            )

            save_debug(
                page,
                "debug_no_download"
            )

            browser.close()

            raise RuntimeError(
                "沒有偵測到 APK 下載事件"
            )

        # ====================================================
        # 保存 APK
        # ====================================================

        download = (
            download_state["download"]
        )

        print()
        print(
            "💾 正在保存 APK..."
        )

        DOWNLOAD_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        download.save_as(
            str(APK_PATH)
        )

        print()
        print(
            f"✅ APK 已保存："
            f"{APK_PATH}"
        )

        browser.close()

    # ========================================================
    # 檢查 APK 是否存在
    # ========================================================

    if not APK_PATH.exists():

        raise RuntimeError(
            "下載事件存在，"
            "但找不到 APK："
            + str(APK_PATH)
        )

    file_size = (
        APK_PATH.stat().st_size
    )

    print()
    print(
        f"📦 APK 大小："
        f"{file_size / 1024 / 1024:.2f} MB"
    )

    if file_size == 0:

        raise RuntimeError(
            "APK 檔案大小為 0"
        )

    # ========================================================
    # 驗證 APK Magic
    # ========================================================

    with open(
        APK_PATH,
        "rb"
    ) as f:

        magic = f.read(4)

    print(
        f"APK Magic：{magic!r}"
    )

    if magic != b"PK\x03\x04":

        raise RuntimeError(
            "下載的檔案不是有效 APK/ZIP"
        )

    print(
        "✅ APK Magic 正確"
    )

    return APK_PATH


# ============================================================
# 上傳 R2
# ============================================================

def upload_to_r2(apk_path):

    print()
    print("=" * 60)
    print("⑧ 上傳 Cloudflare R2")
    print("=" * 60)

    print(
        f"🪣 Bucket：{R2_BUCKET}"
    )

    print(
        f"📄 Object：{R2_OBJECT}"
    )

    print(
        f"📦 本地檔案：{apk_path}"
    )

    if not R2_ENDPOINT:

        raise RuntimeError(
            "R2_ENDPOINT 尚未設定"
        )

    # --------------------------------------------------------
    # 建立 R2 S3 Client
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 上傳
    # --------------------------------------------------------

    print()
    print(
        "☁️ 開始上傳..."
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
    print(
        "🎉 R2 上傳成功！"
    )

    print(
        f"🪣 Bucket：{R2_BUCKET}"
    )

    print(
        f"📄 Object：{R2_OBJECT}"
    )


# ============================================================
# 清理本地 APK
# ============================================================

def cleanup():

    print()
    print("=" * 60)
    print("⑨ 清理本地檔案")
    print("=" * 60)

    # --------------------------------------------------------
    # 刪除指定 APK
    # --------------------------------------------------------

    if APK_PATH.exists():

        try:

            APK_PATH.unlink()

            print(
                f"🗑️ 已刪除："
                f"{APK_PATH}"
            )

        except Exception as e:

            print(
                f"⚠️ APK 刪除失敗："
                f"{e}"
            )

    else:

        print(
            "ℹ️ 沒有主要 APK"
        )

    # --------------------------------------------------------
    # 清理其他 APK
    # --------------------------------------------------------

    if DOWNLOAD_DIR.exists():

        for file in DOWNLOAD_DIR.glob(
            "*.apk"
        ):

            try:

                file.unlink()

                print(
                    f"🗑️ 已刪除："
                    f"{file}"
                )

            except Exception as e:

                print(
                    f"⚠️ 無法刪除："
                    f"{file} - {e}"
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
        # 1. R2 設定
        # ----------------------------------------------------

        check_r2_config()

        # ----------------------------------------------------
        # 2. 準備下載目錄
        # ----------------------------------------------------

        prepare_download_dir()

        # ----------------------------------------------------
        # 3. 取得 5147 頁面
        # ----------------------------------------------------

        html = get_source_page()

        # ----------------------------------------------------
        # 4. 找 9997 API
        # ----------------------------------------------------

        api_url = find_download_api(
            html
        )

        # ----------------------------------------------------
        # 5. 取得最新 dmpdmp URL
        # ----------------------------------------------------

        download_url = get_lanzou_url(
            api_url
        )

        # ----------------------------------------------------
        # 6. Chromium + 兩階段按鈕
        # ----------------------------------------------------

        apk_path = browser_download(
            download_url
        )

        # ----------------------------------------------------
        # 7. 上傳 R2
        # ----------------------------------------------------

        upload_to_r2(
            apk_path
        )

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

        sys.exit(1)

    finally:

        # ----------------------------------------------------
        # 不論成功 / 失敗都清理
        # ----------------------------------------------------

        cleanup()

        print()

        if success:

            print(
                "✅ 任務成功完成"
            )

        else:

            print(
                "⚠️ 任務失敗，"
                "但已執行清理"
            )


# ============================================================
# 程式入口
# ============================================================

if __name__ == "__main__":
    main()
