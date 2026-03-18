const WORKER_URL = 'https://xpxc.qzz.io/api';
const TARGET_API = 'http://47.96.230.2:9997/qqyxNew/addDHM';

// --- 1. 計算行數工具 ---
function updateLineCount() {
    const textarea = document.getElementById('codes');
    const lineDisplay = document.getElementById('line-count');
    if (!textarea || !lineDisplay) return;
    
    const text = textarea.value;
    // 過濾掉空行，只計算有內容的代碼
    const lines = text.split('\n').filter(line => line.trim() !== '').length;
    lineDisplay.innerText = `${lines} 行`;
}

// --- 2. 頁面初始化 ---
window.onload = async () => {
    const textarea = document.getElementById('codes');
    if (!textarea) return;

    // 先跑一次行數歸零或檢查
    updateLineCount();

    try {
        const res = await fetch(WORKER_URL);
        const data = await res.json();
        if (data && data.code) {
            textarea.value = data.code.split(',').join('\n');
            updateLineCount();
        }
    } catch (e) {
        console.warn("[系統] 無法連線至 Worker，嘗試讀取本地緩存...");
        try {
            const local = localStorage.getItem('gift_codes');
            if (local) {
                textarea.value = local;
                updateLineCount();
            }
        } catch (localErr) {
            console.error("本地儲存讀取失敗");
        }
    }
};

// --- 3. 執行同步與寫入 ---
async function submitData() {
    const textarea = document.getElementById('codes');
    const statusBox = document.getElementById('status-box');
    const statusContent = document.getElementById('status-content');
    const submitBtn = document.getElementById('submitBtn');

    const content = textarea.value.trim();
    if (!content) return alert("❌ 請輸入內容");

    // 介面鎖定與動畫
    submitBtn.disabled = true;
    submitBtn.classList.add('loading'); // 配合 CSS 旋轉特效
    statusBox.style.display = "block";
    statusContent.innerHTML = "<span style='color:#aaa'>[系統] 正在同步資料...</span>";

    // 格式轉換
    const csvFormat = content.split('\n').map(s => s.trim()).filter(s => s !== "").join(',');
    const apiFormat = csvFormat.split(',').join('@==');

    try {
        // A. 同步到 Worker (非同步，不擋主進程)
        fetch(WORKER_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        }).catch(err => console.error("Worker 同步失敗", err));

        // B. 直連 API (重點)
        const response = await fetch(`${TARGET_API}?dhm=${encodeURIComponent(apiFormat)}`);
        const resultText = await response.text();

        // C. 更新介面
        statusContent.innerHTML = `
            <span style='color:#00ff00; font-weight:bold;'>[SUCCESS] 操作完成</span><br>
            <span style='color:#00e5ff'>[SERVER] ${resultText.trim() || "無回傳文字"}</span>
        `;

        // D. 儲存到本地
        try {
            localStorage.setItem('gift_codes', content);
        } catch (e) {
            statusContent.innerHTML += `<br><span style='color:#ffaa00'>[提醒] 瀏覽器限制儲存</span>`;
        }

    } catch (err) {
        statusContent.innerHTML = `<span style='color:#ff4444'>[錯誤] 連線失敗: ${err.message}</span>`;
    } finally {
        submitBtn.disabled = false;
        submitBtn.classList.remove('loading');
    }
}

// --- 4. 清除功能 ---
function clearAll() {
    if (confirm("🗑️ 確定要清空所有代碼嗎？")) {
        const textarea = document.getElementById('codes');
        if (textarea) textarea.value = "";
        
        try {
            localStorage.removeItem('gift_codes');
        } catch (e) {
            console.log("清理失敗");
        }
        
        updateLineCount();
        const statusBox = document.getElementById('status-box');
        if (statusBox) statusBox.style.display = "none";
    }
}
