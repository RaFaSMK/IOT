// useHighlights.ts — Composable com polling automático a cada 5s

import { ref, onMounted, onUnmounted } from 'vue'
import { fetchHighlights, fetchStats, fetchHealth } from '@/services/api'
import type { HighlightEvent, HighlightPoint, HealthStatus } from '@/types/highlight'

const POLL_INTERVAL_MS = 5_000

export function useHighlights() {
  const events = ref<HighlightEvent[]>([])
  const series = ref<HighlightPoint[]>([])
  const health = ref<HealthStatus | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let timer: ReturnType<typeof setInterval> | null = null

  async function refresh() {
    try {
      loading.value = true
      error.value = null
      const [evResp, statsResp, healthResp] = await Promise.all([
        fetchHighlights('-1h'),
        fetchStats('-24h', '1h'),
        fetchHealth(),
      ])
      events.value = evResp.events
      series.value = statsResp.series
      health.value = healthResp
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      loading.value = false
    }
  }

  onMounted(() => {
    refresh()
    timer = setInterval(refresh, POLL_INTERVAL_MS)
  })

  onUnmounted(() => {
    if (timer) clearInterval(timer)
  })

  return { events, series, health, loading, error, refresh }
}
