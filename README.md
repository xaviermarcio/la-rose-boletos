#  La Rose — Gestor de Boletos

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
Se preferir, basta dar duplo clique no `configurar.bat` que ele faz os passos 1 a 5 automaticamente.

---

### Passo 1 — Instalar o Python

Acesse `https://python.org/downloads` e baixe a versão mais recente.

Durante a instalação, **antes de clicar em qualquer coisa**, marque obrigatoriamente a opção **"Add Python to PATH"** que fica na parte de baixo da janela. Sem isso o Python não funciona no terminal.

Clique em "Install Now" e aguarde terminar.

Para confirmar que funcionou, abra o terminal e rode:
```
python --version
```
Deve aparecer algo como `Python 3.12.x`.

---

### Passo 2 — Instalar o Tesseract OCR

O Tesseract é o motor que lê o texto das imagens. Sem ele o sistema roda em modo simulação.

Acesse `https://github.com/UB-Mannheim/tesseract/wiki` e baixe o instalador `.exe` mais recente.

Durante a instalação:
- Na tela de componentes, expanda **"Additional language data"** e marque **"Portuguese"**
- Anote o caminho de instalação — normalmente é `C:\Program Files\Tesseract-OCR`

Agora adicione o Tesseract ao PATH do Windows para que o sistema consiga encontrá-lo:
- Clique com o botão direito em "Este Computador" → Propriedades
- Configurações avançadas do sistema → Variáveis de Ambiente
- Em "Variáveis do sistema" clique em "Path" → Editar → Novo
- Adicione: `C:\Program Files\Tesseract-OCR`
- Clique OK em tudo e **feche e reabra o terminal**

Para confirmar:
```
tesseract --version
```

---

### Passo 3 — Instalar o Poppler (para leitura de PDF)

O Poppler permite que o sistema leia boletos em formato PDF.

Acesse `https://github.com/oschwartz10612/poppler-windows/releases` e baixe o `.zip` mais recente. Extraia em `C:\poppler`.

Adicione ao PATH da mesma forma que o Tesseract, mas com o caminho:
```
C:\poppler\Library\bin
```

Para confirmar:
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

**Se não, copie a pasta do projeto** para um lugar fácil de achar, como `C:\Users\SEU_NOME\Documents\la-rose-boletos`.

---

### Passo 5 — Instalar as dependências Python

Este é o passo mais importante para o sistema funcionar.

Abra o terminal **dentro da pasta raiz do projeto** (onde fica o `requirements.txt`) e rode:

```
pip install -r requirements.txt
```

**O que esse comando faz:**
O `pip` é o gerenciador de pacotes do Python — funciona como uma loja de bibliotecas. O `-r requirements.txt` manda ele ler o arquivo `requirements.txt` que lista todas as bibliotecas necessárias e instalar cada uma automaticamente. Você só precisa rodar esse comando uma vez por máquina. Se um dia precisar atualizar as bibliotecas, basta rodar de novo.

Aguarde terminar. Vai aparecer várias linhas de download. Quando terminar deve aparecer `Successfully installed`.

Para confirmar que tudo foi instalado:
```
pip list
```
Procure na lista: fastapi, uvicorn, pytesseract, opencv-python-headless, firebase-admin, pdf2image.

---

### Passo 6 — Configurar o Firebase

O Firebase é onde os dados ficam salvos na nuvem. Você precisa configurar duas coisas: as credenciais do frontend e a chave do backend.

**6.1 — Credenciais do frontend (firebase-config.js)**

Acesse `https://console.firebase.google.com` e abra o projeto `larose-boletos`. Vá em Configurações do projeto (engrenagem ⚙️) → Seus apps → clique no app web `la-rose-web`. Copie o objeto `firebaseConfig` que aparece lá.

Na pasta `frontend/` do projeto, copie o arquivo `firebase-config.exemplo.js`, renomeie a cópia para `firebase-config.js` e substitua os valores de exemplo pelos seus dados reais.

**6.2 — Chave de serviço do backend (firebase-key.json)**

No Firebase Console vá em Configurações do projeto → aba "Contas de serviço" → clique em "Gerar nova chave privada" → confirme. Um arquivo JSON será baixado. Renomeie para `firebase-key.json` e coloque dentro da pasta `backend/`.

---

### Passo 7 — Criar o arquivo .env

Na raiz do projeto, copie o arquivo `.env.exemplo` e renomeie a cópia para `.env`. Abra e confirme que está assim:
```
FIREBASE_KEY_PATH=firebase-key.json
```
Salve e feche.

---

### Passo 8 — Iniciar o sistema

Dê duplo clique no `iniciar.bat`.

Quando aparecer no terminal `Uvicorn running on http://0.0.0.0:8000`, abra o Chrome e acesse:
```
http://localhost:8000
```

---

## Uso no dia a dia

Depois que tudo estiver configurado, o único passo necessário é:

1. Dar duplo clique no `iniciar.bat`
2. Acessar `http://localhost:8000` no Chrome

O sistema funciona em qualquer cidade desde que o notebook esteja com você e conectado à internet. A internet é necessária apenas para o Firebase carregar e salvar os dados — o OCR e o processamento de imagem funcionam localmente.

---

## Acessar pelo celular

Quando o servidor estiver rodando no notebook, o IP local aparece no canto superior direito da interface. Qualquer celular conectado na **mesma rede Wi-Fi** pode acessar pelo IP exibido. Exemplo:
```
http://192.168.0.50:8000
```

---

## Lojas cadastradas

| Loja | CNPJ | Identificação na NFe |
|------|------|----------------------|
| Loja 1 — Matriz | 37.319.385/0001-64 | `37319385000164` |
| Loja 2 — Filial | 37.319.385/0002-45 | `37319385000245` |

O sistema identifica a loja automaticamente lendo o CNPJ embutido na chave de 44 dígitos da NFe.

---

## Template gerado para WhatsApp

O envio é feito em duas mensagens separadas para facilitar o pagamento.

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

**Mensagem 2 — Linha digitável (só números, sem pontos e espaços):**
```
23793381286000782713694000063305892340000125000
```

---

## O que aprendi construindo isso

Quando comecei não sabia nada sobre APIs, OCR ou Firebase. Aprendi que Python com FastAPI é muito mais simples do que parece para criar um servidor. Que o Tesseract precisa de uma boa imagem para funcionar — iluminação e foco fazem toda a diferença. Que o Firebase é surpreendentemente fácil quando você entende coleções e documentos. E que JavaScript moderno com async/await é completamente diferente e melhor do que o JavaScript antigo.

O mais importante: aprendi que dá para construir uma ferramenta real, que resolve um problema real, sem precisar contratar ninguém. Com paciência, organização e vontade de aprender, qualquer pessoa chega lá.

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
