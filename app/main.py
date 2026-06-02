from fastapi import FastAPI

from app.api.public import exposures, factsheet, holdings, nav, performance, products

app = FastAPI(
    title="Prisma Factsheet API",
    description="Daily-batch factsheet system for Spring Street Prisma products",
    version="0.1.0",
)

app.include_router(products.router)
app.include_router(factsheet.router)
app.include_router(nav.router)
app.include_router(holdings.router)
app.include_router(exposures.router)
app.include_router(performance.router)


@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok"}
