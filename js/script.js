async function submitData() {
    const textarea = document.getElementById('codes');
    const status = document.getElementById('status');
    const content = textarea.value.trim();

    if (!content) return alert("請輸入禮包碼");

    // UI 反饋：顯示進度
    status.style.display = "block";
    status.innerHTML = "⏳ 正在透過 Worker 轉發 HTTP 請求...";
    status.style.color = "#ff9500";

    const codesArray = content.split('\n').map(s => s.trim()).filter(s => s !== "");
    const csvFormat = codesArray.join(',');

    try {
        const response = await fetch('http://xpxc.qzz.io/api', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        });

        const result = await response.json();

        if (result.success) {
            // 這裡可以抓到 Worker 從伺服器拿回來的真正結果了！
            status.innerHTML = `✅ 發送成功！<br>伺服器回應：${result.backendResponse}`;
            status.style.color = "#34c759";
            localStorage.setItem('gift_codes', content);
        } else {
            throw new Error(result.error);
        }
    } catch (err) {
        status.innerHTML = `❌ 轉發失敗：${err.message}`;
        status.style.color = "#ff3b30";
    }
}
