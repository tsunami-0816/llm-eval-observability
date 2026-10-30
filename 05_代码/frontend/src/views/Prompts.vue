<template>
  <div>
    <h2>Prompt 版本</h2>
    <el-button type="primary" @click="dialogVisible = true">新建版本</el-button>
    <el-button @click="compareDialogVisible = true" style="margin-left: 10px">对比版本</el-button>
    <el-table :data="prompts" style="margin-top: 15px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="version" label="版本" />
      <el-table-column prop="description" label="描述" />
      <el-table-column prop="created_at" label="创建时间" />
    </el-table>

    <el-dialog v-model="dialogVisible" title="新建 Prompt 版本">
      <el-form :model="form">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="版本"><el-input v-model="form.version" placeholder="v1.0" /></el-form-item>
        <el-form-item label="内容"><el-input v-model="form.content" type="textarea" :rows="4" placeholder="含 {{'{{input}}'}} 占位" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="createPrompt">创建</el-button>
      </template>
    </el-dialog>

    <!-- 版本对比对话框 -->
    <el-dialog v-model="compareDialogVisible" title="Prompt 版本对比" width="70%">
      <el-select v-model="compareA" placeholder="选版本 A" style="width: 200px; margin-right: 20px">
        <el-option v-for="p in prompts" :key="p.id" :label="`${p.name} ${p.version}`" :value="p.id" />
      </el-select>
      <el-select v-model="compareB" placeholder="选版本 B" style="width: 200px">
        <el-option v-for="p in prompts" :key="p.id" :label="`${p.name} ${p.version}`" :value="p.id" />
      </el-select>
      <el-button type="primary" @click="doCompare" style="margin-left: 20px">对比</el-button>

      <el-row :gutter="20" style="margin-top: 20px" v-if="compareResult">
        <el-col :span="12">
          <h4>版本 A</h4>
          <el-input type="textarea" :rows="10" v-model="compareResult.a.content" readonly />
        </el-col>
        <el-col :span="12">
          <h4>版本 B</h4>
          <el-input type="textarea" :rows="10" v-model="compareResult.b.content" readonly />
        </el-col>
      </el-row>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import client from '../api/client'

const prompts = ref<any[]>([])
const dialogVisible = ref(false)
const form = reactive({ name: '', version: '', content: '' })

const compareDialogVisible = ref(false)
const compareA = ref<number>()
const compareB = ref<number>()
const compareResult = ref<{ a: any; b: any } | null>(null)

async function loadPrompts() {
  prompts.value = await client.get('/api/prompts')
}

async function createPrompt() {
  await client.post('/api/prompts', form)
  ElMessage.success('创建成功')
  dialogVisible.value = false
  form.name = form.version = form.content = ''
  loadPrompts()
}

function doCompare() {
  if (!compareA.value || !compareB.value) {
    ElMessage.warning('请选两个版本')
    return
  }
  const a = prompts.value.find(p => p.id === compareA.value)
  const b = prompts.value.find(p => p.id === compareB.value)
  compareResult.value = { a, b }
}

onMounted(loadPrompts)
</script>
