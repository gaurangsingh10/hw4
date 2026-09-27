import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { formatPrice } from '../api'
import { lineKey, useCart } from '../cart'

export default function CartDrawer() {
  const { items, count, subtotal, isOpen, close, setQuantity, remove, lastAdded } = useCart()
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && close()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isOpen, close])

  return (
    <div className={`cart-root${isOpen ? ' open' : ''}`} aria-hidden={!isOpen}>
      <div className="cart-backdrop" onClick={close} />
      <aside className="cart-drawer" role="dialog" aria-label="Shopping cart">
        <header className="cart-head">
          <h2>Your cart {count > 0 && <span className="cart-count">{count}</span>}</h2>
          <button className="cart-x" onClick={close} aria-label="Close cart">×</button>
        </header>

        {items.length === 0 ? (
          <div className="cart-empty">
            <div className="cart-empty-icon">🛍</div>
            <p>Your cart is empty.</p>
            <Link to="/products" className="btn" onClick={close}>Browse products</Link>
            <p className="muted small">Tip: ask the assistant to “add the navy hoodie in M to my cart”.</p>
          </div>
        ) : (
          <>
            <ul className="cart-lines">
              {items.map((i) => {
                const key = lineKey(i)
                return (
                  <li key={key} className={key === lastAdded ? 'flash' : ''}>
                    <Link to={`/products/${i.product_id}`} onClick={close} className="cart-thumb">
                      <img src={i.image_url} alt="" />
                    </Link>
                    <div className="cart-info">
                      <Link to={`/products/${i.product_id}`} onClick={close}><strong>{i.name}</strong></Link>
                      <span className="muted small">Size {i.size} · {formatPrice(i.price)} each</span>
                      <div className="stepper" aria-label={`Quantity for ${i.name}`}>
                        <button onClick={() => setQuantity(key, i.quantity - 1)} disabled={i.quantity <= 1} aria-label="Decrease">−</button>
                        <span>{i.quantity}</span>
                        <button onClick={() => setQuantity(key, i.quantity + 1)} disabled={i.quantity >= i.stock} aria-label="Increase">+</button>
                        {i.quantity >= i.stock && <span className="muted small">max in stock</span>}
                      </div>
                    </div>
                    <div className="cart-right">
                      <strong>{formatPrice(i.price * i.quantity)}</strong>
                      <button className="link-btn" onClick={() => remove(key)}>Remove</button>
                    </div>
                  </li>
                )
              })}
            </ul>
            <footer className="cart-foot">
              <div className="cart-total"><span>Subtotal</span><strong>{formatPrice(subtotal)}</strong></div>
              <button className="btn wide" onClick={() => setNotice('Checkout is coming soon. Your cart is saved on this device.')}>
                Checkout
              </button>
              {notice && <p className="notice">{notice}</p>}
            </footer>
          </>
        )}
      </aside>
    </div>
  )
}
