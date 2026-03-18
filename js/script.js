const WORKER_URL = 'https://xpxc.qzz.io/api';

// 初始化：載入時自動同步雲端 D1
window.onload = async () => {
    updateLineCount();
    const textarea = document.getElementById('codes');
    const statusBox = document.getElementById('status-box');
    const statusContent = document.getElementById('status-content');

    try {
        const res = await fetch(WORKER_URL);
        const data = await res.json();
        if (data.code) {
            textarea.value = data.code.split(',').filter(s => s.trim() !== "").join('\n');
            updateLineCount();
        }
    } catch (e) {
        const local = localStorage.getItem('gift_codes');
        if (local) textarea.value = local;
        updateLineCount();
    }
};

// 提交資料：發送給 Worker 處理
async function submitData() {
    const textarea = document.getElementById('codes');
    const statusBox = document.getElementById('status-box');
    const statusContent = document.getElementById('status-content');
    const submitBtn = document.getElementById('submitBtn');

    const content = textarea.value.trim();
    if (!content) return alert("❌ 請先輸入禮包碼");

    submitBtn.disabled = true;
    statusBox.style.display = "block";
    statusContent.innerHTML = "<span style='color:#888'>[SYSTEM] 正在封裝數據包...</span>";

    // 格式轉換：換行 -> 逗號
    const csvFormat = content.split('\n').map(s => s.trim()).filter(s => s !== "").join(',');

    try {
        const response = await fetch(WORKER_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        });

        const result = await response.json();

        if (result.success) {
            statusContent.innerHTML = `<span style='color:#fff'>[SUCCESS] 同步完成</span><br>[SERVER] ${result.backendResponse}`;
            localStorage.setItem('gift_codes', content);
        } else {
            statusContent.innerHTML = `<span style='color:#ff4444'>[ERROR] ${result.error}</span>`;
        }
    } catch (err) {
        statusContent.innerHTML = `<span style='color:#ff4444'>[FATAL] 通訊失敗: ${err.message}</span>`;
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
    if (confirm("🗑️ 確定要清空嗎？")) {
        document.getElementById('codes').value = "";
        localStorage.removeItem('gift_codes');
        updateLineCount();
        document.getElementById('status-box').style.display = "none";
    }
}
