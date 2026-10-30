<template>
  <div>
    <h2>评测记录</h2>
    <el-table :data="runs" v-loading="loading" style="width: 100%">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="dataset_id" label="Dataset" width="80" />
      <el-table-column prop="prompt_a_id" label="Prompt A" width="90" />
      <el-table-column prop="prompt_b_id" label="Prompt B" width="90" />
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'done' ? 'success' : row.status === 'running' ? 'warning' : 'danger'">
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="score_a_avg" label="A 得分" width="90" />
      <el-table-column prop="score_b_avg" label="B 得分" width="90" />
      <el-table-column prop="total_cases" label="Case 数" width="90" />
      <el-table-column prop="started_at" label="开始时间" />
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push(`/runs/${row.id}`)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import client from '../api/client'

const runs = ref<any[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    runs.value = await client.get('/api/runs')
  } catch (e) {
    console.error('加载 runs 失败', e)
  } finally {
    loading.value = false
  }
})
</script>
