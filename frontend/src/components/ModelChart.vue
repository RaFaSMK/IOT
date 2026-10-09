<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { ScatterChart, BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import type {Metrics} from '@/services/court'
use([CanvasRenderer, ScatterChart, BarChart, LineChart, GridComponent, TooltipComponent])
const props = defineProps<{metrics: Metrics; importance?: boolean}>()
const option = computed(() => props.importance ? {
  grid: {left: 210, right: 20, top: 15, bottom: 30}, tooltip: {trigger: 'axis'},
  xAxis: {type: 'value', axisLabel: {color: '#94a3b8'}},
  yAxis: {type: 'category', inverse: true, data: props.metrics.importance.slice(0, 8).map(item => item.feature), axisLabel: {color: '#94a3b8', fontSize: 10}},
  series: [{type: 'bar', data: props.metrics.importance.slice(0, 8).map(item => item.value), itemStyle: {color: '#38d9ae'}}],
} : {
  grid: {left: 60, right: 25, top: 20, bottom: 55}, tooltip: {trigger: 'item'},
  xAxis: {type: 'value', name: 'Real', nameLocation: 'middle', nameGap: 30, axisLabel: {color: '#94a3b8'}},
  yAxis: {type: 'value', name: 'Previsto', axisLabel: {color: '#94a3b8'}, splitLine: {lineStyle: {color: '#243346'}}},
  series: [{type: 'scatter', data: props.metrics.scatter.map(item => [item.real, item.predicted]), symbolSize: 5, itemStyle: {color: '#38d9ae'}}],
})
</script>
<template><VChart :option="option" autoresize class="model-chart" /></template>
<style scoped>.model-chart {height: 290px; width: 100%;}</style>
