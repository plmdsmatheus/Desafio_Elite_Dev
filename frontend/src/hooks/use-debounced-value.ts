import { useEffect, useState } from "react"

/** Returns `value`, but only after it's stopped changing for `delayMs` —
 * used so typing into a filter doesn't fire a request per keystroke while
 * still applying instantly once the user pauses. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])

  return debounced
}
