import { useEffect } from 'react'

interface Props {
  currentIndex: number
  total: number
  onPrev: () => void
  onNext: () => void
}

export default function QuestionNav({ currentIndex, total, onPrev, onNext }: Props) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.altKey && e.key === 'ArrowLeft') {
        e.preventDefault()
        onPrev()
      }
      if (e.altKey && e.key === 'ArrowRight') {
        e.preventDefault()
        onNext()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onPrev, onNext])

  const isFirst = currentIndex <= 0
  const isLast = currentIndex >= total - 1

  return (
    <div className="flex items-center justify-between">
      <button
        onClick={onPrev}
        disabled={isFirst}
        className="inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        <svg className="mr-1.5 w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        Prev
      </button>

      <span className="text-sm text-gray-600">
        Question <span className="font-medium">{currentIndex + 1}</span> of{' '}
        <span className="font-medium">{total}</span>
      </span>

      <button
        onClick={onNext}
        disabled={isLast}
        className="inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        Next
        <svg className="ml-1.5 w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </div>
  )
}
