import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'
import logger, { setRequestId } from './logger'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
})

request.interceptors.request.use(
  (config) => {
    logger.info('api', `→ ${config.method?.toUpperCase()} ${config.url}`, {
      url: config.url,
      method: config.method,
      hasData: !!config.data,
    })
    return config
  },
  (error) => {
    logger.error('api', `✗ request error`, {
      url: error.config?.url,
      code: error.code,
      message: error.message,
    })
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  (response) => {
    const rid = response.headers['x-request-id']
    if (rid) setRequestId(rid)

    logger.info('api', `← ${response.status} ${response.config.url}`, {
      status: response.status,
      url: response.config.url,
      responseTimeMs: response.headers['x-response-time-ms'] || '-',
      hasData: !!response.data,
    })

    const res = response.data

    if (res.ok === false) {
      ElMessage.error(res.error?.message || '请求失败')
      return Promise.reject(new Error(res.error?.message || '请求失败'))
    }

    return res
  },
  (error) => {
    logger.error('api', `✗ ${error.config?.url}`, {
      url: error.config?.url,
      status: error.response?.status,
      code: error.code,
      message: error.message,
    })

    if (error.response) {
      const status = error.response.status
      const message = error.response.data?.error?.message || error.message

      switch (status) {
        case 400:
          ElMessage.error(`参数错误: ${message}`)
          break
        case 401:
          ElMessage.error('未授权，请重新登录')
          break
        case 403:
          ElMessage.error('拒绝访问')
          break
        case 404:
          ElMessage.error('资源不存在')
          break
        case 500:
          ElMessage.error(`服务器错误: ${message}`)
          break
        default:
          ElMessage.error(message || '网络错误')
      }
    } else if (error.code === 'ECONNABORTED') {
      ElMessage.error('请求超时，请稍后重试')
    } else {
      ElMessage.error('网络连接异常，请检查网络')
    }

    return Promise.reject(error)
  }
)

export default request
