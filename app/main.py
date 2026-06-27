from fastapi import FastAPI

app = FastAPI(title="ShopFloor")


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}
