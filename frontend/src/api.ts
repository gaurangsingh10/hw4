import type { ChatMessage, ChatReply, PageContext, Product, User } from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { credentials: 'same-origin', ...init })
  if (!res.ok) {
    // FastAPI puts a human-readable message in `detail`; fall back to the status line.
    const body = await res.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : `${res.status} ${res.statusText}`
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

const postJson = <T>(path: string, data: unknown) =>
  request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })

export const getProducts = () => request<Product[]>('/api/products')

export const getProduct = (id: string) =>
  request<Product>(`/api/products/${encodeURIComponent(id)}`)

// `history` is only used by the server for guests; logged-in history comes from the DB.
// `page` tells the agent what the shopper is looking at ("do you have *this* in pink?").
export const sendChat = (
  message: string,
  history: Pick<ChatMessage, 'role' | 'content'>[],
  page: PageContext,
  cart: { product_id: string; size: string; quantity: number }[],
) => postJson<ChatReply>('/api/chat', { message, history, page, cart })

export const getChatHistory = () => request<ChatMessage[]>('/api/chat/history')

export interface SignupData {
  first_name: string
  last_name: string
  email: string
  password: string
  confirm_password: string
}

export const signup = (data: SignupData) => postJson<User>('/api/auth/signup', data)

export const login = (email: string, password: string) =>
  postJson<User>('/api/auth/login', { email, password })

export const logout = () => postJson<{ ok: boolean }>('/api/auth/logout', {})

export const getMe = () => request<User>('/api/auth/me')

export const formatPrice = (price: number) => `$${price.toFixed(2)}`
