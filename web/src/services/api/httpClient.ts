import axios, { type InternalAxiosRequestConfig } from 'axios'
import { isEmbedded, requestFbsToken } from '@/services/auth/fbsBridge'

const httpClient = axios.create({
  baseURL: '/api'
})

httpClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Embedded, a rejected token is renewed through the Feedbacksystem and the request sent once more.
httpClient.interceptors.response.use(undefined, async (error) => {
  const config = error.config as (InternalAxiosRequestConfig & { fbsRetried?: boolean }) | undefined
  if (isEmbedded && error.response?.status === 401 && config && !config.fbsRetried) {
    config.fbsRetried = true
    if (await requestFbsToken()) return httpClient(config)
  }
  return Promise.reject(error)
})

export default httpClient
