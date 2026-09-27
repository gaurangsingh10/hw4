import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { formatPrice } from '../api'
import type { Product } from '../types'

const LOW_STOCK_UNITS = 3

function stockBadge(product: Product): { label: string; tone: 'low' | 'out' } | null {
  if (product.total_stock === 0) return { label: 'Sold out', tone: 'out' }
  const low = product.inventory.filter((s) => s.quantity > 0 && s.quantity <= LOW_STOCK_UNITS)
  if (low.length > 0) return { label: `Only a few left in ${low.map((s) => s.size).join(', ')}`, tone: 'low' }
  return null
}

interface Props {
  product: Product
  /** Position in a grid; staggers the entrance animation when set. */
  index?: number
}

// Used on the Products page, Home, and the chat showcase panel, so every card
// opens the same /products/:id detail page.
export default function ProductCard({ product, index }: Props) {
  const badge = stockBadge(product)
  const style = index === undefined ? undefined : ({ '--i': index } as CSSProperties)

  return (
    <Link
      to={`/products/${product.product_id}`}
      className={`card${index === undefined ? '' : ' animate-in'}`}
      style={style}
    >
      <div className="card-img">
        <img src={product.image_url} alt={product.name} loading="lazy" />
        <span className="card-cat">{product.category}</span>
        {badge && <span className={`card-badge ${badge.tone}`}>{badge.label}</span>}
      </div>
      <div className="card-body">
        <h3>{product.name}</h3>
        <p className="price">{formatPrice(product.price)}</p>
        <p className="card-desc">{product.description}</p>
      </div>
    </Link>
  )
}
