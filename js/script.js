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
    } catch (e) { console.warn("D1 同步失敗"); }
};

async function submitData() {
    const textarea = document.getElementById('codes');
    const statusBox = document.getElementById('status-box');
    const statusContent = document.getElementById('status-content');
    const submitBtn = document.getElementById('submitBtn');

    if (!textarea.value.trim()) return alert("❌ 請輸入內容");

    submitBtn.disabled = true;
    statusBox.style.display = "block";
    statusContent.innerHTML = "<span style='color:#888'>[SYSTEM] 正在通過 IP 通道直連轉發...</span>";

    const csvFormat = textarea.value.split('\n').map(s => s.trim()).filter(s => s !== "").join(',');

    try {
        const response = await fetch(WORKER_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        });

        const result = await response.json();

        if (result.success) {
            statusContent.innerHTML = `<span style='color:#fff'>[SUCCESS] 指令已確認</span><br>[SERVER] ${result.backendResponse}`;
            localStorage.setItem('gift_codes', textarea.value);
        } else {
            statusContent.innerHTML = `<span style='color:#ff4444'>[NODE ERROR] ${result.error}</span>`;
        }
    } catch (err) {
        statusContent.innerHTML = `<span style='color:#ff4444'>[FATAL ERROR] 連線中斷: ${err.message}</span>`;
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
        updateLineCount();
        document.getElementById('status-box').style.display = "none";
    }
}
