// /functions/addDHM.js
export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);

  // 1. 抓取原本網址後面的參數 (例如 ?dhm=ABC)
  const params = url.search;

  // 2. 設定目標：直接對準你的 HTTP 地址
  // 這裡用 http 而不是 https，且連到目標路徑
  const targetUrl = `http://47.96.230.2:9997/qqyxNew/addDHM${params}`;

  try {
    // 3. 由 Cloudflare 伺服器發起請求 (不受瀏覽器 HSTS 影響)
    const response = await fetch(targetUrl, {
      method: request.method,
      headers: request.headers,
      redirect: 'manual' // 防止中間產生意外的跳轉
    });

    // 4. 把結果回傳給瀏覽器
    const body = await response.text();
    return new Response(body, {
      status: response.status,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "text/plain; charset=utf-8"
      }
    });

  } catch (e) {
    return new Response("代理轉發失敗: " + e.message, { status: 500 });
  }
}
