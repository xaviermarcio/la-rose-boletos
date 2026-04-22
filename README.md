# 🌸 La Rose — Gestor de Boletos

> *Construído do zero por Márcio Xavier, para resolver um problema real do dia a dia.*

---

## A história por trás do projeto

Sou Márcio, gestor da La Rose, e este sistema nasceu de uma necessidade simples: controlar os boletos das duas lojas, saber o que vence, o que foi pago, e facilitar a vida de quem faz os pagamentos — mandando tudo formatado direto no WhatsApp.

Antes era tudo no papel, em conversa perdida no WhatsApp ou planilha desatualizada. Decidi aprender a construir algo do zero que resolvesse isso de verdade. Cada linha de código aqui foi pensada para a realidade da La Rose.

---

## O que o sistema faz

**Fluxo completo — NFe + Boleto**
Sobe a foto da Nota Fiscal. O sistema lê a chave de 44 dígitos e identifica automaticamente se é Loja 1 ou Loja 2. Depois você sobe o boleto — o sistema extrai o código, valor e vencimento. Confere, ajusta e salva no Firebase.

**Fluxo só boleto**
Quando não tem a NFe em mãos, você escolhe a loja manualmente e sobe só o boleto (foto JPG/PNG ou PDF).

**Dois botões de envio separados**
O template é dividido em duas mensagens. O primeiro botão copia as informações do boleto (loja, fornecedor, valor, vencimento). O segundo copia a linha digitável limpa — só números, sem pontos e espaços — pronta para colar direto no app bancário sem quebrar linha.

**Calendário**
Visualização mensal dos boletos organizados por data de vencimento. Clique em qualquer dia para ver os boletos e agir diretamente.

**Código Rápido**
Quando mandam só o boleto e você precisa só do código. Sobe a foto ou PDF, extrai o código na hora e copia. Sem salvar nada no banco.

**Histórico**
Todo template que você envia fica salvo na aba Histórico para consulta futura.

---

## Tecnologias utilizadas

- **Backend:** Python com FastAPI — o servidor que processa as imagens e se comunica com o Firebase
- **OCR:** Tesseract + OpenCV + pytesseract — lê as imagens e extrai os dados automaticamente
- **Banco de dados:** Firebase Firestore — os dados ficam na nuvem, acessíveis de qualquer lugar com internet
- **Frontend:** HTML + JavaScript + Barlow — interface que roda no navegador
- **PWA:** O sistema pode ser instalado como app no celular e no computador

---

## Estrutura de arquivos

```
la-rose-boletos/
├── README.md                      ← este arquivo
├── .env                           ← suas configurações locais (nunca vai pro GitHub)
├── .env.exemplo                   ← modelo para criar o .env
├── .gitignore                     ← arquivos que o Git ignora
├── iniciar.bat                    ← inicia o sistema (use no dia a dia)
├── configurar.bat                 ← configura tudo do zero (use na primeira vez)
├── requirements.txt               ← lista de dependências Python
│
├── backend/
│   ├── main.py                    ← servidor FastAPI com todas as rotas
│   ├── ocr_engine.py              ← motor de OCR e extração de dados
│   └── firebase-key.json          ← sua chave privada do Firebase (você baixa)
│
└── frontend/
    ├── index.html                 ← interface completa
    ├── app.js                     ← lógica JavaScript
    ├── firebase-config.js         ← suas credenciais do Firebase (você cria)
    ├── firebase-config.exemplo.js ← modelo para criar o firebase-config.js
    ├── manifest.json              ← configuração PWA
    ├── sw.js                      ← Service Worker para cache offline
    └── icons/
        ├── icon-192.png           ← ícone do app
        └── icon-512.png           ← ícone do app maior
```

---

## Instalação completa — do zero

Use este guia sempre que formatar o notebook ou instalar em um PC novo.

> **Atalho:** Se preferir não fazer manualmente, dê duplo clique no `configurar.bat` como **Administrador** (botão direito → Executar como administrador) e ele instala o Tesseract e o Poppler automaticamente.

---

### Passo 1 — Instalar o Python

Acesse `https://python.org/downloads` e baixe a versão mais recente.

Durante a instalação, **antes de clicar em qualquer coisa**, marque obrigatoriamente a opção **"Add Python to PATH"** que fica na parte de baixo da janela. Sem isso o Python não funciona no terminal.

Para confirmar que funcionou, abra o terminal e rode:
```
python --version
```
Deve aparecer algo como `Python 3.12.x`.

---

### Passo 2 — Instalar o Tesseract OCR

O Tesseract é o motor que lê o texto das imagens de NFe e boletos. Sem ele o sistema roda em modo simulação — funciona mas não lê imagens reais.

#### Opção A — Automático (recomendado)

Dê duplo clique no `configurar.bat` como **Administrador**. Ele baixa e instala tudo automaticamente. Pule para o Passo 3.

#### Opção B — Manual (se o bat não funcionar)

**1.** Acesse `https://github.com/UB-Mannheim/tesseract/wiki`

**2.** Clique no link de download do instalador Windows 64-bit — o arquivo termina em `.exe` e tem um nome parecido com `tesseract-ocr-w64-setup-5.4.0.exe`

**3.** Abra o instalador. Na tela de seleção de componentes:
- Expanda **"Additional language data (download)"**
- Marque **"Portuguese"**
- Mantenha o caminho padrão: `C:\Program Files\Tesseract-OCR`

**4.** Conclua a instalação normalmente.

**5.** Adicione o Tesseract ao PATH do Windows para que o sistema consiga encontrá-lo:
- Pressione `Win + R`, digite `sysdm.cpl` e pressione Enter
- Clique em **"Configurações avançadas do sistema"**
- Clique em **"Variáveis de Ambiente"**
- Na seção **"Variáveis do sistema"** encontre a variável **"Path"** e clique em **"Editar"**
- Clique em **"Novo"** e adicione: `C:\Program Files\Tesseract-OCR`
- Clique OK em todas as janelas

**6.** Feche todos os terminais abertos e abra um novo terminal para o PATH ser reconhecido.

**7.** Confirme que funcionou:
```
tesseract --version
```
Deve aparecer algo como `tesseract v5.4.0`.

**8.** Confirme que o português foi instalado:
```
tesseract --list-langs
```
Deve aparecer `por` na lista.

#### Se o Tesseract não aparecer após instalação

Às vezes o Windows não reconhece mesmo após adicionar ao PATH. Nesse caso, abra o arquivo `backend/ocr_engine.py` e adicione o caminho diretamente. Encontre a linha:

```python
caminhos_possiveis = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
```

E confirme que o caminho bate com onde o Tesseract foi instalado no seu PC. Se instalou em outro lugar, adicione o caminho correto na lista.

---

### Passo 3 — Instalar o Poppler (para leitura de PDF)

O Poppler permite que o sistema processe boletos enviados em formato PDF.

#### Opção A — Automático (recomendado)

O `configurar.bat` já instala o Poppler automaticamente junto com o Tesseract.

#### Opção B — Manual

**1.** Acesse `https://github.com/oschwartz10612/poppler-windows/releases`

**2.** Baixe o `.zip` mais recente (algo como `Release-24.08.0-0.zip`)

**3.** Extraia o conteúdo em `C:\poppler` — certifique-se que a estrutura fique assim:
```
C:\poppler\
└── Library\
    └── bin\
        ├── pdftoppm.exe
        ├── pdfinfo.exe
        └── ...
```

**4.** Adicione ao PATH do Windows seguindo o mesmo processo do Tesseract, mas com o caminho: `C:\poppler\Library\bin`

**5.** Feche e reabra o terminal. Confirme:
```
pdftoppm -v
```

---

### Passo 4 — Baixar o projeto

**Se você tem o repositório no GitHub:**
```
git clone https://github.com/SEU_USUARIO/la-rose-boletos.git
cd la-rose-boletos
```

**Se não**, copie a pasta do projeto para um lugar fácil como `C:\Users\SEU_NOME\Documents\la-rose-boletos`.

---

### Passo 5 — Instalar as dependências Python

Abra o terminal **dentro da pasta raiz do projeto** (onde fica o `requirements.txt`) e rode:

```
pip install -r requirements.txt

python -m pip install -r requirements.txt
```

**O que esse comando faz:** o `pip` é o gerenciador de pacotes do Python. O `-r requirements.txt` manda ele ler o arquivo que lista todas as bibliotecas necessárias e instalar cada uma automaticamente. Você só precisa rodar esse comando uma vez por máquina.

Para confirmar:
```
pip list
```
Procure na lista: fastapi, uvicorn, pytesseract, opencv-python-headless, firebase-admin, pdf2image.

---

### Passo 6 — Configurar o Firebase

**6.1 — Credenciais do frontend (firebase-config.js)**

Acesse `https://console.firebase.google.com`, abra o projeto `larose-boletos`. Vá em Configurações do projeto ⚙️ → Seus apps → clique no app web. Copie o objeto `firebaseConfig`.

Na pasta `frontend/`, copie `firebase-config.exemplo.js`, renomeie para `firebase-config.js` e substitua os valores pelos seus dados reais.

**6.2 — Chave de serviço do backend (firebase-key.json)**

No Firebase Console vá em Configurações do projeto → aba "Contas de serviço" → "Gerar nova chave privada". Renomeie o arquivo baixado para `firebase-key.json` e coloque dentro da pasta `backend/`.

---

### Passo 7 — Criar o arquivo .env

Na raiz do projeto, copie `.env.exemplo` e renomeie para `.env`. Confirme que está assim:
```
FIREBASE_KEY_PATH=firebase-key.json
```

---

### Passo 8 — Iniciar o sistema

Dê duplo clique no `iniciar.bat`. Quando aparecer:
```
Uvicorn running on http://0.0.0.0:8000
OCR: Ativo
Firebase: Configurado
```

Abra o Chrome e acesse `http://localhost:8000`.

---

## Uso no dia a dia

O único passo necessário após a configuração inicial:

1. Duplo clique no `iniciar.bat`
2. Acessar `http://localhost:8000` no Chrome

O sistema funciona em qualquer cidade desde que o notebook esteja com você e conectado à internet. A internet é necessária para o Firebase — o OCR funciona localmente.

---

## Acessar pelo celular

Com o servidor rodando, o IP aparece no canto superior direito da interface. Qualquer celular na mesma rede Wi-Fi acessa pelo IP exibido:
```
http://192.168.0.50:8000
```

---

## Lojas cadastradas

| Loja | CNPJ | Identificação na NFe |
|------|------|----------------------|
| Loja 1 — Matriz | 37.319.385/0001-64 | `37319385000164` |
| Loja 2 — Filial | 37.319.385/0002-45 | `37319385000245` |

---

## Template gerado para WhatsApp

**Mensagem 1 — Informações:**
```
🏪 LA ROSE - Loja 1 (Matriz)
📍 CNPJ: 37.319.385/0001-64

📦 FORNECEDOR: DISTRIBUIDORA EXEMPLO LTDA
💳 PARCELA: 1/1
🗓️ VENCIMENTO: 23/04/2026
💰 VALOR: R$ 1.250,00

✅ Enviado por Márcio Xavier - Gestor La Rose
```

**Mensagem 2 — Linha digitável (só números):**
```
23793381286000782713694000063305892340000125000
```

---

## Próximas melhorias planejadas

- [ ] Autenticação com e-mail e senha via Firebase Auth
- [ ] Relatório mensal em PDF por loja
- [ ] Notificação push quando um boleto vencer em 3 dias
- [ ] Histórico de pagamentos com gráfico mensal
- [ ] Modo offline com sincronização posterior

---

## Licença

Projeto pessoal desenvolvido por **Márcio Xavier — Gestor La Rose**.
Uso interno. Todos os direitos reservados.

---

*Feito com ☕ e muita vontade de aprender.*
