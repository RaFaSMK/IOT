<template>
  <div class="status-card">
    <!-- Status geral -->
    <div class="status-row">
      <div class="status-indicator" :class="overallClass">
        <span class="pulse-dot" />
      </div>
      <div class="status-info">
        <span class="status-label">Sistema</span>
        <span class="status-value" :class="overallClass">{{ overallLabel }}</span>
      </div>
    </div>

    <div class="divider" />

    <!-- Detalhes de dependências -->
    <div class="deps">
      <div class="dep-item">
        <span class="dep-icon">📡</span>
        <span class="dep-name">MQTT Broker</span>
        <span class="dep-dot" :class="mqttClass" />
      </div>
      <div class="dep-item">
        <span class="dep-icon">🗃️</span>
        <span class="dep-name">InfluxDB</span>
        <span class="dep-dot" :class="influxClass" />
      </div>
    </div>

    <div class="divider" />

    <!-- Último evento -->
    <div class="last-event" v-if="lastEvent">
      <span class="last-label">Último evento</span>
      <span class="last-value">
        🎾 Jogador {{ lastEvent.player }} — {{ lastEvent.event_type.toUpperCase() }}
      </span>
      <span class="last-time">{{ formatRelative(lastEvent.time) }}</span>
    </div>
    <div class="last-event" v-else>
      <span class="last-label">Aguardando eventos...</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { HealthStatus, HighlightEvent } from '@/types/highlight'

const props = defineProps<{
  health: HealthStatus | null
  lastEvent: HighlightEvent | undefined
}>()

const isOk = computed(() => props.health?.status === 'ok')
const overallClass = computed(() => (isOk.value ? 'ok' : 'degraded'))
const overallLabel = computed(() => (isOk.value ? 'Online' : 'Degradado'))

const mqttOk = computed(() => props.health?.dependencies.mqtt_broker.status === 'ok')
const influxOk = computed(() => props.health?.dependencies.influxdb.status === 'pass')

const mqttClass = computed(() => (mqttOk.value ? 'dot-ok' : 'dot-fail'))
const influxClass = computed(() => (influxOk.value ? 'dot-ok' : 'dot-fail'))

function formatRelative(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60) return `há ${diff}s`
  if (diff < 3600) return `há ${Math.floor(diff / 60)}min`
  return new Date(iso).toLocaleTimeString('pt-BR')
}
</script>

<style scoped>
.status-card {
  background: var(--glass-bg);
  backdrop-filter: blur(12px);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.status-indicator {
  position: relative;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.status-indicator.ok { background: rgba(0, 229, 160, 0.15); border: 2px solid var(--accent-green); }
.status-indicator.degraded { background: rgba(239, 68, 68, 0.15); border: 2px solid #ef4444; }

.pulse-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  display: block;
}

.ok .pulse-dot {
  background: var(--accent-green);
  box-shadow: 0 0 0 0 rgba(0, 229, 160, 0.7);
  animation: pulse-green 2s infinite;
}

.degraded .pulse-dot {
  background: #ef4444;
  box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7);
  animation: pulse-red 2s infinite;
}

@keyframes pulse-green {
  0%   { box-shadow: 0 0 0 0 rgba(0, 229, 160, 0.6); }
  70%  { box-shadow: 0 0 0 12px rgba(0, 229, 160, 0); }
  100% { box-shadow: 0 0 0 0 rgba(0, 229, 160, 0); }
}
@keyframes pulse-red {
  0%   { box-shadow: 0 0 0 0 rgba(239,68,68,0.6); }
  70%  { box-shadow: 0 0 0 12px rgba(239,68,68,0); }
  100% { box-shadow: 0 0 0 0 rgba(239,68,68,0); }
}

.status-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  display: block;
}
.status-value {
  font-size: 1.1rem;
  font-weight: 700;
}
.status-value.ok { color: var(--accent-green); }
.status-value.degraded { color: #ef4444; }

.divider { height: 1px; background: var(--glass-border); }

.deps { display: flex; flex-direction: column; gap: 0.5rem; }

.dep-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--text-secondary);
}
.dep-icon { font-size: 1rem; }
.dep-name { flex: 1; }

.dep-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-ok   { background: var(--accent-green); }
.dot-fail { background: #ef4444; }

.last-event {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.last-label {
  font-size: 0.72rem;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.last-value { font-size: 0.9rem; font-weight: 600; color: var(--text-primary); }
.last-time { font-size: 0.75rem; color: var(--text-secondary); }
</style>
