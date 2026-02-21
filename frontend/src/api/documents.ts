import api from './client';

export interface UploadResponse {
  success: boolean;
  message: string;
  url: string;
  user_id: string;
  filename: string;
}

export interface ProcessDocResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface JobStatus {
  job_id: string;
  user_id: string;
  status: string;
  error_message?: string;
  document_id?: string;
  question_count: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface Document {
  id: string;
  filename: string;
  status: string;
  question_count: number;
  user_id: string;
  file_type?: string;
  source_url?: string;
  public_markdown?: string;
  created_at: string;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
  page: number;
  page_size: number;
}

export interface QuestionListItem {
  id: string;
  question_number?: number;
  question_type?: string;
  topic?: string;
  difficulty?: string;
  preview: string;
}

export interface Question {
  id: string;
  document_id: string;
  user_id: string;
  question_number?: number;
  question_text: string;
  question_type?: string;
  options?: Record<string, string>;
  correct_answer?: string;
  difficulty?: string;
  topic?: string;
  subtopic?: string;
  grade_level?: string;
  cognitive_level?: string;
  tags?: string[];
  is_classified: boolean;
  image_urls?: string[];
  created_at?: string;
}

export interface QuestionListResponse {
  questions: QuestionListItem[];
  total: number;
  page: number;
  page_size: number;
}

export async function uploadDocument(file: File, userId: string): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('user_id', userId);
  const { data } = await api.post<UploadResponse>('/documently/api/v1/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function processDocument(documentUrl: string, userId: string): Promise<ProcessDocResponse> {
  const { data } = await api.post<ProcessDocResponse>('/documently/api/v1/process-doc', {
    document_url: documentUrl,
    user_id: userId,
  });
  return data;
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const { data } = await api.get<JobStatus>(`/documently/api/v1/jobs/${jobId}`);
  return data;
}

export async function listDocuments(
  userId: string,
  page: number = 1,
  pageSize: number = 20,
): Promise<DocumentListResponse> {
  const { data } = await api.get<DocumentListResponse>('/documently/api/v1/documents', {
    params: { user_id: userId, page, page_size: pageSize },
  });
  return data;
}

export async function getDocument(documentId: string): Promise<Document> {
  const { data } = await api.get<Document>(`/documently/api/v1/documents/${documentId}`);
  return data;
}

export async function listQuestions(
  documentId: string,
  page: number = 1,
  pageSize: number = 50,
): Promise<QuestionListResponse> {
  const { data } = await api.get<QuestionListResponse>(
    `/documently/api/v1/documents/${documentId}/questions`,
    { params: { page, page_size: pageSize } },
  );
  return data;
}

export async function getQuestion(documentId: string, questionId: string): Promise<Question> {
  const { data } = await api.get<Question>(
    `/documently/api/v1/documents/${documentId}/questions/${questionId}`,
  );
  return data;
}

export async function updateQuestion(
  documentId: string,
  questionId: string,
  questionText: string,
  reEmbed: boolean = false,
  options?: Record<string, string>,
  correctAnswer?: string,
): Promise<Question> {
  const body: Record<string, unknown> = {
    question_text: questionText,
    re_embed: reEmbed,
  };
  if (options !== undefined) body.options = options;
  if (correctAnswer !== undefined) body.correct_answer = correctAnswer;
  const { data } = await api.put<Question>(
    `/documently/api/v1/documents/${documentId}/questions/${questionId}`,
    body,
  );
  return data;
}
