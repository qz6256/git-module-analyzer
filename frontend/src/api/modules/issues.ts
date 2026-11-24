import request from '../request'
import type {
  ImportResult,
  Issue,
  IssueCommitLink,
  IssueCreateInput,
  IssueDetail,
  RelinkResult,
} from '@/types'

export interface IssueQuery {
  q?: string
  issue_type?: string
  status?: string
  assessment?: string
}

export const issuesApi = {
  getIssues: (repoId: number, params?: IssueQuery) =>
    request.get<Issue[]>(`/repositories/${repoId}/issues`, { params }),

  createIssue: (repoId: number, data: IssueCreateInput) =>
    request.post<Issue>(`/repositories/${repoId}/issues`, data),

  importIssues: (repoId: number, csvText: string) =>
    request.post<ImportResult>(`/repositories/${repoId}/issues/import`, { csv_text: csvText }),

  relink: (repoId: number) =>
    request.post<RelinkResult>(`/repositories/${repoId}/relink`, {}),

  getIssueDetail: (issueId: number) => request.get<IssueDetail>(`/issues/${issueId}`),

  updateIssue: (issueId: number, data: Partial<IssueCreateInput> & { status?: string }) =>
    request.put<Issue>(`/issues/${issueId}`, data),

  deleteIssue: (issueId: number) => request.delete<void>(`/issues/${issueId}`),

  confirmLink: (linkId: number) =>
    request.post<IssueCommitLink>(`/issue-links/${linkId}/confirm`, {}),

  rejectLink: (linkId: number) =>
    request.post<IssueCommitLink>(`/issue-links/${linkId}/reject`, {}),

  getIssueLinks: (repoId: number) =>
    request.get<IssueCommitLink[]>(`/repositories/${repoId}/issue-links`),
}
