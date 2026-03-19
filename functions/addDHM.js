export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);

  // 1. 抓取前端傳過來的參數 (例如 ?dhm=GVD48BPZ...)
  const params = url.search;

  // 2. 設定阿里雲的目標地址 (用 HTTP IP 避開瀏覽器限制)
  const targetUrl = `http://47.96.230.2:9997/qqyxNew/addDHM${params}`;

  try {
    // 3. 在伺服器端發起連線
    const response = await fetch(targetUrl, {
      method: "GET", // 根據你原本的邏輯，這是 GET 請求
      headers: {
        "User-Agent": "Cloudflare-Pages-Proxy",
        "Accept": "*/*"
      }
    });

    // 4. 讀取阿里雲回傳的內容
    const body = await response.text();

    // 5. 回傳給前端 DHM.js
    return new Response(body, {
      status: 200,
      headers: {
        "Access-Control-Allow-Origin": "*", // 允許跨域
        "Content-Type": "text/plain; charset=utf-8",
        "Cache-Control": "no-cache"
      }
    });

  } catch (e) {
    // 如果連不上阿里雲，會在這裡報錯
    return new Response("[代理錯誤] 無法連線至伺服器: " + e.message, { 
      status: 500,
      headers: { "Access-Control-Allow-Origin": "*" }
    });
  }
}
