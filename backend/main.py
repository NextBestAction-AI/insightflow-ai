from fastapi import FastAPI

app = FastAPI(
    title="InsightFlow AI",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "message": "InsightFlow AI Backend Running"
    }