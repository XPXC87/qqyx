export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);

  // 1. 抓取前端傳過來的所有參數 (?dhm=...)
  const params = url.search;

  // 2. 目標阿里雲地址 (直接敲 IP 避開 HTTPS 強制轉向)
  const targetUrl = `http://47.96.230.2:9997/qqyxNew/addDHM${params}`;

  try {
    // 3. 發起後端連線，設定 10 秒超時防止掛死
    const response = await fetch(targetUrl, {
      method: "GET", 
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        "Accept": "*/*",
        "Connection": "keep-alive"
      },
      // 避免阿里雲伺服器太慢導致前端一直轉圈圈
      signal: AbortSignal.timeout(10000) 
    });

    // 4. 抓取阿里雲回傳的原始文字
    const resultText = await response.text();

    // 5. 回傳給前端 (如果阿里雲沒回東西，我們補一個 [OK] 讓前端知道有通)
    return new Response(resultText || "Cloudflare: 請求已送達伺服器", {
      status: 200,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "text/plain; charset=utf-8",
        "Cache-Control": "no-cache"
      }
    });

  } catch (e) {
    // 如果連不上 IP (例如阿里雲掛了或防火牆擋掉)
    return new Response(`[代理連線失敗]: ${e.message}`, { 
      status: 500,
      headers: { "Access-Control-Allow-Origin": "*" }
    });
  }
}
