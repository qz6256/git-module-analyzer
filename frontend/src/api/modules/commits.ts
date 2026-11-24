import request from '../request'
import type { CommitAnalysis } from '@/types'

export interface CommitQuery {
  q?: string
  file?: string
  branch?: string
  risk?: string
  user_id?: number
}

export const commitsApi = {
  getCommits: (repoId: number, params?: CommitQuery) =>
    request.get<CommitAnalysis[]>(`/repositories/${repoId}/commits`, { params }),
}
