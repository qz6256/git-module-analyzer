import request from '../request'
import type { User, UserUpdateInput } from '@/types'

export const usersApi = {
  getUsers: () => request.get<User[]>('/users'),

  updateUser: (id: number, data: UserUpdateInput) =>
    request.put<User>(`/users/${id}`, data),

  deleteUser: (id: number) => request.delete<void>(`/users/${id}`),

  setUserRoles: (id: number, roleCodes: string[]) =>
    request.post<User>(`/users/${id}/roles`, { role_codes: roleCodes }),
}
