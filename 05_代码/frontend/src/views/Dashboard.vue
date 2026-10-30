<template>
  <div>
    <h2>监控看板</h2>
    <el-row :gutter="20">
      <el-col :span="6"><el-card><div>调用次数</div><h2>{{ summary.calls ?? '-' }}</h2></el-card></el-col>
      <el-col :span="6"><el-card><div>Token 总量</div><h2>{{ summary.tokens ?? '-' }}</h2></el-card></el-col>
      <el-col :span="6"><el-card><div>成本 (USD)</div><h2>${{ summary.cost ?? '-' }}</h2></el-card></el-col>
      <el-col :span="6"><el-card><div>错误率</div><h2>{{ (summary.error_rate * 100 ?? '-') + '%' }}</h2></el-card></el-col>
    </el-row>
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card>
          <div>P50 / P99 延迟 (ms)</div>
          <div ref="chartRef" style="height: 300px; margin-top: 10px"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <div>P50: {{ summary.p50_ms ?? '-' }} ms | P99: {{ summary.p99_ms ?? '-' }} ms</div>
          <div style="margin-top: 10px; color: #999; font-size: 13px">最近 7 天趋势，数据来自 ClickHouse trace_records 表</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import client from '../api/client'

const summary = ref<any>({})
const chartRef = ref<HTMLElement>()

async function loadData() {
  summary.value = await client.get('/api/metrics/summary?range_days=7')
  const timeseries = await client.get('/api/metrics/timeseries?metric=latency&range_days=7')
  await nextTick()
  if (chartRef.value && timeseries.length) {
    const chart = echarts.init(chartRef.value)
    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['P50', 'P99'] },
      xAxis: { type: 'category', data: timeseries.map((t: any) => t.date) },
      yAxis: { type: 'value', name: 'ms' },
      series: [
        { name: 'P50', type: 'line', data: timeseries.map((t: any) => t.p50) },
        { name: 'P99', type: 'line', data: timeseries.map((t: any) => t.p99) },
      ],
    })
  }
}

onMounted(loadData)
</script>
