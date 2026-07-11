import { useEffect, useRef, useState } from 'react'

interface SwitchToastProps {
  /** Name of the document that was switched to. null = no toast. */
  documentName: string | null
  /** Duration before auto-dismiss in ms (FRD: 3 seconds). */
  duration?: number
}

/**
 * Toast notification shown on every document switch (FRD FR-PDF-012).
 * Auto-dismisses after 3 seconds.
 */
export function SwitchToast({ documentName, duration = 3000 }: SwitchToastProps) {
  const [visible, setVisible] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!documentName) return
    setVisible(true)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setVisible(false), duration)
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [documentName, duration])

  if (!visible || !documentName) return null

  return (
    <div
      id="switch-toast"
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-xl px-5 py-2.5 shadow-lg"
      style={{
        backgroundColor: 'var(--color-truboard-primary)',
        color: 'white',
        fontSize: 'var(--font-size-sm)',
        fontWeight: 500,
        animation: 'fadeInUp 0.2s ease-out',
      }}
    >
      Switched to {documentName} — your conversation continues.
    </div>
  )
}
