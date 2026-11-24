import request from '../request'
import type {
  ConfirmResult,
  KnowledgeStatus,
  ModuleCandidate,
  ModuleCommitQuery,
  ModuleContributor,
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
    request.get<ProjectModule[]>(`/repositories/${repoId}/modules`),

  getProjectModules: (projectId: number) =>
    request.get<ProjectModuleOverview[]>(`/projects/${projectId}/modules`),

  getModuleDetail: (moduleId: number) =>
    request.get<ModuleDetail>(`/modules/${moduleId}`),

  getModuleCommits: (moduleId: number, params?: ModuleCommitQuery) =>
    request.get<Paged<ModuleChangeEvent>>(`/modules/${moduleId}/commits`, { params }),

  updateModule: (moduleId: number, data: ModuleUpdateInput) =>
    request.put<{ id: number }>(`/modules/${moduleId}`, data),

  getModuleCandidates: (repoId: number) =>
    request.get<ModuleCandidate[]>(`/repositories/${repoId}/module-candidates`),

  confirmCandidate: (id: number) =>
    request.post<ConfirmResult>(`/module-candidates/${id}/confirm`, {}),

  ignoreCandidate: (id: number) =>
    request.post<void>(`/module-candidates/${id}/ignore`, {}),
}

export type { ModuleContributor }
