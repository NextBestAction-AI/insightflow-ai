import sys
sys.path.append('.')
from app.main import app
from fastapi.routing import APIRoute

for route in app.routes:
    if isinstance(route, APIRoute):
        if any(token in route.path for token in ['workflow','analyze','upload','approve','reject','customer-health','recommendation']):
            print(route.path)
