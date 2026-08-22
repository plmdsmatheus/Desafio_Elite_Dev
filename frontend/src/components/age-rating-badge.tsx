import { cn } from "@/lib/utils"
import type { EventAgeRating } from "@/types"

// Same colors as Brazil's official ClassInd classificação indicativa
// pictograms — recognizable at a glance from posters/TV to anyone in the
// target audience, not an arbitrary palette choice.
const AGE_RATING_COLOR: Record<Exclude<EventAgeRating, "">, string> = {
  L: "bg-[#2fa63f]",
  "10": "bg-[#2f9bd6]",
  "12": "bg-[#f2b300]",
  "14": "bg-[#f2711c]",
  "16": "bg-[#e0342a]",
  "18": "bg-black border border-white/80",
}

export function AgeRatingBadge({ rating }: { rating: Exclude<EventAgeRating, ""> }) {
  return (
    <span
      className={cn(
        "flex size-4 shrink-0 items-center justify-center rounded-[3px] text-[9px] font-extrabold leading-none text-white",
        AGE_RATING_COLOR[rating],
      )}
    >
      {rating}
    </span>
  )
}
