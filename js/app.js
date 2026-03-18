/**
 * 球球英雄工具站 - 核心腳本 BY XPXC
 */

const themeBtn = document.getElementById('theme-toggle');
const bodyEl = document.body;

// 切換主題函數
function toggleTheme() {
    bodyEl.classList.toggle('light-mode');
    
    // 儲存設定到瀏覽器
    const isLight = bodyEl.classList.contains('light-mode');
    localStorage.setItem('theme_pref', isLight ? 'light' : 'dark');
    
    // 更新按鈕文字
    updateButtonText(isLight);
}

// 更新按鈕顯示文字
function updateButtonText(isLight) {
    if (themeBtn) {
        themeBtn.textContent = isLight ? "切換深色模式" : "切換淺色模式";
    }
}

// 初始化：檢查本地儲存或系統偏好
window.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme_pref');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    // 判斷邏輯：
    // 1. 如果存過 light，就用 light
    // 2. 如果沒存過，且系統不是深色，就用 light
    if (savedTheme === 'light' || (!savedTheme && !systemPrefersDark)) {
        bodyEl.classList.add('light-mode');
        updateButtonText(true);
    } else {
        updateButtonText(false);
    }
});
