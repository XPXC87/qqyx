async function submitData() {
    const textarea = document.getElementById('codes');
    const content = textarea.value.trim();
    const status = document.getElementById('status');
    
    if (!content) return alert("請輸入禮包碼");

    status.style.display = "block";
    status.innerText = "正在嘗試直接發送請求...";
    status.style.color = "#007bff";

    // 1. 格式轉換：偵測換行轉為 @==
    const apiFormat = content.split('\n')
                             .map(s => s.trim())
                             .filter(s => s !== "")
                             .join('@==');

    // 2. 組合最終 API 網址 (不加 encodeURIComponent 試試看，有些 API 很挑)
    const targetUrl = `http://47.96.230.2:9997/qqyxNew/addDHM?dhm=${apiFormat}`;

    try {
        // 使用 no-cors 模式嘗試強行撞擊 API
        // 注意：no-cors 模式下你拿不到 API 回傳的成功或失敗訊息
        await fetch(targetUrl, {
            mode: 'no-cors',
            method: 'GET'
        });

        // 因為 no-cors 拿不到結果，我們同步存一份到 D1 當紀錄就好
        saveToCloudOnly(content);
        
        status.innerText = "🚀 請求已發送！(請確認 API 是否有收到資料)";
        status.style.color = "#28a745";
    } catch (e) {
        status.innerText = "❌ 直接發送失敗，可能是瀏覽器攔截了不安全的 HTTP 請求";
        status.style.color = "#dc3545";
    }
}

// 僅備份到雲端，不處理轉發
async function saveToCloudOnly(content) {
    const csvFormat = content.split('\n').map(s => s.trim()).filter(s => s !== "").join(',');
    try {
        await fetch('https://xpxc.qzz.io/api', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        });
    } catch (e) {
        console.log("雲端備份失敗");
    }
}
