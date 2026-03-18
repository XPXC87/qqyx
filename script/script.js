const API_URL = 'https://xpxc.qzz.io/api';

// 頁面載入：先讀本地，再讀雲端並把逗號轉回換行
window.onload = async () => {
    const localData = localStorage.getItem('gift_codes');
    if (localData) document.getElementById('codes').value = localData;

    try {
        const r = await fetch(API_URL);
        const d = await r.json();
        if (d.code) {
            // 將資料庫的逗號轉回網頁的換行
            const formattedCode = d.code.split(',').join('\n');
            document.getElementById('codes').value = formattedCode;
            localStorage.setItem('gift_codes', formattedCode);
        }
    } catch (e) {
        console.log("雲端讀取失敗，使用本地存檔");
    }
};

// 儲存：把換行轉成逗號存入雲端
async function saveToCloud(showMsg = true) {
    const textarea = document.getElementById('codes');
    const content = textarea.value.trim();
    
    // 轉成逗號格式
    const csvFormat = content.split('\n')
                             .map(s => s.trim())
                             .filter(s => s !== "")
                             .join(',');

    localStorage.setItem('gift_codes', content);

    try {
        await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        });
        if (showMsg) showStatus("☁️ 雲端已存為逗號格式", "#007bff");
    } catch (e) {
        if (showMsg) showStatus("💾 僅存於本地", "#dc3545");
    }
}

// 提交：開啟分頁 (維持 @== 格式)
function submitToTab() {
    const content = document.getElementById('codes').value.trim();
    if (!content) return alert("請輸入禮包碼");

    saveToCloud(false);

    const joined = content.split('\n')
                          .map(s => s.trim())
                          .filter(s => s !== "")
                          .join('@==');
    
    const targetUrl = `http://47.96.230.2:9997/qqyxNew/addDHM?dhm=${encodeURIComponent(joined)}`;
    window.open(targetUrl, '_blank');
    showStatus("✅ 已開啟分頁提交", "#28a745");
}

function showStatus(msg, color) {
    const s = document.getElementById('status');
    s.innerText = msg;
    s.style.color = color;
    s.style.display = "block";
    setTimeout(() => { s.style.display = "none"; }, 3000);
}
