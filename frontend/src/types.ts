export interface SizeStock {
  size: string
  quantity: number
}

export interface Product {
  product_id: string
  name: string
  garment_type: string
  category: string
  description: string
  colors: string[]
  search_tags: string[]
  image_url: string
  price: number
  total_stock: number
  inventory: SizeStock[]
}

export interface CartAction {
  type: 'add'
  product: Product
  size: string
  quantity: number
}

export interface FactCheck {
  prices_checked: number
  stock_checked: number
  corrected: boolean
}

export interface ChatReply {
  reply: string
  products: Product[]
  showcase: ShowcaseResult | null
  cart_actions: CartAction[]
  fact_check: FactCheck | null
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  products?: Product[]
  showcase?: ShowcaseResult | null
  cart_actions?: CartAction[]
  fact_check?: FactCheck | null
  created_at?: string // set on messages restored from the server
  local?: boolean // greetings generated in the browser; never sent as history
}

export interface PageContext {
  path: string
  product_id: string | null
  showcase_title: string | null
}

export interface User {
  id: number
  first_name: string
  last_name: string
  name: string
  email: string
}

export interface SearchFilters {
  query: string | null
  category: string | null
  color: string | null
  max_price: number | null
  size: string | null
}

export interface ShowcaseResult {
  title: string
  filters: SearchFilters
  total_matches: number
  products: Product[]
}
