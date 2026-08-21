import { apiClient } from "@/api/client"
import type { Event, GateValidateResponse, Paginated } from "@/types"

export function getGateEvents(page: number) {
  return apiClient
    .get<Paginated<Event>>("/gate/events", { params: { page } })
    .then((res) => res.data)
}

export interface ValidateTicketInput {
  code: string
  event_id: number
}

export function validateTicket(input: ValidateTicketInput) {
  return apiClient.post<GateValidateResponse>("/gate/validate", input).then((res) => res.data)
}
