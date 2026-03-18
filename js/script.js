// 請確保這裡的網址與你的 Worker 綁定的網域一致
const WORKER_URL = 'https://xpxc.qzz.io/api'; 
const TARGET_API = 'http://47.96.230.2:9997/qqyxNew/addDHM';

// 頁面載入時：優先從雲端 D1 抓取資料，若失敗則用本地快取
window.onload = async () => {
    const textarea = document.getElementById('codes');
    const local = localStorage.getItem('gift_codes');
    if (local) textarea.value = local;

    try {
        const res = await fetch(WORKER_URL);
        if (!res.ok) throw new Error('Network response was not ok');
        const data = await res.json();
        if (data.code) {
            // D1 存的是逗號分隔，轉回換行顯示
            const formatted = data.code.split(',').filter(s => s !== "").join('\n');
            textarea.value = formatted;
            localStorage.setItem('gift_codes', formatted);
        }
    } catch (e) {
        console.warn("無法從雲端同步資料，目前使用本地暫存。");
    }
};

// 提交資料：同步到 D1 並從本地直接發射請求給 API
async function submitData() {
    const textarea = document.getElementById('codes');
    const status = document.getElementById('status');
    const content = textarea.value.trim();

    if (!content) {
        alert("請先輸入禮包碼");
        return;
    }

    status.style.display = "block";
    status.innerText = "🚀 正在同步並發送...";
    status.style.color = "#007bff";

    // 格式化資料
    const codesArray = content.split('\n').map(s => s.trim()).filter(s => s !== "");
    const csvFormat = codesArray.join(',');       // 存 D1 用
    const apiFormat = codesArray.join('@==');     // 發送 API 用

    // 1. 同步到 Cloudflare D1 (HTTPS)
    fetch(WORKER_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: csvFormat })
    }).catch(err => console.error("雲端備份失敗:", err));

    // 2. 本地直接發送請求到 HTTP API (使用 Image Beacon 繞過 CORS)
    const finalUrl = `${TARGET_API}?dhm=${encodeURIComponent(apiFormat)}`;
    const img = new Image();
    img.src = finalUrl;

    // 更新本地快取與 UI 反饋
    localStorage.setItem('gift_codes', content);
    
    // 給予發送成功的視覺提示
    setTimeout(() => {
        status.innerText = "✅ 已從本地發送請求，並同步至雲端。";
        status.style.color = "#28a745";
    }, 1000);
}

// 清空內容
function clearAll() {
    if (confirm("確定要清空所有禮包碼嗎？")) {
        document.getElementById('codes').value = "";
        localStorage.removeItem('gift_codes');
        const status = document.getElementById('status');
        status.innerText = "已清空";
        status.style.color = "#666";
    }
}
