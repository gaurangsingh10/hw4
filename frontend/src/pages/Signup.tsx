import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

const MIN_PASSWORD_LENGTH = 8

export default function Signup() {
  const { user, signup } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    password: '',
    confirm_password: '',
  })
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (user) return <Navigate to="/" replace />

  const update = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }))

  const mismatch = form.confirm_password.length > 0 && form.password !== form.confirm_password

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (form.password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`)
      return
    }
    if (form.password !== form.confirm_password) {
      setError('Passwords do not match.')
      return
    }
    setSubmitting(true)
    try {
      await signup(form)
      navigate('/')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="auth" onSubmit={handleSubmit}>
      <h1>Join Campus Customs</h1>
      <div className="row">
        <label>
          First name
          <input required autoComplete="given-name" value={form.first_name} onChange={update('first_name')} />
        </label>
        <label>
          Last name
          <input required autoComplete="family-name" value={form.last_name} onChange={update('last_name')} />
        </label>
      </div>
      <label>
        Email
        <input type="email" required autoComplete="email" value={form.email} onChange={update('email')} />
      </label>
      <label>
        Password
        <input
          type="password"
          required
          minLength={MIN_PASSWORD_LENGTH}
          autoComplete="new-password"
          value={form.password}
          onChange={update('password')}
        />
        <span className="hint">At least {MIN_PASSWORD_LENGTH} characters.</span>
      </label>
      <label>
        Confirm password
        <input
          type="password"
          required
          autoComplete="new-password"
          value={form.confirm_password}
          onChange={update('confirm_password')}
          aria-invalid={mismatch}
        />
        {mismatch && <span className="hint error">Passwords don't match yet.</span>}
      </label>
      {error && <p className="notice error" role="alert">{error}</p>}
      <button className="btn" type="submit" disabled={submitting}>
        {submitting ? 'Creating account…' : 'Create Account'}
      </button>
      <p className="muted">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </form>
  )
}
