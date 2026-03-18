const API_URL = 'https://xpxc.qzz.io/api';

// 頁面載入：讀取並轉換格式
window.onload = async () => {
    // 優先讀取本地快取
    const localData = localStorage.getItem('gift_codes');
    if (localData) document.getElementById('codes').value = localData;

    try {
        const r = await fetch(API_URL);
        const d = await r.json();
        if (d.code) {
            // 將雲端的逗號格式轉回換行顯示
            const formatted = d.code.split(',').filter(s => s !== "").join('\n');
            document.getElementById('codes').value = formatted;
            localStorage.setItem('gift_codes', formatted);
        }
    } catch (e) {
        console.log("雲端讀取失敗，使用本地數據");
    }
};

// 核心提交功能：同步雲端 + 請求 Worker 轉發
async function submitData() {
    const textarea = document.getElementById('codes');
    const content = textarea.value.trim();
    const btn = document.querySelector('.btn-submit');
    
    if (!content) return alert("請輸入禮包碼");

    btn.disabled = true;
    btn.innerText = "同步轉發中...";
    showStatus("正在連線伺服器...", "#007bff");

    // 格式準備：
    // 1. 雲端存檔用逗號 (,)
    const csvFormat = content.split('\n').map(s => s.trim()).filter(s => s !== "").join(',');
    // 2. 本地顯示用換行
    localStorage.setItem('gift_codes', content);

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat }) // 傳送 CSV 格式給 Worker
        });
        
        const result = await response.json();
        
        if (result.success) {
            showStatus(`✅ 同步成功！回應：${result.backendMsg}`, "#28a745");
        } else {
            showStatus(`⚠️ 轉發異常：${result.backendMsg}`, "#dc3545");
        }
    } catch (e) {
        showStatus("❌ 網路連線錯誤", "#dc3545");
    } finally {
        btn.disabled = false;
        btn.innerText = "提交並同步 API";
    }
}

function showStatus(msg, color) {
    const s = document.getElementById('status');
    s.innerText = msg;
    s.style.color = color;
    s.style.display = "block";
}
