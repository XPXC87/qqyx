const WORKER_URL = 'https://xpxc.qzz.io/api';
const TARGET_API = 'http://47.96.230.2:9997/qqyxNew/addDHM';

window.onload = async () => {
    const textarea = document.getElementById('codes');
    try {
        const res = await fetch(WORKER_URL);
        const data = await res.json();
        if (data.code) {
            // 將逗號轉回換行並填入
            textarea.value = data.code.split(',').join('\n');
        }
    } catch (e) {
        // 如果 Worker 連不上，讀取本地存檔
        const local = localStorage.getItem('gift_codes');
        if (local) {
            textarea.value = local;
        }
    }
    // 關鍵：無論是從 Worker 抓還是從本地抓，最後都跑一次行數計算
    updateLineCount(); 
};

async function submitData() {
    const textarea = document.getElementById('codes');
    const statusBox = document.getElementById('status-box');
    const statusContent = document.getElementById('status-content');
    const submitBtn = document.getElementById('submitBtn');

    const content = textarea.value.trim();
    if (!content) return alert("❌ 請輸入內容");

    submitBtn.disabled = true;
    statusBox.style.display = "block";
    statusContent.innerHTML = "[系統] 正在處理資料並寫入 API...";

    const csvFormat = content.split('\n').map(s => s.trim()).filter(s => s !== "").join(',');
    const apiFormat = csvFormat.split(',').join('@==');

    try {
        // 1. 同步到 Worker D1 (備份)
        fetch(WORKER_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        });

        // 2. 直連 API
        const response = await fetch(`${TARGET_API}?dhm=${encodeURIComponent(apiFormat)}`);
        const resultText = await response.text();

        // 顯示成功字樣 (改成綠色 #00ff00)
        statusContent.innerHTML = `<span style='color:#00ff00'>[成功] 操作完成</span><br>[服務器回傳]: ${resultText.trim() || "無回傳文字"}`;

        // --- 優化：處理本地儲存報錯 ---
        try {
            localStorage.setItem('gift_codes', content);
        } catch (e) {
            statusContent.innerHTML += `<br><span style='color:#ffaa00'>[提醒] 瀏覽器已阻擋本地儲存，下次重新整理頁面可能需重新讀取。</span>`;
        }

    } catch (err) {
        statusContent.innerHTML = `<span style='color:#ff4444'>[錯誤] 寫入失敗: ${err.message}</span>`;
    } finally {
        submitBtn.disabled = false;
    }
}

// 修改清除功能的報錯處理
function clearAll() {
    if (confirm("🗑️ 確定清除？")) {
        document.getElementById('codes').value = "";
        try {
            localStorage.removeItem('gift_codes');
        } catch (e) {
            console.log("無法清除本地資料，因為權限被阻擋");
        }
        updateLineCount();
        document.getElementById('status-box').style.display = "none";
    }
}
