import type { Policy } from '../../types'

interface PolicyListProps {
  documents: Policy[]
  activeDocument: Policy | null
  isLoading: boolean
  isError: boolean
  onSelect: (policy: Policy) => void
}

export function PolicyList({ documents, activeDocument, isLoading, isError, onSelect }: PolicyListProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col gap-2 px-2 pt-2">
        {[...Array(5)].map((_, i) => (
          <div
            key={i}
            className="h-10 animate-pulse rounded-lg"
            style={{ backgroundColor: 'var(--color-truboard-primary-200)' }}
          />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <p className="px-3 py-4 text-sm" style={{ color: 'var(--color-destructive)' }}>
        Failed to load policies. Please refresh.
      </p>
    )
  }

  if (documents.length === 0) {
    return (
      <p className="px-3 py-4 text-sm" style={{ color: 'var(--color-muted-fg)' }}>
        No policies available yet.
      </p>
    )
  }

  return (
    <ul className="flex flex-col gap-0.5 px-2">
      {documents.map((policy) => {
        const isActive = activeDocument?.id === policy.id
        return (
          <li key={policy.id}>
            <button
              type="button"
              id={`policy-${policy.id}`}
              onClick={() => onSelect(policy)}
              className="w-full rounded-lg px-3 py-2.5 text-left text-sm font-medium transition-all duration-150"
              style={{
                backgroundColor: isActive
                  ? 'var(--color-truboard-primary)'
                  : 'transparent',
                color: isActive
                  ? 'white'
                  : 'var(--color-foreground)',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = 'var(--color-truboard-primary-200)'
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = 'transparent'
                }
              }}
              title={`${policy.policy_name} — v${policy.version}`}
            >
              <span className="block truncate">{policy.policy_name}</span>
              <span
                className="block text-xs font-normal"
                style={{ color: isActive ? 'rgba(255,255,255,0.65)' : 'var(--color-muted-fg)' }}
              >
                v{policy.version}
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
