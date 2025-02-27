from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI on Vercel"}

# Required for Vercel deployment
from mangum import Mangum
handler = Mangum(app)
