import { useQuery } from '@tanstack/react-query'
import { getJobStatus, type JobStatus } from '../api/documents'

interface UseJobPollingOptions {
  jobId: string | null
  onCompleted?: (job: JobStatus) => void
  onFailed?: (job: JobStatus) => void
}

export default function useJobPolling({ jobId, onCompleted, onFailed }: UseJobPollingOptions) {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: async () => {
      const job = await getJobStatus(jobId!)
      if (job.status === 'completed' && onCompleted) {
        onCompleted(job)
      }
      if (job.status === 'failed' && onFailed) {
        onFailed(job)
      }
      return job
    },
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return 3000
      if (data.status === 'completed' || data.status === 'failed') return false
      return 3000
    },
  })
}
