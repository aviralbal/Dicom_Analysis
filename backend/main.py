from fastapi import FastAPI
from mangum import Mangum  # Required for Vercel

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend"}

# Required for Vercel deployment
handler = Mangum(app)
