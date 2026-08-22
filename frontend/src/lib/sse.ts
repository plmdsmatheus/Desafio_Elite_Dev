import { apiClient, tokenStorage } from "@/api/client"

const RETRY_DELAY_MS = 3000

/** Subscribes to a backend Server-Sent Events stream and calls `onMessage`
 * for every `data:` event received. Uses `fetch` instead of the native
 * `EventSource` — `EventSource` can't send custom headers, and this app's
 * auth is a bearer JWT (no cookies), so it has no way to authenticate a
 * native `EventSource` connection. Reconnects automatically on any
 * disconnect/error after a short delay, since a stream can end on its own
 * (the backend caps connection lifetime) as well as on network hiccups.
 * Returns an unsubscribe function — call it on unmount to stop reconnecting
 * and abort any in-flight connection. */
export function subscribeSSE<T>(path: string, onMessage: (data: T) => void): () => void {
  const controller = new AbortController()
  let stopped = false

  async function run() {
    while (!stopped) {
      try {
        const access = tokenStorage.getAccess()
        const res = await fetch(`${apiClient.defaults.baseURL}${path}`, {
          headers: access ? { Authorization: `Bearer ${access}` } : {},
          signal: controller.signal,
        })
        if (!res.ok || !res.body) throw new Error(`SSE request failed: ${res.status}`)

        const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
        let buffer = ""
        while (!stopped) {
          const { value, done } = await reader.read()
          if (done) break
          buffer += value
          const events = buffer.split("\n\n")
          buffer = events.pop() ?? ""
          for (const raw of events) {
            const dataLine = raw.split("\n").find((line) => line.startsWith("data:"))
            if (!dataLine) continue // heartbeat/comment line — nothing to parse
            onMessage(JSON.parse(dataLine.slice(5).trim()) as T)
          }
        }
      } catch {
        // Connection dropped, was refused, or the abort fired on unmount —
        // either way fall through to the retry delay below (or exit the
        // loop entirely if `stopped` was the cause).
      }
      if (!stopped) await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS))
    }
  }

  run()

  return () => {
    stopped = true
    controller.abort()
  }
}
