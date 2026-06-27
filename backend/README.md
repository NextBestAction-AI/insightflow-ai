# Backend compatibility notes

This backend now supports both the newer app-based layout and the older-style entry points used by the original project structure.

## Start with the newer layout

```powershell
cd backend
uvicorn app.main:app --reload
```

## Start with the older layout

```powershell
cd backend
python main.py
```

The compatibility wrappers in the top-level backend package forward to the current implementation in app/ so the repository can be merged more easily with older branches.
