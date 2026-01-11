/**
 * Iteration Chat Modal
 *
 * Full-screen modal wrapper for the IterationChat component.
 */

import { IterationChat } from './IterationChat'
import type { IterationMetadata } from '../hooks/useIterationChat'

interface IterationChatModalProps {
  isOpen: boolean
  projectName: string
  onClose: () => void
  onComplete: (metadata: IterationMetadata) => void
}

export function IterationChatModal({
  isOpen,
  projectName,
  onClose,
  onComplete,
}: IterationChatModalProps) {
  if (!isOpen) return null

  const handleComplete = (metadata: IterationMetadata) => {
    onComplete(metadata)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 bg-[var(--color-neo-bg)]">
      <IterationChat
        projectName={projectName}
        onComplete={handleComplete}
        onCancel={onClose}
      />
    </div>
  )
}