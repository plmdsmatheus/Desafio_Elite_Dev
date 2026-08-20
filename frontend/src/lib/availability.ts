export type AvailabilityLevel = "high" | "low" | "sold_out"

/** Traffic-light read on remaining stock: sold out, running low (≤15% left), or plenty. */
export function getAvailabilityLevel(available: number, capacity: number): AvailabilityLevel {
  if (available <= 0) return "sold_out"
  if (capacity > 0 && available / capacity <= 0.15) return "low"
  return "high"
}
