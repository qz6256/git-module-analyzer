import request from '../request'
import type { DatabaseStatus, HealthStatus, LlmConfig, LlmConfigUpdate, LlmTestResult } from '@/types'

export const settingsApi = {
  getLlmConfig: () => request.get<LlmConfig>('/settings/llm'),

  updateLlmConfig: (data: LlmConfigUpdate) => request.put<LlmConfig>('/settings/llm', data),

  testLlm: () => request.post<LlmTestResult>('/settings/llm/test', {}),

  getDatabaseStatus: () => request.get<DatabaseStatus>('/settings/database'),

  getHealth: () => request.get<HealthStatus>('/health', { silent: true }),
}
