import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { getQuestion, updateQuestion, listQuestions } from '../api/documents'
import QuestionNav from '../components/QuestionNav'
import MarkdownEditor from '../components/MarkdownEditor'
import MarkdownPreview from '../components/MarkdownPreview'
import useUnsavedChanges from '../hooks/useUnsavedChanges'

export default function QuestionEditPage() {
  const { id: documentId, qid: questionId } = useParams<{ id: string; qid: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [editedText, setEditedText] = useState('')
  const [originalText, setOriginalText] = useState('')

  const hasUnsavedChanges = editedText !== originalText

  useUnsavedChanges(hasUnsavedChanges)

  // Fetch the current question
  const { data: question, isLoading: questionLoading } = useQuery({
    queryKey: ['question', documentId, questionId],
    queryFn: () => getQuestion(documentId!, questionId!),
    enabled: !!documentId && !!questionId,
  })

  // Fetch all questions for navigation
  const { data: questionsData } = useQuery({
    queryKey: ['questions', documentId, 1],
    queryFn: () => listQuestions(documentId!, 1, 50),
    enabled: !!documentId,
  })

  // Build the question index list
  const questionIds = useMemo(
    () => questionsData?.questions.map((q) => q.id) ?? [],
    [questionsData],
  )
  const currentIndex = questionIds.indexOf(questionId ?? '')
  const total = questionsData?.total ?? 0

  // Compose full editable text: question + options
  useEffect(() => {
    if (question) {
      let fullText = question.question_text
      if (question.options && Object.keys(question.options).length > 0) {
        fullText += '\n\n---\n\n**Options:**\n'
        for (const [key, value] of Object.entries(question.options)) {
          fullText += `\n- **${key}.** ${value}`
        }
        if (question.correct_answer) {
          fullText += `\n\n**Correct Answer:** ${question.correct_answer}`
        }
      }
      setEditedText(fullText)
      setOriginalText(fullText)
    }
  }, [question])

  // Parse the combined markdown back into question_text, options, correct_answer
  function parseEditedText(text: string) {
    const parts = text.split(/\n---\n/)
    const questionText = parts[0].trim()
    const options: Record<string, string> = {}
    let correctAnswer: string | undefined

    if (parts.length > 1) {
      const optionsSection = parts.slice(1).join('\n---\n')
      // Match lines like: - **A.** some text
      const optionRegex = /- \*\*([A-Z])\.\*\*\s*(.+)/g
      let match
      while ((match = optionRegex.exec(optionsSection)) !== null) {
        options[match[1]] = match[2].trim()
      }
      // Match: **Correct Answer:** X
      const answerMatch = optionsSection.match(/\*\*Correct Answer:\*\*\s*(.+)/)
      if (answerMatch) {
        correctAnswer = answerMatch[1].trim()
      }
    }

    return { questionText, options, correctAnswer }
  }

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: () => {
      const { questionText, options, correctAnswer } = parseEditedText(editedText)
      const hasOptions = Object.keys(options).length > 0
      return updateQuestion(
        documentId!, questionId!, questionText, false,
        hasOptions ? options : undefined,
        correctAnswer,
      )
    },
    onSuccess: () => {
      setOriginalText(editedText)
      queryClient.invalidateQueries({ queryKey: ['question', documentId, questionId] })
      queryClient.invalidateQueries({ queryKey: ['questions', documentId] })
      toast.success('Question saved')
    },
    onError: (err: Error) => {
      toast.error(`Save failed: ${err.message}`)
    },
  })

  const handleSave = useCallback(() => {
    if (!hasUnsavedChanges) return
    saveMutation.mutate()
  }, [hasUnsavedChanges, saveMutation])

  // Ctrl+S / Cmd+S shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        handleSave()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [handleSave])

  const handlePrev = useCallback(() => {
    if (currentIndex > 0) {
      navigate(`/documents/${documentId}/questions/${questionIds[currentIndex - 1]}`)
    }
  }, [currentIndex, documentId, questionIds, navigate])

  const handleNext = useCallback(() => {
    if (currentIndex < questionIds.length - 1) {
      navigate(`/documents/${documentId}/questions/${questionIds[currentIndex + 1]}`)
    }
  }, [currentIndex, documentId, questionIds, navigate])

  if (questionLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Loading question...</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Top bar */}
      <div className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(`/documents/${documentId}`)}
              className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
            >
              <svg className="mr-1.5 w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
              Back
            </button>

            {question && (
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <span className="inline-flex text-xs font-medium px-2 py-0.5 rounded bg-gray-100 text-gray-700">
                  {question.question_type}
                </span>
                <span>{question.topic}</span>
                <span
                  className={`inline-flex text-xs font-medium px-2 py-0.5 rounded ${
                    question.difficulty === 'hard'
                      ? 'bg-red-100 text-red-700'
                      : question.difficulty === 'medium'
                        ? 'bg-yellow-100 text-yellow-700'
                        : 'bg-green-100 text-green-700'
                  }`}
                >
                  {question.difficulty}
                </span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            {/* Unsaved indicator */}
            {hasUnsavedChanges && (
              <span className="flex items-center gap-1.5 text-xs text-amber-600">
                <span className="w-2 h-2 rounded-full bg-amber-500" />
                Unsaved
              </span>
            )}

            <button
              onClick={handleSave}
              disabled={!hasUnsavedChanges || saveMutation.isPending}
              className="px-4 py-1.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saveMutation.isPending ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      </div>

      {/* Question navigation */}
      {total > 0 && (
        <div className="bg-white border-b border-gray-200 px-4 py-2">
          <div className="max-w-7xl mx-auto">
            <QuestionNav
              currentIndex={currentIndex}
              total={total}
              onPrev={handlePrev}
              onNext={handleNext}
            />
          </div>
        </div>
      )}

      {/* Editor + Preview split pane */}
      <div className="flex-1 flex flex-col md:flex-row min-h-0">
        {/* Editor */}
        <div className="flex flex-col min-h-[300px] md:min-h-0 md:w-1/2 md:min-w-0">
          <div className="px-4 py-2 bg-gray-100 border-b border-gray-200">
            <span className="text-xs font-medium text-gray-600 uppercase tracking-wider">
              Editor
            </span>
          </div>
          <div className="flex-1 overflow-hidden">
            <MarkdownEditor value={editedText} onChange={setEditedText} />
          </div>
        </div>

        {/* Divider */}
        <div className="hidden md:block w-px bg-gray-200 shrink-0" />
        <div className="md:hidden h-px bg-gray-200" />

        {/* Preview */}
        <div className="flex flex-col min-h-[300px] md:min-h-0 md:w-1/2 md:min-w-0">
          <div className="px-4 py-2 bg-gray-100 border-b border-gray-200">
            <span className="text-xs font-medium text-gray-600 uppercase tracking-wider">
              Preview
            </span>
          </div>
          <div className="flex-1 overflow-auto bg-white">
            <MarkdownPreview content={editedText} />
          </div>
        </div>
      </div>
    </div>
  )
}
