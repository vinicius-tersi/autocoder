import { useState } from 'react'
import { useStartIteration } from '../hooks/useProjects'
import { X, GitBranch, Loader2 } from 'lucide-react'

interface AddIterationModalProps {
  projectName: string
  onClose: () => void
}

export function AddIterationModal({ projectName, onClose }: AddIterationModalProps) {
  const [instructions, setInstructions] = useState('')
  const startIteration = useStartIteration(projectName)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!instructions.trim()) return

    startIteration.mutate(
      { instructions },
      {
        onSuccess: () => {
          onClose()
        },
      }
    )
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white border-3 border-black p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto shadow-neo">
        <div className="flex justify-between items-center mb-4">
          <h2 className="font-display font-bold text-2xl flex items-center gap-2">
            <GitBranch size={24} />
            Add Project Iteration
          </h2>
          <button onClick={onClose} className="neo-btn neo-btn-secondary p-2">
            <X size={20} />
          </button>
        </div>

        <div className="mb-4 p-4 bg-yellow-50 border-3 border-yellow-600">
          <p className="font-bold text-yellow-900 mb-2">⚠️ This will:</p>
          <ul className="list-disc list-inside text-sm text-yellow-800 space-y-1">
            <li>Create a versioned backup of app_spec.txt and features.db</li>
            <li>Generate iteration instructions for the Initializer Agent</li>
            <li>Add NEW features to the database (preserving existing ones)</li>
            <li>The agent will process this on next run</li>
          </ul>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block font-display font-bold mb-2">
              Expansion Instructions
            </label>
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              className="w-full border-3 border-black p-3 font-mono text-sm resize-y min-h-[200px] focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Example: Add user profile functionality with the following features:
- Profile page showing user info and avatar
- Edit profile form with validation
- Avatar upload with image preview
- Profile settings (privacy, notifications)"
              required
            />
            <p className="text-sm text-gray-600 mt-2">
              Describe what you want to add. Be specific about features, screens, and behaviors.
            </p>
          </div>

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="neo-btn neo-btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={startIteration.isPending || !instructions.trim()}
              className="neo-btn neo-btn-primary flex items-center gap-2"
            >
              {startIteration.isPending ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Creating Iteration...
                </>
              ) : (
                <>
                  <GitBranch size={18} />
                  Start Iteration
                </>
              )}
            </button>
          </div>

          {startIteration.isError && (
            <div className="mt-4 p-3 bg-red-50 border-3 border-red-600 text-red-900">
              <p className="font-bold">Error creating iteration:</p>
              <p className="text-sm">{startIteration.error?.message || 'Unknown error'}</p>
            </div>
          )}
        </form>
      </div>
    </div>
  )
}