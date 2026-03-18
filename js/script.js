const WORKER_URL = 'http://xpxc.qzz.io/api';

// 初始化：讀取資料
window.onload = async () => {
    const textarea = document.getElementById('codes');
    try {
        const res = await fetch(WORKER_URL);
        const data = await res.json();
        if (data.code) {
            textarea.value = data.code.split(',').join('\n');
            localStorage.setItem('gift_codes', textarea.value);
        }
    } catch (e) {
        const local = localStorage.getItem('gift_codes');
        if (local) textarea.value = local;
    }
};

// 提交資料
async function submitData() {
    const textarea = document.getElementById('codes');
    const status = document.getElementById('status');
    const content = textarea.value.trim();

    if (!content) return alert("請輸入禮包碼");

    status.style.display = "block";
    status.innerHTML = "⏳ 正在同步雲端並轉發 API...";
    status.style.color = "#ffd60a";

    // 轉為逗號分隔存入 D1
    const csvFormat = content.split('\n').map(s => s.trim()).filter(s => s !== "").join(',');

    try {
        const response = await fetch(WORKER_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        });

        const result = await response.json();

        if (result.success) {
            status.innerHTML = `✅ 發送成功！<br>伺服器回應：${result.backendResponse}`;
            status.style.color = "#32d74b";
            localStorage.setItem('gift_codes', content);
        } else {
            throw new Error(result.error);
        }
    } catch (err) {
        status.innerHTML = `❌ 轉發失敗：${err.message}`;
        status.style.color = "#ff453a";
    }
}

function clearAll() {
    if (confirm("確定清空？")) {
        document.getElementById('codes').value = "";
        localStorage.removeItem('gift_codes');
    }
}
