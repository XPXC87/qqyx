const WORKER_URL = 'https://xpxc.qzz.io/api';

// 頁面載入時自動從 D1 同步
window.onload = async () => {
    const textarea = document.getElementById('codes');
    const statusBox = document.getElementById('status-box');
    const statusContent = document.getElementById('status-content');

    // 顯示讀取中狀態
    statusBox.style.display = "block";
    statusContent.innerHTML = "📡 正在從雲端節點同步資料...";

    try {
        // 向 Worker 發送 GET 請求
        const res = await fetch(WORKER_URL, {
            method: 'GET',
            headers: { 'Cache-Control': 'no-cache' }
        });

        if (!res.ok) throw new Error('連線失敗');

        const data = await res.json();

        if (data.code) {
            // D1 存的是逗號分隔，轉回換行顯示在 Textarea
            const formatted = data.code.split(',').filter(s => s.trim() !== "").join('\n');
            textarea.value = formatted;
            
            // 更新行數顯示
            updateLineCount();
            
            statusContent.innerHTML = "✅ 雲端同步完成";
            setTimeout(() => { statusBox.style.display = "none"; }, 2000);
        } else {
            statusContent.innerHTML = "ℹ️ 雲端目前無存檔資料";
        }
    } catch (e) {
        console.error("同步失敗:", e);
        statusContent.innerHTML = "⚠️ 無法連線至雲端，改用本地快取";
        const local = localStorage.getItem('gift_codes');
        if (local) textarea.value = local;
        updateLineCount();
    }
};

// 別忘了行數計算函數
function updateLineCount() {
    const text = document.getElementById('codes').value;
    const lines = text.split('\n').filter(line => line.trim() !== '').length;
    const display = document.getElementById('line-count');
    if (display) display.innerText = `${lines} 行`;
}

async function submitData() {
    const textarea = document.getElementById('codes');
    const status = document.getElementById('status');
    const content = textarea.value.trim();

    if (!content) return alert("請輸入禮包碼");

    status.style.display = "block";
    status.innerHTML = "⏳ 正在偽裝發送中...";
    status.style.color = "#ffd60a";

    const csvFormat = content.split('\n').map(s => s.trim()).filter(s => s !== "").join(',');

    try {
        const response = await fetch(WORKER_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        });

        const result = await response.json();

        if (result.success) {
            // 這裡就會顯示伺服器回傳的「添加成功」或「重複使用」
            status.innerHTML = `✅ 回傳結果：${result.backendResponse}`;
            status.style.color = "#32d74b";
        } else {
            status.innerHTML = `❌ 錯誤：${result.error}`;
            status.style.color = "#ff453a";
        }
    } catch (err) {
        status.innerHTML = `❌ 連線失敗：${err.message}`;
        status.style.color = "#ff453a";
    }
}
