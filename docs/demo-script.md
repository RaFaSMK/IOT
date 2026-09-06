# Roteiro da Demo ao Vivo — 28/09

**Duração total:** ~11 minutos  
**Cenário principal:** Wokwi (VS Code) → Mosquitto → FastAPI → InfluxDB → Vue  
**Cenário de fallback:** `simulate_button.py` (caso Wokwi falhe)

---

## ✅ Checklist Pré-Demo (fazer 15 min antes)

- [ ] Mosquitto rodando: `netstat -an | findstr 1883`
- [ ] InfluxDB rodando: abrir `http://localhost:8086`
- [ ] Backend rodando: `http://localhost:8000/api/health` retorna `"status":"ok"`
- [ ] Frontend rodando: `http://localhost:5173` abre o dashboard
- [ ] Dashboard está **verde** (Sistema: Online)
- [ ] Wokwi: sketch compilado, Gateway ativo, botão visível
- [ ] Telas abertas: VS Code (Wokwi) + browser com dashboard
- [ ] Aumentar zoom do VS Code para 150% para a plateia ver melhor

---

## 🎬 Roteiro Passo a Passo

### Ato 1 — Contexto (2 min)

> *Mostrar slide ou falar de memória:*

"O problema é simples: durante um rally de beach tennis, momentos incríveis acontecem e se perdem. Nossa solução usa um botão IoT na quadra — quando o árbitro ou treinador aperta, o sistema registra o highlight automaticamente, grava no banco de dados e exibe em tempo real no dashboard."

"A arquitetura segue o fluxo: **ESP32 → MQTT → FastAPI → InfluxDB → Vue.js**."

---

### Ato 2 — Infraestrutura (1 min)

> *Mostrar terminal do Mosquitto e a UI do InfluxDB:*

1. "Aqui está o Mosquitto rodando — broker MQTT na porta 1883."
2. Abrir `http://localhost:8086` → aba **Data Explorer**
3. "InfluxDB já tem dados históricos." *(seed rodado antes)*
4. Mostrar o bucket `smart_court` → alguns points já visíveis

---

### Ato 3 — Wokwi em ação (2 min) ⭐ PONTO ALTO

> *Focar no VS Code com o Wokwi aberto:*

1. "Aqui está o ESP32 simulado no Wokwi — botão verde no GPIO 13, LED azul no GPIO 2."
2. Pressionar o botão uma vez → **LED pisca** → "O ESP32 acabou de publicar um evento MQTT."
3. Mudar para o terminal do backend → mostrar o log chegando em tempo real:
   ```
   📨  MQTT [quadra/highlight] → {"court_id": "court_01", ...}
   💾  Highlight gravado no InfluxDB
   🎬  [VIDEO STUB] Captura concluída (simulado)
   ✅  Evento processado
   ```

---

### Ato 4 — InfluxDB confirmando (1 min)

> *Mostrar a UI do InfluxDB:*

1. Abrir **Data Explorer** → `SELECT * FROM highlight_events ORDER BY time DESC LIMIT 5`
2. "O point que acabamos de criar está aqui — timestamp, quadra, jogador."

---

### Ato 5 — Dashboard em tempo real (2 min) ⭐

> *Mostrar `http://localhost:5173`:*

1. "O dashboard atualiza automaticamente a cada 5 segundos."
2. Apontar para o KPI "Última hora" — número subiu
3. Mostrar o Log de Eventos — evento apareceu no topo com animação
4. Apontar o gráfico de barras — barra da hora atual cresceu

---

### Ato 6 — Múltiplos eventos (1 min)

1. Apertar o botão no Wokwi mais **3–4 vezes**
2. "Cada clique é um highlight registrado."
3. Aguardar ≤5s → dashboard atualiza → gráfico cresce ao vivo

---

### Ato 7 — Video Stub + Evolução (1 min)

1. Mostrar o log do terminal:
   ```
   🎬  [VIDEO STUB] Gravando 10s de vídeo → videos/highlight_court_01_A_...mp4
   🎬  [VIDEO STUB] Captura concluída (simulado). Integração real prevista para o 2º bimestre.
   ```
2. "A arquitetura já está preparada. No 2º bi, substituímos esse stub pela captura real de câmera IP."

---

### Ato 8 — Encerramento (1 min)

"Em resumo: com um único botão, criamos um pipeline IoT completo — dispositivo → mensageria → backend → banco de dados → dashboard — usando tecnologias de mercado: MQTT, FastAPI, InfluxDB e Vue.js."

---

## 🆘 Plano de Fallback

Se o Wokwi falhar (rede, licença, etc.), use o simulador:

```powershell
# Em um terminal separado
uv run --project backend python scripts/simulate_button.py
# Pressione ENTER para cada evento — a demo continua idêntica
```

O restante do pipeline é **exatamente o mesmo**. A plateia não percebe diferença.

---

## 🔗 URLs de referência rápida

| Serviço | URL |
|---|---|
| Dashboard Vue | http://localhost:5173 |
| API Swagger | http://localhost:8000/docs |
| InfluxDB UI | http://localhost:8086 |
| Health check | http://localhost:8000/api/health |
