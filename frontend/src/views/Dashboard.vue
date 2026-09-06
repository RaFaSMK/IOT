<template>
  <main class="dashboard">
    <!-- Header -->
    <header class="dash-header">
      <div class="header-brand">
        <span class="brand-icon">🏐</span>
        <div>
          <h1 class="brand-title">Quadra Inteligente</h1>
          <p class="brand-sub">Beach Tennis · IoT Dashboard</p>
        </div>
      </div>
      <div class="header-meta">
        <span class="refresh-badge" :class="{ spinning: loading }">↻</span>
        <span class="meta-time">Atualiza a cada 5s</span>
      </div>
    </header>

    <!-- Erro global -->
    <div v-if="error" class="error-banner">
      ⚠️ {{ error }}
    </div>

    <!-- KPI Cards -->
    <section class="kpi-row">
      <div class="kpi-card">
        <span class="kpi-value">{{ totalToday }}</span>
        <span class="kpi-label">Highlights hoje</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-value">{{ totalLastHour }}</span>
        <span class="kpi-label">Última hora</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-value">{{ topPlayer }}</span>
        <span class="kpi-label">Jogador líder</span>
      </div>
    </section>

    <!-- Grid principal -->
    <section class="dash-grid">
      <div class="col-left">
        <CourtStatus :health="health" :last-event="events[0]" />
      </div>
      <div class="col-main">
        <HighlightChart :series="series" />
        <EventLog :events="events" />
      </div>
    </section>

    <!-- Footer -->
    <footer class="dash-footer">
      <span>Smart Court IoT · MQTT → InfluxDB → Vue 3</span>
      <span>Quadra: court_01</span>
    </footer>
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import HighlightChart from '@/components/HighlightChart.vue'
import EventLog from '@/components/EventLog.vue'
import CourtStatus from '@/components/CourtStatus.vue'
import { useHighlights } from '@/composables/useHighlights'

const { events, series, health, loading, error } = useHighlights()

const totalToday = computed(() => series.value.reduce((s, p) => s + p.count, 0))
const totalLastHour = computed(() => events.value.length)
const topPlayer = computed(() => {
  const count: Record<string, number> = {}
  for (const ev of events.value) count[ev.player] = (count[ev.player] ?? 0) + 1
  const top = Object.entries(count).sort((a, b) => b[1] - a[1])[0]
  return top ? `Jogador ${top[0]}` : '—'
})
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 1.5rem clamp(1rem, 4vw, 3rem);
  max-width: 1400px;
  margin: 0 auto;
}

/* ── Header ── */
.dash-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 1rem;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.brand-icon { font-size: 2.2rem; }

.brand-title {
  font-size: 1.6rem;
  font-weight: 800;
  margin: 0;
  background: linear-gradient(135deg, #00e5a0, #0070f3);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.brand-sub { font-size: 0.8rem; color: var(--text-secondary); margin: 0; }

.header-meta { display: flex; align-items: center; gap: 0.5rem; }

.refresh-badge {
  font-size: 1.2rem;
  color: var(--accent-green);
  display: inline-block;
  transition: transform 0.3s;
}
.refresh-badge.spinning { animation: spin 1s linear infinite; }

@keyframes spin { to { transform: rotate(360deg); } }

.meta-time { font-size: 0.75rem; color: var(--text-secondary); }

/* ── Error Banner ── */
.error-banner {
  background: rgba(239,68,68,0.12);
  border: 1px solid #ef4444;
  color: #fca5a5;
  border-radius: 10px;
  padding: 0.75rem 1rem;
  font-size: 0.875rem;
}

/* ── KPI Row ── */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}

.kpi-card {
  background: var(--glass-bg);
  backdrop-filter: blur(12px);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  transition: border-color 0.2s, transform 0.2s;
}

.kpi-card:hover {
  border-color: var(--accent-green);
  transform: translateY(-2px);
}

.kpi-value {
  font-size: 2rem;
  font-weight: 800;
  color: var(--accent-green);
  font-variant-numeric: tabular-nums;
}

.kpi-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

/* ── Main Grid ── */
.dash-grid {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 1.25rem;
  align-items: start;
}

.col-left { display: flex; flex-direction: column; }

.col-main {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* ── Footer ── */
.dash-footer {
  display: flex;
  justify-content: space-between;
  font-size: 0.72rem;
  color: #334155;
  padding-top: 0.5rem;
  border-top: 1px solid var(--glass-border);
  flex-wrap: wrap;
  gap: 0.5rem;
}

/* ── Responsivo ── */
@media (max-width: 768px) {
  .kpi-row { grid-template-columns: 1fr 1fr; }
  .dash-grid { grid-template-columns: 1fr; }
}

@media (max-width: 480px) {
  .kpi-row { grid-template-columns: 1fr; }
}
</style>
