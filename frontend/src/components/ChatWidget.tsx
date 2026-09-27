import { useEffect, useRef, useState, type FormEvent } from 'react'
import Markdown from 'react-markdown'
import { Link, useLocation, useMatch, useNavigate } from 'react-router-dom'
import { formatPrice, getChatHistory, getProduct, sendChat } from '../api'
import { useAuth } from '../auth'
import { useShowcase } from '../showcase'
import { useCart } from '../cart'
import type { ChatMessage, PageContext, Product, ShowcaseResult } from '../types'

const MAX_GUEST_HISTORY = 20
// Guests have no server-side history, so keep their chat for this browser tab only.
const GUEST_CHAT_KEY = 'cc_guest_chat'

function loadGuestChat(): ChatMessage[] | null {
  try {
    const raw = sessionStorage.getItem(GUEST_CHAT_KEY)
    return raw ? (JSON.parse(raw) as ChatMessage[]) : null
  } catch {
    return null
  }
}

function greeting(firstName?: string, returning = false): ChatMessage {
  const content = returning
    ? `Welcome back, ${firstName}! I've kept our last conversation above. What can I find for you today? 💙`
    : `Hey${firstName ? ` ${firstName}` : ''}! I'm the Campus Customs assistant. Ask me about hoodies, sizes, or what's in stock. 💙`
  return { role: 'assistant', content, local: true }
}

function ChatProductCard({ product }: { product: Product }) {
  return (
    <Link to={`/products/${product.product_id}`} className="chat-card">
      <img src={product.image_url} alt="" />
      <span>
        <strong>{product.name}</strong>
        <span className="price">{formatPrice(product.price)}</span>
      </span>
    </Link>
  )
}

export default function ChatWidget() {
  const { user, loading } = useAuth()
  const { showcase: onScreen, show } = useShowcase()
  const cart = useCart()
  const navigate = useNavigate()
  const location = useLocation()
  const detail = useMatch('/products/:productId')
  const productId = detail?.params.productId ?? null

  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([greeting()])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [viewing, setViewing] = useState<{ id: string; name: string } | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  // Swap conversations when the shopper logs in or out.
  useEffect(() => {
    if (loading) return
    let cancelled = false
    const reset = user
      ? getChatHistory()
          .then((h) => [...h, greeting(user.first_name, h.length > 0)])
          .catch(() => [greeting(user.first_name)])
      : Promise.resolve(loadGuestChat() ?? [greeting()])
    reset.then((m) => !cancelled && setMessages(m))
    return () => {
      cancelled = true
    }
  }, [user, loading])

  // Jump straight to the latest message when the panel opens or history loads;
  // glide only for messages arriving during the conversation.
  const lastCount = useRef(0)
  useEffect(() => {
    const jump = messages.length - lastCount.current > 2
    lastCount.current = messages.length
    endRef.current?.scrollIntoView({ behavior: jump ? 'auto' : 'smooth' })
  }, [messages, sending])
  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ behavior: 'auto' })
  }, [open])

  useEffect(() => {
    if (loading) return
    if (user) sessionStorage.removeItem(GUEST_CHAT_KEY)
    else sessionStorage.setItem(GUEST_CHAT_KEY, JSON.stringify(messages.slice(-MAX_GUEST_HISTORY - 1)))
  }, [messages, user, loading])

  // Other parts of the site can open the chat with a suggested message (e.g. Products empty state).
  useEffect(() => {
    const onOpen = (e: Event) => {
      setOpen(true)
      const text = (e as CustomEvent<string>).detail
      if (text) setInput(text)
    }
    window.addEventListener('cc:open-chat', onOpen)
    return () => window.removeEventListener('cc:open-chat', onOpen)
  }, [])

  // Name of the product on screen, for the "Viewing" chip in the chat header.
  useEffect(() => {
    if (!productId) return
    let cancelled = false
    getProduct(productId)
      .then((p) => !cancelled && setViewing({ id: p.product_id, name: p.name }))
      .catch(() => !cancelled && setViewing(null))
    return () => {
      cancelled = true
    }
  }, [productId])
  const viewingName = viewing && viewing.id === productId ? viewing.name : null

  function pageContext(): PageContext {
    return {
      path: location.pathname,
      product_id: productId,
      showcase_title: !productId && onScreen ? onScreen.title : null,
    }
  }

  function openShowcase(result: ShowcaseResult) {
    show(result)
    // The panel is hidden on detail pages, so hop to Products first.
    if (productId) navigate('/products')
    setTimeout(() => document.querySelector('.showcase')?.scrollIntoView({ behavior: 'smooth' }), 50)
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const text = input.trim()
    if (!text || sending) return
    const history = messages
      .filter((m) => !m.local)
      .slice(-MAX_GUEST_HISTORY)
      .map(({ role, content }) => ({ role, content }))
    setInput('')
    setMessages((m) => [...m, { role: 'user', content: text }])
    setSending(true)
    try {
      const cartLines = cart.items.map(({ product_id, size, quantity }) => ({ product_id, size, quantity }))
      const { reply, products, showcase, cart_actions, fact_check } = await sendChat(text, history, pageContext(), cartLines)
      // Items the assistant added (already stock-checked server-side) go into the real cart.
      for (const a of cart_actions) cart.add(a.product, a.size, a.quantity, false)
      // Search results go onto the page; the chat just gets a pointer to them.
      if (showcase) show(showcase)
      setMessages((m) => [...m, { role: 'assistant', content: reply, products, showcase, cart_actions, fact_check }])
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: (err as Error).message || "Sorry, I couldn't reach the server.", local: true },
      ])
    } finally {
      setSending(false)
    }
  }

  const restoredCount = messages.filter((m) => m.created_at).length

  return (
    <div className="chat">
      {open && (
        <section className="chat-panel" aria-label="Chat with Campus Customs">
          <header className="chat-header">
            <div>
              <strong>Campus Customs Assistant</strong>
              {viewingName && (
                <span className="chat-context" title="The assistant knows which product you're looking at">
                  👀 Viewing: {viewingName}
                </span>
              )}
            </div>
            <button onClick={() => setOpen(false)} aria-label="Close chat">
              ×
            </button>
          </header>
          <div className="chat-messages">
            {messages.map((m, i) => (
              <div key={i} className="msg-wrap">
                {i === 0 && m.created_at && <div className="chat-divider">Earlier conversation</div>}
                {i === restoredCount && restoredCount > 0 && <div className="chat-divider">This visit</div>}
                <div className={`msg ${m.role}`}>
                  <div className={`bubble ${m.role}`}>
                    {m.role === 'assistant' ? <Markdown>{m.content}</Markdown> : m.content}
                  </div>
                  {m.fact_check && (
                    <span
                      className={`fact-badge${m.fact_check.corrected ? ' corrected' : ''}`}
                      title={`${m.fact_check.prices_checked} price(s) and ${m.fact_check.stock_checked} stock number(s) matched the live database`}
                    >
                      ✓ Prices & stock checked against live inventory{m.fact_check.corrected ? ' (auto-corrected)' : ''}
                    </span>
                  )}
                  {m.cart_actions && m.cart_actions.length > 0 && (
                    <button className="chat-cart-link" onClick={cart.open}>
                      🛍 Added {m.cart_actions.map((a) => `${a.quantity} × ${a.product.name} (${a.size})`).join(', ')} · View cart
                    </button>
                  )}
                  {m.showcase && (
                    <button className="chat-showcase-link" onClick={() => openShowcase(m.showcase!)}>
                      ✦ {m.showcase.total_matches} {m.showcase.title} on the page ↑
                    </button>
                  )}
                  {m.products && m.products.length > 0 && (
                    <div className="chat-cards">
                      {m.products.map((p) => (
                        <ChatProductCard key={p.product_id} product={p} />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {sending && <div className="bubble assistant typing">Thinking…</div>}
            <div ref={endRef} />
          </div>
          <form className="chat-input" onSubmit={handleSubmit}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={viewingName ? 'Ask about this item…' : 'Ask about a product…'}
              aria-label="Chat message"
              maxLength={1000}
            />
            <button type="submit" disabled={sending || !input.trim()}>
              Send
            </button>
          </form>
        </section>
      )}
      <button className="chat-toggle" onClick={() => setOpen((o) => !o)} aria-label="Toggle chat">
        {open ? '×' : '💬'}
      </button>
    </div>
  )
}
