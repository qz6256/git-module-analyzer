import request from '../request'
import type {
  MemberCreateInput,
  MemberOut,
  Project,
  ProjectCreateInput,
  ProjectOverview,
  Repository,
} from '@/types'

export interface ProjectQuery {
  city?: string
  domain?: string
  status?: string
  keyword?: string
}

export const projectsApi = {
  getProjects: (params?: ProjectQuery) => request.get<Project[]>('/projects', { params }),

  createProject: (data: ProjectCreateInput) => request.post<Project>('/projects', data),

  getProject: (id: number) => request.get<Project>(`/projects/${id}`),

  updateProject: (id: number, data: Partial<ProjectCreateInput>) =>
    request.put<Project>(`/projects/${id}`, data),

  deleteProject: (id: number) => request.delete<void>(`/projects/${id}`),

  getProjectOverview: (id: number) =>
    request.get<ProjectOverview>(`/projects/${id}/overview`),

  getMembers: (id: number) => request.get<MemberOut[]>(`/projects/${id}/members`),

  addMember: (id: number, data: MemberCreateInput) =>
    request.post<MemberOut>(`/projects/${id}/members`, data),

  removeMember: (id: number, userId: number) =>
    request.delete<void>(`/projects/${id}/members/${userId}`),

  getRepositories: (id: number) =>
    request.get<Repository[]>(`/projects/${id}/repositories`),
}
