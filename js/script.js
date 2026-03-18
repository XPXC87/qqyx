const API_URL = 'https://xpxc.qzz.io/api';

// 頁面載入：讀取 D1 數據 (CSV 格式) 並轉為換行顯示
window.onload = async () => {
    // 優先讀取本地快取
    const localData = localStorage.getItem('gift_codes');
    if (localData) document.getElementById('codes').value = localData;

    try {
        const r = await fetch(API_URL);
        const d = await r.json();
        if (d.code) {
            // 關鍵：將資料庫的逗號轉回換行
            const formatted = d.code.split(',').filter(s => s !== "").join('\n');
            document.getElementById('codes').value = formatted;
            localStorage.setItem('gift_codes', formatted);
        }
    } catch (e) {
        console.log("讀取失敗，使用本地存檔");
    }
};

// 提交功能
async function submitData() {
    const textarea = document.getElementById('codes');
    const content = textarea.value.trim();
    const btn = document.querySelector('.btn-submit');
    const status = document.getElementById('status');
    
    if (!content) return alert("請輸入禮包碼");

    btn.disabled = true;
    btn.innerText = "同步轉發中...";
    status.style.display = "block";
    status.innerText = "正在連線伺服器...";
    status.style.color = "#007bff";

    // 準備存入資料庫的格式 (逗號分隔)
    const csvFormat = content.split('\n')
                             .map(s => s.trim())
                             .filter(s => s !== "")
                             .join(',');

    // 更新本地快取
    localStorage.setItem('gift_codes', content);

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat }) 
        });
        
        const result = await response.json();
        
        if (result.success) {
            status.innerText = `✅ 成功！回應：${result.backendMsg}`;
            status.style.color = "#28a745";
        } else {
            status.innerText = `⚠️ 異常：${result.backendMsg}`;
            status.style.color = "#dc3545";
        }
    } catch (e) {
        status.innerText = "❌ 網路連線錯誤";
        status.style.color = "#dc3545";
    } finally {
        btn.disabled = false;
        btn.innerText = "提交並同步 API";
    }
}

function clearAll() {
    if(confirm("確定要清空嗎？這也會同步清除雲端紀錄。")) {
        document.getElementById('codes').value = "";
        localStorage.removeItem('gift_codes');
        // 可選：發送空內容給伺服器以清空 D1
    }
}
