# Arquitetura — Quadra Inteligente de Beach Tennis

## Visão Geral

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CAMADA DE DISPOSITIVO                           │
│                                                                     │
│   ┌──────────────────────────┐   ┌──────────────────────────────┐   │
│   │  ESP32 (Wokwi Simulator) │   │   simulate_button.py         │   │
│   │  ┌─────────┐ ┌───────┐  │   │   (fallback sem hardware)    │   │
│   │  │ Button  │ │  LED  │  │   │                              │   │
│   │  │ GPIO 13 │ │ GPIO2 │  │   │   python scripts/            │   │
│   │  └────┬────┘ └───────┘  │   │   simulate_button.py         │   │
│   │       │ debounce 300ms   │   └──────────────┬───────────────┘   │
│   └───────┼──────────────────┘                  │                   │
│           │ MQTT publish                         │ MQTT publish      │
│           │ quadra/highlight                     │ quadra/highlight  │
└───────────┼──────────────────────────────────────┼───────────────────┘
            │                                      │
            ▼                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     CAMADA DE MENSAGERIA                            │
│                                                                     │
│              ┌──────────────────────────────┐                       │
│              │    Mosquitto Broker 2.x       │                       │
│              │    TCP :1883 / WS :9001        │                       │
│              │    allow_anonymous true        │                       │
│              └──────────────────────────────┘                       │
│                          │ subscribe                                │
└──────────────────────────┼─────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     CAMADA DE BACKEND                               │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                  FastAPI :8000                               │   │
│   │                                                             │   │
│   │   mqtt/subscriber.py  ──►  services/highlight_service.py    │   │
│   │   (thread daemon)              │                            │   │
│   │                                ├──► influx_service.py       │   │
│   │                                └──► video_stub.py           │   │
│   │                                                             │   │
│   │   api/routes.py                                             │   │
│   │   ├── GET /api/highlights                                   │   │
│   │   ├── GET /api/highlights/stats                             │   │
│   │   └── GET /api/health                                       │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                          │ write / query                            │
└──────────────────────────┼─────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     CAMADA DE ARMAZENAMENTO                         │
│                                                                     │
│              ┌──────────────────────────────┐                       │
│              │    InfluxDB 2.x :8086         │                       │
│              │                              │                       │
│              │  measurement: highlight_events│                       │
│              │  tag:    court_id            │                       │
│              │  fields: player, event_type  │                       │
│              │  time:   epoch UTC (s)        │                       │
│              └──────────────────────────────┘                       │
│                          │ Flux query (polling 5s)                 │
└──────────────────────────┼─────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     CAMADA DE VISUALIZAÇÃO                          │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │              Vue 3 Dashboard :5173                           │   │
│   │                                                             │   │
│   │   CourtStatus    │  HighlightChart (ECharts)                │   │
│   │   ─────────────  │  ─────────────────────────               │   │
│   │   • Online/Off   │  • Barras por hora (24h)                 │   │
│   │   • MQTT status  │  • DataZoom interativo                   │   │
│   │   • InfluxDB ok  │                                          │   │
│   │   • Último evento│  EventLog                                │   │
│   │                  │  ─────────────────────────               │   │
│   │                  │  • Lista animada (últimos 100)           │   │
│   │                  │  • Polling automático 5s                 │   │
│   └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Decisões de Design

### Por que FastAPI desde o 1º bi?
Evita migração de Flask→FastAPI no 2º bi. A estrutura de routers e middleware já está pronta para receber endpoints REST adicionais.

### Por que InfluxDB 2.x?
UI web embutida facilita demonstração ao vivo. A query Flux é mais expressiva que SQL para séries temporais.

### Por que ECharts via vue-echarts?
Gráficos de série temporal com DataZoom e tooltip customizado em menos linhas de código que Chart.js.

### Por que Paho-MQTT em thread daemon?
O subscriber MQTT precisa de um loop bloqueante (`loop_forever`). Rodá-lo em thread daemon evita bloquear o event loop do Uvicorn/asyncio.

### Por que simulate_button.py?
Garante que o sistema funciona mesmo sem o Wokwi (fallback para demo em caso de problemas de rede/licença).

## Tecnologias

| Camada | Tecnologia | Versão |
|---|---|---|
| Dispositivo | ESP32 (Wokwi) + Arduino C++ | — |
| Mensageria | Mosquitto MQTT | 2.x |
| Backend | FastAPI + Uvicorn | 0.111+ |
| Cliente MQTT | Paho-MQTT | 2.x |
| Banco de dados | InfluxDB | 2.7+ |
| Frontend | Vue 3 + TypeScript | 3.x |
| Bundler | Vite | 6.x |
| Gráficos | ECharts + vue-echarts | 5.x |
| Gerenc. Python | uv | 0.4+ |
