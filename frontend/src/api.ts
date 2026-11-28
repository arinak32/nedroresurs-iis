// Обращения к серверу. Токен хранится в localStorage и передаётся в заголовке Authorization.
const TOKEN_KEY = 'nedro_token'

export const token = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

async function request<T>(method: string, url: string, body?: unknown, form = false): Promise<T> {
  const headers: Record<string, string> = {}
  const t = token.get()
  if (t) headers.Authorization = `Bearer ${t}`
  let payload: BodyInit | undefined
  if (form) { payload = new URLSearchParams(body as Record<string, string>) }
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }
  const res = await fetch(url, { method, headers, body: payload })
  if (res.status === 401 && !url.endsWith('/login')) { token.clear(); window.location.href = '/login' }
  if (!res.ok) {
    let msg = 'Ошибка сервера'
    try {
      const j = await res.json()
      msg = typeof j.detail === 'string' ? j.detail : (j.detail?.[0]?.msg ?? msg)
    } catch { /* ответ не JSON */ }
    throw new ApiError(res.status, msg)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

export const api = {
  get: <T,>(url: string, params?: Record<string, unknown>) => {
    const q = params ? '?' + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '').map(([k, v]) => [k, String(v)])) : ''
    return request<T>('GET', url + q)
  },
  post: <T,>(url: string, body?: unknown) => request<T>('POST', url, body),
  put: <T,>(url: string, body?: unknown) => request<T>('PUT', url, body),
  login: (username: string, password: string) =>
    request<{ access_token: string }>('POST', '/api/auth/login', { username, password }, true),
}

// ── типы ответов сервера
export type Role = 'director' | 'manager' | 'accountant' | 'lawyer' | 'mechanic' | 'driver' | 'admin'
export interface User { id: number; login: string; full_name: string; role: Role }
export interface Product { id: number; name: string; price_m3: string }
export interface Address { id: number; address: string; distance_km: string; heavy_restricted: boolean }
export interface Client { id: number; name: string; inn: string | null; client_type: string; phone: string | null; addresses: Address[] }
export type OrderStatus = 'new' | 'awaiting_payment' | 'planning' | 'in_delivery' | 'shipped' | 'done' | 'cancelled'
export interface Order {
  id: number; number: string; client_id: number; client_name: string; product_id: number; product_name: string
  volume_m3: string; method: 'delivery' | 'pickup'; address: string | null; distance_km: string | null
  desired_date: string | null; price_m3: string; delivery_m3: string; amount: string; vat: string; vat_rate: string
  source: 'phone' | 'etp'; procurement_no: string | null; contract_number: string | null; status: OrderStatus; created_at: string
}
export interface OrdersPage { items: Order[]; total: number; counts: Partial<Record<OrderStatus, number>> }
export interface Quote {
  distance_km: string | null; price_m3: string; delivery_m3: string; unit_total: string; amount: string; vat: string
  vat_rate: string; tariff_steps: number; site_name: string; available_m3: string; enough: boolean; trips_needed: number
}
export interface Site { id: number; name: string; product_name: string; capacity_m3: string; volume_m3: string; fill_pct: number }
export interface Quarry { id: number; name: string; site_id: number }
export interface ProductionRow { id: number; shift_date: string; quarry_name: string; product_name: string; volume_m3: string; author: string | null }

export type TripStatus = 'planned' | 'en_route' | 'delivered' | 'cancelled'
export interface Trip {
  id: number; seq: number; order_id: number; order_number: string; client_name: string; client_phone: string | null
  address: string | null; heavy_restricted: boolean; product_name: string; quarry_name: string | null
  vehicle_id: number | null; vehicle_name: string | null; driver_name: string | null
  planned_m3: string; actual_m3: string | null; distance_km: string | null; status: TripStatus
  loaded_at: string | null; delivered_at: string | null
}
export interface Truck { id: number; name: string; driver_name: string | null; status: string }
export interface Plan {
  id: number; plan_date: string; status: 'draft' | 'approved'; total_km: string | null; trips: Trip[]; trucks: Truck[]
  unplanned: { order_id: number; order_number: string; client_name: string; volume_m3: string; trips: number }[]; orders_count: number; blocked: number[]
}
export interface DriverDay { driver_name: string; vehicle_name: string | null; vehicle_model: string | null; plan_date: string; trips: Trip[] }

export const patch = <T,>(url: string, body?: unknown) => request<T>('PATCH', url, body)

export interface Maintenance { id: number; kind: string; description: string | null; started_at: string; planned_end: string | null; finished_at: string | null; mechanic: string | null }
export interface Vehicle {
  id: number; kind: 'dump_truck' | 'excavator' | 'loader'; name: string; model: string; reg_number: string | null
  capacity_m3: string; status: 'on_line' | 'maintenance' | 'repair'; odometer_km: number; engine_hours: number
  counter_unit: string; service_interval: number; service_left: number; service_soon: boolean
  driver_id: number | null; driver_name: string | null; current: Maintenance | null; history: Maintenance[]
}
export interface DriverShort { id: number; full_name: string; vehicle_name: string | null }
