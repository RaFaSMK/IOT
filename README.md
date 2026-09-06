# 🎾 Quadra Inteligente de Beach Tennis — IoT Highlight System

> Sistema IoT ponta a ponta para detecção, persistência e visualização de **highlights esportivos em tempo real**.  
> Disparado por um botão na quadra (ESP32 simulado no Wokwi ou físico), o evento trafega via **MQTT**, é processado pelo backend **FastAPI**, persistido no **InfluxDB 2.x** e exibido instantaneamente em um **Dashboard Vue 3 + ECharts**.

---

## 📖 Sobre o Projeto

Em partidas de esportes de areia como o **Beach Tennis**, jogadas espetaculares (como *aces*, defesas acrobáticas e *rallys* intensos) acontecem em fração de segundos. Gravações contínuas de câmeras geram horas de vídeo bruto, tornando a busca e edição dos melhores momentos demorada e inviável para jogadores e organizadores.

A **Quadra Inteligente** soluciona esse problema conectando a quadra à nuvem:
1. **Acionamento na Borda**: Um botão físico (instalado próximo à rede ou poste da quadra) permite que o atleta ou árbitro sinalize uma jogada marcante no instante em que ela acontece.
2. **Confirmação Visual**: O microcontrolador (ESP32) trata o clique com *debounce* por software e fornece feedback imediato ao acender um LED indicador.
3. **Pipeline de Baixa Latência**: O evento é publicado em milissegundos via protocolo leve **MQTT** para um broker na nuvem/rede local.
4. **Ingestão e Marcação Temporal**: A API FastAPI consome o evento através de um *subscriber* assíncrono, grava a ocorrência com precisão de timestamp UTC no banco de séries temporais **InfluxDB**, e calcula a janela de recorte de vídeo (ex: -15s a +5s da marcação).
5. **Painel em Tempo Real**: Um dashboard moderno em **Vue 3** monitora o status dos serviços, exibe o log dos últimos highlights e gera gráficos analíticos interativos de volume de jogadas por período.

---

## 📐 Arquitetura da Solução

### Fluxo de Dados

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CAMADA DE DISPOSITIVO / BORDA                   │
│                                                                        │
│   ┌───────────────────────────┐      ┌─────────────────────────────┐   │
│   │   ESP32 (Simulado Wokwi)  │      │     simulate_button.py      │   │
│   │   • Botão físico (GPIO 13)│      │   (CLI de simulação rápida) │   │
│   │   • LED status   (GPIO 2) │      │                             │   │
│   │   • Debounce 300ms        │      │   uv run python             │   │
│   │   • WiFi (Wokwi-GUEST)    │      │   scripts/simulate_button.py│   │
│   └─────────────┬─────────────┘      └──────────────┬──────────────┘   │
│                 │                                   │                  │
│                 │ MQTT publish (quadra/highlight)   │ MQTT publish     │
└─────────────────┼───────────────────────────────────┼──────────────────┘
                  │                                   │
                  ▼                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        CAMADA DE MENSAGERIA                            │
│                                                                        │
│           Broker MQTT: broker.hivemq.com (Porta :1883)                 │
│              (ou Mosquitto local para execução offline)                │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ MQTT subscribe
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        CAMADA DE BACKEND & REGRAS                      │
│                                                                        │
│   FastAPI (Python 3.11+ via uv) :8000                                  │
│   ├── mqtt/subscriber.py   → Thread daemon conectada ao broker MQTT    │
│   ├── services/            → highlight_service.py                      │
│   │                          ├── influx_service.py (gravação)          │
│   │                          └── video_stub.py (janela de corte)       │
│   └── api/routes.py        → Endpoints REST (/highlights, /stats)      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Flux Write / Flux Query
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        CAMADA DE ARMAZENAMENTO                         │
│                                                                        │
│   InfluxDB 2.x (Porta :8086)                                           │
│   • Organização: smart-court                                           │
│   • Bucket:      smart_court                                           │
│   • Measurement: highlight_events                                      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Polling HTTP / REST (5s)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        CAMADA DE VISUALIZAÇÃO                          │
│                                                                        │
│   Vue 3 + TypeScript + Vite :5173                                      │
│   ├── Status da Quadra & Conectividade (Health Check)                  │
│   ├── Gráfico Temporal ECharts (Agregação por hora + DataZoom)         │
│   └── Log Dinâmico dos Últimos 100 Highlights                          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Pré-requisitos

Para rodar todo o ecossistema na sua máquina, instale as seguintes ferramentas:

| Ferramenta | Versão Recomendada | Finalidade | Como Obter |
|---|---|---|---|
| **Python** | 3.11+ | Backend FastAPI e scripts de teste | [python.org](https://www.python.org/) |
| **uv** *(Recomendado)* | 0.4+ | Gerenciador ultrarrápido de pacotes Python | `pip install uv` ou [astral.sh/uv](https://docs.astral.sh/uv/) |
| **Node.js** | 20+ (LTS) | Servidor de desenvolvimento do frontend | [nodejs.org](https://nodejs.org/) |
| **InfluxDB** | 2.7+ | Banco de dados de séries temporais | [portal.influxdata.com](https://portal.influxdata.com/downloads/) |
| **VS Code + Wokwi** | Atual | Simulação do microcontrolador ESP32 | Extensão `Wokwi Simulator` na loja do VS Code |
| **Arduino IDE 2.x** *(Opcional)* | 2.x | Apenas se for alterar o código C++ do ESP32 | [arduino.cc](https://www.arduino.cc/en/software) |
| **Mosquitto** *(Opcional)* | 2.x | Apenas se desejar broker MQTT local offline | [mosquitto.org](https://mosquitto.org/download/) |

> **Nota sobre o Broker MQTT:**  
> Por padrão, o projeto utiliza o broker público **`broker.hivemq.com:1883`**, dispensando a instalação de qualquer broker na sua máquina local e permitindo que a simulação no Wokwi se comunique diretamente com o backend!

---

## 🚀 Como Rodar o Projeto (Passo a Passo)

### 1️⃣ Subir e Configurar o InfluxDB

1. Inicie o serviço do InfluxDB no terminal:
   ```powershell
   influxd
   ```
2. Abra o navegador em: **`http://localhost:8086`**
3. Na tela de boas-vindas (*Get Started*), configure:
   - **Username / Password:** crie suas credenciais de acesso local à interface web
   - **Organization Name:** **`smart-court`** *(obrigatório ser exatamente esse)*
   - **Bucket Name:** **`smart_court`** *(obrigatório ser exatamente esse)*
4. Gere o Token de Autenticação:
   - No menu lateral esquerdo, vá em **Load Data** → **API Tokens**
   - Clique em **Generate API Token** → **All Access API Token**
   - Copie o token gerado (ele será usado na variável `INFLUX_TOKEN` do backend).

---

### 2️⃣ Configurar e Iniciar o Backend (FastAPI)

1. Acesse a pasta do backend:
   ```powershell
   cd backend
   ```
2. Crie o arquivo `.env` copiando o modelo `.env.example`:
   ```powershell
   copy .env.example .env
   ```
3. Abra o arquivo `.env` e cole o seu token do InfluxDB:
   ```env
   # ── MQTT ───────────────────────────────────────────────────────────────────
   MQTT_BROKER_HOST=broker.hivemq.com
   MQTT_BROKER_PORT=1883
   MQTT_TOPIC=quadra/highlight
   MQTT_CLIENT_ID=smart-court-backend

   # ── InfluxDB ───────────────────────────────────────────────────────────────
   INFLUX_URL=http://localhost:8086
   INFLUX_TOKEN=SEU_TOKEN_COPIADO_DO_INFLUXDB_AQUI
   INFLUX_ORG=smart-court
   INFLUX_BUCKET=smart_court

   # ── FastAPI ────────────────────────────────────────────────────────────────
   API_HOST=0.0.0.0
   API_PORT=8000
   ```
4. Instale as dependências e inicie o backend:
   ```powershell
   # Usando uv (recomendado):
   uv sync
   uv run python main.py

   # Ou usando pip padrão:
   pip install -r requirements.txt
   python main.py
   ```
5. Valide que o backend está ativo:
   - **Swagger / OpenAPI:** [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Health Check:** [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

### 3️⃣ Iniciar o Frontend (Vue 3 + ECharts)

1. Em um novo terminal, entre na pasta do frontend:
   ```powershell
   cd frontend
   ```
2. Instale as dependências do projeto:
   ```powershell
   npm install
   ```
3. Inicie o servidor de desenvolvimento:
   ```powershell
   npm run dev
   ```
4. Acesse o painel pelo navegador:
   👉 **`http://localhost:5173`**

---

### 4️⃣ Disparando Eventos de Highlight

Você pode gerar eventos de highlight de **3 formas diferentes**:

#### Opção A: ESP32 Simulado no Wokwi (Hardware Virtual)
O binário do microcontrolador já está compilado e pronto na pasta `iot/wokwi/sketch/build/`.
1. Abra o arquivo [`iot/wokwi/diagram.json`](file:///d:/Projetos/IOT/iot/wokwi/diagram.json) no VS Code.
2. Pressione `F1` no VS Code e selecione: **`Wokwi: Start Simulator`**.
3. Na placa simulada:
   - O ESP32 conectará ao WiFi virtual `Wokwi-GUEST` e ao broker `broker.hivemq.com`.
   - O LED azul piscará 3 vezes indicando que está pronto.
4. **Clique no botão verde "HIGHLIGHT"**:
   - O LED azul dará uma piscada longa de confirmação.
   - O log do Wokwi exibirá: `📤 {"court_id":"court_01",...} | ✅`.
   - O backend receberá a mensagem e em até 5 segundos o evento surgirá no dashboard!

> **Quer alterar o código C++ do ESP32?**  
> 1. Abra a pasta `iot/wokwi/sketch/sketch.ino` no **Arduino IDE**.  
> 2. Certifique-se de instalar as bibliotecas `PubSubClient` e `ArduinoJson` no gerenciador de bibliotecas.  
> 3. Selecione a placa **ESP32 Dev Module**.  
> 4. Vá em **Sketch** → **Export Compiled Binary** (`Ctrl+Alt+S`). O Arduino IDE atualizará os binários em `build/` automaticamente.

---

#### Opção B: Simulador em Python (CLI sem precisar de simulação gráfica)
Se quiser testar rapidamente sem abrir o simulador Wokwi:

```powershell
# Modo interativo: pressione [ENTER] para registrar um highlight ou digite A/B para mudar o jogador
uv run --project backend python scripts/simulate_button.py

# Modo automático: dispara 10 eventos em intervalos randômicos de 1 a 3 segundos
uv run --project backend python scripts/simulate_button.py --auto --count 10
```

---

#### Opção C: Injetar Dados Históricos (Seed)
Para ver os gráficos de barras temporais do ECharts totalmente preenchidos de imediato:

```powershell
# Cria 50 eventos realistas distribuídos pelas últimas 24 horas
uv run --project backend python scripts/seed_influx.py
```
Abra o dashboard (`http://localhost:5173`) e observe os dados populados nos gráficos e tabelas!

---

## 🔌 Contrato de Mensageria MQTT

- **Broker Padrão:** `broker.hivemq.com` (porta `1883`, TCP sem TLS)
- **Tópico:** `quadra/highlight`
- **QoS:** `1` (At least once)

### Formato do Payload (JSON)
```json
{
  "court_id": "court_01",
  "player": "A",
  "event_type": "highlight",
  "timestamp": 1741267800
}
```

| Campo | Tipo | Obrigatório | Descrição | Exemplo |
|---|---|:---:|---|---|
| `court_id` | string | Sim | Identificador da quadra física | `"court_01"` |
| `player` | string | Sim | Jogador ou lado da quadra associado ao lance (`"A"` ou `"B"`) | `"A"` |
| `event_type` | string | Sim | Classificação da jogada (`highlight`, `ace`, `winner`, `error`) | `"highlight"` |
| `timestamp` | integer | Sim | Timestamp Unix UTC (em segundos) do instante do clique | `1741267800` |

---

## 🗄️ Modelagem de Dados (InfluxDB)

Os dados são armazenados na série temporal sob o measurement `highlight_events`:

| Elemento InfluxDB | Nome | Tipo | Descrição |
|---|---|---|---|
| **Measurement** | `highlight_events` | string | Coleção de eventos de marcação de jogadas |
| **Tag** | `court_id` | string (indexado) | Identificador da quadra (permite filtros rápidos) |
| **Field** | `player` | string | Jogador que efetuou a jogada |
| **Field** | `event_type` | string | Tipo da jogada registrada |
| **Time** | `_time` | timestamp | Timestamp com precisão de nanossegundos em UTC |

---

## 📡 Endpoints da API REST (FastAPI)

| Método | Endpoint | Parâmetros de Query | Descrição |
|---|---|---|---|
| `GET` | `/api/highlights` | `start` (padrão: `"-1h"`), `limit` (padrão: `100`), `court_id` | Retorna lista dos highlights mais recentes com metadados de vídeo |
| `GET` | `/api/highlights/stats` | `start` (padrão: `"-24h"`), `bucket_interval` (padrão: `"1h"`), `court_id` | Retorna total de highlights agrupados por janela temporal para gráficos |
| `GET` | `/api/health` | — | Verifica saúde da conexão com o Broker MQTT e o InfluxDB |
| `GET` | `/docs` | — | Documentação interativa Swagger UI |
| `GET` | `/redoc` | — | Documentação ReDoc |

---

## 📁 Estrutura de Diretórios do Projeto

```
smart-court/ (d:\Projetos\IOT)
├── backend/                         # Backend FastAPI + MQTT Subscriber
│   ├── api/
│   │   └── routes.py                # Rotas REST da aplicação
│   ├── config/
│   │   └── settings.py              # Leitura de variáveis de ambiente (.env)
│   ├── mqtt/
│   │   └── subscriber.py            # Paho-MQTT client em background thread
│   ├── services/
│   │   ├── highlight_service.py     # Orquestração do processamento de eventos
│   │   ├── influx_service.py        # Integração e queries Flux com InfluxDB 2.x
│   │   └── video_stub.py            # Cálculo de marcadores de vídeo (start/end time)
│   ├── .env.example                 # Exemplo de configuração de ambiente
│   ├── main.py                      # Ponto de entrada FastAPI (Uvicorn)
│   └── pyproject.toml               # Dependências Python gerenciadas pelo uv
├── frontend/                        # Dashboard Web Vue 3 + TypeScript
│   ├── src/
│   │   ├── components/              # Componentes de UI (CardStatus, Gráficos, Log)
│   │   ├── composables/             # Hooks reativos (useHighlights.ts)
│   │   ├── services/                # Chamadas HTTP com Axios/Fetch
│   │   ├── views/                   # Telas principais (Dashboard.vue)
│   │   └── App.vue                  # Componente raiz
│   ├── package.json                 # Dependências Node.js
│   └── vite.config.ts               # Configuração do Vite
├── iot/
│   └── wokwi/                       # Simulação ESP32 no Wokwi
│       ├── sketch/
│       │   ├── sketch.ino           # Código-fonte C++ para ESP32
│       │   └── build/               # Binários compilados (.bin / .elf)
│       ├── diagram.json             # Circuito eletrônico (ESP32 + Botão + LED + Resistor)
│       └── wokwi.toml               # Configuração da extensão Wokwi
├── scripts/                         # Ferramentas auxiliares
│   ├── simulate_button.py           # Simulador CLI de botão via terminal
│   └── seed_influx.py               # Gerador de massa de dados históricos
├── infra/
│   └── mosquitto/                   # Configuração para Mosquitto local (opcional)
│       └── mosquitto.conf
└── docs/                            # Documentação técnica adicional
    ├── architecture.md              # Detalhamento de arquitetura
    ├── mqtt-topics.md               # Especificação de tópicos MQTT
    └── demo-script.md               # Roteiro para apresentações e demonstrações
```

---

## 🛠️ Resolução de Problemas (Troubleshooting)

### 1. Backend não conecta ao InfluxDB
- Certifique-se de que o executável `influxd` está rodando no terminal.
- Verifique se a organização (`smart-court`) e o bucket (`smart_court`) foram criados exatamente com esses nomes.
- Cheque se o token em `INFLUX_TOKEN` no arquivo `backend/.env` foi copiado integralmente.

### 2. O Wokwi não encontra os arquivos compilados
- Verifique se o arquivo `iot/wokwi/wokwi.toml` aponta para `sketch/build/esp32.esp32.esp32/sketch.ino.elf`.
- Caso tenha modificado o arquivo `sketch.ino`, gere novos binários no Arduino IDE via menu:  
  *Sketch* → *Export Compiled Binary* (`Ctrl+Alt+S`).

### 3. Falha de conexão com o Broker MQTT
- O broker padrão `broker.hivemq.com` requer conexão com a internet ativa na porta 1883.
- Se a sua rede bloquear a porta 1883 de saída (alguns WiFi corporativos bloqueiam), você pode iniciar o Mosquitto localmente (`mosquitto -v -c infra/mosquitto/mosquitto.conf`) e definir `MQTT_BROKER_HOST=localhost` no `backend/.env`.

### 4. Letras quebradas ou erro de log no terminal Windows
- O backend inclui `sys.stdout.reconfigure(encoding="utf-8")` por padrão em `backend/main.py`, garantindo que os emojis e logs coloridos funcionem normalmente no PowerShell do Windows.

---

## 🎓 Contexto Acadêmico

Projeto concebido e desenvolvido para a disciplina de **Internet das Coisas (IoT)**.  
Demonstra a aplicação prática de:
- Computação na borda (Edge Computing) com tratamento de bouncing e estados em microcontrolador;
- Protocolo de mensageria assíncrona para telemetria (MQTT);
- Persistência e análise de séries temporais (TSDB com InfluxDB);
- APIs REST modernas de alta performance (FastAPI);
- Visualização de dados analíticos reativos em tempo real (Vue 3 + ECharts).
