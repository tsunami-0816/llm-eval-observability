import axios from 'axios'
import { ElMessage } from 'element-plus'

// 修复-SEC003: 后端全接口已挂 X-API-Key 鉴权，前端统一带 key（本地 dev key，可用 VITE_API_KEY 覆盖）
const client = axios.create({
  baseURL: '/',
  timeout: 10000,
  headers: { 'X-API-Key': import.meta.env.VITE_API_KEY || 'dev-sdk-key-change-me' },
})

client.interceptors.response.use(
  (resp) => {
    const body = resp.data
    if (body.code !== 0) {
      ElMessage.error(body.message || '请求失败')
      return Promise.reject(new Error(body.message))
    }
    return body.data
  },
  (err) => {
    ElMessage.error(err.response?.data?.detail || err.message || '网络错误')
    return Promise.reject(err)
  },
)

export default client
