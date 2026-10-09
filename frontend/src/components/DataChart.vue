<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, ScatterChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
use([CanvasRenderer, LineChart, ScatterChart, BarChart, GridComponent, TooltipComponent, LegendComponent])
const props = defineProps<{points: {time: string; value: number}[]; label?: string}>()
const option = computed(() => ({
  tooltip: {trigger: 'axis'},
  grid: {left: 50, right: 20, top: 25, bottom: 40},
  xAxis: {type: 'time', axisLabel: {color: '#94a3b8'}},
  yAxis: {type: 'value', name: props.label || '', axisLabel: {color: '#94a3b8'}, splitLine: {lineStyle: {color: '#243346'}}},
  series: [{type: 'line', data: props.points.map(point => [point.time, point.value]), showSymbol: false, lineStyle: {color: '#38d9ae'}, areaStyle: {color: '#38d9ae', opacity: .08}}],
}))
</script>
<template><VChart :option="option" autoresize class="data-chart" /></template>
<style scoped>.data-chart {height: 250px; width: 100%;}</style>
