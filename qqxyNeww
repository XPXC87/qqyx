export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);

  // 獲取網址後面的 dhm=... 參數
  const params = url.search;

  // 這裡就是關鍵：後端伺服器去連阿里雲 HTTP IP，瀏覽器管不著
  const targetUrl = `http://47.96.230.2:9997/qqyxNew/addDHM${params}`;

  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers: request.headers,
      redirect: 'manual'
    });

    const body = await response.text();
    return new Response(body, {
      status: response.status,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "text/plain; charset=utf-8"
      }
    });
  } catch (e) {
    return new Response("後端代理失敗: " + e.message, { status: 500 });
  }
}
