import { isAxiosError } from "axios"

/**
 * DRF error bodies vary by source: `{"detail": "..."}` for auth/permission
 * errors, `{"field": ["msg"]}` for serializer validation. This normalizes
 * whatever comes back into one message to show the user.
 */
export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (!isAxiosError(error)) return fallback

  const data = error.response?.data
  if (!data) return fallback
  if (typeof data.detail === "string") return data.detail

  const firstFieldError = Object.values(data).find(
    (value): value is string[] => Array.isArray(value) && typeof value[0] === "string",
  )
  return firstFieldError?.[0] ?? fallback
}

/**
 * Same DRF error body, but split per field — `{"email": ["já existe"]}` becomes
 * `{email: "já existe"}` — so a form can show each message right under its own
 * input instead of one message floating near the submit button.
 */
export function getApiFieldErrors(error: unknown): Record<string, string> {
  if (!isAxiosError(error)) return {}

  const data = error.response?.data
  if (!data || typeof data !== "object") return {}

  const fieldErrors: Record<string, string> = {}
  for (const [field, value] of Object.entries(data)) {
    if (field === "detail") continue
    if (Array.isArray(value) && typeof value[0] === "string") {
      fieldErrors[field] = value[0]
    }
  }
  return fieldErrors
}
