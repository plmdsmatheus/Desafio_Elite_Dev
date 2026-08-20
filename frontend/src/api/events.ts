import { apiClient } from "@/api/client"
import type { Event, EventCategory, Paginated } from "@/types"

export interface EventListParams {
  q?: string
  city?: string
  category?: EventCategory | ""
  date?: string
  page?: number
}

export function listEvents(params: EventListParams) {
  const cleanParams = Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== "" && value != null),
  )
  return apiClient.get<Paginated<Event>>("/events/", { params: cleanParams }).then((res) => res.data)
}
