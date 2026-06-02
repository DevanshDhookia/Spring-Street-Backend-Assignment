from fastapi import FastAPI

app = FastAPI(
    title="Prisma Factsheet API",
    description="Daily-batch factsheet system for Spring Street Prisma products",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}
