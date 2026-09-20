import os
import re
import sys
import time
import hashlib
from pathlib import Path
from urllib.parse import urljoin

import requests
import boto3
from botocore.config import Config
from playwright.sync_api import sync_playwright


# =========================================================
# 基本設定
# =========================================================

SOURCE_PAGE = "http://47.96.230.2:5147/qqyx/downloadScript.html"

VERSION_API = "http://47.96.230.2:9997/version/getDownloUrl"

R2_BUCKET = "qqyx"
R2_OBJECT = "球球英雄脚本.apk"

WORK_DIR = Path("work")
DOWNLOAD_DIR = WORK_DIR / "downloads"

MAX_APK_SIZE = 200 * 1024 * 1024

TIMEOUT = 60


# =========================================================
# HTTP Session
# =========================================================

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
})


# =========================================================
# 工具
# =========================================================

def log(msg):
    print(f"[+] {msg}", flush=True)


def error(msg):
    print(f"[!] {msg}", flush=True)


def sha256_file(path):
    h = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            data = f.read(1024 * 1024)

            if not data:
                break

            h.update(data)

    return h.hexdigest()


def is_apk(path):
    try:
        if not path.exists():
            return False

        if path.stat().st_size < 4:
            return False

        with open(path, "rb") as f:
            magic = f.read(4)

        # APK 本質上是 ZIP
        return magic == b"PK\x03\x04"

    except Exception:
        return False


# =========================================================
# 取得 9997 URL
# =========================================================

def get_download_url():
    log("讀取入口頁...")

    r = session.get(
        SOURCE_PAGE,
        timeout=TIMEOUT,
        allow_redirects=True
    )

    r.raise_for_status()

    html = r.text

    log(f"入口頁 HTTP {r.status_code}")
    log(f"入口頁長度: {len(html)}")

    # 優先從頁面尋找 version/getDownloUrl
    match = re.search(
        r'https?://[^"\']*/version/getDownloUrl',
        html
    )

    if match:
        api_url = match.group(0)
    else:
        api_url = VERSION_API

    log(f"Version API: {api_url}")

    r = session.get(
        api_url,
        timeout=TIMEOUT,
        allow_redirects=True
    )

    log(f"Version API HTTP {r.status_code}")

    r.raise_for_status()

    download_url = r.text.strip()

    if not download_url:
        raise RuntimeError("Version API 沒有回傳下載網址")

    if not download_url.startswith(("http://", "https://")):
        raise RuntimeError(
            f"Version API 回傳內容不像 URL：{download_url[:200]}"
        )

    log("成功取得下載入口")

    # 不把完整臨時 URL 打到 log
    print(
        "[+] Download URL: "
        + download_url[:80]
        + ("..." if len(download_url) > 80 else "")
    )

    return download_url


# =========================================================
# Playwright 正常瀏覽器下載
# =========================================================

def browser_download(url):
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    log("啟動 Chromium...")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            accept_downloads=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
        )

        page = context.new_page()

        # =================================================
        # 監控所有 response
        # =================================================

        apk_responses = []

        def response_handler(response):
            try:
                content_type = (
                    response.headers.get("content-type", "")
                    .lower()
                )

                disposition = (
                    response.headers.get(
                        "content-disposition",
                        ""
                    )
                    .lower()
                )

                response_url = response.url.lower()

                if (
                    ".apk" in response_url
                    or "application/vnd.android.package-archive"
                    in content_type
                    or ".apk" in disposition
                ):
                    log(
                        "偵測到可能的 APK Response: "
                        + response.url[:100]
                    )

                    apk_responses.append(response)

            except Exception:
                pass

        page.on("response", response_handler)

        try:

            log("開啟下載入口...")

            with page.expect_download(
                timeout=30000
            ) as download_info:

                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

            download = download_info.value

            filename = download.suggested_filename

            if not filename:
                filename = "qqyx.apk"

            if not filename.lower().endswith(".apk"):
                filename += ".apk"

            output = DOWNLOAD_DIR / filename

            log(f"瀏覽器取得下載：{filename}")

            download.save_as(str(output))

            if is_apk(output):
                log(f"APK 驗證成功：{output}")
                return output

        except Exception as e:

            log(
                "沒有直接捕獲 Playwright Download："
                + str(e)
            )

        # =================================================
        # 如果不是標準 Download，等待頁面正常跳轉
        # =================================================

        log("等待頁面正常跳轉/驗證...")

        deadline = time.time() + 90

        while time.time() < deadline:

            try:

                current_url = page.url

                log(
                    "目前頁面："
                    + current_url[:120]
                )

                # 找 APK 連結
                links = page.locator(
                    "a[href]"
                ).all()

                for link in links:

                    try:
                        href = link.get_attribute(
                            "href"
                        )

                        if not href:
                            continue

                        absolute = urljoin(
                            current_url,
                            href
                        )

                        if ".apk" in absolute.lower():

                            log(
                                "找到 APK 連結"
                            )

                            r = session.get(
                                absolute,
                                timeout=60,
                                stream=True
                            )

                            if r.status_code != 200:
                                continue

                            output = (
                                DOWNLOAD_DIR
                                / "qqyx.apk"
                            )

                            with open(
                                output,
                                "wb"
                            ) as f:

                                for chunk in r.iter_content(
                                    1024 * 1024
                                ):

                                    if chunk:
                                        f.write(chunk)

                            if is_apk(output):

                                log(
                                    "APK 驗證成功"
                                )

                                return output

                    except Exception:
                        continue

                # =================================================
                # 監控 response
                # =================================================

                for response in apk_responses:

                    try:

                        data = response.body()

                        if (
                            data[:4]
                            == b"PK\x03\x04"
                        ):

                            output = (
                                DOWNLOAD_DIR
                                / "qqyx.apk"
                            )

                            with open(
                                output,
                                "wb"
                            ) as f:
                                f.write(data)

                            if is_apk(output):

                                log(
                                    "從 Response 成功取得 APK"
                                )

                                return output

                    except Exception:
                        pass

                time.sleep(2)

            except Exception:
                time.sleep(2)

    raise RuntimeError(
        "瀏覽器流程結束，但沒有取得有效 APK。"
        "如果頁面要求 CAPTCHA/人工驗證，"
        "GitHub Actions 無法代替人工完成。"
    )


# =========================================================
# 上傳 R2
# =========================================================

def upload_r2(apk_path):

    account_id = os.environ.get(
        "ffe4b2080a30225540740e53bf5627e3"
    )

    access_key = os.environ.get(
        "36bd19aeb7dbfff245db6dfe2bbba669"
    )

    secret_key = os.environ.get(
        "a30ffe8451760d26565714b7d304125859276279e9f83227f20755ec160e244a"
    )

    if not account_id:
        raise RuntimeError(
            "缺少 R2_ACCOUNT_ID"
        )

    if not access_key:
        raise RuntimeError(
            "缺少 R2_ACCESS_KEY_ID"
        )

    if not secret_key:
        raise RuntimeError(
            "缺少 R2_SECRET_ACCESS_KEY"
        )

    endpoint = (
        f"https://{account_id}.r2.cloudflarestorage.com"
    )

    log("連線 Cloudflare R2...")

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=Config(
            signature_version="s3v4"
        )
    )

    size = apk_path.stat().st_size

    if size <= 0:
        raise RuntimeError(
            "APK 檔案大小為 0"
        )

    if size > MAX_APK_SIZE:
        raise RuntimeError(
            f"APK 太大：{size} bytes"
        )

    sha256 = sha256_file(apk_path)

    log(f"APK 大小：{size / 1024 / 1024:.2f} MB")
    log(f"SHA256：{sha256}")

    log(
        f"上傳到 R2："
        f"{R2_BUCKET}/{R2_OBJECT}"
    )

    s3.upload_file(
        str(apk_path),
        R2_BUCKET,
        R2_OBJECT,
        ExtraArgs={
            "ContentType":
                "application/vnd.android.package-archive"
        }
    )

    # =====================================================
    # 上傳後驗證
    # =====================================================

    obj = s3.head_object(
        Bucket=R2_BUCKET,
        Key=R2_OBJECT
    )

    remote_size = obj.get(
        "ContentLength",
        0
    )

    log(
        f"R2 上傳完成，遠端大小："
        f"{remote_size / 1024 / 1024:.2f} MB"
    )

    if remote_size != size:
        raise RuntimeError(
            "R2 遠端檔案大小與本地不同"
        )

    log("R2 驗證成功")


# =========================================================
# 清理
# =========================================================

def cleanup():

    if not DOWNLOAD_DIR.exists():
        return

    log("清理暫存 APK...")

    for path in DOWNLOAD_DIR.glob("*.apk"):

        try:

            path.unlink()

            log(
                f"已刪除：{path.name}"
            )

        except Exception as e:

            error(
                f"刪除失敗：{path} / {e}"
            )


# =========================================================
# Main
# =========================================================

def main():
    apk_path = None

    try:
        # 你的主要下載流程
        # 取得 9997 URL
        # Playwright 開啟頁面
        # 等待 APK
        # 上傳 R2
        pass

    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        raise

    finally:
        # 不管成功或失敗都清理 APK
        if apk_path:
            try:
                if os.path.exists(apk_path):
                    os.remove(apk_path)
                    print(f"🗑️ 已刪除本地 APK: {apk_path}")
            except Exception as e:
                print(f"⚠️ 刪除 APK 失敗: {e}")


if __name__ == "__main__":
    main()
