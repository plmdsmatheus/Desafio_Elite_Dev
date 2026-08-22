import { Radio } from "lucide-react"
import { useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { useSSE } from "@/hooks/use-sse"
import { AVAILABILITY_TEXT_CLASS, getAvailabilityLevel } from "@/lib/availability"
import { cn } from "@/lib/utils"

interface AvailabilitySnapshot {
  tickets_available: number
  tickets_sold: number
  capacity: number
}

interface LiveAvailabilityProps {
  eventId: number
  initial: AvailabilitySnapshot
}

/** Right-hand panel on the checkout review step: the same
 * tickets_available/capacity the page loaded with, kept live via SSE instead
 * of going stale the moment someone else buys while this customer is still
 * deciding. Purely informational — the actual stock guarantee is still the
 * row lock in ReservationPayView, not this display. */
export function LiveAvailability({ eventId, initial }: LiveAvailabilityProps) {
  const [snapshot, setSnapshot] = useState<AvailabilitySnapshot>(initial)

  useSSE<AvailabilitySnapshot>(`/events/${eventId}/availability/stream`, setSnapshot)

  const level = getAvailabilityLevel(snapshot.tickets_available, snapshot.capacity)
  const soldOut = level === "sold_out"

  return (
    <Card className="h-fit w-full">
      <CardContent className="flex flex-col items-center gap-3 py-8 text-center">
        <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <Radio className="size-3.5 animate-pulse text-primary" />
          Disponibilidade ao vivo
        </span>

        <span className={cn("text-4xl font-bold tabular-nums", AVAILABILITY_TEXT_CLASS[level])}>
          {snapshot.tickets_available}
        </span>

        <p className="text-sm text-muted-foreground">
          {soldOut
            ? "Ingressos esgotados"
            : `de ${snapshot.capacity} ingresso${snapshot.capacity === 1 ? "" : "s"} no total`}
        </p>
      </CardContent>
    </Card>
  )
}
