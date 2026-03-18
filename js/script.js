const WORKER_URL = 'https://xpxc.qzz.io/api';
const API_BASE = 'http://47.96.230.2:9997/qqyxNew/addDHM';

// 初始載入
window.onload = async () => {
    const textarea = document.getElementById('codes');
    try {
        const res = await fetch(WORKER_URL);
        const data = await res.json();
        if (data.code) {
            textarea.value = data.code.split(',').join('\n');
        }
    } catch (e) {
        const local = localStorage.getItem('gift_codes');
        if (local) textarea.value = local;
    }
};

async function submitAndOpen() {
    const textarea = document.getElementById('codes');
    const content = textarea.value.trim();
    if (!content) return alert("請輸入內容");

    const csvFormat = content.split('\n').map(s => s.trim()).filter(s => s !== "").join(',');
    const apiFormat = csvFormat.split(',').join('@==');

    // 1. 存入 Worker 備份
    try {
        await fetch(WORKER_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        });
        localStorage.setItem('gift_codes', content);
    } catch (e) {
        console.error("雲端同步失敗");
    }

    // 2. 直接開啟新分頁請求 API (徹底解決 1003 與 Mixed Content)
    const finalUrl = `${API_BASE}?dhm=${encodeURIComponent(apiFormat)}`;
    window.open(finalUrl, '_blank');
}

function clearAll() {
    if (confirm("確定清除？")) {
        document.getElementById('codes').value = "";
        localStorage.removeItem('gift_codes');
    }
}
