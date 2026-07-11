import { useRef, useState, type DragEvent } from 'react'

interface UploadZoneProps {
  onFiles: (files: FileList | File[]) => void
  disabled?: boolean
}

/**
 * Drag-and-drop + click-to-browse upload zone (FRD FR-ADMIN-004).
 * Only visual/interaction — actual upload triggered by "Upload" button in FileRow parent.
 */
export function UploadZone({ onFiles, disabled = false }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    if (!disabled && e.dataTransfer.files.length > 0) {
      onFiles(e.dataTransfer.files)
    }
  }

  return (
    <div
      id="upload-zone"
      role="button"
      tabIndex={0}
      aria-label="Upload PDF files — click or drag and drop"
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => e.key === 'Enter' && !disabled && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      className="flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-8 py-12 text-center transition-all duration-150"
      style={{
        borderColor: isDragging
          ? 'var(--color-truboard-secondary)'
          : 'var(--color-truboard-primary-300)',
        backgroundColor: isDragging
          ? 'hsl(25 90% 59% / 6%)'
          : 'var(--color-truboard-primary-100)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.6 : 1,
      }}
    >
      {/* Icon */}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="40" height="40"
        viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth="1.5"
        strokeLinecap="round" strokeLinejoin="round"
        style={{ color: isDragging ? 'var(--color-truboard-secondary)' : 'var(--color-truboard-primary-400)' }}
      >
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="17 8 12 3 7 8" />
        <line x1="12" y1="3" x2="12" y2="15" />
      </svg>

      <div>
        <p className="text-sm font-medium" style={{ color: 'var(--color-truboard-primary)' }}>
          {isDragging ? 'Drop PDFs here' : 'Drag & drop PDFs here'}
        </p>
        <p className="mt-1 text-xs" style={{ color: 'var(--color-muted-fg)' }}>
          or click to browse — max 50 MB per file
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        multiple
        className="hidden"
        onChange={(e) => e.target.files && onFiles(e.target.files)}
        aria-hidden="true"
      />
    </div>
  )
}
