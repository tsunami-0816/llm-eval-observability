<template>
  <div>
    <h2>评测集管理</h2>
    <el-button type="primary" @click="dsDialog = true">新建评测集</el-button>

    <el-table :data="datasets" style="margin-top: 15px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="description" label="描述" />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" @click="selectDataset(row)">管理 Cases</el-button>
          <el-button size="small" type="primary" @click="openRunDialog(row)">跑评测</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dsDialog" title="新建评测集">
      <el-form :model="dsForm">
        <el-form-item label="名称"><el-input v-model="dsForm.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="dsForm.description" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dsDialog = false">取消</el-button>
        <el-button type="primary" @click="createDataset">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="caseDialog" title="管理 Cases" width="60%">
      <el-input v-model="caseText" type="textarea" :rows="6" placeholder="每行一条，格式：输入|期望输出" />
      <el-button type="primary" style="margin-top: 10px" @click="importCases">导入</el-button>
      <el-table :data="cases" style="margin-top: 15px">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="input" label="输入" />
        <el-table-column prop="expected_output" label="期望输出" />
      </el-table>
    </el-dialog>

    <!-- 跑评测对话框 -->
    <el-dialog v-model="runDialog" title="跑 A/B 评测">
      <el-form>
        <el-form-item label="Prompt A">
          <el-select v-model="runForm.prompt_a_id" placeholder="选版本 A" style="width: 100%">
            <el-option v-for="p in prompts" :key="p.id" :label="`${p.name} ${p.version}`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="Prompt B">
          <el-select v-model="runForm.prompt_b_id" placeholder="选版本 B" style="width: 100%">
            <el-option v-for="p in prompts" :key="p.id" :label="`${p.name} ${p.version}`" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="runDialog = false">取消</el-button>
        <el-button type="primary" @click="startRun">开始评测</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import client from '../api/client'
import { useRouter } from 'vue-router'

const router = useRouter()
const datasets = ref<any[]>([])
const cases = ref<any[]>([])
const prompts = ref<any[]>([])
const currentDatasetId = ref(0)
const dsDialog = ref(false)
const caseDialog = ref(false)
const runDialog = ref(false)
const caseText = ref('')
const dsForm = reactive({ name: '', description: '' })
const runForm = reactive({ prompt_a_id: 0, prompt_b_id: 0 })

async function loadDatasets() {
  datasets.value = await client.get('/api/datasets')
}

async function loadPrompts() {
  prompts.value = await client.get('/api/prompts')
}

async function createDataset() {
  await client.post('/api/datasets', dsForm)
  ElMessage.success('创建成功')
  dsDialog.value = false
  dsForm.name = dsForm.description = ''
  loadDatasets()
}

async function selectDataset(row: any) {
  currentDatasetId.value = row.id
  caseDialog.value = true
  cases.value = await client.get(`/api/datasets/${row.id}/cases`)
}

async function importCases() {
  const lines = caseText.value.trim().split('\n').filter(Boolean)
  const cases_data = lines.map((line) => {
    const [input, expected] = line.split('|')
    return { input: input.trim(), expected_output: (expected || '').trim() }
  })
  await client.post(`/api/datasets/${currentDatasetId.value}/cases`, { cases: cases_data })
  ElMessage.success(`导入 ${cases_data.length} 条`)
  cases.value = await client.get(`/api/datasets/${currentDatasetId.value}/cases`)
}

function openRunDialog(row: any) {
  currentDatasetId.value = row.id
  runDialog.value = true
}

async function startRun() {
  if (!runForm.prompt_a_id || !runForm.prompt_b_id) {
    ElMessage.warning('请选 Prompt A 和 B')
    return
  }
  const res = await client.post('/api/runs', {
    dataset_id: currentDatasetId.value,
    prompt_a_id: runForm.prompt_a_id,
    prompt_b_id: runForm.prompt_b_id,
  })
  ElMessage.success(`评测已启动，Run ID: ${res.run_id}`)
  runDialog.value = false
  setTimeout(() => router.push('/runs'), 1000)
}

onMounted(() => {
  loadDatasets()
  loadPrompts()
})
</script>
