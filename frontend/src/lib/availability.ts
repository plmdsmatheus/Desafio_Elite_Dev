export type AvailabilityLevel = "high" | "low" | "sold_out"

/** Traffic-light read on remaining stock: sold out, running low (≤15% left), or plenty. */
export function getAvailabilityLevel(available: number, capacity: number): AvailabilityLevel {
  if (available <= 0) return "sold_out"
  if (capacity > 0 && available / capacity <= 0.15) return "low"
  return "high"
}

/** Shared text color per level — reused by the event card badge and the
 * purchase panel so the semaphore reads the same everywhere. */
export const AVAILABILITY_TEXT_CLASS: Record<AvailabilityLevel, string> = {
  high: "text-success",
  low: "text-warning",
  sold_out: "text-destructive",
}
