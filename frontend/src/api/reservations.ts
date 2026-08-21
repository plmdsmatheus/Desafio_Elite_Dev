import { apiClient } from "@/api/client"
import type { PaymentResult, Reservation } from "@/types"

export interface CreateReservationInput {
  event: number
  quantity?: number
  seat_ids?: number[]
}

export function createReservation(input: CreateReservationInput) {
  return apiClient.post<Reservation>("/reservations", input).then((res) => res.data)
}

export interface PayReservationInput {
  card_number: string
  card_name?: string
  expiry?: string
  cvv?: string
}

export function payReservation(reservationId: number, input: PayReservationInput) {
  return apiClient
    .post<PaymentResult>(`/reservations/${reservationId}/pay`, input)
    .then((res) => res.data)
}

/** Gives up a still-unpaid reservation, freeing any held seats right away
 * instead of making the next buyer wait out the hold. Safe to call
 * fire-and-forget — a no-op server-side if the reservation isn't pending
 * anymore (already paid/declined/released). */
export function releaseReservation(reservationId: number) {
  return apiClient
    .post<Reservation>(`/reservations/${reservationId}/release`)
    .then((res) => res.data)
}
