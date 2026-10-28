import type { AxiosResponse } from 'axios'
import httpClient from '@/services/api/httpClient'
import type { FbsTokens, TokenClaims } from '@/services/api/types/auth'

class AuthService {
  validateToken(): Promise<AxiosResponse<boolean>> {
    return httpClient.get('/auth/validate')
  }

  getMe(): Promise<AxiosResponse<TokenClaims>> {
    return httpClient.get('/auth/me')
  }

  exchangeCode(code: string, codeVerifier: string, redirectUri: string): Promise<AxiosResponse<FbsTokens>> {
    return httpClient.post('/auth/token', { code, codeVerifier, redirectUri })
  }

  refreshTokens(refreshToken: string): Promise<AxiosResponse<FbsTokens>> {
    return httpClient.post('/auth/refresh', { refreshToken })
  }
}

export default new AuthService()
