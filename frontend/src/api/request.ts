import axios, { type AxiosError, type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import type { ApiError } from '@/types'

declare module 'axios' {
  export interface AxiosRequestConfig {
    /** 为 true 时不弹全局错误提示（由调用方自行处理） */
    silent?: boolean
  }
}

/** token 存储键，供 auth store 共用 */
export const TOKEN_KEY = 'gma_token'

/** 响应拦截器直接返回 data，对外暴露解包后的类型 */
interface ApiClient {
  <T = unknown, R = T>(config: AxiosRequestConfig): Promise<R>
  <T = unknown, R = T>(url: string, config?: AxiosRequestConfig): Promise<R>
  get<T = unknown, R = T>(url: string, config?: AxiosRequestConfig): Promise<R>
  post<T = unknown, R = T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<R>
  put<T = unknown, R = T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<R>
  delete<T = unknown, R = T>(url: string, config?: AxiosRequestConfig): Promise<R>
}

const instance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

instance.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

function extractMessage(data: unknown, fallback: string): string {
  if (typeof data === 'string' && data) return data
  if (data && typeof data === 'object') {
    const detail: unknown = (data as ApiError).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return (detail as unknown[])
        .map((item: unknown) => {
          if (typeof item === 'string') return item
          if (item && typeof item === 'object' && 'msg' in item) {
            return String((item as { msg: unknown }).msg)
          }
          return ''
        })
        .filter(Boolean)
        .join('; ')
    }
  }
  return fallback
}

instance.interceptors.response.use(
  (response: AxiosResponse) => response.data,
  (error: AxiosError) => {
    const status = error.response?.status
    const url = error.config?.url ?? ''
    const message = extractMessage(error.response?.data, error.message || '请求失败，请稍后重试')

    if (status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      // 登录接口的 401 由表单自己提示，不弹全局消息、不跳转
      if (!url.includes('/auth/login')) {
        ElMessage.error('登录已过期，请重新登录')
        import('@/router')
          .then(({ default: router }) => {
            router.push({
              path: '/login',
              query: { redirect: router.currentRoute.value.fullPath },
            })
          })
          .catch(() => {
            window.location.href = '/login'
          })
      }
    } else if (!error.config?.silent) {
      ElMessage.error(message)
    }

    return Promise.reject(new Error(message))
  },
)

export default instance as unknown as ApiClient
