import { CalendarDays } from "lucide-react"
import { useState } from "react"
import { formatDateShort } from "@/lib/format"
import { CATEGORY_LABEL } from "@/lib/labels"
import { cn } from "@/lib/utils"

interface EventThumbnailProps {
  src: string
  category: string
  dateTime: string
  className?: string
}

/** Falls back to a designed placeholder when there's no image, or the URL
 * 404s (the seeded demo events point at made-up image URLs) — a plain broken
 * image icon reads as an error, not as "no photo yet". */
export function EventThumbnail({ src, category, dateTime, className }: EventThumbnailProps) {
  const [failed, setFailed] = useState(false)

  if (!src || failed) {
    return (
      <div
        className={cn(
          "relative flex flex-col items-center justify-center gap-1 overflow-hidden bg-gradient-to-br from-primary/20 via-primary/5 to-transparent",
          className,
        )}
      >
        <CalendarDays className="size-9 text-primary/40" strokeWidth={1.5} />
        <p className="text-xs font-medium text-primary/70">
          {CATEGORY_LABEL[category] ?? category} · {formatDateShort(dateTime)}
        </p>
      </div>
    )
  }

  return (
    <img
      src={src}
      alt=""
      className={cn("object-cover", className)}
      onError={() => setFailed(true)}
    />
  )
}
