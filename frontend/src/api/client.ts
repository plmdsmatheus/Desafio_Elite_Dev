import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios"

const ACCESS_TOKEN_KEY = "access_token"
const REFRESH_TOKEN_KEY = "refresh_token"

export const tokenStorage = {
  getAccess: () => localStorage.getItem(ACCESS_TOKEN_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_TOKEN_KEY),
  set: (access: string, refresh: string) => {
    localStorage.setItem(ACCESS_TOKEN_KEY, access)
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh)
  },
  clear: () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  },
}

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api",
})

apiClient.interceptors.request.use((config) => {
  const access = tokenStorage.getAccess()
  if (access) {
    config.headers.Authorization = `Bearer ${access}`
  }
  return config
})

// Single in-flight refresh shared by every request that hits a 401 at the same
// time, so a burst of parallel requests doesn't fire the refresh endpoint N times.
let refreshPromise: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  const refresh = tokenStorage.getRefresh()
  if (!refresh) throw new Error("No refresh token available")

  const { data } = await axios.post<{ access: string }>(
    `${apiClient.defaults.baseURL}/auth/refresh`,
    { refresh },
  )
  tokenStorage.set(data.access, refresh)
  return data.access
}

// A 401 from these means "wrong credentials" or "refresh token is dead" — not
// "access token expired", so retrying them through the refresh flow makes no
// sense and would just swallow the real error behind a refresh failure.
const AUTH_ENDPOINTS = ["/auth/login", "/auth/register", "/auth/refresh"]

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as
      | (InternalAxiosRequestConfig & { _retry?: boolean })
      | undefined

    const isAuthEndpoint = AUTH_ENDPOINTS.some((path) => originalRequest?.url?.includes(path))

    if (error.response?.status !== 401 || !originalRequest || originalRequest._retry || isAuthEndpoint) {
      throw error
    }

    originalRequest._retry = true
    try {
      refreshPromise ??= refreshAccessToken().finally(() => {
        refreshPromise = null
      })
      const access = await refreshPromise
      originalRequest.headers.Authorization = `Bearer ${access}`
      return apiClient(originalRequest)
    } catch (refreshError) {
      tokenStorage.clear()
      throw refreshError
    }
  },
)
