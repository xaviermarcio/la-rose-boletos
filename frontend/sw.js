// LA ROSE — Service Worker
// Gerencia cache para funcionamento offline e carregamento rápido.

const CACHE = "la-rose-v2";

// Lista de arquivos que serão salvos no cache na primeira visita
const ARQUIVOS = [
  "/",
  "/app.js",
  "/manifest.json",
];

// ── INSTALL ───────────────────────────────────────────────────────
// Executado uma vez quando o Service Worker é instalado.
// Abre o cache e salva os arquivos essenciais.
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ARQUIVOS))
  );
  // Ativa imediatamente sem esperar o usuário recarregar a página
  self.skipWaiting();
});

// ── ACTIVATE ──────────────────────────────────────────────────────
// Executado quando uma nova versão do SW é ativada.
// Apaga caches antigos de versões anteriores do app.
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((nomes) =>
      Promise.all(
        nomes
          .filter((n) => n !== CACHE)
          .map((n) => caches.delete(n))
      )
    )
  );
  // Assume controle de todas as abas abertas imediatamente
  self.clients.claim();
});

// ── FETCH ─────────────────────────────────────────────────────────
// Intercepta TODA requisição de rede que o app faz.
// Estratégia dividida em dois casos:
//
// CASO 1 — Chamadas à API (/api/...):
//   Sempre vai para a rede porque os dados precisam ser ao vivo.
//   Se a rede falhar, retorna mensagem de erro amigável em JSON.
//
// CASO 2 — Todo o resto (HTML, JS, CSS, fontes):
//   Tenta o cache primeiro. Se não tiver no cache, busca na rede
//   e já salva no cache para a próxima vez.
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // Caso 1: API sempre vai para a rede
  if (url.pathname.startsWith("/api/")) {
    e.respondWith(
      fetch(e.request).catch(() =>
        new Response(
          JSON.stringify({ erro: "Sem conexão. Verifique sua rede." }),
          { headers: { "Content-Type": "application/json" } }
        )
      )
    );
    return;
  }

  // Caso 2: cache primeiro, rede como fallback
  e.respondWith(
    caches.match(e.request).then((cached) => {
      if (cached) return cached;

      return fetch(e.request).then((resposta) => {
        // Clona a resposta porque ela só pode ser lida uma vez
        const clone = resposta.clone();
        caches.open(CACHE).then((cache) => {
          cache.put(e.request, clone);
        });
        return resposta;
      });
    })
  );
});