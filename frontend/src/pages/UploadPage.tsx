import { useState } from 'react'
import { Link } from 'react-router-dom'
import axios from 'axios'
import toast from 'react-hot-toast'
import UploadDropzone from '../components/UploadDropzone'
import JobStatusTracker from '../components/JobStatusTracker'
import { uploadDocument, processDocument } from '../api/documents'

function getErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    if (err.code === 'ERR_NETWORK' || !err.response) {
      const base = import.meta.env.VITE_API_URL || 'http://localhost:8000'
      return `Cannot reach API at ${base}. Is the backend running?`
    }
    const status = err.response.status
    const detail = (err.response.data as { detail?: string })?.detail
    if (status === 401) return detail || 'Invalid client credentials. Check VITE_CLIENT_ID and VITE_CLIENT_SECRET in frontend/.env and ensure the client exists (manage_clients create).'
    if (detail) return typeof detail === 'string' ? detail : JSON.stringify(detail)
    return err.message || `Request failed (${status})`
  }
  return err instanceof Error ? err.message : 'Upload failed'
}

export default function UploadPage() {
  const [userId, setUserId] = useState(
    () => import.meta.env.VITE_CLIENT_ID || '',
  )
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)

  const handleUpload = async () => {
    if (!selectedFile) {
      toast.error('Please select a file first')
      return
    }
    if (!userId.trim()) {
      toast.error('Please enter a User ID')
      return
    }

    setIsUploading(true)
    try {
      const uploadResult = await uploadDocument(selectedFile, userId)
      toast.success('File uploaded successfully')

      const processResult = await processDocument(uploadResult.url, userId)
      setJobId(processResult.job_id)
      toast.success('Processing started')
    } catch (err: unknown) {
      toast.error(getErrorMessage(err))
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-4 py-12">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Upload Document</h1>
          <Link
            to="/documents"
            className="text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            View Documents
          </Link>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6">
          {/* User ID input */}
          <div>
            <label htmlFor="userId" className="block text-sm font-medium text-gray-700 mb-1">
              User ID
            </label>
            <input
              id="userId"
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="Enter your user ID"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isUploading || !!jobId}
            />
          </div>

          {/* Dropzone */}
          <UploadDropzone
            onFileSelected={setSelectedFile}
            selectedFile={selectedFile}
            disabled={isUploading || !!jobId}
          />

          {/* Upload button */}
          {!jobId && (
            <button
              onClick={handleUpload}
              disabled={!selectedFile || isUploading || !userId.trim()}
              className="w-full py-2.5 px-4 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isUploading ? (
                <span className="inline-flex items-center">
                  <svg
                    className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  Uploading...
                </span>
              ) : (
                'Upload & Process'
              )}
            </button>
          )}

          {/* Job Status */}
          {jobId && (
            <div className="pt-2">
              <JobStatusTracker jobId={jobId} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
