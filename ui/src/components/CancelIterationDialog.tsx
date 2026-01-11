import { useState } from 'react'
import { XCircle, AlertTriangle, CheckCircle } from 'lucide-react'
import type { ActiveIterationResponse, CancelIterationResponse } from '../lib/api'

interface CancelIterationDialogProps {
  iteration: ActiveIterationResponse['iteration']
  onCancel: (version: number, restoreBackups: boolean) => Promise<CancelIterationResponse>
  onClose: () => void
}

export function CancelIterationDialog({
  iteration,
  onCancel,
  onClose,
}: CancelIterationDialogProps) {
  const [restoreBackups, setRestoreBackups] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [result, setResult] = useState<CancelIterationResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (!iteration) {
    return null
  }

  const handleConfirm = async () => {
    setCancelling(true)
    setError(null)

    try {
      const response = await onCancel(iteration.version, restoreBackups)
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel iteration')
      setCancelling(false)
    }
  }

  // Success state
  if (result) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div className="neo-card max-w-lg w-full p-6 space-y-4">
          <div className="flex items-start gap-3">
            <CheckCircle className="text-[var(--color-neo-done)] flex-shrink-0" size={24} />
            <div className="flex-1">
              <h2 className="text-xl font-bold mb-2">Iteration Cancelled Successfully</h2>
              <p className="text-[var(--color-neo-text-secondary)] mb-4">{result.message}</p>

              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-[var(--color-neo-text-secondary)]">Features removed:</span>
                  <span className="font-mono font-bold">{result.features_removed}</span>
                </div>

                <div className="pl-4 space-y-1 text-[var(--color-neo-text-secondary)]">
                  <div className="flex justify-between">
                    <span>Pending:</span>
                    <span className="font-mono">{result.features_by_status.pending}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>In Progress:</span>
                    <span className="font-mono">{result.features_by_status.in_progress}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Done:</span>
                    <span className="font-mono">{result.features_by_status.done}</span>
                  </div>
                </div>

                {result.backups_restored && (
                  <div className="flex items-center gap-2 text-[var(--color-neo-done)] pt-2">
                    <CheckCircle size={16} />
                    <span>Backups restored successfully</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="flex justify-end pt-4">
            <button onClick={onClose} className="neo-btn">
              Close
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Confirmation state
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="neo-card max-w-lg w-full p-6 space-y-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="text-yellow-500 flex-shrink-0" size={24} />
          <div className="flex-1">
            <h2 className="text-xl font-bold mb-2">Cancel Iteration v{iteration.version}?</h2>
            <p className="text-[var(--color-neo-text-secondary)] mb-4">
              This will remove all features created by this iteration.
            </p>

            {error && (
              <div className="mb-4 p-3 bg-red-500/10 border-2 border-red-500 text-red-500 rounded-lg text-sm">
                {error}
              </div>
            )}

            <div className="space-y-3 mb-4">
              <div className="p-4 bg-[var(--color-neo-bg)] rounded-lg border-2 border-[var(--color-neo-border)]">
                <h3 className="font-bold mb-2 text-sm">Features to Remove</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-[var(--color-neo-text-secondary)]">Total:</span>
                    <span className="font-mono font-bold">
                      {/* Calculate based on next_priority assumption */}
                      (will be counted)
                    </span>
                  </div>
                  <div className="text-xs text-[var(--color-neo-text-secondary)]">
                    All features with priority ≥ {iteration.next_priority}
                  </div>
                </div>
              </div>

              <div className="p-4 bg-[var(--color-neo-bg)] rounded-lg border-2 border-[var(--color-neo-border)]">
                <h3 className="font-bold mb-2 text-sm">Backups Preserved</h3>
                <div className="space-y-1 text-sm text-[var(--color-neo-text-secondary)]">
                  <div className="font-mono">{iteration.spec_backup}</div>
                  <div className="font-mono">{iteration.db_backup}</div>
                </div>
              </div>

              <label className="flex items-center gap-3 p-3 bg-[var(--color-neo-bg)] rounded-lg border-2 border-[var(--color-neo-border)] cursor-pointer hover:border-[var(--color-neo-primary)] transition-colors">
                <input
                  type="checkbox"
                  checked={restoreBackups}
                  onChange={(e) => setRestoreBackups(e.target.checked)}
                  className="w-5 h-5"
                />
                <div className="flex-1">
                  <div className="font-medium text-sm">Restore backups (advanced)</div>
                  <div className="text-xs text-[var(--color-neo-text-secondary)]">
                    Revert app_spec.txt and features.db to backup state
                  </div>
                </div>
              </label>
            </div>
          </div>
        </div>

        <div className="flex gap-3 pt-4">
          <button
            onClick={onClose}
            disabled={cancelling}
            className="neo-btn flex-1"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={cancelling}
            className="neo-btn neo-btn-danger flex-1 flex items-center justify-center gap-2"
          >
            {cancelling ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Cancelling...</span>
              </>
            ) : (
              <>
                <XCircle size={16} />
                <span>Confirm Cancellation</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}