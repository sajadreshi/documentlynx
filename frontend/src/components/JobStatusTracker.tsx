import { useNavigate } from 'react-router-dom'
import useJobPolling from '../hooks/useJobPolling'

const STAGES = [
  'queued',
  'ingesting',
  'parsing',
  'validating',
  'persisting',
  'classifying',
  'vectorizing',
  'completed',
] as const

interface Props {
  jobId: string
}

export default function JobStatusTracker({ jobId }: Props) {
  const navigate = useNavigate()

  const { data: job, isLoading, error } = useJobPolling({
    jobId,
  })

  if (isLoading) {
    return (
      <div className="text-center py-8 text-gray-500">Loading job status...</div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
        Failed to fetch job status: {(error as Error).message}
      </div>
    )
  }

  if (!job) return null

  // Backend uses `status` as both the status and the current stage name.
  // When status is "failed", it's not in STAGES — we show failure at step 1.
  const currentStage = job.status
  const isFailed = currentStage === 'failed'
  const isCompleted = currentStage === 'completed'
  const stageIndex = STAGES.indexOf(currentStage as typeof STAGES[number])
  // If failed or unknown status, default to index 0 (queued)
  const currentStageIndex = stageIndex >= 0 ? stageIndex : 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700">Processing Pipeline</h3>
        <span
          className={`text-xs font-medium px-2.5 py-0.5 rounded-full ${
            isFailed
              ? 'bg-red-100 text-red-700'
              : isCompleted
                ? 'bg-green-100 text-green-700'
                : 'bg-blue-100 text-blue-700'
          }`}
        >
          {job.status}
        </span>
      </div>

      {/* Stepper */}
      <div className="relative">
        <div className="flex items-center justify-between">
          {STAGES.map((stage, index) => {
            const isActive = index === currentStageIndex && !isFailed
            const isDone = index < currentStageIndex || isCompleted
            const isFailedStage = isFailed && index === currentStageIndex

            return (
              <div key={stage} className="flex flex-col items-center flex-1">
                <div className="relative flex items-center justify-center w-full">
                  {/* Connector line (before) */}
                  {index > 0 && (
                    <div
                      className={`absolute right-1/2 h-0.5 w-full ${
                        isDone ? 'bg-green-500' : 'bg-gray-200'
                      }`}
                    />
                  )}
                  {/* Connector line (after) */}
                  {index < STAGES.length - 1 && (
                    <div
                      className={`absolute left-1/2 h-0.5 w-full ${
                        isDone && index < currentStageIndex - 1 || (isDone && isCompleted)
                          ? 'bg-green-500'
                          : 'bg-gray-200'
                      }`}
                    />
                  )}
                  {/* Circle */}
                  <div
                    className={`relative z-10 w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                      isFailedStage
                        ? 'bg-red-500 text-white'
                        : isDone
                          ? 'bg-green-500 text-white'
                          : isActive
                            ? 'bg-blue-500 text-white animate-pulse'
                            : 'bg-gray-200 text-gray-500'
                    }`}
                  >
                    {isDone ? (
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    ) : isFailedStage ? (
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    ) : (
                      index + 1
                    )}
                  </div>
                </div>
                <span
                  className={`mt-2 text-xs text-center ${
                    isActive ? 'text-blue-600 font-medium' : isFailedStage ? 'text-red-600 font-medium' : 'text-gray-500'
                  }`}
                >
                  {stage}
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Error message */}
      {isFailed && job.error_message && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
          <span className="font-medium">Error:</span> {job.error_message}
        </div>
      )}

      {/* Completed action */}
      {isCompleted && (
        <div className="text-center">
          <button
            onClick={() => navigate(`/documents/${job.document_id}`)}
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
          >
            Review Questions
            <svg className="ml-2 w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </button>
        </div>
      )}
    </div>
  )
}
