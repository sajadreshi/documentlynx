import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getDocument, listQuestions } from '../api/documents'

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)

  const { data: doc, isLoading: docLoading } = useQuery({
    queryKey: ['document', id],
    queryFn: () => getDocument(id!),
    enabled: !!id,
  })

  const { data: questionsData, isLoading: questionsLoading } = useQuery({
    queryKey: ['questions', id, page],
    queryFn: () => listQuestions(id!, page, 50),
    enabled: !!id,
  })

  const totalPages = questionsData
    ? Math.ceil(questionsData.total / questionsData.page_size)
    : 0

  if (docLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Loading document...</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto px-4 py-12">
        {/* Back button */}
        <Link
          to="/documents"
          className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-6"
        >
          <svg className="mr-1.5 w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Documents
        </Link>

        {/* Document info */}
        {doc && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-xl font-bold text-gray-900">{doc.filename}</h1>
                <div className="mt-2 flex items-center gap-4 text-sm text-gray-500">
                  <span>
                    Status:{' '}
                    <span
                      className={`font-medium ${
                        doc.status === 'completed' || doc.status === 'processed'
                          ? 'text-green-600'
                          : doc.status === 'failed'
                            ? 'text-red-600'
                            : 'text-yellow-600'
                      }`}
                    >
                      {doc.status}
                    </span>
                  </span>
                  <span>Questions: <span className="font-medium">{doc.question_count}</span></span>
                  <span>Created: {new Date(doc.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Questions table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Questions</h2>
          </div>

          {questionsLoading && (
            <div className="text-center py-12 text-gray-500">Loading questions...</div>
          )}

          {questionsData && questionsData.questions.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              No questions generated yet.
            </div>
          )}

          {questionsData && questionsData.questions.length > 0 && (
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-16">
                    #
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Topic
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Difficulty
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Preview
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {questionsData.questions.map((q, index) => (
                  <tr
                    key={q.id}
                    onClick={() => navigate(`/documents/${id}/questions/${q.id}`)}
                    className="hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {(page - 1) * 50 + index + 1}
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex text-xs font-medium px-2 py-0.5 rounded bg-gray-100 text-gray-700">
                        {q.question_type}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-700">
                      {q.topic}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex text-xs font-medium px-2 py-0.5 rounded ${
                          q.difficulty === 'hard'
                            ? 'bg-red-100 text-red-700'
                            : q.difficulty === 'medium'
                              ? 'bg-yellow-100 text-yellow-700'
                              : 'bg-green-100 text-green-700'
                        }`}
                      >
                        {q.difficulty}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500 truncate max-w-xs">
                      {q.preview.slice(0, 80)}
                      {q.preview.length > 80 ? '...' : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-4">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 text-sm font-medium rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="text-sm text-gray-600">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1.5 text-sm font-medium rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
