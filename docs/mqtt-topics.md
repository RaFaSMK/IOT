# Tópicos MQTT — Quadra Inteligente de Beach Tennis

## Broker

| Campo | Valor |
|---|---|
| Host | `localhost` (ou IP local para Wokwi) |
| Porta TCP | `1883` |
| Porta WebSocket | `9001` |
| Auth | Anônimo (sem usuário/senha) |
| QoS padrão | 1 (at least once) |

---

## Tópico Principal

### `quadra/highlight`

Publicado pelo ESP32 (Wokwi) ou pelo `simulate_button.py` a cada clique no botão.  
Consumido pelo `mqtt/subscriber.py` do backend.

#### Payload (JSON)

```json
{
  "court_id":   "court_01",
  "player":     "A",
  "event_type": "highlight",
  "timestamp":  1695900000
}
```

#### Campos

| Campo | Tipo | Obrigatório | Valores válidos |
|---|---|---|---|
| `court_id` | string | ✅ | `"court_01"` |
| `player` | string | ✅ | `"A"` \| `"B"` |
| `event_type` | string | ✅ | `"highlight"` \| `"ace"` \| `"winner"` \| `"error"` |
| `timestamp` | integer | ⚠️ opcional | Epoch Unix (segundos). Se ausente, o backend usa `time.time()` |

---

## Como testar manualmente

```bash
# Subscribir (terminal 1)
mosquitto_sub -h localhost -t "quadra/highlight" -v

# Publicar (terminal 2)
mosquitto_pub -h localhost -t "quadra/highlight" \
  -m '{"court_id":"court_01","player":"A","event_type":"ace","timestamp":1695900000}'
```

---

## Evolução prevista para o 2º Bimestre

| Tópico | Propósito |
|---|---|
| `quadra/highlight` | Mantido (botão) |
| `quadra/sensor2` | Segundo sensor (TBD) |
| `quadra/status` | Heartbeat do ESP32 (online/offline) |
