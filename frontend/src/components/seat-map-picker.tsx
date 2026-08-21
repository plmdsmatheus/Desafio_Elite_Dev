import { useQuery } from "@tanstack/react-query"
import { Armchair } from "lucide-react"
import { getEventSeats } from "@/api/events"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

// Polling, not WebSockets: a few seconds of staleness in what the customer
// SEES is fine, because the actual guarantee against double-booking is the
// select_for_update lock in the backend's hold_seats, not this read — see
// apps.ticketing.seating.
const POLL_INTERVAL_MS = 4000

interface SeatMapPickerProps {
  eventId: number
  selectedSeatIds: number[]
  onToggleSeat: (seatId: number) => void
}

export function SeatMapPicker({ eventId, selectedSeatIds, onToggleSeat }: SeatMapPickerProps) {
  const { data: seats, isLoading } = useQuery({
    queryKey: ["event-seats", eventId],
    queryFn: () => getEventSeats(eventId),
    refetchInterval: POLL_INTERVAL_MS,
  })

  if (isLoading || !seats) {
    return <Skeleton className="h-48 w-full" />
  }

  const rows: [string, typeof seats][] = []
  for (const seat of seats) {
    const lastRow = rows.at(-1)
    if (lastRow && lastRow[0] === seat.row_label) {
      lastRow[1].push(seat)
    } else {
      rows.push([seat.row_label, [seat]])
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="mx-auto w-full max-w-full overflow-x-auto rounded-lg border bg-muted/30 p-3">
        <div className="mx-auto mb-3 w-fit rounded bg-muted px-6 py-1 text-center text-[10px] font-medium tracking-wide text-muted-foreground">
          PALCO / TELA
        </div>
        <div className="mx-auto flex w-fit flex-col gap-1">
          {rows.map(([rowLabel, rowSeats]) => (
            <div key={rowLabel} className="flex items-center gap-1.5">
              <span className="w-4 shrink-0 text-right text-[10px] text-muted-foreground">
                {rowLabel}
              </span>
              <div className="flex gap-1">
                {rowSeats.map((seat) => {
                  const isSelected = selectedSeatIds.includes(seat.id)
                  const isLocked = seat.status === "sold" || seat.status === "held"
                  return (
                    <button
                      key={seat.id}
                      type="button"
                      title={
                        seat.status === "mine"
                          ? `${seat.label} — reservado por você numa tentativa anterior; selecionar de novo libera aquela reserva`
                          : seat.label
                      }
                      disabled={isLocked && !isSelected}
                      onClick={() => onToggleSeat(seat.id)}
                      className={cn(
                        "flex size-6 shrink-0 items-center justify-center rounded transition-colors sm:size-7",
                        isSelected && "text-primary",
                        !isSelected &&
                          seat.status === "available" &&
                          "text-muted-foreground hover:text-primary",
                        !isSelected && seat.status === "mine" && "text-warning hover:text-primary",
                        !isSelected &&
                          seat.status === "held" &&
                          "cursor-not-allowed text-muted-foreground/30",
                        !isSelected &&
                          seat.status === "sold" &&
                          "cursor-not-allowed text-muted-foreground/20",
                      )}
                    >
                      <Armchair
                        className="size-full"
                        strokeWidth={1.5}
                        fill={isSelected ? "currentColor" : "none"}
                      />
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <Armchair className="size-4 text-muted-foreground" strokeWidth={1.5} />
          Disponível
        </span>
        <span className="flex items-center gap-1.5">
          <Armchair className="size-4 text-primary" strokeWidth={1.5} fill="currentColor" />
          Selecionado
        </span>
        <span className="flex items-center gap-1.5">
          <Armchair className="size-4 text-muted-foreground/30" strokeWidth={1.5} />
          Ocupado / em escolha por outra pessoa
        </span>
      </div>
    </div>
  )
}
