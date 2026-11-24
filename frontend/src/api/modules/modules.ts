import request from '../request'
import type { ConfirmResult, ModuleCandidate, ModuleDetail, ProjectModule } from '@/types'

export const modulesApi = {
  getModules: (repoId: number) =>
    request.get<ProjectModule[]>(`/repositories/${repoId}/modules`),

  getModuleDetail: (moduleId: number) =>
    request.get<ModuleDetail>(`/modules/${moduleId}`),

  getModuleCandidates: (repoId: number) =>
    request.get<ModuleCandidate[]>(`/repositories/${repoId}/module-candidates`),

  confirmCandidate: (id: number) =>
    request.post<ConfirmResult>(`/module-candidates/${id}/confirm`, {}),

  ignoreCandidate: (id: number) =>
    request.post<void>(`/module-candidates/${id}/ignore`, {}),
}
