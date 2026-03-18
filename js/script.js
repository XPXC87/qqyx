const WORKER_URL = 'https://xpxc.qzz.io/api';

// 1. 初始化同步功能
window.onload = async () => {
    updateLineCount(); // 初始化行數
    const textarea = document.getElementById('codes');
    const statusBox = document.getElementById('status-box');
    const statusContent = document.getElementById('status-content');

    console.log("系統啟動：嘗試同步雲端資料...");

    try {
        const res = await fetch(WORKER_URL);
        const data = await res.json();
        if (data.code) {
            // 將逗號轉回換行
            textarea.value = data.code.split(',').filter(s => s.trim() !== "").join('\n');
            updateLineCount();
            console.log("雲端同步成功");
        }
    } catch (e) {
        console.log("雲端同步跳過，使用本地存檔");
        const local = localStorage.getItem('gift_codes');
        if (local) textarea.value = local;
        updateLineCount();
    }
};

// 2. 核心提交函數 (對應 HTML 的 onclick)
async function submitData() {
    const textarea = document.getElementById('codes');
    const statusBox = document.getElementById('status-box');
    const statusContent = document.getElementById('status-content');
    const submitBtn = document.getElementById('submitBtn');

    const content = textarea.value.trim();
    if (!content) {
        alert("⚠️ 請先輸入禮包碼");
        return;
    }

    // UI 鎖定，防止重複點擊
    submitBtn.disabled = true;
    statusBox.style.display = "block";
    statusContent.innerHTML = "📡 正在偽裝發送至節點...";
    statusContent.style.color = "#888";

    // 格式轉換：換行 -> 逗號 (存 D1 用)
    const csvFormat = content.split('\n').map(s => s.trim()).filter(s => s !== "").join(',');

    try {
        const response = await fetch(WORKER_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        });

        const result = await response.json();

        if (result.success) {
            // 顯示 Worker 帶回來的伺服器回傳值
            statusContent.innerHTML = `✅ 同步成功<br>伺服器：${result.backendResponse}`;
            statusContent.style.color = "#fff";
            localStorage.setItem('gift_codes', content);
        } else {
            throw new Error(result.error || "未知錯誤");
        }
    } catch (err) {
        statusContent.innerHTML = `❌ 失敗：${err.message}`;
        statusContent.style.color = "#ff4444";
    } finally {
        submitBtn.disabled = false;
    }
}

// 3. 其他輔助函數
function updateLineCount() {
    const textarea = document.getElementById('codes');
    const display = document.getElementById('line-count');
    if (!textarea || !display) return;
    const lines = textarea.value.split('\n').filter(line => line.trim() !== '').length;
    display.innerText = `${lines} 行`;
}

function clearAll() {
    if (confirm("🗑️ 確定要清空所有內容嗎？")) {
        document.getElementById('codes').value = "";
        localStorage.removeItem('gift_codes');
        updateLineCount();
        document.getElementById('status-box').style.display = "none";
    }
}
    } catch (e) {
        console.error("同步失敗:", e);
        statusContent.innerHTML = "⚠️ 無法連線至雲端，改用本地快取";
        const local = localStorage.getItem('gift_codes');
        if (local) textarea.value = local;
        updateLineCount();
    }
};

// 別忘了行數計算函數
function updateLineCount() {
    const text = document.getElementById('codes').value;
    const lines = text.split('\n').filter(line => line.trim() !== '').length;
    const display = document.getElementById('line-count');
    if (display) display.innerText = `${lines} 行`;
}

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
