import { useQuery, useQueryClient } from "@tanstack/react-query"
import { getMe, login as loginRequest, register as registerRequest, type RegisterInput } from "@/api/auth"
import { tokenStorage } from "@/api/client"
import type { User } from "@/types"

const ME_QUERY_KEY = ["me"]

/**
 * The logged-in user lives in the TanStack Query cache under ["me"] instead of
 * a Context — every component calling useAuth() shares the same cached value
 * automatically, and login/logout just write straight into that cache entry.
 */
export function useAuth() {
  const queryClient = useQueryClient()

  const { data: user = null, isLoading } = useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: () =>
      getMe().catch((error: unknown) => {
        tokenStorage.clear()
        throw error
      }),
    enabled: Boolean(tokenStorage.getAccess()),
    retry: false,
    staleTime: Infinity,
  })

  async function login(email: string, password: string) {
    const data = await loginRequest(email, password)
    tokenStorage.set(data.access, data.refresh)
    queryClient.setQueryData<User>(ME_QUERY_KEY, data.user)
    return data.user
  }

  async function register(input: RegisterInput) {
    await registerRequest(input)
    // Registration doesn't return tokens, so log in right after with the same
    // credentials — one less step for the customer.
    return login(input.email, input.password)
  }

  function logout() {
    tokenStorage.clear()
    queryClient.setQueryData(ME_QUERY_KEY, null)
  }

  return { user, isLoading, login, register, logout }
}
