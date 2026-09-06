<template>
  <div class="chart-wrapper">
    <div class="chart-header">
      <span class="chart-icon">📊</span>
      <h2 class="chart-title">Highlights por Hora (últimas 24h)</h2>
    </div>
    <v-chart class="echarts" :option="option" autoresize />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
} from 'echarts/components'
import type { HighlightPoint } from '@/types/highlight'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, DataZoomComponent])

const props = defineProps<{ series: HighlightPoint[] }>()

const option = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(15,17,23,0.95)',
    borderColor: '#00e5a0',
    borderWidth: 1,
    textStyle: { color: '#e2e8f0', fontSize: 13 },
    formatter: (params: any[]) => {
      const p = params[0]
      const d = new Date(p.axisValue)
      return `<b>${d.toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })}</b><br/>🎾 ${p.value} highlight${p.value !== 1 ? 's' : ''}`
    },
  },
  grid: { left: '3%', right: '3%', bottom: '10%', top: '8%', containLabel: true },
  xAxis: {
    type: 'time',
    axisLine: { lineStyle: { color: '#334155' } },
    axisLabel: {
      color: '#64748b',
      fontSize: 11,
      formatter: (val: number) =>
        new Date(val).toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
    },
    splitLine: { show: false },
  },
  yAxis: {
    type: 'value',
    minInterval: 1,
    axisLine: { show: false },
    axisLabel: { color: '#64748b', fontSize: 11 },
    splitLine: { lineStyle: { color: '#1e293b', type: 'dashed' } },
  },
  dataZoom: [{ type: 'inside', start: 0, end: 100 }],
  series: [
    {
      type: 'bar',
      name: 'Highlights',
      data: props.series.map(p => [p.time, p.count]),
      itemStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: '#00e5a0' },
            { offset: 1, color: '#0070f3' },
          ],
        },
        borderRadius: [4, 4, 0, 0],
      },
      emphasis: {
        itemStyle: { color: '#00ffbd' },
      },
      barMaxWidth: 40,
      animationDuration: 600,
    },
  ],
}))
</script>

<style scoped>
.chart-wrapper {
  background: var(--glass-bg);
  backdrop-filter: blur(12px);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  padding: 1.5rem;
}

.chart-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.chart-icon { font-size: 1.2rem; }

.chart-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.echarts {
  width: 100%;
  height: 280px;
}
</style>
