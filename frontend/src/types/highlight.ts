// Tipos TypeScript para o domínio de highlights

export interface HighlightEvent {
  time: string        // ISO 8601
  court_id: string
  player: string      // 'A' | 'B'
  event_type: string  // 'highlight' | 'ace' | 'winner' | 'error'
}

export interface HighlightStats {
  series: HighlightPoint[]
}

export interface HighlightPoint {
  time: string  // ISO 8601
  count: number
}

export interface HighlightsResponse {
  total: number
  events: HighlightEvent[]
}

export interface HealthStatus {
  status: 'ok' | 'degraded'
  dependencies: {
    mqtt_broker: { status: string; message?: string }
    influxdb: { status: string; message?: string }
  }
}
