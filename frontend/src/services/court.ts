import { reactive, computed } from 'vue'

export interface User { username: string; role: 'viewer' | 'operator' | 'admin' }
export interface Device { id: string; name: string; kind: string; unit: string; config: { min?: number; max?: number }; enabled: boolean }
export interface Event { id: string; timestamp: string; type: string; device_id: string; payload: Record<string, unknown>; correlation_id?: string }
export interface Telemetry { sensors: Record<string, number>; actuators: Record<string, boolean>; simulation?: {step_hours: number; elapsed_hours: number} }
export interface Prediction { status: string; version?: string; health?: number; rul_hours?: number | null; rul_reference_hours?: number; rul_status?: string; rul_reason?: string; rul_interval?: [number, number]; rul_unit?: string; step_hours?: number; source_timestamp?: string }
export interface Job { id: string; kind: string; status: string; progress: number; config: Record<string, unknown>; result: Record<string, unknown>; timestamp: string }
export interface Metrics { test: {mae: number; rmse: number; r2: number}; validation: {mae: number; rmse: number; r2: number}; baseline: {mae: number; rmse: number; r2: number}; beats_baseline: boolean; scope?: string; samples?: {train: number; validation: number; test: number}; scatter: {real: number; predicted: number}[]; importance: {feature: string; value: number}[] }
export interface Model { id: string; active: boolean; timestamp: string; metrics: {metrics: Record<string, Metrics>; accepted: boolean; split: Record<string, number[]>} }
export interface Alert { id: string; device_id: string; message: string; active: boolean; timestamp: string }

export const court = reactive({
  user: null as User | null,
  token: sessionStorage.getItem('court-token') || '',
  connected: false,
  telemetry: null as Telemetry | null,
  timestamp: '',
  prediction: null as Prediction | null,
  history: {} as Record<string, {time: string; value: number | null}[]>,
  devices: [] as Device[],
  recent: [] as Event[],
  alerts: {} as Record<string, boolean>,
  now: Date.now(),
})
export const fresh = computed(() => !!court.timestamp && court.now - Date.parse(court.timestamp) < 10_000)
export const predictionFresh = computed(() => !!court.prediction?.source_timestamp && court.now - Date.parse(court.prediction.source_timestamp) < 10_000 && fresh.value)
export const canOperate = computed(() => court.user?.role === 'operator' || court.user?.role === 'admin')
export const isAdmin = computed(() => court.user?.role === 'admin')
let socket: WebSocket | null = null
let reconnect: ReturnType<typeof setTimeout> | undefined
let epoch = 0
const subscribers = new Set<(event: Event) => void>()

export function subscribe(callback: (event: Event) => void) {
  subscribers.add(callback)
  return () => subscribers.delete(callback)
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (court.token) headers.set('Authorization', `Bearer ${court.token}`)
  if (options.body) headers.set('Content-Type', 'application/json')
  const response = await fetch('/api' + path, {...options, headers})
  if (response.status === 401 && path !== '/login') logout()
  if (!response.ok) {
    let detail = `Erro ${response.status}`
    try { const body = await response.json(); detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail) } catch { /* Sem corpo JSON. */ }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

function appendHistory(identifier: string, time: string, value: number | null) {
  const series = court.history[identifier] || []
  const previous = series.at(-1)
  if (previous && Date.parse(time) <= Date.parse(previous.time)) return
  if (previous && Date.parse(time) - Date.parse(previous.time) > 10_000) {
    series.push({time: new Date(Date.parse(previous.time) + 1).toISOString(), value: null})
  }
  series.push({time, value})
  court.history[identifier] = series.slice(-120)
}

function receive(event: Event) {
  if (event.type === 'telemetry') {
    court.telemetry = event.payload as unknown as Telemetry
    court.timestamp = event.timestamp
    for (const [identifier, value] of Object.entries(court.telemetry.sensors)) {
      appendHistory(identifier, event.timestamp, value)
    }
    for (const [identifier, on] of Object.entries(court.telemetry.actuators)) appendHistory(identifier, event.timestamp, on ? 1 : 0)
    appendHistory('simulator', event.timestamp, 1)
    appendHistory('highlight_button', event.timestamp, court.history.highlight_button?.at(-1)?.value ?? 0)
  } else if (event.type === 'prediction') {
    court.prediction = event.payload as unknown as Prediction
    if (court.prediction.source_timestamp) {
      for (const [id, value] of [['health', court.prediction.health], ['rul_hours', court.prediction.rul_hours]] as const) {
        appendHistory(id, court.prediction.source_timestamp, court.prediction.status === 'ready' ? value ?? null : null)
      }
    }
  } else if (event.type === 'alert') court.alerts[event.device_id] = Boolean(event.payload.active)
  else if (event.type === 'highlight') appendHistory('highlight_button', event.timestamp, (court.history.highlight_button?.at(-1)?.value ?? 0) + 1)
  court.recent.unshift(event)
  court.recent.splice(100)
  subscribers.forEach(callback => callback(event))
}

export const rulText = computed(() => {
  const prediction = court.prediction
  if (!predictionFresh.value || prediction?.status !== 'ready') return 'Indisponível'
  if (prediction.rul_hours == null) return prediction.rul_status === 'not_identifiable' ? 'Sem prazo identificado' : 'Inconclusiva'
  return (prediction.rul_status === 'low_confidence' ? '≈ ' : '') + prediction.rul_hours.toLocaleString('pt-BR', {maximumFractionDigits: 1}) + (prediction.rul_unit === 'simulated_operating_hours' ? ' h simuladas' : ' h (estimativa)')
})

export const rulQualityText = computed(() => {
  if (!predictionFresh.value || court.prediction?.status !== 'ready' || court.prediction.rul_hours == null) return ''
  return court.prediction.rul_status === 'low_confidence' ? 'Baixa confiança' : 'Estimativa experimental'
})

export const rulIntervalText = computed(() => {
  const prediction = court.prediction
  if (!predictionFresh.value || prediction?.status !== 'ready' || !prediction.rul_interval) return ''
  const [low, high] = prediction.rul_interval
  const format = (value: number) => value.toLocaleString('pt-BR', {maximumFractionDigits: 1})
  return `Faixa experimental: ${format(low)} a ${format(high)} h${prediction.rul_unit === 'simulated_operating_hours' ? ' de operação simulada' : ''}`
})

export async function connect() {
  const generation = ++epoch
  clearTimeout(reconnect)
  if (socket) { socket.onclose = null; socket.close() }
  try {
    const {ticket} = await request<{ticket: string}>('/ws-ticket', {method: 'POST'})
    if (generation !== epoch) return
    socket = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/ws?ticket=${encodeURIComponent(ticket)}`)
    socket.onopen = () => {court.connected = true}
    socket.onmessage = message => {
      const event = JSON.parse(message.data)
      if (event.type === 'snapshot') {
        for (const item of event.payload.telemetry) receive(item)
        for (const item of event.payload.predictions) receive(item)
        for (const item of event.payload.alerts || []) receive(item)
      } else if (event.type !== 'heartbeat') receive(event)
    }
    socket.onclose = () => {court.connected = false; if (court.token && generation === epoch) reconnect = setTimeout(connect, 2000)}
    socket.onerror = () => socket?.close()
  } catch { if (court.token && generation === epoch) reconnect = setTimeout(connect, 3000) }
}

export async function signIn(username: string, password: string) {
  const result = await request<{token: string; user: User}>('/login', {method: 'POST', body: JSON.stringify({username, password})})
  court.token = result.token
  court.user = result.user
  sessionStorage.setItem('court-token', result.token)
  await initialize()
}

export async function initialize() {
  court.user = await request<User>('/me')
  court.devices = await request<Device[]>('/devices')
  await connect()
}

export function logout() {
  ++epoch
  clearTimeout(reconnect)
  if (socket) {socket.onclose = null; socket.close()}
  court.token = ''
  court.user = null
  court.connected = false
  court.telemetry = null
  court.prediction = null
  court.timestamp = ''
  court.history = {}
  court.recent = []
  court.alerts = {}
  sessionStorage.removeItem('court-token')
}

export async function command(identifier: string, action: string, on?: boolean) {
  return request<{command_id: string}>(`/devices/${identifier}/command`, {method: 'POST', body: JSON.stringify({action, ...(on !== undefined ? {on} : {})})})
}

export function deviceState(identifier: string) {
  if (!fresh.value) return 'no_data'
  const device = court.devices.find(item => item.id === identifier)
  if (!device?.enabled) return 'no_data'
  if (court.alerts.compressor_01 && ['compressor_01', 'compressor_temperature', 'compressor_current', 'compressor_vibration', 'cooling'].includes(identifier)) return 'critical'
  if (identifier === 'compressor_01' && predictionFresh.value && court.prediction?.status === 'ready') {
    const health = court.prediction.health ?? 100
    return health < 40 ? 'critical' : health < 70 ? 'warning' : 'normal'
  }
  const value = court.telemetry?.sensors[identifier]
  if (value === undefined) return court.telemetry?.actuators[identifier] !== undefined || ['compressor_01', 'highlight_button', 'simulator'].includes(identifier) ? 'normal' : 'no_data'
  if ((device?.config.min !== undefined && value < device.config.min) || (device?.config.max !== undefined && value > device.config.max)) return 'warning'
  return 'normal'
}
