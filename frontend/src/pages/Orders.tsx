import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api, type Order, type OrdersPage, type OrderStatus, type Product } from '../api'
import { useAuth } from '../auth'
import { Head } from '../components/Layout'
import { dateRu, m3, num, plural, rub, STATUS } from '../format'
import NewOrder from './NewOrder'

const TABS: (OrderStatus | '')[] = ['', 'new', 'awaiting_payment', 'planning', 'in_delivery', 'shipped', 'done', 'cancelled']

// действия, доступные менеджеру в каждом статусе (диаграмма состояний, рисунок 2.3)
const ACTIONS: Partial<Record<OrderStatus, [string, string, string][]>> = {
  new: [['issue_invoice', 'Выставить счёт', 'btn-dark'], ['confirm', 'Подтвердить заказ', 'btn-main']],
  awaiting_payment: [['mark_paid', 'Оплата получена', 'btn-main']],
  planning: [],
  shipped: [['close', 'Закрыть заказ', 'btn-main']],
}

export default function Orders() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const [status, setStatus] = useState<OrderStatus | ''>('')
  const [product, setProduct] = useState(0)
  const [source, setSource] = useState('')
  const [q, setQ] = useState('')
  const [sel, setSel] = useState<Order | null>(null)
  const [creating, setCreating] = useState(false)
  const [err, setErr] = useState('')
  const canEdit = user?.role === 'manager'

  const products = useQuery({ queryKey: ['products'], queryFn: () => api.get<Product[]>('/api/products') })
  const data = useQuery({
    queryKey: ['orders', status, product, source, q],
    queryFn: () => api.get<OrdersPage>('/api/orders', { status, product_id: product || undefined, source, q }),
    placeholderData: keepPreviousData,
    refetchInterval: 30000,
  })
  const counts = data.data?.counts ?? {}
  // если статус выбранного заказа изменился (например, водитель доставил рейс) — обновить карточку
  useEffect(() => {
    const fresh = sel && data.data?.items.find(x => x.id === sel.id)
    if (fresh && fresh.status !== sel!.status) setSel(fresh)
  }, [data.data])
  const all = Object.values(counts).reduce((a, b) => a + (b ?? 0), 0)

  const act = async (action: string) => {
    if (!sel) return
    setErr('')
    try {
      const o = await api.post<Order>(`/api/orders/${sel.id}/status`, { action })
      setSel(o)
      qc.invalidateQueries({ queryKey: ['orders'] }); qc.invalidateQueries({ queryKey: ['stock'] })
    } catch (e) { setErr((e as Error).message) }
  }

  return (
    <>
      <Head sub={plural(all, 'заказ', 'заказа', 'заказов')} title="Заказы">
        <input className="input" style={{ width: 220 }} placeholder="Поиск: клиент или №" value={q} onChange={e => setQ(e.target.value)} />
        {canEdit && <button className="btn btn-main" onClick={() => setCreating(true)}>Новый заказ +</button>}
      </Head>
      <div className="head">
        <div className="tabs t">
          {TABS.map(s => (
            <button key={s} className={`tab ${status === s ? 'on' : ''}`} onClick={() => setStatus(s)}>
              {s ? STATUS[s][0] : 'Все'}<small>{s ? counts[s] ?? 0 : all}</small>
            </button>
          ))}
        </div>
        <select className="input" style={{ width: 170 }} value={product} onChange={e => setProduct(Number(e.target.value))}>
          <option value={0}>Вид песка: все</option>
          {products.data?.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select className="input" style={{ width: 170 }} value={source} onChange={e => setSource(e.target.value)}>
          <option value="">Источник: все</option><option value="phone">Телефон</option><option value="etp">Торговая площадка</option>
        </select>
      </div>

      <div className="row">
        <div className="card grow" style={{ padding: '10px 12px' }}>
          {data.isLoading ? <div className="spinner">Загрузка…</div> : data.data?.items.length ? (
            <table className="t">
              <thead><tr><th>№</th><th>Клиент</th><th>Вид песка</th><th>Объём</th><th>Получение</th><th>Статус</th></tr></thead>
              <tbody>
                {data.data.items.map(o => (
                  <tr key={o.id} className={`click ${sel?.id === o.id ? 'sel' : ''}`} onClick={() => { setSel(o); setErr('') }}>
                    <td>{o.number}</td>
                    <td><b>{o.client_name}</b><div className={`sub ${o.source === 'etp' ? 'src-etp' : ''}`}>{o.source === 'etp' ? 'Торговая площадка' : 'Телефон'}</div></td>
                    <td>{o.product_name}</td>
                    <td>{m3(o.volume_m3)}</td>
                    <td>{o.method === 'delivery' ? `Дост. · ${num(o.distance_km)} км` : 'Самовывоз'}</td>
                    <td><span className={`chip ${STATUS[o.status][1]}`}>{STATUS[o.status][0]}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <div className="spinner">Заказов нет{canEdit ? ' — создайте первый кнопкой «Новый заказ»' : ''}</div>}
        </div>

        {sel && (
          <div className="card" style={{ width: 360, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div className="head"><div className="t"><h2>Заказ {sel.number}</h2><div className="muted small">создан {dateRu(sel.created_at)}</div></div>
              <span className={`chip ${STATUS[sel.status][1]}`}>{STATUS[sel.status][0]}</span></div>
            <div className="alert" style={{ background: 'var(--page)', color: 'var(--text)', margin: '8px 0' }}>
              <b>{sel.client_name}</b>{sel.contract_number ? ` · договор ${sel.contract_number}` : ' · по счёту'}
              {sel.procurement_no && <div className="muted small">закупка № {sel.procurement_no}</div>}
            </div>
            <div className="kv"><span>Вид песка</span><span>{sel.product_name}</span></div>
            <div className="kv"><span>Объём</span><span>{m3(sel.volume_m3)}</span></div>
            <div className="kv"><span>Получение</span><span>{sel.method === 'delivery' ? 'Доставка' : 'Самовывоз'}</span></div>
            {sel.address && <div className="kv"><span>Адрес</span><span>{sel.address}</span></div>}
            {sel.distance_km && <div className="kv"><span>Расстояние от карьера</span><span>{num(sel.distance_km)} км</span></div>}
            {sel.desired_date && <div className="kv"><span>Желаемая дата</span><span>{dateRu(sel.desired_date)}</span></div>}
            <div className="card" style={{ padding: 16, marginTop: 8 }}>
              <h3 style={{ marginBottom: 6 }}>Расчёт стоимости</h3>
              <div className="kv"><span>Цена песка</span><span>{rub(sel.price_m3)}/м³</span></div>
              {sel.method === 'delivery' && <div className="kv"><span>Доставка</span><span>+{rub(sel.delivery_m3)}/м³</span></div>}
              <div className="kv"><span>Сумма заказа</span><span className="num-l">{rub(sel.amount)}</span></div>
              <div className="kv"><span>в т. ч. НДС {num(sel.vat_rate)} %</span><span>{rub(sel.vat)}</span></div>
            </div>
            {err && <div className="alert err">{err}</div>}
            {canEdit && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
                {(ACTIONS[sel.status] ?? []).filter(([a]) => a === 'confirm' ? !!sel.contract_number : a === 'issue_invoice' ? !sel.contract_number : true).map(([a, label, cls]) => <button key={a} className={`btn ${cls}`} onClick={() => act(a)}>{label}</button>)}
                {sel.status === 'planning' && sel.method === 'pickup' && <button className="btn btn-main" onClick={() => act('pickup')}>Отгружено в транспорт клиента</button>}
                {sel.status === 'planning' && sel.method === 'delivery' && <div className="muted small">Заказ попадёт в план рейсов: раздел «Рейсы» → «Рассчитать план»</div>}
                {['new', 'awaiting_payment', 'planning'].includes(sel.status) && <button className="btn btn-text" onClick={() => confirm('Отменить заказ?') && act('cancel')}>Отменить заказ</button>}
              </div>
            )}
          </div>
        )}
      </div>
      {creating && <NewOrder onClose={() => setCreating(false)} onCreated={o => { setCreating(false); setSel(o) }} />}
    </>
  )
}
