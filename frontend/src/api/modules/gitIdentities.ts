import request from '../request'
import type { GitIdentity } from '@/types'

export interface UserCommitPage {
  total: number
  page: number
  size: number
  items: Array<{
    id: number
    commit_sha: string
    sha_short: string
    repo_id: number
    project_id: number | null
    branch: string
    author: string
    author_email: string
    committed_at: string | null
    message: string
    summary: string
    risk_level: string
  }>
}

export const gitIdentitiesApi = {
  list: (boundOnly = false) =>
    request.get<{ items: GitIdentity[] }>('/git-identities', {
      params: { bound_only: boundOnly },
    }),

  createManual: (data: { name: string; email: string; user_id?: number | null }) =>
    request.post<GitIdentity>('/git-identities/manual', data),

  bind: (identityId: number, userId: number | null) =>
    request.put(`/git-identities/${identityId}/bind`, { user_id: userId }),

  userCommits: (userId: number, q = '', page = 1, size = 30) =>
    request.get<UserCommitPage>(`/git-identities/users/${userId}/commits`, {
      params: { q, page, size },
    }),
}
