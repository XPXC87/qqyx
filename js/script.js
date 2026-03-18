const WORKER_URL = 'https://xpxc.qzz.io/api';

async function submitData() {
    const textarea = document.getElementById('codes');
    const status = document.getElementById('status');
    const content = textarea.value.trim();

    if (!content) return alert("請輸入禮包碼");

    status.style.display = "block";
    status.innerHTML = "⏳ 正在偽裝發送中...";
    status.style.color = "#ffd60a";

    const csvFormat = content.split('\n').map(s => s.trim()).filter(s => s !== "").join(',');

    try {
        const response = await fetch(WORKER_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        });

        const result = await response.json();

        if (result.success) {
            // 這裡就會顯示伺服器回傳的「添加成功」或「重複使用」
            status.innerHTML = `✅ 回傳結果：${result.backendResponse}`;
            status.style.color = "#32d74b";
        } else {
            status.innerHTML = `❌ 錯誤：${result.error}`;
            status.style.color = "#ff453a";
        }
    } catch (err) {
        status.innerHTML = `❌ 連線失敗：${err.message}`;
        status.style.color = "#ff453a";
    }
}
