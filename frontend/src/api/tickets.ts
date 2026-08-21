import { apiClient } from "@/api/client"
import type { Paginated, Ticket } from "@/types"

export function getPublicTicket(shareSlug: string) {
  return apiClient.get<Ticket>(`/tickets/${shareSlug}/public`).then((res) => res.data)
}

export function getMyTickets(page: number) {
  return apiClient
    .get<Paginated<Ticket>>("/tickets/mine", { params: { page } })
    .then((res) => res.data)
}
