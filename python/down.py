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

        print()
        print("=" * 60)
        print("❌ 執行失敗")
        print("=" * 60)

        print(
            f"{type(e).__name__}: {e}"
        )

        sys.exit(1)

    print()
    print("=" * 60)
    print("🎉 全部完成")
    print("=" * 60)
    print("✅ 任務成功完成")


if __name__ == "__main__":
    main()
