from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import auth, catalog, clients, orders, production

app = FastAPI(
    title="ИИС «Недроресурс»",
    description="Интеллектуальная информационная система управления предприятием: добыча, продажа и доставка песка.",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
# при разработке интерфейс запускается на другом порту (Vite, 5173)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, catalog.router, clients.router, orders.router, production.router):
    app.include_router(r)


@app.get("/api/health", tags=["Служебное"])
def health():
    return {"status": "ok"}
