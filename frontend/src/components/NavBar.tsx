import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { useCart } from '../cart'

const mainLinks = [
  { to: '/', label: 'Home', end: true },
  { to: '/products', label: 'Products' },
  { to: '/about', label: 'About Us' },
]

const linkClass = ({ isActive }: { isActive: boolean }) => `nav-link${isActive ? ' active' : ''}`

export default function NavBar() {
  const { user, logout } = useAuth()
  const cart = useCart()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/')
  }

  return (
    <header className="nav">
      <Link to="/" className="brand">
        Campus <span>Customs</span>
      </Link>
      <nav>
        {mainLinks.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end} className={linkClass}>
            {l.label}
          </NavLink>
        ))}
        <button className="nav-link cart-btn" onClick={cart.open} aria-label={`Cart, ${cart.count} items`}>
          🛍 Cart
          {cart.count > 0 && (
            <span key={cart.count} className="cart-badge">
              {cart.count}
            </span>
          )}
        </button>
        {user ? (
          <>
            <span className="nav-user">Hi, {user.first_name}</span>
            <button className="nav-link cta" onClick={handleLogout}>
              Log Out
            </button>
          </>
        ) : (
          <>
            <NavLink to="/login" className={linkClass}>
              Log In
            </NavLink>
            <NavLink to="/signup" className={(s) => `${linkClass(s)} cta`}>
              Create Account
            </NavLink>
          </>
        )}
      </nav>
    </header>
  )
}
