export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);
  const targetUrl = `http://47.96.230.2:9997/qqyxNew/addDHM${url.search}`;

  try {
    const response = await fetch(targetUrl, {
      method: "GET",
      headers: {
        // 完全偽裝成真實的電腦 Chrome 瀏覽器
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://xpxc.qzz.io/"
      }
    });

    const body = await response.text();
    // 增加一個判斷，如果阿里雲回傳空的，我們回傳狀態碼供除錯
    return new Response(body || `連線成功但無內容(Status:${response.status})`, {
      status: 200,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "text/plain; charset=utf-8"
      }
    });
  } catch (e) {
    return new Response("代理失敗(可能是阿里雲防火牆擋了): " + e.message, { status: 500 });
  }
}
