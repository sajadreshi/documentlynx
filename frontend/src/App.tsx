import { Routes, Route, Navigate } from 'react-router-dom'
import UploadPage from './pages/UploadPage'
import DocumentsPage from './pages/DocumentsPage'
import DocumentDetailPage from './pages/DocumentDetailPage'
import QuestionEditPage from './pages/QuestionEditPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<UploadPage />} />
      <Route path="/documents" element={<DocumentsPage />} />
      <Route path="/documents/:id" element={<DocumentDetailPage />} />
      <Route path="/documents/:id/questions/:qid" element={<QuestionEditPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
