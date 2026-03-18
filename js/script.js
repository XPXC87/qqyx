const WORKER_URL = 'https://xpxc.qzz.io/api';
const TARGET_API = 'http://47.96.230.2:9997/qqyxNew/addDHM';

window.onload = async () => {
    updateLineCount();
    const textarea = document.getElementById('codes');
    try {
        const res = await fetch(WORKER_URL);
        const data = await res.json();
        if (data.code) {
            textarea.value = data.code.split(',').join('\n');
            updateLineCount();
        }
    } catch (e) {
        const local = localStorage.getItem('gift_codes');
        if (local) textarea.value = local;
    }
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
    statusContent.innerHTML = "[系統日誌] 正在處理資料並寫入 API...";

    const csvFormat = content.split('\n').map(s => s.trim()).filter(s => s !== "").join(',');
    const apiFormat = csvFormat.split(',').join('@==');

    try {
        // 1. 同步到 Worker D1 (備份)
        fetch(WORKER_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        });

        // 2. 直連 API 並獲取數據 (因為是 HTTP，現在不會報錯了)
        const response = await fetch(`${TARGET_API}?dhm=${encodeURIComponent(apiFormat)}`);
        const resultText = await response.text();

        // 顯示結果，例如「添加成功」
        statusContent.innerHTML = `<span style='color:#fff'>[成功] 操作完成</span><br>[服務器回傳]:${resultText.trim() || "無回傳文字"}`;
        localStorage.setItem('gift_codes', content);
        
    } catch (err) {
        statusContent.innerHTML = `<span style='color:#ff4444'>[錯誤] 寫入失敗: ${err.message}</span><br><small>請確認 API 伺服器已開啟跨域 (CORS) 權限</small>`;
    } finally {
        submitBtn.disabled = false;
    }
}

function updateLineCount() {
    const text = document.getElementById('codes').value;
    const lines = text.split('\n').filter(line => line.trim() !== '').length;
    document.getElementById('line-count').innerText = `${lines} 行`;
}

function clearAll() {
    if (confirm("🗑️ 確定清除？")) {
        document.getElementById('codes').value = "";
        localStorage.removeItem('gift_codes');
        updateLineCount();
        document.getElementById('status-box').style.display = "none";
    }
}
