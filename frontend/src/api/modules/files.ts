import request from '../request'
import type { FileDetail, Paged, SourceFile, SourcePreview } from '@/types'

export interface FileQuery {
  q?: string
  module?: string
  risk?: string
  page?: number
  size?: number
}

export interface FileDetailQuery {
  branch?: string
  risk?: string
  author?: string
}

export const filesApi = {
  getFiles: (repoId: number, params?: FileQuery) =>
    request.get<Paged<SourceFile>>(`/repositories/${repoId}/files`, { params }),

  getFileDetail: (fileId: number, params?: FileDetailQuery) =>
    request.get<FileDetail>(`/files/${fileId}`, { params }),

  getFileDoc: (fileId: number) =>
    request.get<string>(`/files/${fileId}/doc`, { responseType: 'text' }),

  getFileSource: (fileId: number, branch?: string) =>
    request.get<SourcePreview>(`/files/${fileId}/source`, {
      params: branch ? { branch } : undefined,
    }),
}
