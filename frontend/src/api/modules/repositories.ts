import request from '../request'
import type {
  BranchState,
  JobInfo,
  Repository,
  RepositoryCreateInput,
  RepositoryUpdateInput,
} from '@/types'

export const repositoriesApi = {
  createRepository: (projectId: number, data: RepositoryCreateInput, autoInit = true) =>
    request.post<Repository>(`/projects/${projectId}/repositories`, data, {
      params: { auto_init: autoInit ? 1 : 0 },
    }),

  updateRepository: (id: number, data: RepositoryUpdateInput) =>
    request.put<Repository>(`/repositories/${id}`, data),

  deleteRepository: (id: number) => request.delete<void>(`/repositories/${id}`),

  initializeRepository: (id: number) =>
    request.post<JobInfo>(`/repositories/${id}/initialize`, {}),

  syncRepository: (id: number, branch?: string) =>
    request.post<JobInfo>(`/repositories/${id}/sync`, branch ? { branch } : {}),

  getJob: (jobId: string) => request.get<JobInfo>(`/jobs/${encodeURIComponent(jobId)}`),

  getBranches: (id: number) => request.get<BranchState[]>(`/repositories/${id}/branches`),
}
