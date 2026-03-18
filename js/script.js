const WORKER_URL = 'https://xpxc.qzz.io/api';

window.onload = async () => {
    updateLineCount();
    const textarea = document.getElementById('codes');
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

async function submitData() {
    const textarea = document.getElementById('codes');
    const statusBox = document.getElementById('status-box');
    const statusContent = document.getElementById('status-content');
    const submitBtn = document.getElementById('submitBtn');

    if (!textarea.value.trim()) return alert("❌ 請輸入內容");

    submitBtn.disabled = true;
    statusBox.style.display = "block";
    statusContent.innerHTML = "[SYSTEM] 數據發送中...";

    const csvFormat = textarea.value.split('\n').map(s => s.trim()).filter(s => s !== "").join(',');

    try {
        const response = await fetch(WORKER_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        });

        const result = await response.json();

        if (result.success) {
            // 直接顯示後端抓回來的內容
            statusContent.innerHTML = `[SUCCESS] 同步完成<br>[SERVER] ${result.backendResponse}`;
            statusContent.style.color = "#fff";
            localStorage.setItem('gift_codes', textarea.value);
        } else {
            statusContent.innerHTML = `[ERROR] ${result.error}`;
            statusContent.style.color = "#ff4444";
        }
    } catch (err) {
        statusContent.innerHTML = `[FATAL] 網絡中斷: ${err.message}`;
        statusContent.style.color = "#ff4444";
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
