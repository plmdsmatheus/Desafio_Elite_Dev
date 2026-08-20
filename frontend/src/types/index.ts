export type UserRole = "organizer" | "customer" | "gate"

export interface User {
  id: number
  email: string
  role: UserRole
  first_name: string
  last_name: string
}

export type EventCategory = "show" | "movie"
export type EventStatus = "draft" | "published" | "canceled"
export type EventSourceProvider = "ticketmaster" | "tmdb" | "manual"

export interface Event {
  id: number
  organizer: number
  organizer_name: string
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
  status: EventStatus
  tickets_sold: number
  tickets_available: number
  created_at: string
  updated_at: string
}

export type ReservationStatus = "pending" | "paid" | "declined" | "canceled"

export interface Reservation {
  id: number
  event: Event
  quantity: number
  status: ReservationStatus
  total_price: string
  created_at: string
}

export type TicketStatus = "valid" | "used" | "canceled"

export interface Ticket {
  id: number
  event: Event
  public_code: string
  share_slug: string
  status: TicketStatus
  used_at: string | null
  created_at: string
  qr_payload: string
  share_url: string
}

export interface PaymentResult {
  reservation: Reservation
  payment_status: "approved" | "declined"
  tickets: Ticket[]
}

export type GateValidateResult = "valido" | "invalido" | "ja_utilizado" | "evento_errado"

export interface GateValidateResponse {
  result: GateValidateResult
  detail: string
  ticket?: Ticket
}

export interface CatalogItem {
  provider: "ticketmaster" | "tmdb"
  external_id: string
  title: string
  category: EventCategory
  image_url: string
  description: string
  subtitle: string
  suggested_venue_name: string
  suggested_address: string
  suggested_city: string
  suggested_date_time: string | null
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
