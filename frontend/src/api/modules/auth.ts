import request from '../request'
import type { LoginRequest, LoginResponse, RegisterRequest, User } from '@/types'

export const authApi = {
  register: (data: RegisterRequest) =>
    request.post<User>('/auth/register', data, { silent: true }),

  login: (data: LoginRequest) =>
    request.post<LoginResponse>('/auth/login', data, { silent: true }),

  getMe: () => request.get<User>('/auth/me', { silent: true }),

  refresh: () =>
    request.post<{ access_token: string }>('/auth/refresh', {}, { silent: true }),
}
