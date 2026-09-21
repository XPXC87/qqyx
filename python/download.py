import os
import sys
import time
from pathlib import Path

import requests
import boto3
from botocore.config import Config

# ============================================================
# 下載 / R2 設定
# ============================================================

DOWNLOAD_DIR = Path.cwd() / "downloads"
APK_PATH = DOWNLOAD_DIR / "球球英雄脚本.apk"
URL_FILE = Path.cwd() / "apk_url.txt"

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")

R2_BUCKET = "qqyx"
R2_OBJECT = "球球英雄脚本.apk"

R2_ENDPOINT = (
    f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    if R2_ACCOUNT_ID else None
)

session = requests.Session()

# ============================================================
# 下載真正 APK
# ============================================================
def download_apk(apk_url, referer=None):

    print()
    print("=" * 60)
    print("⑦ 下載 APK")
    print("=" * 60)

    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 只使用一個暫存檔，正式檔案只會在完整下載並驗證後產生。
    # 因此同一輪流程不會同時寫入兩份 APK。
    temp_path = DOWNLOAD_DIR / "download.tmp"


    max_retries = 10

    for attempt in range(1, max_retries + 1):
        print()
        print(f"📥 APK 下載 {attempt}/{max_retries}")


        try:
            # 如果知道產生 APK 連結的頁面，就使用真正的頁面作為 Referer。
            # 不再使用固定的 slsstm2.dmpdmp.com，避免 Referer 不匹配。

            with session.get(
                apk_url,
                stream=True,
                timeout=(10, 10),
                allow_redirects=True,
            ) as response:

                response_elapsed = time.monotonic() - request_started

                print(
                    f"✅ 已取得 HTTP 回應 "
                    f"({response_elapsed:.2f} 秒)"
                )
                print(f"HTTP : {response.status_code}")
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
                print(f"✅ APK 已保存")

                return APK_PATH

        except requests.exceptions.ReadTimeout as e:
            print()
            print("⏱️ 連續 5 秒沒有收到資料")
            print(f"⚠️ ReadTimeout：{e}")


            if attempt < max_retries:
                print("🔄 不等待，立即重新建立單一下載連線...")
                continue
            raise

        except requests.exceptions.ConnectTimeout as e:
            print()
            print("⏱️ 建立下載連線超過 10 秒")
            print(f"⚠️ ConnectTimeout：{e}")


            if attempt < max_retries:
                print("🔄 不等待，立即重新建立單一下載連線...")
                continue
            raise

        except requests.exceptions.ConnectionError as e:
            print()
            print("❌ APK 連線錯誤")
            print(f"⚠️ ConnectionError：{e}")


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
# Main
# ============================================================

def main():
    print()
    print("=" * 60)
    print("📥 QQYX APK 下載 / R2 上傳")
    print("=" * 60)

    if not URL_FILE.exists():
        raise RuntimeError(
            f"找不到 {URL_FILE}，請先執行 parse.py"
        )

    apk_url = URL_FILE.read_text(encoding="utf-8").strip()

    if not apk_url.startswith(("http://", "https://")):
        raise RuntimeError(
            f"apk_url.txt 內容不是有效 URL：{apk_url[:300]}"
        )

    print(f"🔗 讀取 APK URL：{apk_url}")

    apk_path = download_apk(
        apk_url,
        referer=apk_url,
    )

    upload_to_r2(apk_path)

    print()
    print("=" * 60)
    print("🎉 下載 + R2 上傳完成")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ 執行失敗")
        print("=" * 60)
        print(f"{type(e).__name__}: {e}")
        sys.exit(1)
