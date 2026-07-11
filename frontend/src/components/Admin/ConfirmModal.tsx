interface ConfirmModalProps {
  isOpen: boolean
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  onConfirm: () => void
  onCancel: () => void
  /** 'danger' renders the confirm button in red */
  variant?: 'default' | 'danger'
}

/**
 * Generic confirmation modal for SHA-256 dedup prompts (FRD FR-ADMIN-007 / FR-ADMIN-008).
 * Renders a backdrop + centred card.
 */
export function ConfirmModal({
  isOpen,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
  variant = 'default',
}: ConfirmModalProps) {
  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0, 29, 86, 0.45)' }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div
        className="w-full max-w-md rounded-2xl p-6 shadow-xl"
        style={{ backgroundColor: 'white' }}
      >
        <h2
          id="modal-title"
          className="text-base font-semibold"
          style={{ color: 'var(--color-truboard-primary)' }}
        >
          {title}
        </h2>
        <p
          className="mt-2 text-sm leading-relaxed"
          style={{ color: 'var(--color-foreground)' }}
        >
          {message}
        </p>

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            id="modal-cancel"
            onClick={onCancel}
            className="rounded-lg px-4 py-2 text-sm font-medium transition-colors"
            style={{
              backgroundColor: 'var(--color-truboard-primary-200)',
              color: 'var(--color-truboard-primary)',
            }}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            id="modal-confirm"
            onClick={onConfirm}
            className="rounded-lg px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90"
            style={{
              backgroundColor:
                variant === 'danger'
                  ? 'var(--color-destructive)'
                  : 'var(--color-truboard-primary)',
            }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
