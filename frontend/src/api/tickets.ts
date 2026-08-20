import { apiClient } from "@/api/client"
import type { Ticket } from "@/types"

export function getPublicTicket(shareSlug: string) {
  return apiClient.get<Ticket>(`/tickets/${shareSlug}/public`).then((res) => res.data)
}
