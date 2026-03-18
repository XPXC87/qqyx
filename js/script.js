/**
 * 禮包碼同步終端 - 前端邏輯
 * 功能：同步 D1 資料庫 + 本地直接發射 HTTP 請求
 */

const WORKER_URL = 'https://xpxc.qzz.io/api';
const TARGET_API = 'http://47.96.230.2:9997/qqyxNew/addDHM';

// 1. 頁面載入：自動從雲端同步最後一筆資料
window.onload = async () => {
    const textarea = document.getElementById('codes');
    const statusBox = document.getElementById('status-box');
    const statusContent = document.getElementById('status-content');

    console.log("⚡ 終端啟動：正在聯繫雲端節點...");

    try {
        const res = await fetch(WORKER_URL, { method: 'GET' });
        const data = await res.json();
        
        if (data.code) {
            // 將 D1 的逗號格式轉回換行顯示
            textarea.value = data.code.split(',').filter(s => s.trim() !== "").join('\n');
            updateLineCount();
            console.log("✅ 雲端同步成功");
        }
    } catch (e) {
        console.warn("⚠️ 雲端連線失敗，改用本地快取");
        const local = localStorage.getItem('gift_codes');
        if (local) textarea.value = local;
        updateLineCount();
    }
};

// 2. 核心發送函數
async function submitData() {
    const textarea = document.getElementById('codes');
    const statusBox = document.getElementById('status-box');
    const statusContent = document.getElementById('status-content');
    const submitBtn = document.querySelector('.btn-primary');

    const content = textarea.value.trim();
    if (!content) {
        alert("❌ 請輸入禮包碼");
        return;
    }

    // --- UI 狀態更新 ---
    submitBtn.disabled = true;
    statusBox.style.display = "block";
    statusContent.innerHTML = "📡 正在同步雲端備份...";
    statusContent.style.color = "#888";

    // 格式化資料
    const codesArray = content.split('\n').map(s => s.trim()).filter(s => s !== "");
    const csvFormat = codesArray.join(',');       // 存 D1 用
    const apiFormat = codesArray.join('@==');     // 發送 API 用

    try {
        // --- A. 同步到雲端 D1 (走 HTTPS Worker) ---
        // 這一步如果失敗不影響發送，只是沒備份而已
        fetch(WORKER_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        }).then(() => console.log("☁️ D1 備份完成"))
          .catch(err => console.error("☁️ D1 備份失敗:", err));

        // --- B. 【核心】本地直接發射 HTTP 請求 ---
        // 使用 Image Beacon 繞過 HTTPS/HTTP 混合內容限制與 1003 錯誤
        statusContent.innerHTML = "🚀 正在從本地發射指令至伺服器...";
        
        const finalUrl = `${TARGET_API}?dhm=${encodeURIComponent(apiFormat)}&t=${Date.now()}`;
        const img = new Image();
        
        // 監聽發射結果（即便 API 回傳不是圖片，onerror 觸發通常也代表請求已送達）
        img.onload = () => finalize();
        img.onerror = () => finalize();
        
        img.src = finalUrl;

    } catch (err) {
        statusContent.innerHTML = `❌ 發生錯誤: ${err.message}`;
        statusContent.style.color = "#ff4444";
        submitBtn.disabled = false;
    }

    function finalize() {
        statusContent.innerHTML = "✅ 指令已發出！<br><span style='font-size:12px;'>由於 HTTPS 限制，請至遊戲內確認結果。</span>";
        statusContent.style.color = "#ffffff";
        localStorage.setItem('gift_codes', content);
        submitBtn.disabled = false;
        
        // 成功後三秒自動收起狀態欄
        setTimeout(() => {
            // statusBox.style.display = "none"; 
        }, 3000);
    }
}

// 3. 輔助函數：計算行數
function updateLineCount() {
    const textarea = document.getElementById('codes');
    const display = document.getElementById('line-count');
    if (!textarea || !display) return;
    const lines = textarea.value.split('\n').filter(line => line.trim() !== '').length;
    display.innerText = `${lines} 行`;
}

// 4. 輔助函數：清空
function clearAll() {
    if (confirm("🗑️ 確定要清空所有內容嗎？")) {
        const textarea = document.getElementById('codes');
        textarea.value = "";
        localStorage.removeItem('gift_codes');
        updateLineCount();
        document.getElementById('status-box').style.display = "none";
    }
}
