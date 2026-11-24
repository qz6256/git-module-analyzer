import request from '../request'
import type {
  ConfirmResult,
  KnowledgeStatus,
  ModuleCandidate,
  ModuleCommitQuery,
  ModuleDetail,
  ModuleChangeEvent,
  Paged,
  ProjectModule,
  ProjectModuleOverview,
} from '@/types'

export interface ModuleUpdateInput {
  module_owner_user_id?: number | null
  knowledge_status?: KnowledgeStatus
  review_due_at?: string | null
}

export const modulesApi = {
  getModules: (repoId: number) =>
    request.get<{ items: ProjectModule[] }>(`/repositories/${repoId}/modules`)
      .then((res) => res.items || []),

  getProjectModules: (projectId: number) =>
    request.get<{ items: ProjectModuleOverview[] }>(`/projects/${projectId}/modules`)
      .then((res) => res.items || []),

  getModuleDetail: (moduleId: number) =>
    request.get<ModuleDetail>(`/modules/${moduleId}`),

  getModuleCommits: (moduleId: number, params?: ModuleCommitQuery) =>
    request.get<Paged<ModuleChangeEvent>>(`/modules/${moduleId}/commits`, { params }),

  updateModule: (moduleId: number, data: ModuleUpdateInput) =>
    request.put<{ id: number }>(`/modules/${moduleId}`, data),

  getModuleCandidates: (repoId: number) =>
    request.get<{ items: ModuleCandidate[] }>(`/repositories/${repoId}/module-candidates`)
      .then((res) => res.items || []),

  confirmCandidate: (id: number) =>
    request.post<ConfirmResult>(`/module-candidates/${id}/confirm`, {}),

  ignoreCandidate: (id: number) =>
    request.post<void>(`/module-candidates/${id}/ignore`, {}),
}
