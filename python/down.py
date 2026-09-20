import os
import re
import sys
import time
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

DOWNLOAD_DIR = Path.cwd() / "downloads"
APK_PATH = DOWNLOAD_DIR / "球球英雄脚本.apk"

# dmpdmp 最多重試次數
BROWSER_RETRIES = 3

# 等待網頁元素
PAGE_LOAD_TIMEOUT = 30000
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
# 單一執行鎖
# ============================================================
# GitHub Actions 已經有 concurrency；這裡再加一層本地鎖，避免同一個
# runner/工作目錄意外同時啟動兩個 down.py，造成兩個 APK GET。
LOCK_PATH = DOWNLOAD_DIR / ".download.lock"


def acquire_process_lock():
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    try:
        fd = os.open(
            LOCK_PATH,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        print(f"🔒 已取得單一執行鎖：{LOCK_PATH}")
    except FileExistsError:
        raise RuntimeError(
            "偵測到另一個 down.py 正在執行，已拒絕第二個流程。"
        )


def release_process_lock():
    try:
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
            print(f"🔓 已釋放執行鎖：{LOCK_PATH}")
    except Exception as e:
        print(f"⚠️ 無法釋放執行鎖：{e}")


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
                        wait_until="commit",
                        timeout=5000,
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
                        "⏳ 3 秒後重新嘗試..."
                    )

                    time.sleep(3)

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
# 執行環境清理
# ============================================================

def cleanup_runtime():
    print()
    print("=" * 60)
    print("🧹 清理執行環境")
    print("=" * 60)

    import gc
    import subprocess

    try:
        gc.collect()
        print("✅ Python GC 已執行")
    except Exception as e:
        print(f"⚠️ Python GC 清理失敗：{e}")

    # GitHub Actions Linux Runner 上，確認 Chromium/Chrome 沒有殘留。
    # 不碰其他系統程序。
    for process_name in ("chromium", "chromium-headless-shell"):
        try:
            subprocess.run(
                ["pkill", "-9", "-f", process_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass

    print("✅ Chromium 殘留程序檢查完成")

    # 清除本次下載可能留下的暫存檔。
    if DOWNLOAD_DIR.exists():
        for pattern in ("*.tmp", "*.part", "*.crdownload"):
            for file in DOWNLOAD_DIR.glob(pattern):
                try:
                    file.unlink()
                    print(f"🗑️ 清除暫存：{file}")
                except Exception as e:
                    print(f"⚠️ 無法清除暫存：{file} - {e}")

    print("✅ 執行環境清理完成")


# ============================================================
# 下載真正 APK
# ============================================================
def download_apk(apk_url, referer=None):

    print()
    print("=" * 60)
    print("⑦ 下載 APK")
    print("=" * 60)

    print(f"🌐 APK URL：{apk_url[:200]}")

    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 只使用一個暫存檔，正式檔案只會在完整下載並驗證後產生。
    # 因此同一輪流程不會同時寫入兩份 APK。
    temp_path = DOWNLOAD_DIR / "download.tmp"

    if temp_path.exists():
        try:
            temp_path.unlink()
            print(f"🗑️ 清除上一輪暫存檔：{temp_path}")
        except Exception as e:
            raise RuntimeError(
                f"無法清除舊暫存檔：{temp_path} - {e}"
            )

    max_retries = 5

    for attempt in range(1, max_retries + 1):
        print()
        print(f"📥 APK 下載 {attempt}/{max_retries}")

        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/124.0.0.0 "
                    "Safari/537.36"
                ),
                "Accept": "*/*",
                "Accept-Encoding": "identity",
                "Connection": "close",
            }

            # 如果知道產生 APK 連結的頁面，就使用真正的頁面作為 Referer。
            # 不再使用固定的 slsstm2.dmpdmp.com，避免 Referer 不匹配。
            if referer:
                headers["Referer"] = referer

            request_started = time.monotonic()

            print("⏳ 等待伺服器回應...")

            with session.get(
                apk_url,
                headers=headers,
                stream=True,
                # 5 秒建立連線；連線建立後 5 秒內沒有收到任何資料
                # 就會觸發 ReadTimeout。
                timeout=(5, 5),
                allow_redirects=True,
            ) as response:

                response_elapsed = time.monotonic() - request_started

                print(
                    f"✅ 已取得 HTTP 回應 "
                    f"({response_elapsed:.2f} 秒)"
                )
                print(f"HTTP : {response.status_code}")
                print(f"Final: {response.url}")
                print(
                    "Type : "
                    f"{response.headers.get('Content-Type')}"
                )
                print(
                    "Length: "
                    f"{response.headers.get('Content-Length')}"
                )

                response.raise_for_status()

                total_header = response.headers.get("Content-Length")
                try:
                    total = int(total_header) if total_header else None
                except (TypeError, ValueError):
                    total = None

                downloaded = 0
                last_report_time = time.monotonic()
                download_started = time.monotonic()

                with open(temp_path, "wb") as f:
                    for chunk in response.iter_content(
                        chunk_size=256 * 1024
                    ):
                        if not chunk:
                            continue

                        f.write(chunk)
                        downloaded += len(chunk)

                        now = time.monotonic()

                        # 每 5 秒顯示一次，而不是每 5 MB。
                        # 這樣即使下載速度很慢，也不會看起來像完全卡死。
                        if (
                            now - last_report_time >= 5
                            or (
                                total is not None
                                and downloaded >= total
                            )
                        ):
                            elapsed = max(
                                now - download_started,
                                0.001,
                            )
                            speed_mbps = (
                                downloaded / 1024 / 1024
                            ) / elapsed

                            if total:
                                percent = (
                                    downloaded / total * 100
                                )
                                total_mb = (
                                    total / 1024 / 1024
                                )
                                downloaded_mb = (
                                    downloaded / 1024 / 1024
                                )
                                print(
                                    f"📦 {downloaded_mb:.2f} MB / "
                                    f"{total_mb:.2f} MB "
                                    f"({percent:.1f}%) | "
                                    f"{speed_mbps:.2f} MB/s"
                                )
                            else:
                                downloaded_mb = (
                                    downloaded / 1024 / 1024
                                )
                                print(
                                    f"📦 {downloaded_mb:.2f} MB | "
                                    f"{speed_mbps:.2f} MB/s"
                                )

                            last_report_time = now

                file_size = temp_path.stat().st_size

                print()
                print(
                    f"📦 下載完成："
                    f"{file_size / 1024 / 1024:.2f} MB"
                )

                if file_size == 0:
                    raise RuntimeError(
                        "下載檔案大小為 0"
                    )

                # APK 本質上是 ZIP；正常 APK 通常以 PK\x03\x04 開頭。
                with open(temp_path, "rb") as f:
                    magic = f.read(4)

                print(f"APK Magic：{magic!r}")

                if magic != b"PK\x03\x04":
                    raise RuntimeError(
                        "下載內容不是有效 APK/ZIP"
                    )

                print("✅ APK Magic 正確")

                if APK_PATH.exists():
                    try:
                        APK_PATH.unlink()
                    except Exception as e:
                        raise RuntimeError(
                            f"無法替換舊 APK：{APK_PATH} - {e}"
                        )

                temp_path.replace(APK_PATH)

                print()
                print(f"✅ APK 已保存：{APK_PATH}")

                return APK_PATH

        except requests.exceptions.ReadTimeout as e:
            print()
            print("⏱️ 連續 5 秒沒有收到資料")
            print(f"⚠️ ReadTimeout：{e}")

            if temp_path.exists():
                try:
                    temp_path.unlink()
                    print("🗑️ 已刪除不完整暫存檔")
                except Exception:
                    pass

            if attempt < max_retries:
                print("🔄 不等待，立即重新建立單一下載連線...")
                continue
            raise

        except requests.exceptions.ConnectTimeout as e:
            print()
            print("⏱️ 建立下載連線超過 5 秒")
            print(f"⚠️ ConnectTimeout：{e}")

            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

            if attempt < max_retries:
                print("🔄 不等待，立即重新建立單一下載連線...")
                continue
            raise

        except requests.exceptions.ConnectionError as e:
            print()
            print("❌ APK 連線錯誤")
            print(f"⚠️ ConnectionError：{e}")

            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

            if attempt < max_retries:
                print("🔄 不等待，立即重新建立單一下載連線...")
                continue
            raise

        except Exception as e:
            print()
            print(
                f"❌ APK 下載失敗："
                f"{type(e).__name__}: {e}"
            )

            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

            if attempt < max_retries:
                print("🔄 不等待，立即重新建立單一下載連線...")
                continue
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
    lock_acquired = False

    try:

        acquire_process_lock()
        lock_acquired = True

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
            apk_url,
            referer=download_url,
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

        if lock_acquired:
            release_process_lock()

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
