import { Calendar, MapPin, ShieldAlert } from "lucide-react"
import { type MouseEvent, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { EventThumbnail } from "@/components/event-thumbnail"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import {
  AVAILABILITY_TEXT_CLASS,
  type AvailabilityLevel,
  getAvailabilityLevel,
} from "@/lib/availability"
import { formatCurrency, formatDateShort } from "@/lib/format"
import { AGE_RATING_LABEL, CATEGORY_BADGE_CLASS, CATEGORY_LABEL } from "@/lib/labels"
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
  const completed = event.effective_status === "completed"
  const level = getAvailabilityLevel(event.tickets_available, event.capacity)
  const [tilt, setTilt] = useState({ x: 0, y: 0 })

  // Captured once on enter, not re-measured on every mousemove: by the time
  // a move handler fires, the element already carries the transform from the
  // previous frame, so getBoundingClientRect() on it mid-hover returns the
  // rotated (foreshortened) box instead of the flat layout one — feeding a
  // skewed rect back into the tilt math, which is what made one edge read as
  // flat while tilting from the opposite side. Measuring only on enter (when
  // the transform is guaranteed neutral, since leave always resets it) keeps
  // the whole gesture working off one consistent, untransformed rect.
  const rectRef = useRef<DOMRect | null>(null)

  function handleMouseEnter(event: MouseEvent<HTMLAnchorElement>) {
    rectRef.current = event.currentTarget.getBoundingClientRect()
  }

  function handleMouseMove(event: MouseEvent<HTMLAnchorElement>) {
    const rect = rectRef.current ?? event.currentTarget.getBoundingClientRect()
    const px = (event.clientX - rect.left) / rect.width
    const py = (event.clientY - rect.top) / rect.height
    setTilt({ x: (0.5 - py) * MAX_TILT_DEG * 2, y: (px - 0.5) * MAX_TILT_DEG * 2 })
  }

  function handleMouseLeave() {
    setTilt({ x: 0, y: 0 })
    rectRef.current = null
  }

  const card = (
    <Card
      className={cn(
        "h-full overflow-hidden py-0 transition-all",
        !completed &&
          "hover:-translate-y-0.5 hover:ring-2 hover:ring-primary hover:shadow-[0_0_20px_-2px_var(--brand-accent)]",
      )}
    >
      <div className="relative h-36 overflow-hidden sm:h-40">
        <EventThumbnail
          src={event.image_url}
          category={event.category}
          dateTime={event.date_time}
          className={cn(
            "h-full w-full transition-transform duration-300",
            !completed && "group-hover:scale-105",
          )}
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
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="line-clamp-1 text-left">
                {event.venue_name}, {event.city}
              </span>
            </TooltipTrigger>
            <TooltipContent>
              {event.venue_name}, {event.city}
            </TooltipContent>
          </Tooltip>
        </p>
        <p className="flex items-center gap-1.5">
          <Calendar className="size-3.5 shrink-0" />
          {formatDateShort(event.date_time)}
        </p>

        <div className="mt-auto flex items-end justify-between pt-2">
          <span className="text-lg font-bold text-primary">{formatCurrency(event.price)}</span>
          {!completed && (
            <span
              className={cn(
                "flex items-center gap-1.5 text-xs font-medium",
                AVAILABILITY_TEXT_CLASS[level],
              )}
            >
              <span className={cn("size-2 rounded-full", AVAILABILITY_DOT[level])} />
              {availabilityLabel(level, event.tickets_available)}
            </span>
          )}
        </div>

        {event.age_rating && (
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <ShieldAlert className="size-3.5 shrink-0" />
            {AGE_RATING_LABEL[event.age_rating]}
          </p>
        )}
      </CardContent>
    </Card>
  )

  // Realizado: not clickable, no detail page, no availability count — just a
  // visual record that it happened, not an active listing.
  if (completed) {
    return <div className="block">{card}</div>
  }

  return (
    <Link
      to={`/eventos/${event.id}`}
      className="group block"
      onMouseEnter={handleMouseEnter}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{
        transform: `perspective(800px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
        transition: "transform 300ms cubic-bezier(0.22, 1, 0.36, 1)",
      }}
    >
      {card}
    </Link>
  )
}
