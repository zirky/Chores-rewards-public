from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.database import init_db
from app.routers import auth, tasks, completions, settlements, children


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Chores Rewards",
    description="Domácí checklist odměn pro děti s Lightning Network payoutem",
    version="0.1.2",
    lifespan=lifespan,
    # Vypnout automatický trailing-slash redirect – způsobuje CORS preflight fail
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Pro MVP lokální síť – zpzřínit v produkci
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,        prefix="/api/auth",        tags=["auth"])
app.include_router(children.router,    prefix="/api/children",    tags=["children"])
app.include_router(tasks.router,       prefix="/api/tasks",       tags=["tasks"])
app.include_router(completions.router, prefix="/api/completions", tags=["completions"])
app.include_router(settlements.router, prefix="/api/settlements", tags=["settlements"])


@app.get("/")
async def root():
    return {"status": "ok", "app": "chores-rewards", "version": "0.1.2"}
