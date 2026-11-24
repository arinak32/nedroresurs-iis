import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api, type Client, type Order, type Product, type Quote } from '../api'
import { m3, num, rub } from '../format'

// Окно регистрации заказа: цена и остаток пересчитываются при каждом изменении (вариант использования «include»)
export default function NewOrder({ onClose, onCreated }: { onClose: () => void; onCreated: (o: Order) => void }) {
  const qc = useQueryClient()
  const clients = useQuery({ queryKey: ['clients'], queryFn: () => api.get<Client[]>('/api/clients') })
  const products = useQuery({ queryKey: ['products'], queryFn: () => api.get<Product[]>('/api/products') })
  const [f, setF] = useState({ client_id: 0, product_id: 0, volume_m3: '', method: 'delivery' as 'delivery' | 'pickup',
    address_id: 0, desired_date: '', source: 'phone' as 'phone' | 'etp', procurement_no: '' })
  const [quote, setQuote] = useState<Quote | null>(null)
  const [qErr, setQErr] = useState('')
  const [err, setErr] = useState('')
  const [newClient, setNewClient] = useState(false)
  const set = (k: keyof typeof f, v: unknown) => setF(p => ({ ...p, [k]: v }))
  const client = clients.data?.find(c => c.id === f.client_id)

  useEffect(() => { if (products.data && !f.product_id) set('product_id', products.data[0].id) }, [products.data])
  useEffect(() => { if (client && f.method === 'delivery') set('address_id', client.addresses[0]?.id ?? 0) }, [f.client_id])

  // пересчёт цены
  useEffect(() => {
    setQuote(null); setQErr('')
    const v = Number(f.volume_m3)
    if (!f.product_id || !v || (f.method === 'delivery' && !f.address_id)) return
    const t = setTimeout(() => {
      api.get<Quote>('/api/orders/quote', { product_id: f.product_id, volume_m3: v, method: f.method,
        address_id: f.method === 'delivery' ? f.address_id : undefined, client_id: f.client_id || undefined })
        .then(setQuote).catch(e => setQErr(e.message))
    }, 250)
    return () => clearTimeout(t)
  }, [f.product_id, f.volume_m3, f.method, f.address_id, f.client_id])

  const save = async () => {
    setErr('')
    try {
      const o = await api.post<Order>('/api/orders', { ...f, volume_m3: Number(f.volume_m3),
        address_id: f.method === 'delivery' ? f.address_id : null, desired_date: f.desired_date || null,
        procurement_no: f.source === 'etp' ? f.procurement_no : null })
      qc.invalidateQueries({ queryKey: ['orders'] })
      onCreated(o)
    } catch (e) { setErr((e as Error).message) }
  }

  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="head"><h2 className="t">Новый заказ</h2><button className="btn btn-text" onClick={onClose}>Закрыть ✕</button></div>
        <div className="row">
          <div className="card grow" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="field"><label>Клиент</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <select className="input" value={f.client_id} onChange={e => set('client_id', Number(e.target.value))}>
                  <option value={0}>Выберите клиента</option>
                  {clients.data?.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
                <button className="btn btn-light" onClick={() => setNewClient(true)}>+ Новый</button>
              </div>
            </div>
            <div className="grid2">
              <div className="field"><label>Вид песка</label>
                <select className="input" value={f.product_id} onChange={e => set('product_id', Number(e.target.value))}>
                  {products.data?.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select></div>
              <div className="field"><label>Объём, м³</label>
                <input className="input" type="number" min={1} value={f.volume_m3} onChange={e => set('volume_m3', e.target.value)} /></div>
            </div>
            <div className="tabs">
              {(['delivery', 'pickup'] as const).map(m => (
                <button key={m} className={`tab ${f.method === m ? 'on' : ''}`} onClick={() => set('method', m)}>{m === 'delivery' ? 'Доставка' : 'Самовывоз'}</button>
              ))}
            </div>
            {f.method === 'delivery' && (
              <div className="field"><label>Адрес доставки</label>
                <select className="input" value={f.address_id} onChange={e => set('address_id', Number(e.target.value))} disabled={!client}>
                  {!client && <option value={0}>Сначала выберите клиента</option>}
                  {client?.addresses.map(a => <option key={a.id} value={a.id}>{a.address} · {num(a.distance_km)} км{a.heavy_restricted ? ' · ограничение массы' : ''}</option>)}
                </select></div>
            )}
            <div className="grid2">
              <div className="field"><label>Источник</label>
                <select className="input" value={f.source} onChange={e => set('source', e.target.value)}>
                  <option value="phone">Телефон</option><option value="etp">Торговая площадка</option>
                </select></div>
              <div className="field"><label>Желаемая дата</label>
                <input className="input" type="date" value={f.desired_date} onChange={e => set('desired_date', e.target.value)} /></div>
            </div>
            {f.source === 'etp' && <div className="field"><label>Номер закупки</label>
              <input className="input" value={f.procurement_no} onChange={e => set('procurement_no', e.target.value)} /></div>}
          </div>

          <div className="card" style={{ width: 320, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <h3 style={{ marginBottom: 8 }}>Расчёт стоимости</h3>
            {!quote && !qErr && <div className="muted small">Заполните клиента, вид песка, объём и адрес</div>}
            {qErr && <div className="alert err">{qErr}</div>}
            {quote && <>
              <div className="kv"><span>Цена песка</span><span>{rub(quote.price_m3)}/м³</span></div>
              {f.method === 'delivery' && <div className="kv"><span>Доставка: {num(Number(quote.distance_km) * 2)} км туда и обратно</span><span>+{rub(quote.delivery_m3)}/м³</span></div>}
              <div className="kv"><span>Итого за 1 м³</span><span>{rub(quote.unit_total)}</span></div>
              <div style={{ borderTop: '1px solid var(--line)', margin: '6px 0' }} />
              <div className="kv"><span>Сумма заказа</span><span className="num-l">{rub(quote.amount)}</span></div>
              <div className="kv"><span>в т. ч. НДС {num(quote.vat_rate)} %</span><span>{rub(quote.vat)}</span></div>
              <div className={`alert ${quote.enough ? 'ok' : 'warn'}`} style={{ marginTop: 8 }}>
                {quote.enough ? '✓ Достаточно' : '! Не хватает'}: на площадке {m3(quote.available_m3)}
              </div>
              {quote.trips_needed > 0 && <div className="alert" style={{ background: 'var(--sand-light)', color: 'var(--text)' }}>➜ Нужно {quote.trips_needed} рейсов самосвала</div>}
            </>}
          </div>
        </div>
        {err && <div className="alert err">{err}</div>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button className="btn btn-light" onClick={onClose}>Отмена</button>
          <button className="btn btn-main" disabled={!quote || !f.client_id} onClick={save}>Сохранить заказ</button>
        </div>
        {newClient && <NewClient onClose={() => setNewClient(false)} onCreated={c => {
          qc.setQueryData<Client[]>(['clients'], old => [...(old ?? []), c]); set('client_id', c.id); setNewClient(false)
        }} />}
      </div>
    </div>
  )
}

function NewClient({ onClose, onCreated }: { onClose: () => void; onCreated: (c: Client) => void }) {
  const [f, setF] = useState({ name: '', inn: '', client_type: 'construction', address: '', distance_km: '', heavy_restricted: false })
  const [err, setErr] = useState('')
  const save = async () => {
    setErr('')
    try {
      const c = await api.post<Client>('/api/clients', { name: f.name, inn: f.inn || null, client_type: f.client_type,
        addresses: f.address ? [{ address: f.address, distance_km: Number(f.distance_km), heavy_restricted: f.heavy_restricted }] : [] })
      onCreated(c)
    } catch (e) { setErr((e as Error).message) }
  }
  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" style={{ width: 520 }} onClick={e => e.stopPropagation()}>
        <h2>Новый клиент</h2>
        <div className="field"><label>Наименование</label><input className="input" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} /></div>
        <div className="grid2">
          <div className="field"><label>ИНН</label><input className="input" value={f.inn} onChange={e => setF({ ...f, inn: e.target.value })} /></div>
          <div className="field"><label>Тип</label>
            <select className="input" value={f.client_type} onChange={e => setF({ ...f, client_type: e.target.value })}>
              <option value="road">Дорожная организация</option><option value="construction">Строительная организация</option>
              <option value="concrete">Завод ЖБИ</option><option value="private">Частное лицо</option><option value="other">Другое</option>
            </select></div>
        </div>
        <div className="field"><label>Адрес доставки</label><input className="input" value={f.address} onChange={e => setF({ ...f, address: e.target.value })} /></div>
        <div className="grid2">
          <div className="field"><label>Расстояние от карьеров, км (в одну сторону)</label><input className="input" type="number" value={f.distance_km} onChange={e => setF({ ...f, distance_km: e.target.value })} /></div>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 22 }}>
            <input type="checkbox" checked={f.heavy_restricted} onChange={e => setF({ ...f, heavy_restricted: e.target.checked })} /> дорога с ограничением массы</label>
        </div>
        {err && <div className="alert err">{err}</div>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button className="btn btn-light" onClick={onClose}>Отмена</button>
          <button className="btn btn-main" disabled={!f.name || (!!f.address && !f.distance_km)} onClick={save}>Сохранить</button>
        </div>
      </div>
    </div>
  )
}
