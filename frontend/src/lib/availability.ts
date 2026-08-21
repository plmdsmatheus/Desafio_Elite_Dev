export type AvailabilityLevel = "high" | "low" | "sold_out"

// Simple sanity cap on a single reservation — not a business rule from the
// backend, just keeps the quantity stepper from scrolling to absurd numbers.
export const MAX_QUANTITY_PER_RESERVATION = 10

/** Traffic-light read on remaining stock: sold out, running low, or plenty.
 * "Low" uses a 20% threshold with a floor of 3 units so small-capacity
 * events (e.g. a 5-seat venue) can still show an amber warning before
 * jumping straight to sold out — a pure percentage cutoff never triggers
 * for them (5 * 0.15 rounds under 1, so "low" was unreachable). The floor
 * also means a bigger event bought down in coarse batches (e.g. 10 at a
 * time on a 60-capacity event) actually passes through the amber band
 * instead of skipping it. */
export function getAvailabilityLevel(available: number, capacity: number): AvailabilityLevel {
  if (available <= 0) return "sold_out"
  if (capacity > 0 && available <= Math.max(capacity * 0.2, 3)) return "low"
  return "high"
}

/** Shared text color per level — reused by the event card badge and the
 * purchase panel so the semaphore reads the same everywhere. */
export const AVAILABILITY_TEXT_CLASS: Record<AvailabilityLevel, string> = {
  high: "text-success",
  low: "text-warning",
  sold_out: "text-destructive",
}
