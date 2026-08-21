import { Calendar, MapPin } from "lucide-react"
import { type MouseEvent, useState } from "react"
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

// Max single-axis rotation for the tilt-toward-cursor effect — enough to read
// as "weight", not so much it looks like the card is falling over.
const MAX_TILT_DEG = 8

export function EventCard({ event }: { event: Event }) {
  const level = getAvailabilityLevel(event.tickets_available, event.capacity)
  const [tilt, setTilt] = useState({ x: 0, y: 0 })
  const [glare, setGlare] = useState({ x: 50, y: 50, opacity: 0 })

  function handleMouseMove(event: MouseEvent<HTMLAnchorElement>) {
    const rect = event.currentTarget.getBoundingClientRect()
    const px = (event.clientX - rect.left) / rect.width
    const py = (event.clientY - rect.top) / rect.height
    setTilt({ x: (0.5 - py) * MAX_TILT_DEG * 2, y: (px - 0.5) * MAX_TILT_DEG * 2 })
    setGlare({ x: px * 100, y: py * 100, opacity: 1 })
  }

  function handleMouseLeave() {
    setTilt({ x: 0, y: 0 })
    setGlare((g) => ({ ...g, opacity: 0 }))
  }

  return (
    <Link
      to={`/eventos/${event.id}`}
      className="group block"
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{
        transform: `perspective(800px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
        transition: "transform 300ms cubic-bezier(0.22, 1, 0.36, 1)",
      }}
    >
      <Card className="h-full overflow-hidden py-0 transition-all hover:-translate-y-0.5 hover:shadow-lg">
        <div className="relative h-36 overflow-hidden sm:h-40">
          <EventThumbnail
            src={event.image_url}
            category={event.category}
            dateTime={event.date_time}
            className="h-full w-full transition-transform duration-300 group-hover:scale-105"
          />
          {/* Smoky lime reflection that follows the cursor across the image. */}
          <div
            className="pointer-events-none absolute inset-0 transition-opacity duration-300"
            style={{
              opacity: glare.opacity * 0.5,
              background: `radial-gradient(circle at ${glare.x}% ${glare.y}%, var(--brand-accent), transparent 60%)`,
              mixBlendMode: "screen",
            }}
          />
        </div>

        <div className="px-4 pt-3">
          <Badge variant="outline" className={CATEGORY_BADGE_CLASS[event.category]}>
            {CATEGORY_LABEL[event.category] ?? event.category}
          </Badge>
        </div>

        <CardHeader className="pt-2">
          <CardTitle className="line-clamp-2 min-h-11">{event.title}</CardTitle>
        </CardHeader>

        <CardContent className="flex flex-1 flex-col gap-1.5 pb-4 text-sm text-muted-foreground">
          <p className="flex items-center gap-1.5">
            <MapPin className="size-3.5 shrink-0" />
            <span className="line-clamp-1">
              {event.venue_name}, {event.city}
            </span>
          </p>
          <p className="flex items-center gap-1.5">
            <Calendar className="size-3.5 shrink-0" />
            {formatDateShort(event.date_time)}
          </p>

          <div className="mt-auto flex items-end justify-between pt-2">
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
