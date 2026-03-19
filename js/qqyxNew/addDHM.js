export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);

  // 1. 抓取前端傳來的 dhm 參數
  const params = url.search;

  // 2. 目標：阿里雲 HTTP IP (這樣就繞過了瀏覽器的 HSTS 檢查)
  const targetUrl = `http://47.96.230.2:9997/qqyxNew/addDHM${params}`;

  try {
    // 3. 在 Cloudflare 伺服器端發起請求
    const response = await fetch(targetUrl, {
      method: request.method,
      headers: request.headers,
      redirect: 'manual'
    });

    // 4. 把結果丟回給前端 DHM.js
    const body = await response.text();
    return new Response(body, {
      status: response.status,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "text/plain; charset=utf-8"
      }
    });
  } catch (e) {
    return new Response("代理失敗: " + e.message, { status: 500 });
  }
}
