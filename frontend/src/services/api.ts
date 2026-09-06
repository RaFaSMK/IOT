// Cliente HTTP para a API do backend Smart Court

import type {
  HighlightsResponse,
  HighlightStats,
  HealthStatus,
} from '@/types/highlight'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`)
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))
  }
  const res = await fetch(url.toString())
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`)
  return res.json() as Promise<T>
}

/** Lista os highlight events mais recentes */
export function fetchHighlights(start = '-1h'): Promise<HighlightsResponse> {
  return get<HighlightsResponse>('/api/highlights', { start })
}

/** Retorna série temporal de contagens para o gráfico */
export function fetchStats(start = '-24h', bucket_interval = '1h'): Promise<HighlightStats> {
  return get<HighlightStats>('/api/highlights/stats', { start, bucket_interval })
}

/** Verifica status das dependências */
export function fetchHealth(): Promise<HealthStatus> {
  return get<HealthStatus>('/api/health')
}
