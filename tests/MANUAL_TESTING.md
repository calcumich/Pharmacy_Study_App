# Manual Testing

These checks cover the parts of the app that are not exercised by the backend smoke test in [`test_smoke_api.py`](/C:/Users/felze/source/repos/PharmacyStudyApp/tests/test_smoke_api.py), mainly the browser-based frontend flow.

## Prerequisites

- The local database was reset and bootstrapped successfully.
- The backend can connect to the seeded database via `.env`.
- Node modules are installed in [`frontend/`](/C:/Users/felze/source/repos/PharmacyStudyApp/frontend).

## 1. Start the backend

From the repo root:

```powershell
uvicorn app.main:app --reload
```

Expected result:

- The API starts without import or database errors.
- `http://localhost:8000/health` returns `{"status": "ok"}`.

## 2. Point the frontend at the real API

Create `frontend/.env.local` with:

```env
VITE_USE_MOCK=false
VITE_API_BASE_URL=http://localhost:8000
```

Expected result:

- The frontend uses the backend instead of `frontend/src/api/mock.ts`.

## 3. Start the frontend

From [`frontend/`](/C:/Users/felze/source/repos/PharmacyStudyApp/frontend):

```powershell
npm run dev
```

Open the local Vite URL in a browser.

Expected result:

- The app loads without a blank screen or runtime error.
- The yellow `mock data` badge does not appear in the header.

## 4. Validate seeded class and drug browsing

In the UI:

- Select `Cardiovascular` or one of its child classes.
- Select `Antibiotics` or `Penicillins`.

Expected result:

- The left sidebar shows the seeded class tree.
- Selecting a class loads real seeded drugs from the API.
- You can see drugs like `Metoprolol`, `Lisinopril`, or `Amoxicillin`.

## 5. Validate study configuration

In the UI:

- Select one or more drugs.
- Proceed to configuration.
- Leave several attribute types selected.
- Switch between `Flashcard` and `Table`.

Expected result:

- Drug selection updates normally.
- Attribute types are loaded from the database.
- No API errors appear when switching study mode.

## 6. Validate study rendering

In the UI:

- Start a flashcard session.
- Return and start a table session.

Expected result:

- Flashcard mode renders cards backed by seeded drug details.
- Table mode renders rows and cells for the selected drugs and attributes.
- The `New session` action returns you to the initial flow cleanly.

## 7. Basic failure checks

If something is wrong, identify which layer failed:

- Backend fails to start: migration, config, or database issue.
- `/attribute-types` is empty: migration or seed issue.
- Frontend shows the `mock data` badge: env configuration issue.
- UI loads classes but not drug details or study data: API route or seeded data linkage issue.
