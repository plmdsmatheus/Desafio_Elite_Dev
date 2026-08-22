import { apiClient } from "@/api/client"
import type { Event, EventCategory, EventSourceProvider, Paginated, Seat } from "@/types"

// No `status` here on purpose: creation always lands as a draft (the backend
// forces it regardless of what's sent), and publishing/canceling afterwards
// are their own deliberate actions (see publishEvent/cancelEvent below), not
// a value this form ever picks directly.
export interface EventFormInput {
  source_provider: EventSourceProvider
  source_id: string
  title: string
  description: string
  image_url: string
  category: EventCategory
  venue_name: string
  address: string
  city: string
  date_time: string
  capacity: number
  price: string
  has_seat_map: boolean
}

export interface EventListParams {
  q?: string
  city?: string
  category?: EventCategory | ""
  date?: string
  page?: number
  show_unavailable?: boolean
}

export function listEvents(params: EventListParams) {
  const cleanParams = Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== "" && value != null && value !== false),
  )
  return apiClient.get<Paginated<Event>>("/events/", { params: cleanParams }).then((res) => res.data)
}

export function getEventCities() {
  return apiClient.get<string[]>("/events/cities").then((res) => res.data)
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

export function createEvent(input: EventFormInput) {
  return apiClient.post<Event>("/events/", input).then((res) => res.data)
}

export function updateEvent(eventId: string | number, input: Partial<EventFormInput>) {
  return apiClient.patch<Event>(`/events/${eventId}`, input).then((res) => res.data)
}

export function publishEvent(eventId: string | number) {
  return apiClient.patch<Event>(`/events/${eventId}`, { status: "published" }).then((res) => res.data)
}

export function cancelEvent(eventId: string | number) {
  return apiClient.patch<Event>(`/events/${eventId}`, { status: "canceled" }).then((res) => res.data)
}
