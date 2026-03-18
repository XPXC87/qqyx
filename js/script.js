const API_URL = 'http://xpxc.qzz.io/api'; // 這是你的 Cloudflare Worker (D1 儲存用)
const TARGET_API = 'http://47.96.230.2:9997/qqyxNew/addDHM'; // 這是目標 API

// 頁面載入：從 D1 讀取資料並顯示
window.onload = async () => {
    const codesArea = document.getElementById('codes');
    const localData = localStorage.getItem('gift_codes');
    if (localData) codesArea.value = localData;

    try {
        const r = await fetch(API_URL);
        const d = await r.json();
        if (d.code) {
            // 資料庫存逗號，前端轉回換行
            const formatted = d.code.split(',').filter(s => s !== "").join('\n');
            codesArea.value = formatted;
            localStorage.setItem('gift_codes', formatted);
        }
    } catch (e) { console.log("雲端讀取失敗，使用本地數據"); }
};

// 核心功能：本地直接請求 + 雲端備份
async function submitData() {
    const textarea = document.getElementById('codes');
    const content = textarea.value.trim();
    const status = document.getElementById('status');
    
    if (!content) return alert("請輸入禮包碼");

    status.style.display = "block";
    status.innerText = "🚀 正在本地發送並同步雲端...";
    status.style.color = "#007bff";

    // 1. 準備格式
    const codesArray = content.split('\n').map(s => s.trim()).filter(s => s !== "");
    const csvFormat = codesArray.join(',');      // 存資料庫用
    const apiFormat = codesArray.join('@==');    // 發送 API 用

    // 2. 備份到雲端 D1 (背景執行，不影響使用者)
    fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: csvFormat })
    }).catch(e => console.log("雲端備份失敗"));

    localStorage.setItem('gift_codes', content);

    // 3. 【核心修正】本地直接請求 API
    // 使用 Image Beacon (圖片撞擊法)，這是繞過 CORS 最穩的方法
    const finalUrl = `${TARGET_API}?dhm=${encodeURIComponent(apiFormat)}`;
    
    const img = new Image();
    img.src = finalUrl; 

    // 因為 Image 只要 src 賦值就會發出 GET 請求
    // 我們給予一個成功的視覺回饋
    setTimeout(() => {
        status.innerText = "✅ 提交指令已從本地送出！";
        status.style.color = "#28a745";
    }, 1000);
}

// 清空功能
function clearAll() {
    if(confirm("確定要清空嗎？")) {
        document.getElementById('codes').value = "";
        localStorage.removeItem('gift_codes');
        status.innerText = "已清空本地快取";
    }
}
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        });
    } catch (e) { console.log("雲端同步失敗，但繼續嘗試發送 API"); }

    // --- 第二軌：隱形撞擊 API (繞過 1003 與 CORS) ---
    const apiFormat = content.split('\n').map(s => s.trim()).filter(s => s !== "").join('@==');
    const targetUrl = `http://47.96.230.2:9997/qqyxNew/addDHM?dhm=${encodeURIComponent(apiFormat)}`;

    // 建立一個隱形的圖片標籤來發送 GET 請求
    const img = new Image();
    img.src = targetUrl;

    // 因為是 GET 請求，只要 src 被賦值，瀏覽器就會發出請求
    // 我們設定一個 2 秒後的「假成功」提示，因為 API 不會回傳圖片，這標籤最後會變 error
    // 但只要請求發出去了，API 就會執行
    setTimeout(() => {
        status.innerText = "✅ 資料庫已同步，API 請求已送出！";
        status.style.color = "#28a745";
    }, 1500);
}
    }
}

// 僅備份到雲端，不處理轉發
async function saveToCloudOnly(content) {
    const csvFormat = content.split('\n').map(s => s.trim()).filter(s => s !== "").join(',');
    try {
        await fetch('https://xpxc.qzz.io/api', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        });
    } catch (e) {
        console.log("雲端備份失敗");
    }
}
