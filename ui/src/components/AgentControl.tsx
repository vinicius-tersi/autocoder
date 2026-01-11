import { Play, Square, Pause, Loader2 } from 'lucide-react'
import {
  useStartAgent,
  useStopAgent,
  usePauseAgent,
  useResumeAgent,
  useSettings,
} from '../hooks/useProjects'
import type { AgentStatus } from '../lib/types'

interface AgentControlProps {
  projectName: string
  status: AgentStatus
}

export function AgentControl({ projectName, status }: AgentControlProps) {
  const { data: settings } = useSettings()
  const yoloMode = settings?.yolo_mode ?? false

  const startAgent = useStartAgent(projectName)
  const stopAgent = useStopAgent(projectName)
  const pauseAgent = usePauseAgent(projectName)
  const resumeAgent = useResumeAgent(projectName)

  const isLoading = startAgent.isPending || stopAgent.isPending || pauseAgent.isPending || resumeAgent.isPending

  const handleStart = () => startAgent.mutate(yoloMode)
  const handleStop = () => stopAgent.mutate()
  const handlePause = () => pauseAgent.mutate()
  const handleResume = () => resumeAgent.mutate()

  // Show different controls based on status:
  // - stopped/crashed: Show Play button only
  // - running: Show Pause + Stop buttons
  // - paused: Show Resume (Play) + Stop buttons
  const isStopped = status === 'stopped' || status === 'crashed'
  const isRunning = status === 'running'
  const isPaused = status === 'paused'

  return (
    <div className="flex items-center gap-2">
      {/* STOPPED/CRASHED: Show only Play */}
      {isStopped && (
        <button
          onClick={handleStart}
          disabled={isLoading}
          className={`neo-btn text-sm py-2 px-3 ${
            yoloMode ? 'neo-btn-yolo' : 'neo-btn-success'
          }`}
          title={yoloMode ? 'Start Agent (YOLO Mode)' : 'Start Agent'}
          aria-label={yoloMode ? 'Start Agent in YOLO Mode' : 'Start Agent'}
        >
          {isLoading ? (
            <Loader2 size={18} className="animate-spin" />
          ) : (
            <Play size={18} />
          )}
        </button>
      )}

      {/* RUNNING: Show Pause + Stop */}
      {isRunning && (
        <>
          <button
            onClick={handlePause}
            disabled={isLoading}
            className={`neo-btn text-sm py-2 px-3 ${
              yoloMode ? 'neo-btn-yolo' : 'neo-btn-warning'
            }`}
            title="Pause Agent (keeps session alive)"
            aria-label="Pause Agent"
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Pause size={18} />
            )}
          </button>
          <button
            onClick={handleStop}
            disabled={isLoading}
            className={`neo-btn text-sm py-2 px-3 ${
              yoloMode ? 'neo-btn-yolo' : 'neo-btn-danger'
            }`}
            title="Stop Agent (ends session)"
            aria-label="Stop Agent"
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Square size={18} />
            )}
          </button>
        </>
      )}

      {/* PAUSED: Show Resume (Play) + Stop */}
      {isPaused && (
        <>
          <button
            onClick={handleResume}
            disabled={isLoading}
            className={`neo-btn text-sm py-2 px-3 ${
              yoloMode ? 'neo-btn-yolo' : 'neo-btn-success'
            }`}
            title="Resume Agent"
            aria-label="Resume Agent"
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Play size={18} />
            )}
          </button>
          <button
            onClick={handleStop}
            disabled={isLoading}
            className={`neo-btn text-sm py-2 px-3 ${
              yoloMode ? 'neo-btn-yolo' : 'neo-btn-danger'
            }`}
            title="Stop Agent (ends session)"
            aria-label="Stop Agent"
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Square size={18} />
            )}
          </button>
        </>
      )}
    </div>
  )
}
