import { useEffect, useRef } from 'react'

export default function useUnsavedChanges(hasUnsavedChanges: boolean) {
  const unsavedRef = useRef(hasUnsavedChanges)
  unsavedRef.current = hasUnsavedChanges

  // Warn on browser tab close / refresh
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (unsavedRef.current) {
        e.preventDefault()
      }
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [])
}
