import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { formatPrice, getProduct } from '../api'
import type { Product } from '../types'
import { lineKey, useCart } from '../cart'

// Keyed by id so state resets cleanly when navigating between products.
export default function ProductDetail() {
  const { productId = '' } = useParams()
  return <ProductView key={productId} productId={productId} />
}

function ProductView({ productId }: { productId: string }) {
  const [product, setProduct] = useState<Product | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [size, setSize] = useState<string | null>(null)
  const [qty, setQty] = useState(1)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const cart = useCart()

  useEffect(() => {
    getProduct(productId)
      .then(setProduct)
      .catch((e: Error) => setError(e.message))
  }, [productId])

  if (error) return <p className="status error">We couldn't find that product ({error}).</p>
  if (!product) return <p className="status">Loading…</p>

  const selected = product.inventory?.find((s) => s.size === size)
  const inCart = selected ? (cart.items.find((i) => lineKey(i) === lineKey({ product_id: product.product_id, size: selected.size }))?.quantity ?? 0) : 0
  const canAdd = selected ? Math.max(selected.quantity - inCart, 0) : 0

  function handleAdd() {
    if (!selected || !product) return
    const res = cart.add(product, selected.size, qty)
    setMessage({ ok: res.ok, text: res.message })
    if (res.ok) setQty(1)
  }

  return (
    <>
      <Link to="/products" className="back">← Back to products</Link>
      <div className="detail">
        <div className="detail-img">
          <img src={product.image_url} alt={product.name} />
        </div>
        <div className="detail-info">
          <p className="eyebrow">{product.category}</p>
          <h1>{product.name}</h1>
          <p className="price big">{formatPrice(product.price)}</p>
          <p>{product.description}</p>

          <h3>Colors</h3>
          <p className="colors">{product.colors.join(' · ')}</p>

          <h3>Sizes</h3>
          <div className="sizes">
            {product.inventory?.map((s) => (
              <button
                key={s.size}
                className={`size${s.size === size ? ' active' : ''}`}
                disabled={s.quantity === 0}
                onClick={() => {
                  setSize(s.size)
                  setQty(1)
                  setMessage(null)
                }}
                title={s.quantity === 0 ? 'Out of stock' : `${s.quantity} in stock`}
              >
                {s.size}
              </button>
            ))}
          </div>
          <p className="stock">
            {selected
              ? `${selected.quantity} left in ${selected.size}`
              : `${product.total_stock} in stock across all sizes`}
          </p>
          <div className="buy-row">
            {selected && canAdd > 0 && (
              <div className="stepper big" aria-label="Quantity">
                <button onClick={() => setQty((q) => Math.max(1, q - 1))} disabled={qty <= 1} aria-label="Decrease">−</button>
                <span>{qty}</span>
                <button onClick={() => setQty((q) => Math.min(canAdd, q + 1))} disabled={qty >= canAdd} aria-label="Increase">+</button>
              </div>
            )}
            <button className="btn add-btn" disabled={!selected || canAdd === 0} onClick={handleAdd}>
              {!selected ? 'Select a size' : canAdd === 0 ? 'All in your cart' : `Add to cart · ${formatPrice(product.price * qty)}`}
            </button>
          </div>
          {inCart > 0 && <p className="stock">{inCart} in your cart already.</p>}
          {message && <p className={`notice${message.ok ? ' ok' : ' error'}`}>{message.text}</p>}
        </div>
      </div>
    </>
  )
}
