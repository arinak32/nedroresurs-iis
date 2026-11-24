import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { Logo } from '../components/Layout'

export default function Login() {
  const { user, login } = useAuth()
  const [l, setL] = useState('')
  const [p, setP] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  if (user) return <Navigate to={user.role === 'driver' ? '/driver' : '/'} replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(''); setBusy(true)
    try { await login(l, p) } catch (x) { setErr((x as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="login">
      <div className="promo">
        <div className="circle" style={{ width: 520, height: 520, right: -170, top: -90, opacity: .18 }} />
        <div className="circle" style={{ width: 360, height: 360, right: -110, top: 120, opacity: .1 }} />
        <Logo />
        <div style={{ position: 'relative' }}>
          <h1>Добыча, продажа и доставка песка — в одной системе</h1>
          <p>Заказы, рейсы, остатки на площадках, документы и прогноз спроса для ООО «Недроресурс»</p>
        </div>
        <div className="stats">
          <div><b>4</b>карьера</div><div><b>8</b>самосвалов</div><div><b>60 000 м³</b>вместимость площадок</div>
        </div>
      </div>
      <div className="form">
        <form className="box card" style={{ padding: 40 }} onSubmit={submit}>
          <img src="/logo.svg" width={40} height={40} alt="" />
          <h1>Вход в систему</h1>
          <div className="muted">Используйте логин, выданный администратором</div>
          <div className="field"><label>Логин</label><input className="input" value={l} onChange={e => setL(e.target.value)} autoFocus autoComplete="username" /></div>
          <div className="field"><label>Пароль</label><input className="input" type="password" value={p} onChange={e => setP(e.target.value)} autoComplete="current-password" /></div>
          {err && <div className="alert err">{err}</div>}
          <button className="btn btn-main" disabled={busy || !l || !p}>{busy ? 'Входим…' : 'Войти →'}</button>
          <div className="alert" style={{ background: 'var(--page)', color: 'var(--text-2)', fontWeight: 500 }}>
            Разделы меню зависят от роли: директор, менеджер, бухгалтер, юрист, механик или водитель
          </div>
        </form>
      </div>
    </div>
  )
}
