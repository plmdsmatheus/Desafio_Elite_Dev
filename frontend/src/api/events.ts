import { apiClient } from "@/api/client"
import type { Event, EventCategory, Paginated, Seat } from "@/types"

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

export function getEvent(eventId: string | number) {
  return apiClient.get<Event>(`/events/${eventId}`).then((res) => res.data)
}

export function getOrganizerEvents(page: number) {
  return apiClient
    .get<Paginated<Event>>("/organizer/events", { params: { page } })
    .then((res) => res.data)
}

export function getEventSeats(eventId: string | number) {
  return apiClient.get<Seat[]>(`/events/${eventId}/seats`).then((res) => res.data)
}
