"use strict";

import { firebaseConfig } from "./firebase-config.js";
import { initializeApp }
  from "https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js";
import { getFirestore, collection, addDoc, getDocs,
         doc, updateDoc, deleteDoc, query, orderBy,
         where, serverTimestamp }
  from "https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js";

const firebaseApp = initializeApp(firebaseConfig);
const db          = getFirestore(firebaseApp);

// ═══════════════════════════════════════════════════════════════
//  UTILITÁRIO — COPIAR TEXTO
//  Funciona tanto em localhost quanto pelo IP da rede
// ═══════════════════════════════════════════════════════════════
async function copiarTexto(texto) {
  // Tenta clipboard API moderna (localhost e https)
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(texto);
      return true;
    } catch (e) {
      // Fallback abaixo
    }
  }
  // Fallback via execCommand (funciona no IP da rede local)
  try {
    const el = document.createElement("textarea");
    el.value = texto;
    el.style.cssText = "position:fixed;top:-9999px;left:-9999px;opacity:0";
    document.body.appendChild(el);
    el.focus();
    el.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(el);
    if (ok) return true;
  } catch (e) {
    // Nada
  }
  return false;
}

// ═══════════════════════════════════════════════════════════════
//  ESTADO
// ═══════════════════════════════════════════════════════════════
const E = {
  boletos:      [],
  historico:    [],
  filtroLoja:   "todas",
  filtroStatus: "todos",
  filtroLojaH:  "todas",
  termoBusca:   "",
  termoHist:    "",
  calAno:       new Date().getFullYear(),
  calMes:       new Date().getMonth(),
  wizard: {
    fluxo:"", loja_id:"", loja_nome:"", cnpj_loja:"",
    chave_nfe:"", fornecedor:"", valor:null, vencimento:"",
    linha:"", data_emissao:"", numero_nota:"",
  }
};

let API  = "http://localhost:8000";
let _exp = { linha:"", valor:null, vencimento:"" };

// ═══════════════════════════════════════════════════════════════
//  BOOT
// ═══════════════════════════════════════════════════════════════
document.addEventListener("DOMContentLoaded", async () => {
  await carregarConfig();
  await carregarBoletos();
  await carregarHistorico();
  configurarEventos();
  registrarSW();
});

// ═══════════════════════════════════════════════════════════════
//  CONFIG
// ═══════════════════════════════════════════════════════════════
async function carregarConfig() {
  try {
    const d = await api("GET", "/api/config");
    API = `http://${d.ip}:${d.porta}`;
    const dot = document.getElementById("dot");
    const lbl = document.getElementById("dot-lbl");
    dot.className   = d.ocr_ativo ? "dot ativo" : "dot sim";
    lbl.textContent = d.ocr_ativo ? "OCR Ativo" : "OCR Simulado";
    set("ip-display", `http://${d.ip}:${d.porta}`);
  } catch {
    toast("Backend offline. Inicie com iniciar.bat", "erro");
  }
}

// ═══════════════════════════════════════════════════════════════
//  API
// ═══════════════════════════════════════════════════════════════
async function api(metodo, rota, corpo = null) {
  const opts = { method:metodo, headers:{"Content-Type":"application/json"} };
  if (corpo) opts.body = JSON.stringify(corpo);
  const r = await fetch(`${API}${rota}`, opts);
  if (!r.ok) {
    const e = await r.json().catch(() => ({detail:"Erro desconhecido"}));
    throw new Error(e.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

async function enviarImagem(rota, arquivo) {
  const fd = new FormData();
  fd.append("arquivo", arquivo);
  const r = await fetch(`${API}${rota}`, {method:"POST", body:fd});
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    throw new Error(e.detail || "Erro ao processar");
  }
  return r.json();
}

// ═══════════════════════════════════════════════════════════════
//  ABAS
// ═══════════════════════════════════════════════════════════════
function mudarAba(nome, btn) {
  document.querySelectorAll(".pagina").forEach(p => p.classList.remove("ativa"));
  document.querySelectorAll(".aba").forEach(b => b.classList.remove("ativa"));
  document.getElementById(`pag-${nome}`).classList.add("ativa");
  btn.classList.add("ativa");
  if (nome === "calendario") renderCalendario();
}

// ═══════════════════════════════════════════════════════════════
//  BOLETOS
// ═══════════════════════════════════════════════════════════════
async function carregarBoletos() {
  skeleton();
  try {
    const snap = await getDocs(
      query(collection(db,"boletos"), orderBy("vencimento","asc"))
    );
    E.boletos = [];
    snap.forEach(d => E.boletos.push({id:d.id, ...d.data()}));
  } catch (err) {
    console.warn("Firestore:", err);
    try {
      const d = await api("GET", "/api/boletos");
      E.boletos = d.boletos || [];
    } catch { E.boletos = []; }
  }
  renderBoletos();
  atualizarStats();
}

function boletosVisiveis() {
  return E.boletos.filter(b => {
    if (E.filtroLoja   !== "todas" && b.loja_id !== E.filtroLoja)             return false;
    if (E.filtroStatus !== "todos" && b.status  !== E.filtroStatus)            return false;
    if (E.termoBusca   && !b.fornecedor?.toLowerCase().includes(E.termoBusca)) return false;
    return true;
  });
}

function renderBoletos() {
  const grid  = document.getElementById("grid");
  const lista = boletosVisiveis();
  grid.innerHTML = lista.length
    ? lista.map(cardHTML).join("")
    : `<div class="vazio"><div class="vazio__icon">📄</div>
       <h3>Nenhum boleto encontrado</h3>
       <p>Clique em <strong>"+ Novo"</strong> para começar.</p></div>`;
}

function cardHTML(b) {
  const hoje = new Date(); hoje.setHours(0,0,0,0);
  const venc = dataBR(b.vencimento);
  const diff = Math.ceil((venc - hoje) / 86400000);
  const pago = b.status === "PAGO";

  let urg = "";
  if (!pago) {
    if      (diff < 0)   urg = `<span class="urg atrasado">Vencido ${Math.abs(diff)}d</span>`;
    else if (diff === 0) urg = `<span class="urg hoje">Hoje!</span>`;
    else if (diff <= 3)  urg = `<span class="urg urgente">${diff}d</span>`;
    else                 urg = `<span class="urg ok">${diff}d</span>`;
  }

  const sr = (!pago && diff < 0) ? "vencido" : b.status.toLowerCase();

  return `
  <article class="card card--${sr}" id="card-${b.id}">
    <div class="card__corpo">
      <div class="card__top">
        <div style="min-width:0;flex:1">
          <div class="card__nome">${esc(b.fornecedor)}</div>
        </div>
        <div class="card__valor">${brl(b.valor)}</div>
      </div>
      <div class="card__tags">
        <span class="loja loja--${b.loja_id}">${esc(b.loja_nome)}</span>
        <span class="stag stag--${sr}">${sr.toUpperCase()}</span>
        ${urg}
      </div>
      <div class="card__meta">
        <span>🗓 ${b.vencimento}</span>
        <span>💳 ${b.parcela}</span>
        <span>📍 ${esc(b.cnpj_loja)}</span>
      </div>
      <div class="card__linha">${esc(b.linha_digitavel) || "—"}</div>
      ${pago
        ? `<div class="card__acoes-row">
             <button class="btn-tpl del-btn" onclick="remover('${b.id}')">🗑 Remover</button>
           </div>`
        : `<div class="card__acoes">
             <button class="btn-tpl info"   onclick="copiarInfo('${b.id}')">📋 Copiar Info</button>
             <button class="btn-tpl codigo" onclick="copiarLinha('${b.id}')">🔢 Copiar Linha</button>
           </div>
           <div class="card__acoes-row" style="margin-top:.4rem">
             <button class="btn-tpl pago-btn" onclick="marcarPago('${b.id}')">✔ Marcar como Pago</button>
             <button class="btn-tpl del-btn"  onclick="remover('${b.id}')">🗑</button>
           </div>`
      }
    </div>
  </article>`;
}

function skeleton() {
  document.getElementById("grid").innerHTML =
    Array(3).fill(`<div class="card sk">
      <div class="sk-l sk-70"></div>
      <div class="sk-l sk-40"></div>
      <div class="sk-l sk-90"></div>
    </div>`).join("");
}

// ═══════════════════════════════════════════════════════════════
//  STATS
// ═══════════════════════════════════════════════════════════════
function atualizarStats() {
  const hoje  = new Date(); hoje.setHours(0,0,0,0);
  const pend  = E.boletos.filter(b => b.status === "PENDENTE");
  const vhoje = E.boletos.filter(b =>
    +dataBR(b.vencimento) === +hoje && b.status !== "PAGO"
  );
  set("s-total", E.boletos.length);
  set("s-pend",  pend.length);
  set("s-valor", brl(pend.reduce((a,b) => a + (b.valor||0), 0)));
  set("s-hoje",  vhoje.length);
}

// ═══════════════════════════════════════════════════════════════
//  FILTROS
// ═══════════════════════════════════════════════════════════════
function setLoja(btn)     { E.filtroLoja   = btn.dataset.loja; ativar(btn,"fl"); renderBoletos(); }
function setStatus(btn)   { E.filtroStatus = btn.dataset.st;   ativar(btn,"fs"); renderBoletos(); }
function setBusca(v)      { E.termoBusca   = v.trim().toLowerCase(); renderBoletos(); }
function setLojaHist(btn) { E.filtroLojaH  = btn.dataset.loja; ativar(btn,"fh"); renderHistorico(); }
function setBuscaHist(v)  { E.termoHist    = v.trim().toLowerCase(); renderHistorico(); }
function ativar(btn, g) {
  document.querySelectorAll(`[data-g="${g}"]`)
    .forEach(b => b.classList.toggle("ativo", b === btn));
}

// ═══════════════════════════════════════════════════════════════
//  CALENDÁRIO
// ═══════════════════════════════════════════════════════════════
const MESES = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
               "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"];
const DIAS_SEMANA = ["Dom","Seg","Ter","Qua","Qui","Sex","Sáb"];

function calNavegar(dir) {
  E.calMes += dir;
  if (E.calMes > 11) { E.calMes = 0;  E.calAno++; }
  if (E.calMes < 0)  { E.calMes = 11; E.calAno--; }
  renderCalendario();
}

function renderCalendario() {
  set("cal-titulo", `${MESES[E.calMes]} ${E.calAno}`);
  const grid = document.getElementById("cal-grid");
  const hoje = new Date(); hoje.setHours(0,0,0,0);
  const primeiroDia = new Date(E.calAno, E.calMes, 1);
  const ultimoDia   = new Date(E.calAno, E.calMes + 1, 0);
  const inicio      = primeiroDia.getDay();

  const idx = {};
  E.boletos.forEach(b => {
    if (!b.vencimento) return;
    const [d,m,a] = b.vencimento.split("/");
    if (parseInt(m)-1 === E.calMes && parseInt(a) === E.calAno) {
      if (!idx[b.vencimento]) idx[b.vencimento] = [];
      idx[b.vencimento].push(b);
    }
  });

  let html = DIAS_SEMANA.map(d => `<div class="cal-head">${d}</div>`).join("");

  for (let i = 0; i < inicio; i++) {
    const d = new Date(E.calAno, E.calMes, -inicio + i + 1);
    html += `<div class="cal-dia outro-mes"><div class="cal-dia-num">${d.getDate()}</div></div>`;
  }

  for (let d = 1; d <= ultimoDia.getDate(); d++) {
    const data    = new Date(E.calAno, E.calMes, d);
    const chave   = formatDateBR(data);
    const boletos = idx[chave] || [];
    const ehHoje  = +data === +hoje;

    const dots = boletos.slice(0,3).map(b => {
      const diff = Math.ceil((data - hoje) / 86400000);
      const sr = b.status==="PAGO" ? "pago"
               : diff < 0 ? "venc"
               : b.status==="ENVIADO" ? "env" : "pend";
      return `<span class="cal-boleto-dot cal-dot-${sr}">${esc(b.fornecedor?.split(" ")[0]||"—")}</span>`;
    }).join("");

    const mais = boletos.length > 3 ? `<span class="cal-mais">+${boletos.length-3}</span>` : "";
    const onclick = boletos.length ? `onclick="abrirDia('${chave}')"` : "";

    html += `<div class="cal-dia${ehHoje?" hoje":""}" ${onclick}>
      <div class="cal-dia-num">${d}</div>${dots}${mais}</div>`;
  }

  const total = inicio + ultimoDia.getDate();
  const resto = total % 7 === 0 ? 0 : 7 - (total % 7);
  for (let i = 1; i <= resto; i++) {
    html += `<div class="cal-dia outro-mes"><div class="cal-dia-num">${i}</div></div>`;
  }

  grid.innerHTML = html;
}

function abrirDia(chave) {
  const boletos = E.boletos.filter(b => b.vencimento === chave);
  if (!boletos.length) return;
  set("mDia-titulo", `📅 ${chave}`);
  const hoje = new Date(); hoje.setHours(0,0,0,0);
  const lista = document.getElementById("mDia-lista");
  lista.innerHTML = boletos.map(b => {
    const diff = Math.ceil((dataBR(b.vencimento) - hoje) / 86400000);
    const sr   = b.status==="PAGO" ? "pago" : diff < 0 ? "vencido" : b.status.toLowerCase();
    return `
    <div class="dia-item ${sr}">
      <div class="dia-item-nome">${esc(b.fornecedor)}</div>
      <div class="dia-item-info">
        <span><strong>${brl(b.valor)}</strong></span>
        <span>Parcela ${b.parcela}</span>
        <span class="stag stag--${sr}">${sr.toUpperCase()}</span>
      </div>
      ${b.status !== "PAGO" ? `
      <div style="display:flex;gap:.4rem;margin-top:.6rem;flex-wrap:wrap">
        <button class="btn-tpl info"     onclick="copiarInfo('${b.id}');fecharModal('mDia')">📋 Copiar Info</button>
        <button class="btn-tpl codigo"   onclick="copiarLinha('${b.id}');fecharModal('mDia')">🔢 Copiar Linha</button>
        <button class="btn-tpl pago-btn" onclick="marcarPago('${b.id}');fecharModal('mDia')">✔ Pago</button>
      </div>` : ""}
    </div>`;
  }).join("");
  abrirModal("mDia");
}

// ═══════════════════════════════════════════════════════════════
//  MODAIS
// ═══════════════════════════════════════════════════════════════
function abrirModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.style.display = "flex";
  requestAnimationFrame(() => m.classList.add("vis"));
}

function fecharModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.classList.remove("vis");
  setTimeout(() => { m.style.display = "none"; }, 220);
}

function fecharWizard() {
  fecharModal("mWizard");
  setTimeout(resetWizard, 250);
}

function resetWizard() {
  irStep(1, true);
  E.wizard = {fluxo:"",loja_id:"",loja_nome:"",cnpj_loja:"",
              chave_nfe:"",fornecedor:"",valor:null,vencimento:"",
              linha:"",data_emissao:"",numero_nota:""};
  ["nfe-result","boleto-result","boleto-b-result"].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.style.display="none"; el.innerHTML=""; }
  });
  const b = document.getElementById("bloco-boleto");
  if (b) b.style.display = "none";
  document.getElementById("fb-completo")?.classList.remove("selecionado");
  document.getElementById("fb-soboleto")?.classList.remove("selecionado");
  ["fileNfe","fileBoleto","fileBoletoB"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = "";
  });
  ["btn-p2a","btn-p2b"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = true;
  });
}

function irStep(num, silencioso = false) {
  ["sp-1","sp-2a","sp-2b","sp-3"].forEach(id =>
    document.getElementById(id)?.classList.remove("ativo")
  );
  [1,2,3].forEach(n => {
    const el = document.getElementById(`si-${n}`);
    if (!el) return;
    el.classList.remove("ativo","ok");
    if (n < num)   el.classList.add("ok");
    if (n === num) el.classList.add("ativo");
  });
  if      (num === 1) document.getElementById("sp-1").classList.add("ativo");
  else if (num === 2) document.getElementById(E.wizard.fluxo==="soboleto"?"sp-2b":"sp-2a").classList.add("ativo");
  else if (num === 3) { document.getElementById("sp-3").classList.add("ativo"); if (!silencioso) montarFormConferencia(); }
}

function voltarStep3() { irStep(2); }

function escolherFluxo(fluxo) {
  E.wizard.fluxo = fluxo;
  document.getElementById("fb-completo").classList.toggle("selecionado", fluxo==="completo");
  document.getElementById("fb-soboleto").classList.toggle("selecionado", fluxo==="soboleto");
  setTimeout(() => irStep(2), 250);
}

// ═══════════════════════════════════════════════════════════════
//  OCR — NFe
// ═══════════════════════════════════════════════════════════════
function onDropNfe(e) {
  e.preventDefault();
  document.getElementById("dz-nfe").classList.remove("over");
  const f = e.dataTransfer.files[0];
  if (f) processarNfe(f);
}

async function processarNfe(arquivo) {
  if (!arquivo.type.startsWith("image/") && arquivo.type !== "application/pdf" && !arquivo.name?.toLowerCase().endsWith(".pdf")) { toast("Envie JPG, PNG ou PDF da NFe.","erro"); return; }
  loading("Lendo a Nota Fiscal...");
  try {
    const r = await enviarImagem("/api/ocr?tipo=NFe", arquivo);
    ocultarLoading();
    const d = r.dados || {};
    E.wizard.loja_id      = d.loja_id      || "loja1";
    E.wizard.loja_nome    = d.loja_nome    || "Loja 1 (Matriz)";
    E.wizard.cnpj_loja    = d.cnpj_loja    || "37.319.385/0001-64";
    E.wizard.chave_nfe    = d.chave_nfe    || "";
    E.wizard.data_emissao = d.data_emissao || "";
    E.wizard.numero_nota  = d.numero_nota  || "";
    if (d.fornecedor) E.wizard.fornecedor = d.fornecedor;

    const res = document.getElementById("nfe-result");
    res.style.display = "block";
    res.innerHTML = `<div class="nfe-ok">
      <div class="nfe-ok-loja">✅ ${esc(E.wizard.loja_nome)} identificada</div>
      ${E.wizard.fornecedor ? `<div style="font-size:.85rem;color:var(--pago);margin-top:.2rem">📦 ${esc(E.wizard.fornecedor)}</div>` : ""}
      ${E.wizard.chave_nfe  ? `<div class="nfe-ok-chave">Chave: ${esc(E.wizard.chave_nfe)}</div>` : ""}
      ${E.wizard.data_emissao ? `<div style="font-size:.78rem;color:var(--muted)">📅 Emissão: ${esc(E.wizard.data_emissao)}</div>` : ""}
      ${r.simulado ? `<div style="font-size:.72rem;color:var(--env)">⚠️ Modo simulação</div>` : ""}
    </div>`;
    document.getElementById("bloco-boleto").style.display = "block";
    toast("NFe processada! Agora envie o boleto.","sucesso");
  } catch (err) { ocultarLoading(); toast(`Erro na NFe: ${err.message}`,"erro"); }
}

// ═══════════════════════════════════════════════════════════════
//  OCR — Boleto 2A
// ═══════════════════════════════════════════════════════════════
function onDropBoleto(e) {
  e.preventDefault();
  document.getElementById("dz-boleto").classList.remove("over");
  const f = e.dataTransfer.files[0];
  if (f) processarBoleto(f, "2a");
}

async function processarBoleto(arquivo, origem) {
  if (!arquivo.type.startsWith("image/") && arquivo.type !== "application/pdf" && !arquivo.name?.toLowerCase().endsWith(".pdf")) { toast("Envie JPG, PNG ou PDF do boleto.","erro"); return; }
  loading("Lendo o Boleto...");
  try {
    const r = await enviarImagem("/api/ocr?tipo=Boleto", arquivo);
    ocultarLoading();
    const d = r.dados || {};
    if (d.linha_digitavel) E.wizard.linha      = d.linha_digitavel;
    if (d.valor)           E.wizard.valor      = d.valor;
    if (d.vencimento)      E.wizard.vencimento = d.vencimento;

    const resId = origem === "2a" ? "boleto-result" : "boleto-b-result";
    const res   = document.getElementById(resId);
    res.style.display = "block";
    const linha_fmt = d.linha_digitavel
      ? d.linha_digitavel.replace(/\D/g,"")
          .replace(/^(\d{5})(\d{5})(\d{5})(\d{6})(\d{5})(\d{6})(\d)(\d{14})$/,
                   "$1.$2 $3.$4 $5.$6 $7 $8")
      : "";
    const dv_status = d.linha_digitavel ? validarLinha(d.linha_digitavel) : null;
    res.innerHTML = `<div class="boleto-conferencia">
      <div class="bc-header">
        <span class="bc-ok">✅ Boleto lido</span>
        ${dv_status === true  ? '<span class="bc-valido">✔ Código válido</span>' : ""}
        ${dv_status === false ? '<span class="bc-invalido">⚠ Verifique o código</span>' : ""}
      </div>
      <div class="bc-label">Compare com o boleto físico:</div>
      <div class="bc-codigo">${esc(linha_fmt) || "Código não encontrado — preencha manualmente na próxima etapa"}</div>
      <div class="bc-meta">
        ${d.valor      ? `<span class="bc-chip">💰 ${brl(d.valor)}</span>`      : ""}
        ${d.vencimento ? `<span class="bc-chip">🗓 ${d.vencimento}</span>` : ""}
      </div>
    </div>`;
    document.getElementById(origem==="2a" ? "btn-p2a" : "btn-p2b").disabled = false;
    if (r.corrigido) {
      toast("Boleto processado! Codigo corrigido automaticamente.", "sucesso");
    } else {
      toast("Boleto processado! Confira os dados.", "sucesso");
    }
  } catch (err) { ocultarLoading(); toast(`Erro: ${err.message}`,"erro"); }
}

// ═══════════════════════════════════════════════════════════════
//  OCR — Boleto 2B
// ═══════════════════════════════════════════════════════════════
function onDropBoletoB(e) {
  e.preventDefault();
  document.getElementById("dz-boleto-b").classList.remove("over");
  const f = e.dataTransfer.files[0];
  if (f) processarBoletoB(f);
}

async function processarBoletoB(arquivo) {
  if (!arquivo.type.startsWith("image/") && arquivo.type !== "application/pdf" && !arquivo.name?.toLowerCase().endsWith(".pdf")) {
    toast("Envie JPG, PNG ou PDF do boleto.","erro");
    return;
  }
  const lp = document.getElementById("loja-manual").value.split("|");
  E.wizard.loja_id   = lp[0];
  E.wizard.loja_nome = lp[1];
  E.wizard.cnpj_loja = lp[2];
  loading("Lendo o Boleto...");
  try {
    const r    = await enviarImagem("/api/ocr?tipo=Boleto", arquivo);
    ocultarLoading();
    const d    = r.dados || {};
    if (d.linha_digitavel) E.wizard.linha      = d.linha_digitavel;
    if (d.valor)           E.wizard.valor      = d.valor;
    if (d.vencimento)      E.wizard.vencimento = d.vencimento;

    const res = document.getElementById("boleto-b-result");
    res.style.display = "block";
    const linha_fmt = d.linha_digitavel
      ? d.linha_digitavel.replace(/\D/g,"")
          .replace(/^(\d{5})(\d{5})(\d{5})(\d{6})(\d{5})(\d{6})(\d)(\d{14})$/,
                   "$1.$2 $3.$4 $5.$6 $7 $8")
      : "";
    const dv_status = d.linha_digitavel ? validarLinha(d.linha_digitavel) : null;
    res.innerHTML = `<div class="boleto-conferencia">
      <div class="bc-header">
        <span class="bc-ok">✅ Boleto lido</span>
        ${dv_status === true  ? '<span class="bc-valido">✔ Código válido</span>' : ""}
        ${dv_status === false ? '<span class="bc-invalido">⚠ Verifique o código</span>' : ""}
      </div>
      <div class="bc-label">Compare com o boleto físico:</div>
      <div class="bc-codigo">${esc(linha_fmt) || "Código não encontrado — preencha manualmente na próxima etapa"}</div>
      <div class="bc-meta">
        ${d.valor      ? `<span class="bc-chip">💰 ${brl(d.valor)}</span>`      : ""}
        ${d.vencimento ? `<span class="bc-chip">🗓 ${d.vencimento}</span>` : ""}
      </div>
    </div>`;
    document.getElementById("btn-p2b").disabled = false;
    toast("Boleto processado! Confira os dados.","sucesso");
  } catch (err) { ocultarLoading(); toast(`Erro: ${err.message}`,"erro"); }
}

// ═══════════════════════════════════════════════════════════════
//  CONFERÊNCIA
// ═══════════════════════════════════════════════════════════════
// ═══════════════════════════════════════════════════════════════
//  VALIDACAO DO CODIGO DE BARRAS (Módulo 10)
// ═══════════════════════════════════════════════════════════════
function validarLinha(linha) {
  const dig = linha.replace(/\D/g, "");
  if (dig.length !== 47) return null;

  function mod10(num) {
    let soma = 0, mult = 2;
    for (let i = num.length - 1; i >= 0; i--) {
      let r = parseInt(num[i]) * mult;
      soma += Math.floor(r / 10) + (r % 10);
      mult = mult === 2 ? 1 : 2;
    }
    const resto = soma % 10;
    return resto === 0 ? 0 : 10 - resto;
  }

  const dv1 = mod10(dig.substring(0, 9));
  const dv2 = mod10(dig.substring(10, 20));
  const dv3 = mod10(dig.substring(21, 31));

  return dv1 === parseInt(dig[9]) &&
         dv2 === parseInt(dig[20]) &&
         dv3 === parseInt(dig[31]);
}

function formatarLinha(linha) {
  const d = linha.replace(/\D/g, "");
  if (d.length !== 47) return linha;
  return `${d.slice(0,5)}.${d.slice(5,10)} ${d.slice(10,15)}.${d.slice(15,21)} ${d.slice(21,26)}.${d.slice(26,32)} ${d[32]} ${d.slice(33)}`;
}

function montarFormConferencia() {
  const w   = E.wizard;
  const div = document.getElementById("form-conf");
  const lojaOpts = [
    ["loja1|Loja 1 (Matriz)|37.319.385/0001-64","Loja 1 (Matriz)"],
    ["loja2|Loja 2 (Filial)|37.319.385/0002-45","Loja 2 (Filial)"],
  ].map(([val,txt]) =>
    `<option value="${val}" ${w.loja_id===val.split("|")[0]?"selected":""}>${txt}</option>`
  ).join("");

  div.innerHTML = `
    <div class="sec-label">📄 Nota Fiscal</div>

    <div class="fg">
      <label class="lbl">Loja</label>
      <select class="inp" id="c-loja">${lojaOpts}</select>
    </div>

    <div class="fg">
      <label class="lbl">Fornecedor</label>
      <input class="inp" id="c-forn" value="${ea(w.fornecedor)}"
             placeholder="Nome do fornecedor (ex: SAO SALVADOR ALIMENTOS SA)"/>
    </div>

    <div class="fg2">
      <div class="fg">
        <label class="lbl">Número da Nota</label>
        <input class="inp" id="c-numnota" value="${ea(w.numero_nota)}"
               placeholder="Ex: 002830937"/>
      </div>
      <div class="fg">
        <label class="lbl">Data de Emissão</label>
        <input class="inp" id="c-emissao" value="${ea(w.data_emissao)}"
               placeholder="DD/MM/AAAA"/>
      </div>
    </div>

    <div class="fg">
      <label class="lbl">Chave de Acesso (44 dígitos)</label>
      <input class="inp mono" id="c-chave" value="${ea(w.chave_nfe)}"
             style="font-size:.64rem" placeholder="44 dígitos sem espaços"/>
    </div>

    <div class="sec-label" style="margin-top:.9rem">💳 Boleto</div>

    <div class="fg">
      <label class="lbl">Linha Digitável</label>
      <input class="inp mono" id="c-linha" value="${ea(w.linha)}"
             placeholder="00000.00000 00000.000000 00000.000000 0 00000000000000"
             oninput="atualizarValidacaoLinha(this.value)"/>
      <div id="linha-status" class="linha-status-box">${gerarStatusLinha(w.linha)}</div>
      <span class="hint">Compare com o boleto físico e corrija se necessário</span>
    </div>

    <div class="fg2">
      <div class="fg">
        <label class="lbl">Vencimento</label>
        <input class="inp" id="c-venc" value="${ea(w.vencimento)}"
               placeholder="DD/MM/AAAA"/>
      </div>
      <div class="fg">
        <label class="lbl">Valor (R$)</label>
        <input class="inp" id="c-valor" type="number" step="0.01" min="0.01"
               value="${w.valor||""}"/>
      </div>
    </div>

    <div class="sec-label" style="margin-top:.9rem">📋 Parcelas</div>

    <div class="fg2">
      <div class="fg">
        <label class="lbl">Parcela Atual</label>
        <input class="inp" id="c-patual" type="number" min="1" value="1" oninput="prvParcela()"/>
      </div>
      <div class="fg">
        <label class="lbl">Total de Parcelas</label>
        <input class="inp" id="c-ptotal" type="number" min="1" value="1" oninput="prvParcela()"/>
      </div>
    </div>
    <div id="prv-parc" class="hint"></div>`;
  prvParcela();
}


function gerarStatusLinha(linha) {
  if (!linha) return "";
  const dig = linha.replace(/\D/g, "");
  if (dig.length !== 47) return `<span class="ls-aviso">⚠ ${dig.length} dígitos (esperado 47)</span>`;
  const valido = validarLinha(linha);
  const fmt = formatarLinha(linha);
  return valido
    ? `<span class="ls-ok">✔ Código válido — ${fmt}</span>`
    : `<span class="ls-erro">✗ Dígito verificador inválido — confira o código no boleto físico</span>`;
}

function atualizarValidacaoLinha(valor) {
  const el = document.getElementById("linha-status");
  if (el) el.innerHTML = gerarStatusLinha(valor);
}

function prvParcela() {
  const a = parseInt(document.getElementById("c-patual")?.value)||1;
  const t = parseInt(document.getElementById("c-ptotal")?.value)||1;
  const q = Math.max(1, t-a+1);
  set("prv-parc", q>1
    ? `📅 Serão criados ${q} registros com vencimentos a cada 30 dias.`
    : "📄 Será criado 1 registro.");
}

// ═══════════════════════════════════════════════════════════════
//  SALVAR
// ═══════════════════════════════════════════════════════════════
async function salvar() {
  const lp      = document.getElementById("c-loja").value.split("|");
  const forn    = document.getElementById("c-forn").value.trim();
  const val     = parseFloat(document.getElementById("c-valor").value);
  const venc    = document.getElementById("c-venc").value.trim();
  const lnh     = document.getElementById("c-linha").value.trim();
  const pa      = parseInt(document.getElementById("c-patual").value)||1;
  const pt      = parseInt(document.getElementById("c-ptotal").value)||1;
  const chave   = document.getElementById("c-chave")?.value.trim()   || "";
  const emissao = document.getElementById("c-emissao")?.value.trim() || "";
  const numnota = document.getElementById("c-numnota")?.value.trim() || "";

  if (!forn)                                return toast("Informe o fornecedor.","erro");
  if (!val||val<=0)                         return toast("Informe um valor válido.","erro");
  if (!/^\d{2}\/\d{2}\/\d{4}$/.test(venc)) return toast("Data inválida. Use DD/MM/AAAA.","erro");

  const btn = document.getElementById("btn-salvar");
  btn.disabled = true;
  btn.innerHTML = `<span class="spin-sm"></span> Salvando...`;

  try {
    if (lnh) {
      const linhaLimpa = lnh.replace(/[\s\.]/g,"");
      const snap = await getDocs(
        query(collection(db,"boletos"), where("linha_limpa","==",linhaLimpa))
      );
      if (!snap.empty) {
        toast("⚠️ Boleto duplicado! Esta linha já está cadastrada.","aviso");
        btn.disabled=false; btn.innerHTML="💾 Salvar";
        return;
      }
    }

    const linhaLimpa = lnh.replace(/[\s\.]/g,"");
    let vencData = parseDateBRObj(venc);

    for (let num=pa; num<=pt; num++) {
      await addDoc(collection(db,"boletos"), {
        fornecedor:      forn,
        loja_id:         lp[0],
        loja_nome:       lp[1],
        cnpj_loja:       lp[2],
        valor:           val,
        vencimento:      formatDateBR(vencData),
        linha_digitavel: num===pa ? lnh : "",
        linha_limpa:     num===pa ? linhaLimpa : "",
        parcela:         `${num}/${pt}`,
        status:          "PENDENTE",
        chave_nfe:       chave,
        data_emissao:    emissao,
        numero_nota:     numnota,
        data_criacao:    serverTimestamp(),
      });
      vencData = new Date(vencData.getTime() + 30*86400000);
    }

    fecharWizard();
    toast(`✅ ${pt-pa+1} boleto(s) salvo(s)!`,"sucesso");
    await carregarBoletos();
  } catch (err) {
    toast(`Erro ao salvar: ${err.message}`,"erro");
  } finally {
    btn.disabled=false; btn.innerHTML="💾 Salvar";
  }
}

// ═══════════════════════════════════════════════════════════════
//  AÇÕES NOS CARDS
// ═══════════════════════════════════════════════════════════════
async function copiarInfo(id) {
  const b = E.boletos.find(x => x.id===id);
  if (!b) return;
  const info = (() => {
    const linhas = [
      `🏪 LA ROSE - ${b.loja_nome}`,
      `📍 CNPJ: ${b.cnpj_loja}`,
      ``,
      `📦 FORNECEDOR: ${b.fornecedor}`,
    ];
    if (b.numero_nota)  linhas.push(`📝 NOTA: Nº ${b.numero_nota}`);
    if (b.data_emissao) linhas.push(`📅 EMISSÃO: ${b.data_emissao}`);
    if (b.chave_nfe)    linhas.push(`🔑 CHAVE: ${b.chave_nfe}`);
    linhas.push(``);
    linhas.push(`💳 PARCELA: ${b.parcela}`);
    linhas.push(`🗓️ VENCIMENTO: ${b.vencimento}`);
    linhas.push(`💰 VALOR: ${brl(b.valor)}`);
    linhas.push(``);
    linhas.push(`✅ Enviado por Márcio Xavier - Gestor La Rose`);
    return linhas.join("\n");
  })()

  const ok = await copiarTexto(info);
  if (!ok) { toast("Erro ao copiar. Tente pelo localhost:8000","erro"); return; }

  try {
    await updateDoc(doc(db,"boletos",id), {status:"ENVIADO"});
    await addDoc(collection(db,"historico"), {
      boleto_id:  id,
      fornecedor: b.fornecedor,
      loja_id:    b.loja_id,
      loja_nome:  b.loja_nome,
      cnpj_loja:  b.cnpj_loja,
      parcela:    b.parcela,
      vencimento: b.vencimento,
      valor:      b.valor,
      linha:      b.linha_digitavel,
      template:   info,
      enviado_em: serverTimestamp(),
    });
    toast("📋 Informações copiadas!","sucesso");
    await carregarBoletos();
    await carregarHistorico();
  } catch (err) { toast(`Erro: ${err.message}`,"erro"); }
}

async function copiarLinha(id) {
  const b = E.boletos.find(x => x.id===id);
  if (!b) return;
  if (!b.linha_digitavel) { toast("Este boleto não tem linha digitável.","aviso"); return; }
  const linhaLimpa = b.linha_digitavel.replace(/\D/g,"");
  const ok = await copiarTexto(linhaLimpa);
  if (ok) toast("🔢 Linha copiada (só números)!","sucesso");
  else    toast("Erro ao copiar. Tente pelo localhost:8000","erro");
}

async function marcarPago(id) {
  if (!confirm("Confirmar pagamento deste boleto?")) return;
  try {
    await updateDoc(doc(db,"boletos",id), {status:"PAGO"});
    toast("✅ Marcado como PAGO!","sucesso");
    await carregarBoletos();
    if (document.getElementById("pag-calendario")?.classList.contains("ativa"))
      renderCalendario();
  } catch (err) { toast(`Erro: ${err.message}`,"erro"); }
}

async function remover(id) {
  if (!confirm("Remover este boleto permanentemente?")) return;
  try {
    await deleteDoc(doc(db,"boletos",id));
    toast("🗑 Removido.","info");
    await carregarBoletos();
  } catch (err) { toast(`Erro: ${err.message}`,"erro"); }
}

// ═══════════════════════════════════════════════════════════════
//  HISTÓRICO
// ═══════════════════════════════════════════════════════════════
async function carregarHistorico() {
  try {
    const snap = await getDocs(
      query(collection(db,"historico"), orderBy("enviado_em","desc"))
    );
    E.historico = [];
    snap.forEach(d => E.historico.push({id:d.id, ...d.data()}));
    set("badge-hist", E.historico.length);
    renderHistorico();
  } catch (err) { console.warn("Histórico:", err); }
}

function historicoVisiveis() {
  return E.historico.filter(h => {
    if (E.filtroLojaH!=="todas" && h.loja_id!==E.filtroLojaH)           return false;
    if (E.termoHist && !h.fornecedor?.toLowerCase().includes(E.termoHist)) return false;
    return true;
  });
}

function renderHistorico() {
  const grid  = document.getElementById("grid-historico");
  const lista = historicoVisiveis();
  if (!lista.length) {
    grid.innerHTML = `<div class="vazio"><div class="vazio__icon">📋</div>
      <h3>Histórico vazio</h3>
      <p>Cada vez que você copiar as informações de um boleto o registro aparece aqui.</p></div>`;
    return;
  }
  grid.innerHTML = lista.map(h => {
    const data = h.enviado_em?.toDate ? h.enviado_em.toDate().toLocaleString("pt-BR") : "—";
    const linha_limpa = (h.linha || "").replace(/\D/g, "");
    const linha_fmt   = linha_limpa.length === 47
      ? `${linha_limpa.slice(0,5)}.${linha_limpa.slice(5,10)} ${linha_limpa.slice(10,15)}.${linha_limpa.slice(15,21)} ${linha_limpa.slice(21,26)}.${linha_limpa.slice(26,32)} ${linha_limpa[32]} ${linha_limpa.slice(33)}`
      : (h.linha || "");

    return `
    <div class="card-hist">
      <div class="ch-header">
        <span class="ch-nome">${esc(h.fornecedor)}</span>
        <span class="loja loja--${h.loja_id}">${esc(h.loja_nome)}</span>
        <span class="stag stag--enviado">Enviado</span>
        <span class="ch-data">${data}</span>
      </div>
      <div class="ch-pre">${esc(h.template)}</div>
      ${h.linha ? `
      <div class="ch-codigo-wrap">
        <div class="ch-codigo-label">🔢 Código do boleto</div>
        <div class="ch-codigo">${esc(linha_fmt)}</div>
        <button class="ch-copiar-linha" onclick="copiarLinhaHist('${h.id}')">
          Copiar só o código
        </button>
      </div>` : ""}
      <div class="ch-acoes">
        <button class="btn-pri" style="font-size:.78rem;padding:.35rem .9rem"
                onclick="copiarTemplateHist('${h.id}')">📋 Copiar novamente</button>
        <button class="btn-sec" style="font-size:.78rem;padding:.35rem .9rem"
                onclick="deletarHist('${h.id}')">🗑 Remover</button>
      </div>
    </div>`;
  }).join("");
}

async function copiarLinhaHist(id) {
  const h = E.historico.find(x => x.id===id);
  if (!h || !h.linha) return;
  const ok = await copiarTexto(h.linha.replace(/\D/g,""));
  if (ok) toast("🔢 Código copiado (só números)!","sucesso");
  else    toast("Erro ao copiar.","erro");
}

async function copiarTemplateHist(id) {
  const h = E.historico.find(x => x.id===id);
  if (!h) return;
  const ok = await copiarTexto(h.template);
  if (ok) toast("📋 Template copiado!","sucesso");
  else    toast("Erro ao copiar.","erro");
}

async function deletarHist(id) {
  if (!confirm("Remover este item do histórico?")) return;
  try {
    await deleteDoc(doc(db,"historico",id));
    toast("🗑 Removido.","info");
    await carregarHistorico();
  } catch (err) { toast(`Erro: ${err.message}`,"erro"); }
}

// ═══════════════════════════════════════════════════════════════
//  MODO EXPRESSO
// ═══════════════════════════════════════════════════════════════
function onDropExp(e) {
  e.preventDefault();
  document.getElementById("dz-exp").classList.remove("over");
  const f = e.dataTransfer.files[0];
  if (f) processarExpresso(f);
}

async function processarExpresso(arquivo) {
  if (!arquivo.type.startsWith("image/") && arquivo.type !== "application/pdf" && !arquivo.name?.toLowerCase().endsWith(".pdf")) {
    toast("Envie JPG, PNG ou PDF.","erro");
    return;
  }
  document.getElementById("exp-resultado").style.display = "none";
  loading("Extraindo código...");
  try {
    const r = await enviarImagem("/api/codigo-rapido", arquivo);
    ocultarLoading();
    _exp = {linha:r.linha_digitavel||"", valor:r.valor, vencimento:r.vencimento||""};

    const aviso = document.getElementById("exp-aviso");
    if (!r.sucesso || !r.linha_digitavel) {
      aviso.textContent   = r.aviso || "Código não encontrado.";
      aviso.style.display = "block";
    } else {
      aviso.style.display = "none";
    }

    set("exp-linha", (_exp.linha).replace(/\D/g,"") || "Não encontrado");
    const partes = [];
    if (r.valor)      partes.push(`💰 ${brl(r.valor)}`);
    if (r.vencimento) partes.push(`🗓 ${r.vencimento}`);
    if (r.simulado)   partes.push(`⚠️ Simulado`);
    set("exp-meta", partes.join("  ·  "));

    const res = document.getElementById("exp-resultado");
    res.style.display = "flex";
    res.style.flexDirection = "column";
  } catch (err) { ocultarLoading(); toast(`Erro: ${err.message}`,"erro"); }
}

async function copiarCodigoRapido() {
  if (!_exp.linha) { toast("Nenhum código para copiar.","aviso"); return; }
  const ok = await copiarTexto(_exp.linha.replace(/\D/g,""));
  if (ok) toast("🔢 Linha digitável copiada!","sucesso");
  else    toast("Erro ao copiar.","erro");
}

async function copiarTemplateRapido() {
  if (!_exp.linha) { toast("Nenhum código para copiar.","aviso"); return; }
  const txt = [
    `💳 BOLETO LA ROSE`,
    _exp.vencimento ? `🗓️ VENCIMENTO: ${_exp.vencimento}` : "",
    _exp.valor      ? `💰 VALOR: ${brl(_exp.valor)}`      : "",
    ``,
    `🔢 LINHA DIGITÁVEL:`,
    _exp.linha.replace(/\D/g,""),
    ``,
    `✅ Enviado por Márcio Xavier - Gestor La Rose`,
  ].filter(Boolean).join("\n");
  const ok = await copiarTexto(txt);
  if (ok) toast("📤 Template copiado!","sucesso");
  else    toast("Erro ao copiar.","erro");
}

// ═══════════════════════════════════════════════════════════════
//  TOAST / LOADING
// ═══════════════════════════════════════════════════════════════
function toast(msg, tipo="info") {
  const c = document.getElementById("toasts");
  const t = document.createElement("div");
  t.className   = `toast toast--${tipo}`;
  t.textContent = msg;
  c.appendChild(t);
  requestAnimationFrame(() => t.classList.add("vis"));
  setTimeout(() => { t.classList.remove("vis"); setTimeout(()=>t.remove(),300); }, 4200);
}

function loading(txt="Aguarde...") {
  set("load-txt", txt);
  document.getElementById("loading").style.display = "flex";
}
function ocultarLoading() {
  document.getElementById("loading").style.display = "none";
}

// ═══════════════════════════════════════════════════════════════
//  EVENTOS
// ═══════════════════════════════════════════════════════════════
function configurarEventos() {
  document.getElementById("fileNfe")
    .addEventListener("change", e => { if (e.target.files[0]) processarNfe(e.target.files[0]); });
  document.getElementById("fileBoleto")
    .addEventListener("change", e => { if (e.target.files[0]) processarBoleto(e.target.files[0],"2a"); });
  document.getElementById("fileBoletoB")
    .addEventListener("change", e => { if (e.target.files[0]) processarBoletoB(e.target.files[0]); });
  document.getElementById("fileExp")
    .addEventListener("change", e => { if (e.target.files[0]) processarExpresso(e.target.files[0]); });
  // Wizard so fecha pelo botao X — nao fecha ao clicar no overlay
  // Isso evita fechar acidentalmente ao digitar ou selecionar campos
  document.getElementById("mWizard")
    .addEventListener("mousedown", e => {
      if (e.target === document.getElementById("mWizard")) {
        e.preventDefault(); // nao fecha, apenas previne foco perdido
      }
    });
  document.getElementById("mDia")
    .addEventListener("click", e => { if (e.target===document.getElementById("mDia")) fecharModal("mDia"); });

  let t1, t2;
  const b1 = document.getElementById("busca");
  const b2 = document.getElementById("busca-hist");
  if (b1) b1.addEventListener("input", e => { clearTimeout(t1); t1=setTimeout(()=>setBusca(e.target.value),300); });
  if (b2) b2.addEventListener("input", e => { clearTimeout(t2); t2=setTimeout(()=>setBuscaHist(e.target.value),300); });
}

// ═══════════════════════════════════════════════════════════════
//  SERVICE WORKER
// ═══════════════════════════════════════════════════════════════
function registrarSW() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js")
      .then(r => console.log("[PWA] SW:", r.scope))
      .catch(e => console.warn("[PWA]", e));
  }
}

// ═══════════════════════════════════════════════════════════════
//  UTILITÁRIOS
// ═══════════════════════════════════════════════════════════════
const brl = v => new Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL"}).format(v||0);
const dataBR = s => { if(!s) return new Date(0); const[d,m,a]=s.split("/").map(Number); return new Date(a,m-1,d); };
const parseDateBRObj = s => { const[d,m,a]=s.split("/").map(Number); return new Date(a,m-1,d); };
const formatDateBR = d => `${String(d.getDate()).padStart(2,"0")}/${String(d.getMonth()+1).padStart(2,"0")}/${d.getFullYear()}`;
const esc  = s => String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
const ea   = s => esc(s).replace(/"/g,"&quot;");
const set  = (id,v) => { const el=document.getElementById(id); if(el) el.textContent=v; };

// ═══════════════════════════════════════════════════════════════
//  GLOBAIS
// ═══════════════════════════════════════════════════════════════
window.mudarAba           = mudarAba;
window.setLoja            = setLoja;
window.setStatus          = setStatus;
window.setBusca           = setBusca;
window.setLojaHist        = setLojaHist;
window.setBuscaHist       = setBuscaHist;
window.abrirModal         = abrirModal;
window.fecharModal        = fecharModal;
window.fecharWizard       = fecharWizard;
window.escolherFluxo      = escolherFluxo;
window.irStep             = irStep;
window.voltarStep3        = voltarStep3;
window.onDropNfe          = onDropNfe;
window.onDropBoleto       = onDropBoleto;
window.onDropBoletoB      = onDropBoletoB;
window.onDropExp          = onDropExp;
window.prvParcela         = prvParcela;
window.salvar             = salvar;
window.copiarInfo         = copiarInfo;
window.copiarLinha        = copiarLinha;
window.marcarPago         = marcarPago;
window.remover            = remover;
window.copiarTemplateHist = copiarTemplateHist;
window.copiarLinhaHist    = copiarLinhaHist;
window.deletarHist        = deletarHist;
window.copiarCodigoRapido = copiarCodigoRapido;
window.copiarTemplateRapido = copiarTemplateRapido;
window.calNavegar             = calNavegar;
window.atualizarValidacaoLinha = atualizarValidacaoLinha;
window.abrirDia           = abrirDia;