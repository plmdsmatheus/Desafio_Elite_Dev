import { useState } from "react"
import { cn } from "@/lib/utils"
import type { Event } from "@/types"

interface HeroBackdropProps {
  events: Event[]
}

interface Slot {
  top: string
  left: string
  rotate: number
  widthClass: string
}

// Fixed, hand-placed positions for up to 6 posters — a scattered collage
// around the centered headline, never dead center where the copy sits (the
// overlay below darkens that zone further so a poster peeking through never
// fights the text for attention).
const SLOTS: Slot[] = [
  { top: "2%", left: "2%", rotate: -8, widthClass: "w-32 sm:w-44" },
  { top: "52%", left: "-2%", rotate: 6, widthClass: "w-28 sm:w-40" },
  { top: "4%", left: "76%", rotate: 7, widthClass: "w-32 sm:w-44" },
  { top: "54%", left: "82%", rotate: -6, widthClass: "w-28 sm:w-40" },
  { top: "-4%", left: "40%", rotate: -3, widthClass: "w-24 sm:w-32" },
  { top: "68%", left: "44%", rotate: 4, widthClass: "w-24 sm:w-32" },
]

/** Decorative poster collage behind the Hero headline, built from the same
 * real event images the page already fetched for the carousel — no new
 * asset or request. Purely atmospheric: pointer-events-none so it never
 * steals a click from the CTA, and a broken poster just disappears (not a
 * placeholder box) since nothing here is meant to be read on its own. */
export function HeroBackdrop({ events }: HeroBackdropProps) {
  const posters = events.filter((event) => event.image_url).slice(0, SLOTS.length)
  const [failedIds, setFailedIds] = useState<Set<number>>(new Set())

  if (posters.length === 0) return null

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      <div className="hero-backdrop-drift absolute inset-0">
        {posters.map((event, index) => {
          if (failedIds.has(event.id)) return null
          const slot = SLOTS[index % SLOTS.length]
          return (
            <img
              key={event.id}
              src={event.image_url}
              alt=""
              className={cn(
                "absolute aspect-[3/4] rounded-xl object-cover opacity-90 shadow-2xl",
                slot.widthClass,
              )}
              style={{ top: slot.top, left: slot.left, transform: `rotate(${slot.rotate}deg)` }}
              onError={() => setFailedIds((prev) => new Set(prev).add(event.id))}
            />
          )
        })}
      </div>
      <div className="absolute inset-0 bg-gradient-to-t from-background via-background/40 to-background/10" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_20%,var(--brand-bg)_78%)]" />
    </div>
  )
}
