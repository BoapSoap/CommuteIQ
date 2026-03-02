# CommuteIQ Frontend

Next.js dashboard for live friction status + personal commute calculator.

## Run locally

```bash
cd frontend
npm install
npm run dev
```

App URL: `http://localhost:3000`

## Env

Create `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Production deploy

- Deploy to Vercel with standard Next.js defaults.
- Set `NEXT_PUBLIC_API_BASE_URL` to your deployed backend URL.
