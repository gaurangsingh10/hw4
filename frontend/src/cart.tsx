import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { getProducts } from './api'
import type { Product } from './types'

// The cart is kept in localStorage so it survives refreshes and visits, for guests and
// logged-in shoppers alike. Prices/stock are refreshed from the API on load.
const STORAGE_KEY = 'cc_cart'

export interface CartItem {
  product_id: string
  size: string
  quantity: number
  name: string
  price: number
  image_url: string
  stock: number // units available in this size (caps the quantity stepper)
}

interface CartState {
  items: CartItem[]
  count: number
  subtotal: number
  isOpen: boolean
  lastAdded: string | null // key of the most recently added line, for the highlight
  add: (product: Product, size: string, quantity?: number, openDrawer?: boolean) => { ok: boolean; message: string }
  setQuantity: (key: string, quantity: number) => void
  remove: (key: string) => void
  clear: () => void
  open: () => void
  close: () => void
}

// eslint-disable-next-line react-refresh/only-export-components
export const lineKey = (i: { product_id: string; size: string }) => `${i.product_id}::${i.size}`

const CartContext = createContext<CartState | null>(null)

function load(): CartItem[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') as CartItem[]
  } catch {
    return []
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>(load)
  const [isOpen, setOpen] = useState(false)
  const [lastAdded, setLastAdded] = useState<string | null>(null)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
  }, [items])

  // Re-price and re-cap every line from the live catalogue once per page load.
  useEffect(() => {
    getProducts()
      .then((products) => {
        const byId = new Map(products.map((p) => [p.product_id, p]))
        setItems((current) =>
          current.flatMap((i) => {
            const p = byId.get(i.product_id)
            if (!p) return []
            const stock = p.inventory.find((s) => s.size === i.size)?.quantity ?? 0
            return [{ ...i, name: p.name, price: p.price, image_url: p.image_url, stock, quantity: Math.min(i.quantity, Math.max(stock, 1)) }]
          }),
        )
      })
      .catch(() => {})
  }, [])

  function add(product: Product, size: string, quantity = 1, openDrawer = true) {
    const stock = product.inventory.find((s) => s.size === size)?.quantity ?? 0
    const key = lineKey({ product_id: product.product_id, size })
    const inCart = items.find((i) => lineKey(i) === key)?.quantity ?? 0
    if (stock === 0) return { ok: false, message: `${size} is sold out.` }
    if (inCart + quantity > stock) return { ok: false, message: `Only ${stock} in ${size}; you already have ${inCart} in your cart.` }
    setItems((current) => {
      const existing = current.find((i) => lineKey(i) === key)
      if (existing) return current.map((i) => (lineKey(i) === key ? { ...i, quantity: i.quantity + quantity, stock } : i))
      return [
        ...current,
        { product_id: product.product_id, size, quantity, name: product.name, price: product.price, image_url: product.image_url, stock },
      ]
    })
    setLastAdded(key)
    if (openDrawer) setOpen(true)
    return { ok: true, message: `Added ${quantity} × ${product.name} (${size})` }
  }

  const value: CartState = {
    items,
    count: items.reduce((n, i) => n + i.quantity, 0),
    subtotal: Math.round(items.reduce((t, i) => t + i.price * i.quantity, 0) * 100) / 100,
    isOpen,
    lastAdded,
    add,
    setQuantity: (key, quantity) =>
      setItems((cur) => cur.map((i) => (lineKey(i) === key ? { ...i, quantity: Math.max(1, Math.min(quantity, i.stock)) } : i))),
    remove: (key) => setItems((cur) => cur.filter((i) => lineKey(i) !== key)),
    clear: () => setItems([]),
    open: () => setOpen(true),
    close: () => setOpen(false),
  }

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useCart() {
  const ctx = useContext(CartContext)
  if (!ctx) throw new Error('useCart must be used inside <CartProvider>')
  return ctx
}
