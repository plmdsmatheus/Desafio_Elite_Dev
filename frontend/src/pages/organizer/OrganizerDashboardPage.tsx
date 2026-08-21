import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { Calendar, MapPin, Pencil, Plus } from "lucide-react"
import { useState } from "react"
import { Link, Navigate } from "react-router-dom"
import { getOrganizerEvents } from "@/api/events"
import { EventThumbnail } from "@/components/event-thumbnail"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuth } from "@/hooks/use-auth"
import { formatCurrency, formatDateShort } from "@/lib/format"
import {
  CATEGORY_BADGE_CLASS,
  CATEGORY_LABEL,
  EVENT_STATUS_BADGE_CLASS,
  EVENT_STATUS_LABEL,
} from "@/lib/labels"
import type { Event } from "@/types"

function OrganizerEventRow({ event }: { event: Event }) {
  const soldPct = event.capacity > 0 ? Math.min((event.tickets_sold / event.capacity) * 100, 100) : 0

  return (
    <Card className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center">
      <div className="h-28 w-full shrink-0 overflow-hidden rounded-lg sm:h-20 sm:w-32">
        <EventThumbnail
          src={event.image_url}
          category={event.category}
          dateTime={event.date_time}
          className="h-full w-full"
        />
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className={CATEGORY_BADGE_CLASS[event.category]}>
            {CATEGORY_LABEL[event.category] ?? event.category}
          </Badge>
          <Badge variant="outline" className={EVENT_STATUS_BADGE_CLASS[event.effective_status]}>
            {EVENT_STATUS_LABEL[event.effective_status] ?? event.effective_status}
          </Badge>
        </div>

        <p className="truncate font-medium">{event.title}</p>

        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <MapPin className="size-3.5 shrink-0" />
            {event.venue_name}, {event.city}
          </span>
          <span className="flex items-center gap-1.5">
            <Calendar className="size-3.5 shrink-0" />
            {formatDateShort(event.date_time)}
          </span>
          <span className="font-medium text-foreground">{formatCurrency(event.price)}</span>
        </div>
      </div>

      <div className="flex w-full flex-col gap-1 sm:w-40">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {event.tickets_sold}/{event.capacity} vendidos
          </span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary" style={{ width: `${soldPct}%` }} />
        </div>
      </div>

      <Button asChild variant="outline" size="sm" className="shrink-0 self-start sm:self-center">
        <Link to={`/organizador/eventos/${event.id}/editar`}>
          <Pencil />
          Editar
        </Link>
      </Button>
    </Card>
  )
}

export function OrganizerDashboardPage() {
  const { user } = useAuth()
  const [page, setPage] = useState(1)

  const { data, isLoading, isPlaceholderData } = useQuery({
    queryKey: ["organizer-events", page],
    queryFn: () => getOrganizerEvents(page),
    enabled: !!user && user.role === "organizer",
    placeholderData: keepPreviousData,
  })

  if (!user) return <Navigate to="/login" replace />
  if (user.role !== "organizer") return <Navigate to="/" replace />

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Meus eventos</h1>
          <p className="text-muted-foreground">Gerencie os eventos que você publicou.</p>
        </div>
        <Button asChild>
          <Link to="/organizador/eventos/novo">
            <Plus />
            Criar evento
          </Link>
        </Button>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full sm:h-20" />
          ))}
        </div>
      ) : !data || data.count === 0 ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="text-muted-foreground">Você ainda não criou nenhum evento.</p>
          <Button asChild>
            <Link to="/organizador/eventos/novo">
              <Plus />
              Criar meu primeiro evento
            </Link>
          </Button>
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-3">
            {data.results.map((event) => (
              <OrganizerEventRow key={event.id} event={event} />
            ))}
          </div>

          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">{data.count} evento(s) encontrado(s)</p>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={!data.previous || isPlaceholderData}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Anterior
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={!data.next || isPlaceholderData}
                onClick={() => setPage((p) => p + 1)}
              >
                Próxima
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
