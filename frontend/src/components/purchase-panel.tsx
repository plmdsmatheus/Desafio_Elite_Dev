import { Link } from "react-router-dom"
import { QuantityStepper } from "@/components/quantity-stepper"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  AVAILABILITY_TEXT_CLASS,
  getAvailabilityLevel,
  MAX_QUANTITY_PER_RESERVATION,
} from "@/lib/availability"
import { formatCurrency } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { Event, User } from "@/types"

function availabilityText(available: number): string {
  if (available <= 0) return "Esgotado"
  if (available === 1) return "Última unidade disponível"
  return `${available} ingressos disponíveis`
}

/** Shorter phrasing for the mobile bar, which has a lot less horizontal room. */
function availabilityTextCompact(available: number): string {
  if (available <= 0) return "Esgotado"
  if (available === 1) return "Última unidade"
  return `${available} disponíveis`
}

interface PurchasePanelProps {
  event: Event
  user: User | null
  quantity: number
  onQuantityChange: (value: number) => void
}

/** Desktop: sticky sidebar card. Mobile: fixed bottom bar (rendered by the
 * same component so price/availability/CTA logic isn't duplicated). */
export function PurchasePanel({ event, user, quantity, onQuantityChange }: PurchasePanelProps) {
  const level = getAvailabilityLevel(event.tickets_available, event.capacity)
  const soldOut = level === "sold_out"
  const canReserve = !!user && user.role === "customer" && !soldOut
  const maxQuantity = Math.min(event.tickets_available, MAX_QUANTITY_PER_RESERVATION)
  const total = quantity * Number(event.price)

  function buildCta(compact: boolean) {
    if (soldOut) {
      return (
        <Button disabled className="w-full">
          Esgotado
        </Button>
      )
    }
    if (!user) {
      return (
        <Button asChild className="w-full">
          <Link to="/login">Entrar para reservar</Link>
        </Button>
      )
    }
    if (user.role !== "customer") {
      return (
        <p className="text-center text-xs text-muted-foreground sm:text-sm">
          {compact ? "Só clientes reservam" : "Só contas de cliente podem reservar ingressos."}
        </p>
      )
    }
    return (
      <Button asChild className="w-full">
        <Link to={`/checkout/${event.id}?qty=${quantity}`}>{compact ? "Reservar" : "Reservar ingressos"}</Link>
      </Button>
    )
  }

  return (
    <>
      {/* Desktop / tablet: sticky card in the layout flow. */}
      <Card className="hidden lg:sticky lg:top-8 lg:block">
        <CardContent className="flex flex-col gap-4">
          <div>
            <p className="text-sm text-muted-foreground">Ingresso</p>
            <p className="text-3xl font-bold text-primary">{formatCurrency(event.price)}</p>
          </div>

          <p className={cn("text-sm font-medium", AVAILABILITY_TEXT_CLASS[level])}>
            {availabilityText(event.tickets_available)}
          </p>

          {canReserve && (
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Quantidade</span>
              <QuantityStepper value={quantity} max={maxQuantity} onChange={onQuantityChange} />
            </div>
          )}

          {canReserve && quantity > 1 && (
            <div className="flex items-center justify-between border-t pt-3 text-sm">
              <span className="text-muted-foreground">Total</span>
              <span className="font-semibold">{formatCurrency(total)}</span>
            </div>
          )}

          {buildCta(false)}
        </CardContent>
      </Card>

      {/* Mobile: the same purchase info as a fixed bottom bar instead of an
       * in-flow card, so it stays reachable without scrolling back up. */}
      <div className="fixed inset-x-0 bottom-0 z-40 border-t bg-card px-4 py-3 shadow-[0_-4px_16px_rgba(0,0,0,0.25)] lg:hidden">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className={cn("truncate text-xs font-medium", AVAILABILITY_TEXT_CLASS[level])}>
              {availabilityTextCompact(event.tickets_available)}
            </p>
            <p className="truncate text-lg font-bold text-primary">
              {formatCurrency(canReserve ? total : event.price)}
            </p>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {canReserve && (
              <QuantityStepper value={quantity} max={maxQuantity} onChange={onQuantityChange} compact />
            )}
            <div className="w-24">{buildCta(true)}</div>
          </div>
        </div>
      </div>
    </>
  )
}
