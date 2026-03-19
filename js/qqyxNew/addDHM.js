// /functions/qqyxNew/addDHM.js
export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);

  // 1. 取得前端傳過來的參數 (dhm=...)
  const params = url.search;

  // 2. 目標地址 (你的阿里雲 HTTP IP)
  const targetUrl = `http://47.96.230.2:9997/qqyxNew/addDHM${params}`;

  try {
    // 3. 在 CF 伺服器後端發起 HTTP 請求 (這步不會被瀏覽器加 S)
    const response = await fetch(targetUrl, {
      method: request.method,
      headers: request.headers,
      redirect: 'manual'
    });

    // 4. 原封不動回傳給你的前端 JS
    const body = await response.text();
    return new Response(body, {
      status: response.status,
      headers: {
        "Access-Control-Allow-Origin": "*", // 允許跨域
        "Content-Type": "text/plain; charset=utf-8"
      }
    });
  } catch (e) {
    return new Response("代理失敗: " + e.message, { status: 500 });
  }
}
