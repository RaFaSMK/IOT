<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, defineAsyncComponent } from 'vue'
import { court, fresh, predictionFresh, canOperate, isAdmin, initialize, signIn, logout, request, command, subscribe, deviceState, rulText, rulIntervalText } from '@/services/court'
import type {Device, Job, Model, Alert, Event} from '@/services/court'
import DataChart from '@/components/DataChart.vue'
import HighlightChart from '@/components/HighlightChart.vue'
import ModelChart from '@/components/ModelChart.vue'
import type {HighlightEvent, HighlightPoint} from '@/types/highlight'
const DigitalTwin = defineAsyncComponent(() => import('@/components/DigitalTwin.vue'))

const page = ref('dashboard')
const username = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')
const notice = ref('')
const pendingCommands = new Map<string, number>()
const selectedSensor = ref('ambient_temperature')
const historyRange = ref('-1h')
const historical = ref<{time: string; value: number}[]>([])
const highlights = ref<HighlightEvent[]>([])
const highlightSeries = ref<HighlightPoint[]>([])
const jobs = ref<Job[]>([])
const models = ref<Model[]>([])
const alerts = ref<Alert[]>([])
interface Queue {name: string; messages: number; ready: number; unacked: number; consumers: number; publish_rate: number; deliver_rate: number}
const queues = ref<Queue[]>([])
const dlq = ref<unknown[]>([])
const auditing = ref<{id: number; timestamp: string; username: string; action: string; details: unknown}[]>([])
const links = ref<{name: string; url: string}[]>([])
const selectedDataset = ref('')
const deviceForm = ref<Device>({id: '', name: '', kind: 'sensor', unit: '', config: {}, enabled: true})
const rule = ref({enabled: true, on_above: 16, off_below: 10})
const lab = ref({equipment_count: 100, sensors_per_type: 1, days: 60, interval_minutes: 5, failure_percent: 65, failure_modes: ['bearing', 'overheating', 'imbalance'], noise: .6, missing_percent: 1, outlier_percent: .5, seed: 42})
const labReadings = computed(() => Math.floor(lab.value.equipment_count * lab.value.days * 1440 / lab.value.interval_minutes) * 3 * lab.value.sensors_per_type)
const question = ref('')
const chat = ref<{role: string; text: string}[]>([])
const chatBusy = ref(false)
const chatStatus = ref('')
let chatAbort: AbortController | undefined
const activeModel = computed(() => models.value.find(model => model.active) || models.value[0])
const latestModel = computed(() => models.value[0])
const activeAlerts = computed(() => alerts.value.filter(alert => alert.active))
const datasets = computed(() => jobs.value.filter(job => job.kind === 'generate' && job.status === 'completed'))
const sensors = computed(() => court.devices.filter(device => device.kind === 'sensor' && device.enabled))
const nav = computed(() => [
  {id: 'dashboard', name: 'Dashboard'}, {id: 'highlights', name: 'Highlights'}, {id: 'twin', name: 'Quadra 3D'},
  {id: 'devices', name: 'Dispositivos'}, {id: 'messaging', name: 'Mensageria'}, {id: 'lab', name: 'Laboratório'},
  {id: 'training', name: 'Treinamento'}, {id: 'insights', name: 'Insights'}, {id: 'assistant', name: 'Assistente'},
  ...(isAdmin.value ? [{id: 'admin', name: 'Administração'}] : []),
])
const pageTitle = computed(() => nav.value.find(item => item.id === page.value)?.name)
const roleLabel = computed(() => ({viewer: 'Visualizador', operator: 'Operador', admin: 'Administrador'}[court.user?.role || 'viewer']))
const insightStatus = computed(() => ({no_model: 'Gere os dados e treine os modelos.', warming_up: 'Coletando a janela inicial de leituras.', equipment_off: 'Compressor desligado; previsão suspensa.', incompatible_model: 'Gere e treine um dataset da dinâmica atual.', incompatible_sampling: 'A cadência do dispositivo não corresponde ao modelo.', ready: 'Inferência em tempo real'}[court.prediction?.status || 'no_model']))
const statusLabels: Record<string, string> = {normal: 'Normal', warning: 'Atenção', critical: 'Crítico', no_data: 'Sem dados'}
const jobLabels: Record<string, string> = {queued: 'Na fila', running: 'Em execução', completed: 'Concluído', failed: 'Falhou'}

function number(value: unknown, digits=1) {return typeof value === 'number' ? value.toLocaleString('pt-BR', {maximumFractionDigits: digits}) : '—'}
function time(value: string) {return new Date(value).toLocaleString('pt-BR')}
async function attempt(action: () => Promise<unknown>, message='') {
  error.value = ''; notice.value = ''; busy.value = true
  try {await action(); if (message) notice.value = message} catch (e) {error.value = e instanceof Error ? e.message : String(e)} finally {busy.value = false}
}
async function loadCommon() {
  const [j, m, a, l] = await Promise.all([request<Job[]>('/jobs'), request<Model[]>('/models'), request<Alert[]>('/alerts'), request<{name: string; url: string}[]>('/admin-links')])
  jobs.value = j; models.value = m; alerts.value = a; links.value = l
  if (!selectedDataset.value && datasets.value[0]) selectedDataset.value = datasets.value[0].id
}
async function loadHistory() {historical.value = await request(`/devices/${selectedSensor.value}/history?start=${historyRange.value}`)}
async function loadHighlights() {
  const [events, stats] = await Promise.all([request<{events: HighlightEvent[]}>('/highlights?start=-24h'), request<{series: HighlightPoint[]}>('/highlights/stats')])
  highlights.value = events.events; highlightSeries.value = stats.series
}
async function loadMessaging() {const data = await request<{queues: Queue[]}>('/messaging'); queues.value = data.queues}
async function loadAdmin() {
  auditing.value = await request('/audit')
  const rows = await request<{config: typeof rule.value; enabled: boolean}[]>('/rules')
  if (rows[0]) rule.value = {...rows[0].config, enabled: rows[0].enabled}
}
async function send(identifier: string, action: string, on?: boolean) {
  await attempt(async () => {
    const sent = await command(identifier, action, on)
    pendingCommands.set(sent.command_id, Date.now())
    notice.value = `Comando enviado (${sent.command_id.slice(0, 8)}). Aguardando confirmação do simulador.`
    const acknowledgement = court.recent.find(event => event.type === 'ack' && event.correlation_id === sent.command_id)
    if (acknowledgement) confirmCommand(acknowledgement)
  })
}
function confirmCommand(event: Event) {
  for (const [id, sent] of pendingCommands) if (Date.now() - sent > 60_000) pendingCommands.delete(id)
  if (!event.correlation_id || !pendingCommands.has(event.correlation_id) || !event.payload.executed) return
  pendingCommands.delete(event.correlation_id)
  const name = court.devices.find(device => device.id === event.device_id)?.name || event.device_id
  notice.value = `Comando confirmado: ${name}.`
}
async function generate() {await attempt(async () => {await request('/lab/generate', {method: 'POST', body: JSON.stringify(lab.value)}); await loadCommon()}, 'Geração enfileirada. Acompanhe o progresso abaixo.')}
async function train() {await attempt(async () => {await request('/models/train', {method: 'POST', body: JSON.stringify({dataset_id: selectedDataset.value})}); await loadCommon()}, 'Treinamento enfileirado.')}
async function saveDevice() {
  await attempt(async () => {await request(`/devices/${deviceForm.value.id}`, {method: 'PUT', body: JSON.stringify(deviceForm.value)}); court.devices = await request<Device[]>('/devices')}, 'Cadastro salvo.')
}
async function disableDevice(identifier: string) {
  await attempt(async () => {await request(`/devices/${identifier}`, {method: 'DELETE'}); court.devices = await request<Device[]>('/devices')}, 'Dispositivo desativado.')
}
function edit(device: Device) {deviceForm.value = JSON.parse(JSON.stringify(device))}
async function ask() {
  if (!question.value.trim() || chatBusy.value) return
  const text = question.value; question.value = ''; chat.value.push({role: 'user', text})
  const answer = {role: 'assistant', text: ''}; chat.value.push(answer)
  const index = chat.value.length - 1
  chatBusy.value = true; chatStatus.value = 'Carregando o modelo local…'; error.value = ''
  chatAbort = new AbortController()
  try {
    const response = await fetch('/api/assistant', {method: 'POST', headers: {'Content-Type': 'application/json', Authorization: `Bearer ${court.token}`}, body: JSON.stringify({question: text}), signal: chatAbort.signal})
    if (!response.ok) {const body = await response.json(); throw new Error(body.detail || 'Assistente indisponível')}
    const reader = response.body?.getReader()
    if (!reader) throw new Error('Streaming indisponível')
    const decoder = new TextDecoder(); let pending = ''
    while (true) {
      const {value, done} = await reader.read()
      if (done) break
      pending += decoder.decode(value, {stream: true})
      const parts = pending.split('\n\n'); pending = parts.pop() || ''
      for (const part of parts) {
        if (!part.startsWith('data: ')) continue
        const data = JSON.parse(part.slice(6))
        if (data.error) throw new Error(data.error)
        if (data.status === 'loading') chatStatus.value = data.text
        else {chatStatus.value = ''; const item = chat.value[index]; if (item) item.text += data.text || ''}
      }
    }
  } catch (e) {if (!(e instanceof DOMException && e.name === 'AbortError')) error.value = e instanceof Error ? e.message : String(e)}
  finally {chatBusy.value = false; chatStatus.value = ''}
}

const unsubscribe = subscribe((event: Event) => {
  if (event.type === 'ack') confirmCommand(event)
  if (event.type === 'job') {
    const job = jobs.value.find(job => job.id === event.payload.job_id)
    if (job) {job.progress = Number(event.payload.progress); job.status = String(event.payload.status)}
    if (event.payload.status === 'completed' || event.payload.status === 'failed') loadCommon().catch(e => {error.value = String(e)})
  }
  if (event.type === 'alert') loadCommon().catch(e => {error.value = String(e)})
  if (event.type === 'highlight') setTimeout(() => loadHighlights().catch(e => {error.value = String(e)}), 700)
})
watch(page, async value => {
  if (!court.user) return
  await attempt(async () => {
    if (value === 'messaging') await loadMessaging()
    else if (value === 'highlights') await loadHighlights()
    else if (value === 'admin' && isAdmin.value) await loadAdmin()
    else if (value === 'lab' || value === 'training' || value === 'insights') await loadCommon()
  })
})
watch(() => court.user, async user => {
  if (user) await attempt(async () => {await loadCommon(); await loadHighlights()})
  else {chatAbort?.abort(); pendingCommands.clear(); chat.value = []; page.value = 'dashboard'; jobs.value = []; models.value = []; alerts.value = []}
})
let timer: ReturnType<typeof setInterval>
let poll: ReturnType<typeof setInterval>
onMounted(async () => {
  timer = setInterval(() => {court.now = Date.now()}, 1000)
  poll = setInterval(() => {if (court.user && page.value === 'messaging') loadMessaging().catch(e => {error.value = String(e)})}, 2500)
  if (court.token) await attempt(initialize)
})
onUnmounted(() => {clearInterval(timer); clearInterval(poll); unsubscribe(); chatAbort?.abort()})
</script>

<template>
  <div v-if="!court.user" class="login-wrap">
    <section class="login-card">
      <span class="eyebrow">BEACH TENNIS · AIoT</span>
      <h1>Quadra Inteligente</h1>
      <p>Highlights, condições da quadra e manutenção dos equipamentos em um só lugar.</p>
      <form @submit.prevent="attempt(() => signIn(username, password))" class="form-stack">
        <label>Usuário<input v-model="username" required autocomplete="username" placeholder="Seu usuário" /></label>
        <label>Senha<input v-model="password" required type="password" autocomplete="current-password" placeholder="Sua senha" /></label>
        <p v-if="error" role="alert" class="error">{{error}}</p>
        <button :disabled="busy">{{busy ? 'Entrando…' : 'Entrar na quadra'}}</button>
      </form>
      <small>Contas de demonstração: visualizador, operador e administrador. Use as senhas geradas na instalação.</small>
    </section>
  </div>
  <div v-else class="court-app">
    <aside class="sidebar">
      <a class="brand" href="#" @click.prevent="page = 'dashboard'"><span class="brand-mark">Q</span><span>Quadra<br /><strong>Inteligente</strong></span></a>
      <span class="eyebrow">BEACH TENNIS</span>
      <nav aria-label="Navegação principal"><button v-for="item in nav" :key="item.id" :class="{active: page === item.id}" @click="page = item.id">{{item.name}}</button></nav>
      <div class="sidebar-bottom"><strong>{{court.user.username}}</strong><small>{{roleLabel}}</small><button class="secondary" @click="logout">Sair</button></div>
    </aside>
    <main class="workspace">
      <header class="page-header"><div><span class="eyebrow">COURT_01</span><h1>{{pageTitle}}</h1></div><div class="live-badge" :class="{offline: !fresh}"><span></span>{{fresh ? 'Dados ao vivo' : 'Sem dados recentes'}}<small>{{court.connected ? 'WebSocket conectado' : 'Reconectando'}}</small></div></header>
      <p v-if="error" role="alert" class="error">{{error}} <button @click="error = ''" class="text-button">Fechar</button></p>
      <p v-if="notice" role="status" class="notice">{{notice}} <button @click="notice = ''" class="text-button">Fechar</button></p>
      <div v-if="!fresh" class="stale">O simulador não enviou leituras recentes. Os valores exibidos são históricos; a cena 3D fica parada.</div>

      <template v-if="page === 'dashboard'">
        <div class="summary-grid">
          <article class="panel"><span class="eyebrow">AMBIENTE</span><h2>{{number(court.telemetry?.sensors.ambient_temperature)}} °C</h2><p>Temperatura da quadra</p></article>
          <article class="panel"><span class="eyebrow">BEBEDOURO</span><h2>{{number(court.telemetry?.sensors.water_temperature)}} °C</h2><p>Temperatura da água</p></article>
          <article class="panel"><span class="eyebrow">COMPRESSOR</span><h2>{{court.prediction?.status === 'ready' && predictionFresh ? number(court.prediction.health, 0) + '/100' : '—'}}</h2><p>Saúde prevista pela IA</p></article>
          <article class="panel"><span class="eyebrow">ALERTAS</span><h2>{{activeAlerts.length}}</h2><p>Alertas preditivos ativos</p></article>
        </div>
        <div class="two-columns">
          <section class="panel"><div class="section-heading"><h2>Leituras da quadra</h2><small>{{court.timestamp ? time(court.timestamp) : 'Aguardando'}}</small></div><div class="sensor-grid"><div v-for="device in sensors" :key="device.id" class="sensor" :class="deviceState(device.id)"><span>{{device.name}}</span><strong>{{number(court.telemetry?.sensors[device.id])}} <small>{{device.unit}}</small></strong><small>{{statusLabels[deviceState(device.id)]}}</small></div></div></section>
          <section class="panel"><h2>Controle da quadra</h2><div class="control-row"><div><strong>Refletores</strong><p>{{court.telemetry?.actuators.floodlights ? 'Ligados' : 'Desligados'}}</p></div><button :disabled="!canOperate || busy" @click="send('floodlights', 'set', !court.telemetry?.actuators.floodlights)">{{court.telemetry?.actuators.floodlights ? 'Desligar' : 'Ligar'}}</button></div><div class="control-row"><div><strong>Refrigeração</strong><p>{{court.telemetry?.actuators.cooling ? 'Ligada' : 'Desligada'}} · regra pela temperatura da água</p></div><span class="tag">Automática</span></div><button :disabled="!canOperate || busy" @click="send('highlight_button', 'highlight')">Registrar highlight</button><hr /><h3>Simulador</h3><div class="button-row"><button class="secondary" :disabled="!canOperate || busy" @click="send('simulator', 'pause')">Pausar leituras</button><button class="secondary" :disabled="!canOperate || busy" @click="send('simulator', 'resume')">Retomar</button></div><small v-if="!canOperate">O visualizador acompanha os dados. Comandos exigem operador ou administrador.</small></section>
        </div>
        <section class="panel"><div class="section-heading"><h2>Histórico dos sensores</h2><div class="button-row"><select v-model="selectedSensor"><option v-for="device in sensors" :key="device.id" :value="device.id">{{device.name}}</option></select><select v-model="historyRange"><option value="-1h">Última hora</option><option value="-24h">24 horas</option><option value="-7d">7 dias</option></select><button class="secondary" @click="attempt(loadHistory)">Consultar histórico</button></div></div><DataChart :points="historical.length ? historical : court.history[selectedSensor] || []" /><small>Consulta ao InfluxDB. Leituras ao vivo chegam pelo WebSocket.</small></section>
      </template>

      <template v-if="page === 'highlights'">
        <section class="panel"><div class="section-heading"><div><h2>Melhores momentos da partida</h2><p>Marcações do botão da quadra, preservadas desde o primeiro bimestre.</p></div><button :disabled="!canOperate || busy" @click="send('highlight_button', 'highlight')">Registrar highlight</button></div></section>
        <HighlightChart :series="highlightSeries" />
        <section class="panel table-scroll"><table><thead><tr><th>Horário</th><th>Quadra</th><th>Jogador</th><th>Evento</th></tr></thead><tbody><tr v-for="(event, index) in highlights" :key="event.time + index"><td>{{time(event.time)}}</td><td>{{event.court_id}}</td><td>{{event.player}}</td><td>{{event.event_type}}</td></tr></tbody></table><p v-if="!highlights.length" class="empty">Ainda não há highlights nas últimas 24 horas.</p></section>
      </template>

      <DigitalTwin v-if="page === 'twin'" @command="(id: string, action: string, on?: boolean) => send(id, action, on)" />

      <template v-if="page === 'devices'">
        <section class="panel table-scroll"><h2>Dispositivos cadastrados</h2><table><thead><tr><th>ID</th><th>Nome</th><th>Tipo</th><th>Estado</th><th v-if="isAdmin">Gerenciar</th></tr></thead><tbody><tr v-for="device in court.devices" :key="device.id"><td><code>{{device.id}}</code></td><td>{{device.name}}</td><td>{{device.kind}}</td><td>{{device.enabled ? statusLabels[deviceState(device.id)] : 'Desativado'}}</td><td v-if="isAdmin"><button class="text-button" @click="edit(device)">Editar</button><button class="text-button" @click="disableDevice(device.id)" :disabled="!device.enabled">Desativar</button></td></tr></tbody></table></section>
        <section v-if="isAdmin" class="panel"><h2>Cadastrar ou editar</h2><form @submit.prevent="saveDevice" class="form-grid"><label>ID<input v-model="deviceForm.id" required pattern="[a-zA-Z0-9_-]+" /></label><label>Nome<input v-model="deviceForm.name" required /></label><label>Tipo<select v-model="deviceForm.kind"><option>sensor</option><option>actuator</option><option>equipment</option><option>button</option><option>simulator</option></select></label><label>Unidade<input v-model="deviceForm.unit" /></label><label>Faixa mínima<input type="number" v-model.number="deviceForm.config.min" step="any" /></label><label>Faixa máxima<input type="number" v-model.number="deviceForm.config.max" step="any" /></label><label class="check"><input type="checkbox" v-model="deviceForm.enabled" />Ativo</label><button :disabled="busy">Salvar dispositivo</button></form><small>Novos IDs precisam corresponder ao dispositivo que publica a telemetria. Sem leituras, o estado é “Sem dados”.</small></section>
      </template>

      <template v-if="page === 'messaging'">
        <section class="panel"><h2>RabbitMQ ao vivo</h2><p>Filas, taxas e consumidores. Para demonstrar acúmulo, pare o gravador com <code>docker compose stop writer</code> e retome com <code>docker compose start writer</code>.</p><div class="table-scroll"><table><thead><tr><th>Fila</th><th>Prontas</th><th>Em entrega</th><th>Consumidores</th><th>Publicação/s</th><th>Entrega/s</th></tr></thead><tbody><tr v-for="queue in queues" :key="queue.name"><td><code>{{queue.name}}</code></td><td>{{queue.ready}}</td><td>{{queue.unacked}}</td><td>{{queue.consumers}}</td><td>{{number(queue.publish_rate)}}</td><td>{{number(queue.deliver_rate)}}</td></tr></tbody></table></div></section>
        <section class="panel"><h2>Últimas mensagens</h2><div class="message-log"><details v-for="event in court.recent.slice(0, 30)" :key="event.id"><summary><span class="tag">{{event.type}}</span> {{event.device_id}} <small>{{time(event.timestamp)}}</small></summary><pre>{{JSON.stringify(event, null, 2)}}</pre></details></div></section>
        <section v-if="isAdmin" class="panel"><div class="section-heading"><h2>Mensagens mortas — DLQ</h2><button class="secondary" @click="attempt(async () => {dlq = await request('/messaging/dlq')})">Inspecionar DLQ</button></div><pre v-if="dlq.length">{{JSON.stringify(dlq, null, 2)}}</pre><p v-else class="empty">Nenhuma mensagem carregada. A inspeção preserva as mensagens na fila.</p></section>
      </template>

      <template v-if="page === 'lab'">
        <section class="panel"><h2>Dados sintéticos do compressor</h2><p>Simulação da vida dos equipamentos, com degradação gradual, ciclo diário e imperfeições nos sensores.</p><form @submit.prevent="generate" class="form-grid"><label>Equipamentos<input v-model.number="lab.equipment_count" type="number" min="10" max="200" /></label><label>Sensores de cada tipo<input v-model.number="lab.sensors_per_type" type="number" min="1" max="4" /></label><label>Período em dias<input v-model.number="lab.days" type="number" min="7" max="365" /></label><label>Intervalo em minutos<input v-model.number="lab.interval_minutes" type="number" min="1" max="60" /></label><label>Equipamentos com falha (%)<input v-model.number="lab.failure_percent" type="number" min="10" max="95" /></label><label>Ruído<input v-model.number="lab.noise" type="number" min="0.1" max="3" step="0.1" /></label><label>Leituras faltantes (%)<input v-model.number="lab.missing_percent" type="number" min="0" max="15" step="0.1" /></label><label>Outliers (%)<input v-model.number="lab.outlier_percent" type="number" min="0" max="5" step="0.1" /></label><label>Semente aleatória<input v-model.number="lab.seed" type="number" min="0" /></label><fieldset><legend>Modos de falha</legend><label class="check"><input type="checkbox" v-model="lab.failure_modes" value="bearing" />Rolamento</label><label class="check"><input type="checkbox" v-model="lab.failure_modes" value="overheating" />Superaquecimento</label><label class="check"><input type="checkbox" v-model="lab.failure_modes" value="imbalance" />Desbalanceamento</label></fieldset><div><strong>{{number(labReadings, 0)}} leituras</strong><p>Mínimo: 1 milhão. Máximo: 20 milhões de leituras e 2 milhões de amostras.</p><button :disabled="!isAdmin || busy || labReadings < 1000000 || !lab.failure_modes.length">Gerar dados</button><small v-if="!isAdmin">Geração disponível ao administrador.</small></div></form></section>
        <section class="panel"><h2>Jobs de geração</h2><article class="job" v-for="job in jobs.filter(job => job.kind === 'generate')" :key="job.id"><div class="section-heading"><code>{{job.id.slice(0, 8)}}</code><span>{{jobLabels[job.status]}} · {{job.progress}}%</span></div><progress :value="job.progress" max="100"></progress><p v-if="job.result.readings">{{number(job.result.readings, 0)}} leituras geradas</p><p v-if="job.result.error" class="error">{{job.result.error}}</p></article><p v-if="!jobs.some(job => job.kind === 'generate')" class="empty">Nenhum dataset gerado ainda.</p></section>
      </template>

      <template v-if="page === 'training'">
        <section class="panel"><h2>Treinar saúde e vida útil restante</h2><p>A divisão usa equipamentos distintos em treino, validação e teste. Uma versão só entra em uso se ambos os regressores superarem a previsão da média.</p><div class="button-row"><select v-model="selectedDataset"><option disabled value="">Selecione um dataset concluído</option><option v-for="dataset in datasets" :key="dataset.id" :value="dataset.id">{{dataset.id.slice(0, 8)}} · {{number(dataset.result.readings, 0)}} leituras</option></select><button :disabled="!isAdmin || busy || !selectedDataset" @click="train">Treinar dois modelos</button><button class="secondary" @click="attempt(loadCommon)">Atualizar versões</button></div><article class="job" v-for="job in jobs.filter(job => job.kind === 'train')" :key="job.id"><div class="section-heading"><code>{{job.id.slice(0, 8)}}</code><span>{{jobLabels[job.status]}} · {{job.progress}}%</span></div><progress :value="job.progress" max="100"></progress><p v-if="job.result.error" class="error">{{job.result.error}}</p></article></section>
        <section v-if="latestModel && activeModel && latestModel.id !== activeModel.id" class="panel"><h2>Último treino: {{latestModel.id.slice(0, 8)}}</h2><p>Esta versão não foi ativada. A inferência continua usando {{activeModel.id.slice(0, 8)}}; as métricas abaixo correspondem à versão em uso.</p></section><template v-if="activeModel"><section class="panel"><h2>Versão {{activeModel.id.slice(0, 8)}}</h2><p>{{activeModel.active ? 'Em uso na inferência' : 'Não ativada'}} · {{time(activeModel.timestamp)}}</p><p>Equipamentos por conjunto: treino {{activeModel.metrics.split.train?.length}}, validação {{activeModel.metrics.split.validation?.length}}, teste {{activeModel.metrics.split.test?.length}}.</p></section><section class="panel" v-for="(metric, name) in activeModel.metrics.metrics" :key="name"><h2>{{name === 'health' ? 'Índice de saúde (0–100)' : 'Vida útil restante (horas de operação simuladas)'}}</h2><p v-if="metric.scope === 'degradation_observed'">Modelo avaliado nas janelas com degradação observável. Em condição saudável, o prazo é inconclusivo.</p><p v-if="metric.samples">Amostras: treino {{number(metric.samples.train, 0)}}, validação {{number(metric.samples.validation, 0)}}, teste {{number(metric.samples.test, 0)}}.</p><span class="tag" :class="metric.beats_baseline ? 'normal' : 'critical'">{{metric.beats_baseline ? 'Superou a base simples' : 'Não superou a base simples'}}</span><table><thead><tr><th>Conjunto</th><th>MAE</th><th>RMSE</th><th>R²</th></tr></thead><tbody><tr><td>Teste</td><td>{{number(metric.test.mae, 3)}}</td><td>{{number(metric.test.rmse, 3)}}</td><td>{{number(metric.test.r2, 3)}}</td></tr><tr><td>Validação</td><td>{{number(metric.validation.mae, 3)}}</td><td>{{number(metric.validation.rmse, 3)}}</td><td>{{number(metric.validation.r2, 3)}}</td></tr><tr><td>Base simples (média)</td><td>{{number(metric.baseline.mae, 3)}}</td><td>{{number(metric.baseline.rmse, 3)}}</td><td>{{number(metric.baseline.r2, 3)}}</td></tr></tbody></table><div class="two-columns"><div><h3>Previsto contra real</h3><ModelChart :metrics="metric" /></div><div><h3>Importância dos atributos</h3><ModelChart :metrics="metric" importance /></div></div></section></template><section v-else class="panel empty">Gere um dataset no Laboratório e execute o primeiro treinamento.</section>
      </template>

      <template v-if="page === 'insights'">
        <section class="panel"><div class="section-heading"><div><span class="eyebrow">MANUTENÇÃO PREDITIVA</span><h2>Compressor do bebedouro</h2><p>{{insightStatus}}</p></div><span class="tag" :class="deviceState('compressor_01')">{{statusLabels[deviceState('compressor_01')]}}</span></div><div class="summary-grid"><div><span>Saúde estimada</span><h2>{{predictionFresh && court.prediction?.status === 'ready' ? number(court.prediction.health, 0) + '/100' : '—'}}</h2></div><div><span>Vida útil restante</span><h2>{{rulText}}</h2></div><div><span>Versão em uso</span><p><code>{{court.prediction?.version?.slice(0, 8) || 'Sem modelo'}}</code></p></div><div><span>Última previsão</span><p>{{court.prediction?.source_timestamp ? time(court.prediction.source_timestamp) : '—'}}</p></div></div><p v-if="predictionFresh && court.prediction?.status === 'ready'">{{court.prediction.rul_reason}} {{rulIntervalText}}</p><p>Saúde é uma estimativa da condição atual e pode variar com as leituras. A RUL só recebe um valor pontual quando a incerteza permite; não é uma contagem regressiva. Cada leitura a cada 2 segundos representa 5 minutos simulados. A RUL indica horas de funcionamento se a degradação atual continuar; as paradas não consomem essas horas. Faixas medidas em dados sintéticos, sem validação em compressor real.</p><h3>Falha simulada</h3><p>A degradação avança enquanto o compressor opera. O ciclo automático pode desligá-lo e pausar a previsão. A RUL pontual pode aparecer apenas na fase final; a IA recebe somente as medições e o relógio simulado, sem os rótulos verdadeiros.</p><div class="button-row"><button :disabled="!canOperate || busy" @click="send('compressor_01', 'inject_fault')">Injetar falha</button><button class="secondary" :disabled="!canOperate || busy" @click="send('compressor_01', 'reset_fault')">Restaurar equipamento</button></div></section>
        <div class="two-columns"><section class="panel"><h2>Tendência de saúde</h2><DataChart :points="court.history.health || []" label="0–100" /></section><section class="panel"><h2>RUL estimada · experimental</h2><p>Períodos sem prazo confiável ou com compressor desligado ficam sem linha.</p><DataChart :points="court.history.rul_hours || []" label="h simuladas" /></section></div>
        <div class="two-columns"><section class="panel"><h2>Tendência de vibração</h2><DataChart :points="court.history.compressor_vibration || []" label="mm/s" /></section><section class="panel"><h2>Alertas preditivos</h2><article v-for="alert in alerts" :key="alert.id" class="alert-item"><span class="tag" :class="alert.active ? 'critical' : 'normal'">{{alert.active ? 'Ativo' : 'Resolvido'}}</span><p>{{alert.message}}</p></article><p v-if="!alerts.length" class="empty">Nenhum alerta registrado.</p><small>Histerese: 3 previsões críticas para abrir; 10 normais para limpar.</small></section></div>
      </template>

      <template v-if="page === 'assistant'">
        <section class="panel"><h2>Assistente da quadra</h2><p>Pergunte sobre as leituras, alertas, saúde do compressor, métricas dos modelos ou arquitetura. As respostas são geradas pelo modelo local.</p><div class="chat-log"><article v-for="(message, index) in chat" :key="index" :class="['chat-message', message.role]"><strong>{{message.role === 'user' ? 'Você' : 'Assistente'}}</strong><p>{{message.text || '…'}}</p></article><p v-if="!chat.length" class="empty">Exemplo: “Qual o estado do compressor e o que significa o alerta?”</p></div><p v-if="chatStatus" role="status">{{chatStatus}}</p><form @submit.prevent="ask" class="chat-form"><textarea v-model="question" placeholder="Sua pergunta sobre os dados da quadra" maxlength="2000" rows="3" :disabled="chatBusy"></textarea><button :disabled="chatBusy || !question.trim()">{{chatBusy ? 'Respondendo…' : 'Enviar pergunta'}}</button></form><small>Até 5 perguntas por minuto por usuário. Respostas exibidas como texto, sem HTML ou imagens.</small></section>
      </template>

      <template v-if="page === 'admin' && isAdmin">
        <section class="panel"><h2>Regra de refrigeração</h2><form @submit.prevent="attempt(() => request('/rules/water_cooling', {method: 'PUT', body: JSON.stringify(rule)}), 'Regra atualizada.')" class="form-grid"><label>Ligar acima de (°C)<input v-model.number="rule.on_above" type="number" min="5" max="30" step="0.5" /></label><label>Desligar abaixo de (°C)<input v-model.number="rule.off_below" type="number" min="2" max="25" step="0.5" /></label><label class="check"><input type="checkbox" v-model="rule.enabled" />Regra ativa</label><button :disabled="busy">Salvar regra</button></form></section><section class="panel table-scroll"><div class="section-heading"><h2>Auditoria</h2><button class="secondary" @click="attempt(loadAdmin)">Atualizar</button></div><table><thead><tr><th>Horário</th><th>Usuário</th><th>Ação</th><th>Detalhes</th></tr></thead><tbody><tr v-for="item in auditing" :key="item.id"><td>{{time(item.timestamp)}}</td><td>{{item.username}}</td><td>{{item.action}}</td><td><details><summary>Ver</summary><pre>{{JSON.stringify(item.details, null, 2)}}</pre></details></td></tr></tbody></table></section>
      </template>
      <footer><span>Quadra Inteligente · segundo bimestre</span><div class="button-row"><a v-for="link in links" :key="link.name" :href="link.url" target="_blank" rel="noopener noreferrer">{{link.name}}</a></div></footer>
    </main>
  </div>
</template>

<style scoped>
.court-app{display:grid;grid-template-columns:220px 1fr;min-height:100vh}.sidebar{position:sticky;top:0;height:100vh;background:#0d1723;border-right:1px solid #253242;padding:28px 20px;display:flex;flex-direction:column;gap:25px}.brand{display:flex;align-items:center;gap:12px;color:#e2e8f0;text-decoration:none;line-height:1.25}.brand-mark{display:grid;place-items:center;width:42px;height:42px;background:#38d9ae;color:#08231b;font-weight:900;border-radius:12px;font-size:24px}.eyebrow{color:#6f91a4;font-size:11px;letter-spacing:1.6px;font-weight:700}.sidebar nav{display:flex;flex-direction:column;gap:4px}.sidebar nav button{text-align:left;background:none;color:#9eb0c0;border-radius:8px;padding:10px 12px;font-weight:500}.sidebar nav button.active{background:#173b35;color:#6ef0ca}.sidebar-bottom{margin-top:auto;display:grid;gap:8px}.workspace{max-width:1500px;width:100%;padding:30px clamp(18px,3vw,45px);display:flex;flex-direction:column;gap:22px}.page-header,.section-heading{display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap}.page-header h1{font-size:28px;margin-top:6px}.live-badge{font-size:12px;display:grid;grid-template-columns:8px 1fr;gap:5px 8px;color:#63e6be}.live-badge>span{width:7px;height:7px;background:#63e6be;border-radius:50%;margin-top:5px}.live-badge small{grid-column:2;color:#7890a3}.live-badge.offline{color:#f2bd65}.live-badge.offline>span{background:#f2bd65}.panel{background:#101c2a;border:1px solid #243346;border-radius:14px;padding:24px;min-width:0}.panel h2{font-size:18px;margin-bottom:12px}.panel h3{font-size:14px;margin:15px 0 6px}.panel p{color:#91a5b7;font-size:14px;margin-bottom:14px}.summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}.summary-grid h2{font-size:30px;margin:10px 0 4px}.summary-grid p{margin:0}.two-columns{display:grid;grid-template-columns:1.3fr 1fr;gap:20px}.sensor-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:18px}.sensor{border-left:3px solid #38d9ae;background:#152332;padding:12px;display:flex;flex-direction:column;gap:5px}.sensor>span{font-size:12px;color:#9eb0c0}.sensor strong{font-size:22px}.sensor.warning{border-color:#f2bd65}.sensor.critical{border-color:#f87171}.sensor.no_data{border-color:#62748a}.control-row{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:16px 0;border-bottom:1px solid #253242;margin-bottom:15px}.control-row p{margin:4px 0 0;font-size:12px}.button-row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}button{background:#38d9ae;border:0;color:#09261e;padding:10px 16px;border-radius:8px;cursor:pointer;font:inherit;font-size:13px;font-weight:650;transition:background .2s}button:hover{background:#67ebc8}button:disabled{opacity:.45;cursor:not-allowed}.secondary{background:#233446;color:#d6e4ef}.secondary:hover{background:#2e465e}.text-button{background:none;color:#88cebf;padding:4px 8px;font-size:12px}.text-button:hover{background:#173b35}input,select,textarea{width:100%;background:#0b1521;color:#d6e4ef;border:1px solid #30455b;border-radius:7px;padding:10px;font:inherit;font-size:13px;min-width:0}select{width:auto;max-width:100%}input:focus,select:focus,textarea:focus{outline:2px solid #38d9ae;outline-offset:1px}.form-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;align-items:end;margin-top:20px}.form-grid label,.form-stack label{display:flex;flex-direction:column;gap:8px;font-size:12px;color:#a8bbcb}.form-grid .check{flex-direction:row;align-items:center;justify-content:flex-start}.check input{width:auto}.form-grid select{width:100%}fieldset{border:1px solid #30455b;border-radius:7px;padding:12px;display:grid;gap:8px;font-size:12px}legend{color:#a8bbcb}.tag{display:inline-block;padding:4px 8px;border-radius:6px;background:#26394a;font-size:11px;color:#aec5d5}.normal{color:#63e6be}.warning{color:#f2bd65}.critical{color:#f87171}.no_data{color:#7890a3}.error,.notice,.stale{border-radius:8px;padding:12px 16px;font-size:13px}.error{color:#fca5a5;background:#3b2026;border:1px solid #734049}.notice{color:#8eead1;background:#12382f;border:1px solid #295d50}.stale{color:#f2cd8d;background:#332a1d;border:1px solid #5d4b2c}table{border-collapse:collapse;width:100%;font-size:12px;margin-top:18px;text-align:left}th{color:#7794a9;font-weight:600;border-bottom:1px solid #30455b;padding:12px}td{padding:12px;border-bottom:1px solid #213142;color:#c5d3de}.table-scroll{overflow-x:auto}pre{white-space:pre-wrap;word-break:break-word;font-size:11px;max-height:340px;overflow:auto;background:#0b1521;padding:14px;border-radius:7px}code{font-size:11px}small{font-size:11px;color:#7890a3}.panel>small{display:block;margin-top:14px}.empty{text-align:center;color:#7890a3;padding:30px 15px}.message-log{max-height:450px;overflow:auto}details{padding:9px 0;border-bottom:1px solid #213142}summary{cursor:pointer;font-size:12px;display:flex;gap:12px;align-items:center}summary small{margin-left:auto}.job{padding:16px 0;border-bottom:1px solid #243346}progress{width:100%;height:7px;accent-color:#38d9ae;margin:14px 0}.alert-item{border-bottom:1px solid #243346;padding:12px 0}.chat-log{min-height:280px;max-height:550px;overflow-y:auto;margin:22px 0;display:flex;flex-direction:column;gap:15px}.chat-message{background:#172b3c;border-radius:9px;padding:14px 18px;max-width:90%;align-self:flex-start}.chat-message.user{background:#153c33;align-self:flex-end}.chat-message strong{font-size:12px;color:#74c9b4}.chat-message p{white-space:pre-wrap;word-break:break-word;margin:8px 0 0;color:#d3e0e9;font-size:14px}.chat-form{display:flex;gap:12px;align-items:flex-end}.chat-form textarea{flex:1}footer{display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap;margin-top:auto;font-size:11px;color:#607f92;padding-top:20px;border-top:1px solid #243346}footer a{color:#86baa9;text-decoration:none}hr{border:0;border-top:1px solid #253242;margin:20px 0}.login-wrap{min-height:100vh;display:grid;place-items:center;padding:30px;background:radial-gradient(ellipse at 50% 20%,#12372e,transparent 65%)}.login-card{width:100%;max-width:440px;border:1px solid #2c4354;background:#101c2a;border-radius:20px;padding:38px}.login-card h1{font-size:30px;margin:12px 0 16px}.login-card>p{font-size:14px;color:#9eb0c0}.form-stack{display:flex;flex-direction:column;gap:18px;margin:28px 0}.login-card>small{display:block;line-height:1.8}@media(max-width:1000px){.court-app{grid-template-columns:175px 1fr}.sidebar{padding:24px 12px}.summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.two-columns{grid-template-columns:1fr}.form-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){.court-app{display:block}.sidebar{height:auto;position:static;padding:18px}.sidebar nav{flex-direction:row;overflow-x:auto;gap:5px}.sidebar nav button{white-space:nowrap}.sidebar>.eyebrow{display:none}.sidebar-bottom{display:flex;align-items:center;gap:12px}.workspace{padding:22px 14px}.form-grid{grid-template-columns:1fr}.panel{padding:18px}.sensor-grid{grid-template-columns:1fr}.page-header h1{font-size:24px}.chat-form{flex-direction:column;align-items:stretch}}
</style>
