import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Calendar, CalendarClock, CheckCircle2, CreditCard, Lock, MapPin, User, XCircle } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom"
import { getEvent } from "@/api/events"
import { createReservation, payReservation, releaseReservation } from "@/api/reservations"
import { LiveAvailability } from "@/components/live-availability"
import { QuantityStepper } from "@/components/quantity-stepper"
import { SeatMapPicker } from "@/components/seat-map-picker"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuth } from "@/hooks/use-auth"
import { getApiErrorMessage } from "@/lib/api-error"
import { MAX_QUANTITY_PER_RESERVATION } from "@/lib/availability"
import { formatCurrency, formatDateTime } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { Event, PaymentResult, Reservation } from "@/types"

type Step = "quantity" | "payment" | "result"

const STEPS: { key: Step; label: string }[] = [
  { key: "quantity", label: "Revisão" },
  { key: "payment", label: "Pagamento" },
  { key: "result", label: "Confirmação" },
]

/** Groups digits in fours ("4111 1111 1111 1111") — display only, the
 * backend receives the raw digits. */
function formatCardNumber(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 19)
  return digits.replace(/(.{4})/g, "$1 ").trim()
}

function formatExpiry(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 4)
  return digits.length > 2 ? `${digits.slice(0, 2)}/${digits.slice(2)}` : digits
}

export function CheckoutPage() {
  const { eventId } = useParams<{ eventId: string }>()
  const [searchParams] = useSearchParams()
  const { user } = useAuth()

  const { data: event, isLoading, isError } = useQuery({
    queryKey: ["event", eventId],
    queryFn: () => getEvent(eventId!),
    enabled: !!eventId,
    retry: false,
  })

  if (!user) return <Navigate to="/login" replace />
  if (user.role !== "customer") return <Navigate to="/" replace />

  if (isLoading) {
    return (
      <div className="flex justify-center pt-4 sm:pt-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <Skeleton className="h-6 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </CardContent>
        </Card>
      </div>
    )
  }

  if (isError || !event) {
    return (
      <div className="flex justify-center pt-4 sm:pt-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Evento não encontrado</CardTitle>
            <CardDescription>
              O link pode estar incorreto ou o evento não está mais disponível.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline">
              <Link to="/eventos">Voltar para a lista de eventos</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  const requestedQty = Number(searchParams.get("qty")) || 1
  const initialQuantity = Math.min(
    Math.max(requestedQty, 1),
    Math.max(Math.min(event.tickets_available, MAX_QUANTITY_PER_RESERVATION), 1),
  )

  // Keyed by event id so the wizard state resets naturally if the user lands
  // on a different event's checkout (same reasoning as EventDetailContent).
  return <CheckoutFlow key={event.id} event={event} initialQuantity={initialQuantity} />
}

function StepIndicator({ current }: { current: Step }) {
  const currentIndex = STEPS.findIndex((s) => s.key === current)

  return (
    <div className="flex items-center justify-center gap-2">
      {STEPS.map((s, i) => (
        <div key={s.key} className="flex items-center gap-2">
          <span
            className={cn(
              "flex size-6 items-center justify-center rounded-full border text-xs font-medium",
              i === currentIndex
                ? "border-primary text-primary"
                : i < currentIndex
                  ? "border-success text-success"
                  : "border-border text-muted-foreground",
            )}
          >
            {i + 1}
          </span>
          <span
            className={cn(
              "hidden text-xs font-medium sm:inline",
              i === currentIndex ? "text-foreground" : "text-muted-foreground",
            )}
          >
            {s.label}
          </span>
          {i < STEPS.length - 1 && <span className="mx-1 h-px w-4 bg-border sm:w-6" />}
        </div>
      ))}
    </div>
  )
}

function CheckoutFlow({ event, initialQuantity }: { event: Event; initialQuantity: number }) {
  const queryClient = useQueryClient()
  const [step, setStep] = useState<Step>("quantity")
  const [quantity, setQuantity] = useState(initialQuantity)
  const [selectedSeatIds, setSelectedSeatIds] = useState<number[]>([])
  const [reservation, setReservation] = useState<Reservation | null>(null)
  const [paymentResult, setPaymentResult] = useState<PaymentResult | null>(null)

  const [reservationError, setReservationError] = useState("")
  const [isReserving, setIsReserving] = useState(false)

  const [cardNumber, setCardNumber] = useState("")
  const [cardName, setCardName] = useState("")
  const [expiry, setExpiry] = useState("")
  const [cvv, setCvv] = useState("")
  const [paymentError, setPaymentError] = useState("")
  const [isPaying, setIsPaying] = useState(false)

  // Mirrors `reservation` / "has this reservation reached a final outcome
  // yet" for the unmount cleanup below — a ref because that cleanup only
  // runs once, on unmount, and would otherwise close over stale state from
  // whichever render it was defined in.
  const reservationRef = useRef<Reservation | null>(null)
  const settledRef = useRef(false)

  useEffect(() => {
    return () => {
      // The customer navigated away (gave up on the event, went back home,
      // clicked another nav link) with an unpaid reservation still open —
      // release it right away instead of making the next buyer wait out the
      // 10-minute hold for seats nobody is still trying to buy. Best-effort:
      // this can't fire on a hard tab close/refresh, only in-app navigation.
      const pending = reservationRef.current
      if (pending && !settledRef.current) {
        releaseReservation(pending.id).catch(() => {})
      }
    }
  }, [])

  const maxQuantity = Math.max(Math.min(event.tickets_available, MAX_QUANTITY_PER_RESERVATION), 1)
  const effectiveQuantity = event.has_seat_map ? selectedSeatIds.length : quantity
  const total = effectiveQuantity * Number(event.price)

  function handleToggleSeat(seatId: number) {
    setSelectedSeatIds((prev) => {
      if (prev.includes(seatId)) return prev.filter((id) => id !== seatId)
      if (prev.length >= maxQuantity) return prev
      return [...prev, seatId]
    })
  }

  async function handleConfirmReservation() {
    setReservationError("")
    setIsReserving(true)
    try {
      const created = event.has_seat_map
        ? await createReservation({ event: event.id, seat_ids: selectedSeatIds })
        : await createReservation({ event: event.id, quantity })
      settledRef.current = false
      reservationRef.current = created
      setReservation(created)
      setStep("payment")
    } catch (err) {
      setReservationError(getApiErrorMessage(err, "Não foi possível criar a reserva."))
      if (event.has_seat_map) {
        // The chosen seat(s) were taken by someone else in the meantime —
        // clear the stale selection and let the next poll show what's
        // actually still free.
        setSelectedSeatIds([])
        queryClient.invalidateQueries({ queryKey: ["event-seats", event.id] })
      }
    } finally {
      setIsReserving(false)
    }
  }

  async function handlePay(formEvent: React.FormEvent) {
    formEvent.preventDefault()
    if (!reservation) return
    setPaymentError("")
    setIsPaying(true)
    try {
      const result = await payReservation(reservation.id, {
        card_number: cardNumber,
        card_name: cardName || undefined,
        expiry: expiry || undefined,
        cvv: cvv || undefined,
      })
      // Settled either way: approved needs no release (it's sold now), and
      // declined already released its own seats server-side — either way
      // there's nothing left for the unmount cleanup to do.
      settledRef.current = true
      setPaymentResult(result)
      setStep("result")
    } catch (err) {
      setPaymentError(getApiErrorMessage(err, "Não foi possível processar o pagamento."))
    } finally {
      setIsPaying(false)
    }
  }

  function handleRetry() {
    reservationRef.current = null
    settledRef.current = false
    setReservation(null)
    setPaymentResult(null)
    setPaymentError("")
    setCardNumber("")
    setCardName("")
    setExpiry("")
    setCvv("")
    setSelectedSeatIds([])
    setStep("quantity")
  }

  /** Explicit "I changed my mind" — unlike handleRetry (used after a decline,
   * where the seats are already released server-side), this fires while the
   * reservation is still pending and holding seats, so it has to release
   * them itself. */
  async function handleCancelReservation() {
    if (reservation) {
      releaseReservation(reservation.id).catch(() => {})
    }
    reservationRef.current = null
    settledRef.current = false
    setReservation(null)
    setPaymentError("")
    setCardNumber("")
    setCardName("")
    setExpiry("")
    setCvv("")
    setSelectedSeatIds([])
    setStep("quantity")
    if (event.has_seat_map) {
      queryClient.invalidateQueries({ queryKey: ["event-seats", event.id] })
    }
  }

  return (
    <div className="flex flex-col items-center gap-6 pt-2 sm:pt-4">
      <StepIndicator current={step} />

      {step === "quantity" && (
        <div
          className={cn(
            "grid w-full gap-4",
            event.has_seat_map ? "max-w-md" : "max-w-3xl lg:grid-cols-[1fr_320px]",
          )}
        >
          <Card className="w-full">
            <CardHeader>
              <CardTitle>Revisar reserva</CardTitle>
              <CardDescription>{event.title}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5 text-sm text-muted-foreground">
                <p className="flex items-center gap-2">
                  <Calendar className="size-4 shrink-0" />
                  {formatDateTime(event.date_time)}
                </p>
                <p className="flex items-center gap-2">
                  <MapPin className="size-4 shrink-0" />
                  {event.venue_name}, {event.city}
                </p>
              </div>

              {event.has_seat_map ? (
                <div className="flex flex-col gap-2 border-t pt-4">
                  <span className="text-sm font-medium">
                    Escolha seus assentos ({selectedSeatIds.length}/{maxQuantity})
                  </span>
                  <SeatMapPicker
                    eventId={event.id}
                    selectedSeatIds={selectedSeatIds}
                    onToggleSeat={handleToggleSeat}
                  />
                </div>
              ) : (
                <div className="flex items-center justify-between border-t pt-4">
                  <span className="text-sm font-medium">Quantidade</span>
                  <QuantityStepper value={quantity} max={maxQuantity} onChange={setQuantity} />
                </div>
              )}

              <div className="flex items-center justify-between text-sm text-muted-foreground">
                <span>Preço unitário</span>
                <span>{formatCurrency(event.price)}</span>
              </div>

              <div className="flex items-center justify-between border-t pt-3 text-lg font-semibold">
                <span>Total</span>
                <span className="text-primary">{formatCurrency(total)}</span>
              </div>

              {reservationError && <p className="text-sm text-destructive">{reservationError}</p>}

              <Button
                onClick={handleConfirmReservation}
                disabled={isReserving || effectiveQuantity === 0}
                className="w-full"
              >
                <CheckCircle2 />
                {isReserving ? "Reservando..." : "Confirmar reserva"}
              </Button>
            </CardContent>
          </Card>

          {!event.has_seat_map && (
            <LiveAvailability
              eventId={event.id}
              initial={{
                tickets_available: event.tickets_available,
                tickets_sold: event.tickets_sold,
                capacity: event.capacity,
              }}
            />
          )}
        </div>
      )}

      {step === "payment" && (
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Pagamento</CardTitle>
            <CardDescription>
              {reservation && reservation.seats.length > 0
                ? `Assentos ${reservation.seats.join(", ")}`
                : `${effectiveQuantity} ingresso(s)`}{" "}
              · {formatCurrency(total)}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handlePay} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="card_number">
                  <CreditCard className="size-3.5 text-muted-foreground" />
                  Número do cartão
                </Label>
                <Input
                  id="card_number"
                  inputMode="numeric"
                  autoComplete="cc-number"
                  placeholder="0000 0000 0000 0000"
                  required
                  value={cardNumber}
                  onChange={(e) => setCardNumber(formatCardNumber(e.target.value))}
                />
                <p className="text-xs text-muted-foreground">
                  Pagamento simulado: número terminado em 0000 é recusado, qualquer outro é
                  aprovado.
                </p>
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="card_name">
                  <User className="size-3.5 text-muted-foreground" />
                  Nome no cartão (opcional)
                </Label>
                <Input
                  id="card_name"
                  autoComplete="cc-name"
                  value={cardName}
                  onChange={(e) => setCardName(e.target.value)}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="expiry">
                    <CalendarClock className="size-3.5 text-muted-foreground" />
                    Validade (opcional)
                  </Label>
                  <Input
                    id="expiry"
                    inputMode="numeric"
                    autoComplete="cc-exp"
                    placeholder="MM/AA"
                    value={expiry}
                    onChange={(e) => setExpiry(formatExpiry(e.target.value))}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="cvv">
                    <Lock className="size-3.5 text-muted-foreground" />
                    CVV (opcional)
                  </Label>
                  <Input
                    id="cvv"
                    inputMode="numeric"
                    autoComplete="cc-csc"
                    maxLength={4}
                    value={cvv}
                    onChange={(e) => setCvv(e.target.value.replace(/\D/g, "").slice(0, 4))}
                  />
                </div>
              </div>

              {paymentError && <p className="text-sm text-destructive">{paymentError}</p>}

              <Button type="submit" disabled={isPaying} className="w-full">
                <CreditCard />
                {isPaying ? "Processando..." : `Pagar ${formatCurrency(total)}`}
              </Button>

              {event.has_seat_map && (
                <Button
                  type="button"
                  variant="ghost"
                  disabled={isPaying}
                  onClick={handleCancelReservation}
                  className="w-full text-muted-foreground"
                >
                  Desistir e escolher outro assento
                </Button>
              )}
            </form>
          </CardContent>
        </Card>
      )}

      {step === "result" && paymentResult && (
        <Card className="w-full max-w-md">
          <CardContent className="flex flex-col items-center gap-4 py-8 text-center">
            {paymentResult.payment_status === "approved" ? (
              <>
                <CheckCircle2 className="size-12 text-success" />
                <div>
                  <h2 className="text-xl font-semibold">Pagamento aprovado!</h2>
                  <p className="text-muted-foreground">
                    {paymentResult.tickets.length} ingresso(s) gerado(s) para {event.title}.
                  </p>
                </div>
                <div className="flex flex-wrap justify-center gap-3">
                  <Button asChild>
                    <Link to="/meus-ingressos">Ver meus ingressos</Link>
                  </Button>
                  <Button asChild variant="outline">
                    <Link to={`/eventos/${event.id}`}>Voltar ao evento</Link>
                  </Button>
                </div>
              </>
            ) : (
              <>
                <XCircle className="size-12 text-destructive" />
                <div>
                  <h2 className="text-xl font-semibold">Pagamento recusado</h2>
                  <p className="text-muted-foreground">
                    Verifique os dados do cartão e tente novamente com uma nova reserva.
                  </p>
                </div>
                <Button onClick={handleRetry}>Tentar novamente</Button>
              </>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
