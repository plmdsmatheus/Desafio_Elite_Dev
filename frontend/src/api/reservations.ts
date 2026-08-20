import { apiClient } from "@/api/client"
import type { PaymentResult, Reservation } from "@/types"

export interface CreateReservationInput {
  event: number
  quantity: number
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
