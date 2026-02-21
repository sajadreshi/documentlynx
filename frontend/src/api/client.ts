import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
});

api.interceptors.request.use((config) => {
  config.headers['X-Client-Id'] = import.meta.env.VITE_CLIENT_ID || '';
  config.headers['X-Client-Secret'] = import.meta.env.VITE_CLIENT_SECRET || '';
  return config;
});

export default api;
