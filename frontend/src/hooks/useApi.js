import { useState, useEffect, useCallback, useRef } from 'react'

export function useApi(fetcher, deps = []) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const fetcherRef            = useRef(fetcher)
  fetcherRef.current          = fetcher

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const d = await fetcherRef.current()
      setData(d)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load() }, [load])

  return { data, loading, error, reload: load }
}

export function usePoll(fetcher, intervalMs = 4000, active = true) {
  const [data, setData]   = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!active) return
    let cancelled = false

    const run = async () => {
      try {
        const d = await fetcher()
        if (!cancelled) setData(d)
      } catch {}
      finally { if (!cancelled) setLoading(false) }
    }

    run()
    const id = setInterval(run, intervalMs)
    return () => { cancelled = true; clearInterval(id) }
  }, [active, intervalMs]) // eslint-disable-line

  return { data, loading }
}
