import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api, ApiError, type DriverDay, type Trip } from '../api'
import { useAuth } from '../auth'
import { m3, num } from '../format'

// ── очередь отметок без связи: отметка сохраняется в телефоне и отправляется, когда появится сеть
type Pending = { url: string; body: Record<string, unknown>; tripId: number; kind: 'load' | 'deliver' }
const QKEY = 'nedro_pending'
const readQ = (): Pending[] => { try { return JSON.parse(localStorage.getItem(QKEY) || '[]') } catch { return [] } }
const writeQ = (q: Pending[]) => { try { localStorage.setItem(QKEY, JSON.stringify(q)) } catch { /* память недоступна */ } }
const uid = () => (crypto.randomUUID?.() ?? `${Date.now()}-${Math.random()}`).slice(0, 64)

async function flush(): Promise<boolean> {
  let q = readQ()
  while (q.length) {
    try { await api.post(q[0].url, q[0].body) }
    catch (e) {
      if (e instanceof ApiError) { /* сервер отказал (например, рейс уже закрыт) — отметку не повторяем */ }
      else return false   // нет сети — попробуем позже
    }
    q = q.slice(1); writeQ(q)
  }
  return true
}

export default function Driver() {
  const { logout } = useAuth()
  const qc = useQueryClient()
  const day = useQuery({ queryKey: ['my-trips'], queryFn: () => api.get<DriverDay>('/api/trips/my'), refetchInterval: 60000 })
  const [pending, setPending] = useState<Pending[]>(readQ())
  const [confirm, setConfirm] = useState<Trip | null>(null)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    const sync = async () => { if (readQ().length && await flush()) { setPending([]); qc.invalidateQueries({ queryKey: ['my-trips'] }) } }
    window.addEventListener('online', sync)
    const t = setInterval(sync, 15000)
    sync()
    return () => { window.removeEventListener('online', sync); clearInterval(t) }
  }, [])

  // статус рейса с учётом отметок, которые ещё не дошли до сервера
  const statusOf = (t: Trip) => {
    const p = pending.filter(x => x.tripId === t.id)
    return p.some(x => x.kind === 'deliver') ? 'delivered' : p.some(x => x.kind === 'load') ? 'en_route' : t.status
  }

  const send = async (item: Pending) => {
    setMsg('')
    try {
      await api.post(item.url, item.body)
      qc.invalidateQueries({ queryKey: ['my-trips'] })
      return true
    } catch (e) {
      if (e instanceof ApiError) { setMsg(e.message); return false }
      const q = [...readQ(), item]; writeQ(q); setPending(q)   // нет связи — в очередь
      return true
    }
  }

  const trips = day.data?.trips ?? []
  const current = trips.find(t => !['delivered', 'cancelled'].includes(statusOf(t)))
  const doneCount = trips.filter(t => statusOf(t) === 'delivered').length
  const km = trips.reduce((a, t) => a + Number(t.distance_km ?? 0), 0)

  if (confirm) return <Confirm trip={confirm} onBack={() => setConfirm(null)} next={trips[trips.indexOf(confirm) + 1]}
    onDone={async v => {
      if (await send({ url: `/api/trips/${confirm.id}/deliver`, body: { actual_m3: v, event_id: uid() }, tripId: confirm.id, kind: 'deliver' })) setConfirm(null)
    }} offline={pending.length > 0} msg={msg} />

  return (
    <div className="drv">
      <div className="drv-top">
        <div className="drv-no">{day.data?.vehicle_name?.replace('Самосвал ', '') ?? '—'}</div>
        <div className="grow"><b>{day.data?.driver_name}</b><div className="muted small">{day.data?.vehicle_name} · {day.data?.vehicle_model} 30 м³</div></div>
        <button className="btn btn-text" onClick={logout}>Выйти</button>
      </div>

      {pending.length > 0 && <div className="alert warn">Нет связи: {pending.length} отметк{pending.length === 1 ? 'а сохранена' : 'и сохранены'} в телефоне и отправ{pending.length === 1 ? 'ится' : 'ятся'} автоматически</div>}
      {msg && <div className="alert err">{msg}</div>}

      {trips.length > 0 && (
        <div className="drv-progress">
          <div className="head"><b className="t">Рейс {Math.min(doneCount + 1, trips.length)} из {trips.length} сегодня</b><span>{num(km)} км</span></div>
          <div className="segs">{trips.map(t => <div key={t.id} className={statusOf(t) === 'delivered' ? 'done' : t === current ? 'now' : ''} />)}</div>
        </div>
      )}

      {day.isLoading ? <div className="spinner">Загрузка…</div>
        : !trips.length ? <div className="card">На сегодня рейсов нет. Задания появятся, когда менеджер утвердит план.</div>
          : !current ? <div className="card" style={{ textAlign: 'center' }}><h2>Все рейсы выполнены ✓</h2><div className="muted">Спасибо за смену!</div></div>
            : (() => {
              const st = statusOf(current)
              return <>
                <div className="drv-steps">
                  <span className={st === 'planned' ? 'on' : 'ok'}>{st === 'planned' ? '1 Погрузка' : '✓ Погрузка'}</span>
                  <span className={st === 'en_route' ? 'on' : ''}>2 В пути</span>
                  <span>3 Выгрузка</span>
                </div>
                <div className="card drv-card">
                  <div className="drv-row"><div className="ico">К</div><div><div className="muted small">{st === 'planned' ? 'Погрузка на карьере' : 'Погружен на карьере'}</div><b>{current.quarry_name} · песок «{current.product_name}»</b></div></div>
                  <div className="drv-row"><div className="ico">➜</div><div><div className="muted small">Куда везти</div><b>{current.client_name}</b><div>{current.address}</div></div></div>
                  {current.heavy_restricted && <div className="alert warn">Ограничение массы на подъезде — используйте объезд</div>}
                  <div className="grid3">
                    <div className="drv-kv"><span>Объём</span><b>{m3(current.planned_m3)}</b></div>
                    <div className="drv-kv"><span>В одну сторону</span><b>{num(Number(current.distance_km) / 2)} км</b></div>
                    <div className="drv-kv"><span>Заказ</span><b>{current.order_number}</b></div>
                  </div>
                </div>
                <div className="grid2">
                  <a className="btn btn-light" href={`https://yandex.ru/maps/?text=${encodeURIComponent(current.address ?? '')}`} target="_blank" rel="noreferrer">Навигатор</a>
                  <a className="btn btn-light" href={current.client_phone ? `tel:${current.client_phone}` : undefined} aria-disabled={!current.client_phone}>Позвонить клиенту</a>
                </div>
                {st === 'planned'
                  ? <button className="btn btn-main drv-big" onClick={() => send({ url: `/api/trips/${current.id}/load`, body: { event_id: uid() }, tripId: current.id, kind: 'load' })}>Погружен, выезжаю</button>
                  : <button className="btn btn-main drv-big" onClick={() => setConfirm(current)}>Выгрузил у клиента</button>}
              </>
            })()}
    </div>
  )
}

function Confirm({ trip, onBack, onDone, next, offline, msg }: { trip: Trip; onBack: () => void; onDone: (v: number) => void; next?: Trip; offline: boolean; msg: string }) {
  const max = Number(trip.planned_m3)
  const [full, setFull] = useState(true)
  const [v, setV] = useState(max)
  return (
    <div className="drv">
      <button className="btn btn-text" style={{ alignSelf: 'flex-start' }} onClick={onBack}>← Назад</button>
      <div><h1 style={{ fontSize: 26 }}>Подтверждение доставки</h1><div className="muted">{trip.order_number} · {trip.client_name}</div></div>
      <div className="card drv-card">
        <b>Клиент принял весь объём?</b>
        <div className="grid2">
          <button className={`btn ${full ? 'btn-dark' : 'btn-light'}`} onClick={() => { setFull(true); setV(max) }}>Да, полностью</button>
          <button className={`btn ${!full ? 'btn-dark' : 'btn-light'}`} onClick={() => setFull(false)}>Нет, частично</button>
        </div>
      </div>
      <div className="card drv-card">
        <b>Фактический объём</b>
        <div className="drv-vol">
          <button className="btn btn-light" disabled={full || v <= 1} onClick={() => setV(Math.max(1, v - 1))}>−</button>
          <div><span className="num-l" style={{ fontSize: 48 }}>{v}</span> м³</div>
          <button className="btn btn-light" disabled={full || v >= max} onClick={() => setV(Math.min(max, v + 1))}>+</button>
        </div>
        <div className="muted small">по заданию — {m3(max)}</div>
      </div>
      {offline && <div className="alert warn">Нет связи — отметка сохранится в телефоне и отправится автоматически</div>}
      {msg && <div className="alert err">{msg}</div>}
      <button className="btn btn-main drv-big" onClick={() => onDone(v)}>Подтвердить доставку</button>
      {next && <div className="muted small" style={{ textAlign: 'center' }}>Следующий рейс: {next.quarry_name} → {next.client_name}, {num(Number(next.distance_km) / 2)} км</div>}
    </div>
  )
}
