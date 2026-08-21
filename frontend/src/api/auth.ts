import { apiClient } from "@/api/client"
import type { User } from "@/types"

export interface LoginResponse {
  access: string
  refresh: string
  user: User
}

export function login(email: string, password: string) {
  return apiClient
    .post<LoginResponse>("/auth/login", { email, password })
    .then((res) => res.data)
}

export interface RegisterInput {
  email: string
  password: string
  first_name?: string
  last_name?: string
}

export function register(data: RegisterInput) {
  return apiClient.post<User>("/auth/register", data).then((res) => res.data)
}

export function getMe() {
  return apiClient.get<User>("/auth/me").then((res) => res.data)
}
