<template>
  <div>
    <el-page-header @back="$router.back()" content="评测详情" />
    <div v-loading="loading" style="margin-top: 20px">
      <el-descriptions :column="3" border v-if="run">
        <el-descriptions-item label="Run ID">{{ run.id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="run.status === 'done' ? 'success' : 'warning'">{{ run.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Case 总数">{{ run.total_cases }}</el-descriptions-item>
        <el-descriptions-item label="Prompt A 平均分">{{ run.score_a_avg }}</el-descriptions-item>
        <el-descriptions-item label="Prompt B 平均分">{{ run.score_b_avg }}</el-descriptions-item>
        <el-descriptions-item label="结束时间">{{ run.finished_at }}</el-descriptions-item>
      </el-descriptions>

      <h3 style="margin-top: 24px">逐 Case 对比</h3>
      <el-table :data="run?.results || []" style="width: 100%" v-if="run?.results?.length">
        <el-table-column prop="case_id" label="Case ID" width="80" />
        <el-table-column prop="score_a" label="A 得分" width="90" />
        <el-table-column prop="score_b" label="B 得分" width="90" />
        <el-table-column prop="judge_reason" label="Judge 理由" />
      </el-table>
      <el-empty v-else description="暂无评测结果" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import client from '../api/client'

const route = useRoute()
const run = ref<any>(null)
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    run.value = await client.get(`/api/runs/${route.params.id}`)
  } catch (e) {
    console.error('加载 run 详情失败', e)
  } finally {
    loading.value = false
  }
})
</script>
