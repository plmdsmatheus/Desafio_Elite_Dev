import { Calendar, MapPin } from "lucide-react"
import { Link } from "react-router-dom"
import { EventThumbnail } from "@/components/event-thumbnail"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  AVAILABILITY_TEXT_CLASS,
  type AvailabilityLevel,
  getAvailabilityLevel,
} from "@/lib/availability"
import { formatCurrency, formatDateShort } from "@/lib/format"
import { CATEGORY_BADGE_CLASS, CATEGORY_LABEL } from "@/lib/labels"
import { cn } from "@/lib/utils"
import type { Event } from "@/types"

const AVAILABILITY_DOT: Record<AvailabilityLevel, string> = {
  high: "bg-success",
  low: "bg-warning",
  sold_out: "bg-destructive",
}

function availabilityLabel(level: AvailabilityLevel, available: number): string {
  if (level === "sold_out") return "Esgotado"
  if (level === "low") return `Últimas ${available}`
  return `${available} disponíveis`
}

export function EventCard({ event }: { event: Event }) {
  const level = getAvailabilityLevel(event.tickets_available, event.capacity)

  return (
    <Link to={`/eventos/${event.id}`} className="group block">
      <Card className="h-full overflow-hidden py-0 transition-all hover:-translate-y-0.5 hover:shadow-lg">
        <div className="h-36 overflow-hidden sm:h-40">
          <EventThumbnail
            src={event.image_url}
            category={event.category}
            dateTime={event.date_time}
            className="h-full w-full transition-transform duration-300 group-hover:scale-105"
          />
        </div>

        <div className="px-4 pt-3">
          <Badge variant="outline" className={CATEGORY_BADGE_CLASS[event.category]}>
            {CATEGORY_LABEL[event.category] ?? event.category}
          </Badge>
        </div>

        <CardHeader className="pt-2">
          <CardTitle className="line-clamp-2">{event.title}</CardTitle>
        </CardHeader>

        <CardContent className="flex flex-col gap-1.5 pb-4 text-sm text-muted-foreground">
          <p className="flex items-center gap-1.5">
            <MapPin className="size-3.5 shrink-0" />
            {event.venue_name}, {event.city}
          </p>
          <p className="flex items-center gap-1.5">
            <Calendar className="size-3.5 shrink-0" />
            {formatDateShort(event.date_time)}
          </p>

          <div className="mt-2 flex items-end justify-between">
            <span className="text-lg font-bold text-primary">{formatCurrency(event.price)}</span>
            <span
              className={cn(
                "flex items-center gap-1.5 text-xs font-medium",
                AVAILABILITY_TEXT_CLASS[level],
              )}
            >
              <span className={cn("size-2 rounded-full", AVAILABILITY_DOT[level])} />
              {availabilityLabel(level, event.tickets_available)}
            </span>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
