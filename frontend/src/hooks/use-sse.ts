import { useEffect, useRef } from "react"
import { subscribeSSE } from "@/lib/sse"

/** Subscribes to a backend SSE stream for the lifetime of the component (or
 * while `enabled` stays true) and calls `onMessage` for every event. Just a
 * thin wrapper around `subscribeSSE` — see that file for the
 * connection/reconnect details.
 *
 * `onMessage` is read through a ref (same pattern as QrScanner's onScanRef)
 * so the connection effect only depends on `path`/`enabled`: an inline
 * callback that gets a new identity every render won't tear down and
 * reopen the stream, but the latest closure still runs on every event. */
export function useSSE<T>(path: string, onMessage: (data: T) => void, enabled = true) {
  const onMessageRef = useRef(onMessage)

  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  useEffect(() => {
    if (!enabled) return
    return subscribeSSE<T>(path, (data) => onMessageRef.current(data))
  }, [path, enabled])
}
