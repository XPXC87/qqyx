const WORKER_URL = 'https://xpxc.qzz.io/api';
const TARGET_API = '/qqyxNew/addDHM'; 
// --- 1. 深淺色模式與初始化 ---
function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const themeIcon = document.getElementById('theme-icon');
    
    // 自動偵測或讀取設定
    if (savedTheme === 'light' || (!savedTheme && window.matchMedia('(prefers-color-scheme: light)').matches)) {
        document.body.classList.add('light-mode');
        themeIcon.innerText = '☀️';
    }
}

function toggleTheme() {
    const body = document.body;
    const themeIcon = document.getElementById('theme-icon');
    const isLight = body.classList.toggle('light-mode');
    
    themeIcon.innerText = isLight ? '☀️' : '🌙';
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
}

// --- 2. 工具功能 ---
function updateLineCount() {
    const textarea = document.getElementById('codes');
    const lineDisplay = document.getElementById('line-count');
    const lines = textarea.value.split('\n').filter(line => line.trim() !== '').length;
    lineDisplay.innerText = `${lines} 行`;
}

window.onload = async () => {
    initTheme();
    updateLineCount();

    const textarea = document.getElementById('codes');
    try {
        const res = await fetch(WORKER_URL);
        const data = await res.json();
        if (data?.code) {
            textarea.value = data.code.split(',').join('\n');
            updateLineCount();
        }
    } catch (e) {
        const local = localStorage.getItem('gift_codes');
        if (local) {
            textarea.value = local;
            updateLineCount();
        }
    }
};

// --- 3. 核心 API 提交 ---
async function submitData() {
    const textarea = document.getElementById('codes');
    const statusBox = document.getElementById('status-box');
    const statusContent = document.getElementById('status-content');
    const submitBtn = document.getElementById('submitBtn');

    const content = textarea.value.trim();
    if (!content) return alert("❌ 請輸入內容");

    submitBtn.disabled = true;
    statusBox.style.display = "block";
    statusContent.innerHTML = "正在同步資料...";

    const csvFormat = content.split('\n').map(s => s.trim()).filter(s => s !== "").join(',');
    const apiFormat = csvFormat.split(',').join('@==');

    try {
        // 同步到 Worker
        fetch(WORKER_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: csvFormat })
        }).catch(err => console.error("Worker 同步失敗", err));

        // 直連 API
        const response = await fetch(`${TARGET_API}?dhm=${encodeURIComponent(apiFormat)}`);
        const resultText = await response.text();

        statusContent.innerHTML = `<b style="color:#00ff00">[成功] 操作完成</b><br>[服務器回應]:${resultText.trim()}`;
        localStorage.setItem('gift_codes', content);
    } catch (err) {
        statusContent.innerHTML = `<span style="color:var(--error)">[錯誤] 連線失敗: ${err.message}</span>`;
    } finally {
        submitBtn.disabled = false;
    }
}

function clearAll() {
    if (confirm("🗑️ 確定要清空嗎？")) {
        document.getElementById('codes').value = "";
        localStorage.removeItem('gift_codes');
        updateLineCount();
        document.getElementById('status-box').style.display = "none";
    }
}
