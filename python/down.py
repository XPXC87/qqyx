import os
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

# GitHub Actions 即時顯示日誌
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

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

DOWNLOAD_DIR = Path.cwd() / "downloads"
APK_PATH = DOWNLOAD_DIR / "球球英雄脚本.apk"

# APK 下載最多等待
DOWNLOAD_TIMEOUT = 180

# dmpdmp 最多重試次數
BROWSER_RETRIES = 2

# 等待網頁元素
PAGE_LOAD_TIMEOUT = 120000
ELEMENT_TIMEOUT = 120000

# ============================================================
# Cloudflare R2
# ============================================================

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")

R2_BUCKET = "qqyx"
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

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/124.0.0.0 "
        "Safari/537.36"
    ),
    "Accept": "*/*",
})


# ============================================================
# R2 設定檢查
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
# 清理舊檔
# ============================================================

def prepare_download_dir():
    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for file in DOWNLOAD_DIR.glob("*.apk"):
        try:
            file.unlink()
            print(f"🗑️ 清除舊 APK：{file}")
        except Exception as e:
            print(
                f"⚠️ 無法刪除舊 APK："
                f"{file} - {e}"
            )


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
        timeout=30,
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
# 保存診斷資料
# ============================================================

def save_debug(page, prefix):

    print()
    print("🛠️ 保存診斷資料...")

    try:

        html_path = (
            Path.cwd()
            / f"{prefix}.html"
        )

        html_path.write_text(
            page.content(),
            encoding="utf-8",
        )

        print(
            f"📄 HTML：{html_path}"
        )

    except Exception as e:

        print(
            f"⚠️ HTML 保存失敗：{e}"
        )

    try:

        screenshot_path = (
            Path.cwd()
            / f"{prefix}.png"
        )

        page.screenshot(
            path=str(screenshot_path),
            full_page=True,
            timeout=5000,
        )

        print(
            f"📸 Screenshot："
            f"{screenshot_path}"
        )

    except Exception as e:

        print(
            f"⚠️ Screenshot 保存失敗：{e}"
        )


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
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/124.0.0.0 "
                "Safari/537.36"
            ),
        )

        page = context.new_page()

        for attempt in range(
            1,
            BROWSER_RETRIES + 1,
        ):

            print()
            print(
                "=" * 60
            )
            print(
                f"🌐 dmpdmp 第 "
                f"{attempt}/{BROWSER_RETRIES} 次嘗試"
            )
            print(
                "=" * 60
            )

            try:

                print(
                    "🌐 開啟下載頁面..."
                )

                try:

                    page.goto(
                        download_url,
                        wait_until=(
                            "domcontentloaded"
                        ),
                        timeout=PAGE_LOAD_TIMEOUT,
                    )

                except PlaywrightTimeoutError:

                    print(
                        "⚠️ 頁面載入超時，"
                        "但繼續檢查頁面..."
                    )

                print()
                print("目前頁面：")

                try:
                    print(page.url)
                except Exception:
                    pass

                print()
                print(
                    "=" * 60
                )
                print(
                    "⑤ 等待「验证并下载」"
                )
                print(
                    "=" * 60
                )

                sub_button = page.locator(
                    "#sub"
                )

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

                sub_button.click(
                    no_wait_after=True
                )

                print(
                    "✅ 已點擊"
                    "「验证并下载」"
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

                if attempt < BROWSER_RETRIES:

                    try:
                        save_debug(
                            page,
                            f"debug_retry_{attempt}",
                        )
                    except Exception:
                        pass

                    print()
                    print(
                        "⏳ 5 秒後重新嘗試..."
                    )

                    time.sleep(5)

                    try:
                        page.close()
                    except Exception:
                        pass

                    page = context.new_page()

                else:

                    try:
                        save_debug(
                            page,
                            "debug_final",
                        )
                    except Exception:
                        pass

                    browser.close()

                    raise


# ============================================================
# 下載真正 APK
# ============================================================

def download_apk(apk_url):

    print()
    print("=" * 60)
    print("⑦ 下載 APK")
    print("=" * 60)

    print(
        "🌐 APK URL："
        f"{apk_url[:200]}",
        flush=True,
    )

    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = (
        DOWNLOAD_DIR
        / "download.tmp"
    )

    # --------------------------------------------------------
    # 下載重試設定
    # --------------------------------------------------------

    max_retries = 3

    # TCP 連線最多等待 20 秒
    connect_timeout = 20

    # 單次讀取若 30 秒沒有收到任何資料就中止
    read_timeout = 30

    # 整個 HTTP 請求最多允許 90 秒
    hard_timeout = 90

    # 失敗後等待 3～5 分鐘再重試
    retry_wait_min = 180
    retry_wait_max = 300

    # 下載進度至少每 5 秒顯示一次
    progress_interval = 5

    for attempt in range(
        1,
        max_retries + 1,
    ):

        print()
        print(
            f"📥 APK 下載 {attempt}/{max_retries}",
            flush=True,
        )

        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass

        try:

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/124.0.0.0 "
                    "Safari/537.36"
                ),
                "Referer": (
                    "https://slsstm2.dmpdmp.com/"
                ),
                "Accept": "*/*",
                "Connection": "close",
            }

            start_time = time.monotonic()

            print(
                "🌐 開始建立 APK HTTP 連線...",
                flush=True,
            )
            print(
                f"⏱️ 連線逾時：{connect_timeout} 秒",
                flush=True,
            )
            print(
                f"⏱️ 讀取逾時：{read_timeout} 秒",
                flush=True,
            )
            print(
                f"⏱️ 整體 HTTP 最長時間：{hard_timeout} 秒",
                flush=True,
            )

            # requests 沒有「整個請求」的 timeout，
            # 因此用 signal 在 Linux/GitHub Actions 上加一道硬限制。
            import signal

            previous_alarm = None
            signal_enabled = False

            def _hard_timeout(signum, frame):
                raise TimeoutError(
                    f"HTTP 整體請求超過 {hard_timeout} 秒"
                )

            try:
                if hasattr(signal, "SIGALRM"):
                    previous_alarm = signal.signal(
                        signal.SIGALRM,
                        _hard_timeout,
                    )
                    signal.setitimer(
                        signal.ITIMER_REAL,
                        hard_timeout,
                    )
                    signal_enabled = True

                with session.get(
                    apk_url,
                    headers=headers,
                    stream=True,
                    timeout=(
                        connect_timeout,
                        read_timeout,
                    ),
                    allow_redirects=True,
                ) as response:

                    print(
                        "✅ HTTP Response 已收到",
                        flush=True,
                    )

                    print(
                        f"HTTP : {response.status_code}",
                        flush=True,
                    )

                    print(
                        "Type : "
                        f"{response.headers.get('Content-Type')}",
                        flush=True,
                    )

                    print(
                        "Length: "
                        f"{response.headers.get('Content-Length')}",
                        flush=True,
                    )

                    print(
                        "Final URL: "
                        f"{response.url[:200]}",
                        flush=True,
                    )

                    response.raise_for_status()

                    total = response.headers.get(
                        "Content-Length"
                    )

                    if total:
                        try:
                            total = int(total)
                        except ValueError:
                            total = None
                    else:
                        total = None

                    downloaded = 0
                    last_report_time = start_time
                    last_report_bytes = 0

                    with open(
                        temp_path,
                        "wb",
                    ) as f:

                        for chunk in response.iter_content(
                            chunk_size=1024 * 1024
                        ):

                            if not chunk:
                                continue

                            f.write(chunk)
                            downloaded += len(chunk)

                            now = time.monotonic()

                            should_report = (
                                downloaded
                                - last_report_bytes
                                >= 1024 * 1024
                                or
                                now
                                - last_report_time
                                >= progress_interval
                            )

                            if should_report:

                                elapsed = max(
                                    now - start_time,
                                    0.001,
                                )

                                speed = (
                                    downloaded
                                    / 1024
                                    / 1024
                                    / elapsed
                                )

                                mb = (
                                    downloaded
                                    / 1024
                                    / 1024
                                )

                                if total:

                                    total_mb = (
                                        total
                                        / 1024
                                        / 1024
                                    )

                                    percent = (
                                        downloaded
                                        / total
                                        * 100
                                    )

                                    print(
                                        f"📦 {mb:.2f} / "
                                        f"{total_mb:.2f} MB "
                                        f"({percent:.1f}%) "
                                        f"速度 {speed:.2f} MB/s",
                                        flush=True,
                                    )

                                else:

                                    print(
                                        f"📦 {mb:.2f} MB "
                                        f"速度 {speed:.2f} MB/s",
                                        flush=True,
                                    )

                                last_report_time = now
                                last_report_bytes = downloaded

            finally:
                if signal_enabled:
                    signal.setitimer(
                        signal.ITIMER_REAL,
                        0,
                    )
                    signal.signal(
                        signal.SIGALRM,
                        previous_alarm,
                    )

            elapsed = max(
                time.monotonic() - start_time,
                0.001,
            )

            if not temp_path.exists():
                raise RuntimeError(
                    "HTTP 請求完成，但沒有產生 APK 檔案"
                )

            file_size = temp_path.stat().st_size

            avg_speed = (
                file_size
                / 1024
                / 1024
                / elapsed
            )

            print()
            print(
                f"📦 下載完成："
                f"{file_size / 1024 / 1024:.2f} MB",
                flush=True,
            )

            print(
                f"⏱️ 下載時間："
                f"{elapsed:.1f} 秒",
                flush=True,
            )

            print(
                f"🚀 平均速度："
                f"{avg_speed:.2f} MB/s",
                flush=True,
            )

            if file_size == 0:
                raise RuntimeError(
                    "下載檔案大小為 0"
                )

            # ------------------------------------------------
            # APK Magic 檢查
            # ------------------------------------------------

            with open(
                temp_path,
                "rb",
            ) as f:
                magic = f.read(4)

            print(
                f"APK Magic：{magic!r}",
                flush=True,
            )

            if magic != b"PK\x03\x04":
                raise RuntimeError(
                    "下載內容不是有效 APK/ZIP"
                )

            print(
                "✅ APK Magic 正確",
                flush=True,
            )

            # ------------------------------------------------
            # 改成正式檔名
            # ------------------------------------------------

            if APK_PATH.exists():
                try:
                    APK_PATH.unlink()
                except Exception:
                    pass

            temp_path.rename(
                APK_PATH
            )

            print()
            print(
                f"✅ APK 已保存："
                f"{APK_PATH}",
                flush=True,
            )

            return APK_PATH

        except Exception as e:

            elapsed = max(
                time.monotonic() - start_time,
                0.001,
            )

            print()
            print(
                f"❌ APK HTTP/下載失敗："
                f"{type(e).__name__}: {e}",
                flush=True,
            )
            print(
                f"⏱️ 本次嘗試耗時：{elapsed:.1f} 秒",
                flush=True,
            )

            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

            if attempt < max_retries:

                wait_seconds = random.randint(
                    retry_wait_min,
                    retry_wait_max,
                )

                print()
                print(
                    f"⏳ {wait_seconds // 60} 分"
                    f" {wait_seconds % 60} 秒後重試...",
                    flush=True,
                )

                # 每 30 秒顯示一次等待進度
                remaining = wait_seconds

                while remaining > 0:

                    sleep_for = min(
                        30,
                        remaining,
                    )

                    time.sleep(sleep_for)
                    remaining -= sleep_for

                    if remaining > 0:
                        print(
                            f"⏳ 尚餘約 {remaining // 60} 分"
                            f" {remaining % 60} 秒...",
                            flush=True,
                        )

            else:
                raise


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

    s3 = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=(
            R2_ACCESS_KEY_ID
        ),
        aws_secret_access_key=(
            R2_SECRET_ACCESS_KEY
        ),
        region_name="auto",
        config=Config(
            signature_version="s3v4"
        ),
    )

    print()
    print("☁️ 開始上傳...")

    s3.upload_file(
        str(apk_path),
        R2_BUCKET,
        R2_OBJECT,
        ExtraArgs={
            "ContentType": (
                "application/vnd.android."
                "package-archive"
            )
        },
    )

    print()
    print("🎉 R2 上傳成功！")

    print(
        f"🪣 Bucket：{R2_BUCKET}"
    )

    print(
        f"📄 Object：{R2_OBJECT}"
    )


# ============================================================
# 清理
# ============================================================

def cleanup():

    print()
    print("=" * 60)
    print("⑨ 清理本地檔案")
    print("=" * 60)

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

    if DOWNLOAD_DIR.exists():

        for file in DOWNLOAD_DIR.iterdir():

            try:

                if file.is_file():

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
# Main
# ============================================================

def main():

    print()
    print("=" * 60)
    print("🚀 QQYX APK 自動同步")
    print("=" * 60)

    success = False

    try:

        # 1
        check_r2_config()

        # 2
        prepare_download_dir()

        # 3
        html = get_source_page()

        # 4
        api_url = find_download_api(
            html
        )

        # 5
        download_url = get_lanzou_url(
            api_url
        )

        # 6
        apk_url = get_verified_apk_url(
            download_url
        )

        # 7
        apk_path = download_apk(
            apk_url
        )

        # 8
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


if __name__ == "__main__":
    main()
