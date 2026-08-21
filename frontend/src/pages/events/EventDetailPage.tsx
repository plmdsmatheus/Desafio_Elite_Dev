import { useQuery } from "@tanstack/react-query"
import { ArrowLeft, Calendar, MapPin, Pencil } from "lucide-react"
import { useState } from "react"
import { Link, useParams } from "react-router-dom"
import { getEvent } from "@/api/events"
import { EventThumbnail } from "@/components/event-thumbnail"
import { PurchasePanel } from "@/components/purchase-panel"
import { ShareButton } from "@/components/share-button"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuth } from "@/hooks/use-auth"
import { formatDateTime } from "@/lib/format"
import { CATEGORY_BADGE_CLASS, CATEGORY_LABEL } from "@/lib/labels"
import type { Event, User } from "@/types"

// Keyless embed (no Google API key/billing needed) — the officially
// documented Maps Embed API requires a key, but this free-text `output=embed`
// form works immediately and is enough for "show roughly where this is".
function mapsEmbedUrl(event: { venue_name: string; address: string; city: string }): string {
  const query = [event.venue_name, event.address, event.city].filter(Boolean).join(", ")
  return `https://www.google.com/maps?q=${encodeURIComponent(query)}&output=embed`
}

export function EventDetailPage() {
  const { eventId } = useParams<{ eventId: string }>()
  const { user } = useAuth()

  const { data: event, isLoading, isError } = useQuery({
    queryKey: ["event", eventId],
    queryFn: () => getEvent(eventId!),
    enabled: !!eventId,
    retry: false,
  })

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-64 w-full rounded-xl sm:h-80" />
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <div className="flex flex-col gap-3">
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-9 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-1/3" />
          </div>
          <Skeleton className="hidden h-48 w-full rounded-xl lg:block" />
        </div>
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
              <Link to="/">Voltar para a lista de eventos</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Keyed by event id so navigating between two event detail pages (same
  // route, different :eventId) remounts this and resets `quantity` to 1
  // naturally, instead of syncing it from an effect.
  return <EventDetailContent key={event.id} event={event} user={user} />
}

function EventDetailContent({ event, user }: { event: Event; user: User | null }) {
  const [quantity, setQuantity] = useState(1)

  return (
    <div className="flex flex-col gap-6 pb-24 lg:pb-0">
      <Link
        to="/"
        className="flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Voltar
      </Link>

      <div className="overflow-hidden rounded-xl border">
        <EventThumbnail
          src={event.image_url}
          category={event.category}
          dateTime={event.date_time}
          className="h-64 w-full sm:h-80"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px] lg:items-start">
        <div className="flex flex-col gap-4">
          <Badge variant="outline" className={`w-fit ${CATEGORY_BADGE_CLASS[event.category]}`}>
            {CATEGORY_LABEL[event.category] ?? event.category}
          </Badge>

          <div className="flex items-start justify-between gap-3">
            <h1 className="text-2xl font-semibold sm:text-3xl">{event.title}</h1>
            <div className="flex shrink-0 gap-2">
              {user?.role === "organizer" && user.id === event.organizer && (
                <Button asChild variant="outline" size="sm">
                  <Link to={`/organizador/eventos/${event.id}/editar`}>
                    <Pencil />
                    Editar evento
                  </Link>
                </Button>
              )}
              <ShareButton title={event.title} />
            </div>
          </div>

          <p className="flex items-center gap-2 text-muted-foreground">
            <Calendar className="size-4 shrink-0" />
            {formatDateTime(event.date_time)}
          </p>

          {event.description && (
            <div className="flex flex-col gap-2 pt-2">
              <h2 className="text-lg font-medium">Sobre o evento</h2>
              <p className="whitespace-pre-line text-muted-foreground">{event.description}</p>
            </div>
          )}

          {event.organizer_name && (
            <div className="flex flex-col gap-1.5 pt-2">
              <h2 className="text-lg font-medium">Organizado por</h2>
              <p className="flex items-center gap-2 text-muted-foreground">
                <span aria-hidden>🎭</span>
                {event.organizer_name}
              </p>
            </div>
          )}

          <div className="flex flex-col gap-1.5 pt-2">
            <h2 className="text-lg font-medium">Local</h2>
            <p className="font-medium">{event.venue_name}</p>
            <p className="flex items-center gap-2 text-muted-foreground">
              <MapPin className="size-4 shrink-0" />
              {event.address ? `${event.address} — ` : ""}
              {event.city}
            </p>
            <div className="mt-2 aspect-video w-full overflow-hidden rounded-xl border">
              <iframe
                src={mapsEmbedUrl(event)}
                title={`Mapa de ${event.venue_name}`}
                className="h-full w-full"
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
              />
            </div>
          </div>
        </div>

        <PurchasePanel event={event} user={user} quantity={quantity} onQuantityChange={setQuantity} />
      </div>
    </div>
  )
}
