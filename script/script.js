const API_URL = 'https://xpxc.qzz.io/api';

// 頁面載入時自動讀取雲端紀錄
window.onload = async () => {
    try {
        const r = await fetch(API_URL);
        const d = await r.json();
        if (d.code) document.getElementById('codes').value = d.code;
    } catch (e) {
        console.error("讀取雲端資料失敗:", e);
    }
};

// 核心功能：提交並開啟新分頁
async function submitToTab() {
    const textarea = document.getElementById('codes');
    const content = textarea.value.trim();
    
    if (!content) {
        alert("請輸入禮包碼！");
        return;
    }

    // 先同步到雲端備份
    saveToCloud(false);

    // 格式處理：偵測換行轉 @==，尾巴不加
    const codeArray = content.split('\n')
                             .map(line => line.trim())
                             .filter(line => line !== "");
    
    const joined = codeArray.join('@==');
    
    // 組合成目標 API 網址
    const targetUrl = `http://47.96.230.2:9997/qqyxNew/addDHM?dhm=${encodeURIComponent(joined)}`;

    // 以新分頁開啟
    window.open(targetUrl, '_blank');
    
    showStatus("✅ 已同步並開啟分頁提交", "var(--success)");
}

// 儲存到雲端 D1
async function saveToCloud(showMsg = true) {
    const content = document.getElementById('codes').value;
    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: content })
        });
        
        if (response.ok && showMsg) {
            showStatus("☁️ 雲端紀錄已更新", "var(--accent)");
        }
    } catch (e) {
        if (showMsg) showStatus("❌ 儲存失敗", "var(--error)");
    }
}

// 顯示狀態提示
function showStatus(msg, color) {
    const s = document.getElementById('status');
    s.innerText = msg;
    s.style.color = color;
    s.style.display = "block";
    setTimeout(() => { s.style.display = "none"; }, 3000);
}
