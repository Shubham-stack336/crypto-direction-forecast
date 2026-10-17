# Deployment guide (Render + Vercel)

Ye guide Hinglish mein hai. Abhi tak **kuch deploy nahi hua hai**. Neeche ke steps aapko apne accounts se karne hain.
Render aur Vercel ke buttons aur menus kabhi-kabhi badalte hain, isliye jahan UI ka naam diya hai wahan screen se
match karke dekho.

Free plan ki baatein (Render docs se, 2026-10-17 ko check ki):
- Free web service **15 minute** bina traffic ke so jata hai; wapas jaagne mein lagbhag **1 minute** lagta hai.
- Free PostgreSQL **30 din** baad expire ho jata hai (uske baad 14 din ka grace period). Data rakhna ho to paid plan lo.
- Free web service par **pre-deploy command nahi hota**, isliye migration `startCommand` ke andar chalti hai.
- Free web service par persistent disk nahi hoti. Hamari app disk par kuch likhti nahi: model files repo ke saath aati
  hain (read-only) aur history PostgreSQL mein jati hai, isliye restart par kuch nahi khota.

## 0. Pehle local par check karo

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest -q
cd ..\frontend
npm test
npm run build
```
Sab pass hona chahiye.

## 1. GitHub par push (backend aur frontend dono ek hi repo mein)

1. GitHub par naya khaali repository banao (README ya .gitignore mat jodna, wo already hain).
2. Project ke root folder se (jahan `render.yaml` hai):
```powershell
git init
git add .
git status        # dhyan se dekho: .env, .venv, node_modules list mein NAHI hone chahiye
git commit -m "Crypto direction forecast: ML engine, API, dashboard"
git branch -M main
git remote add origin https://github.com/<aapka-username>/<repo-name>.git
git push -u origin main
```
`git status` mein agar koi `.env` file dikhe to rukk jao, use commit mat karo. Password ya database URL kabhi GitHub par nahi jana chahiye.

## 2. Render par backend aur PostgreSQL

1. Render Dashboard → **New** → **Blueprint** → apna GitHub repo chuno.
2. Render root ki `render.yaml` padh kar 2 cheezein banayega: database `crypto-predictions-db` aur web service `crypto-direction-api`.
3. Wo `APP_CORS_ORIGINS` ki value poochega (kyunki file mein `sync: false` hai). Abhi Vercel ka URL nahi pata, to
   pehle ye likho: `["http://localhost:5173"]` (square brackets aur double quotes ke saath, ye JSON hai).
4. **Apply** karo. Build mein `pip install -r requirements.txt` chalega. Phir start par pehle `alembic upgrade head`
   (tables banti hain), phir `uvicorn`.
5. Web service ke **Logs** tab mein dekho. Ye lines aani chahiye: `Running upgrade  -> 0001` aur uske baad uvicorn ka
   "Application startup complete".
6. Health check `/health/live` par hai. Wo database par depend nahi karta, taaki database ke chhote hiccup se server
   restart na ho. Database check `/health/ready` mein hota hai.

### Live endpoints test karo
Apna URL `https://<service-name>.onrender.com` hoga:
```powershell
curl https://<service-name>.onrender.com/health/live
curl https://<service-name>.onrender.com/health/ready
curl https://<service-name>.onrender.com/api/v1/models/BTC-USDT/status
curl -X POST https://<service-name>.onrender.com/api/v1/predictions/BTC-USDT
curl "https://<service-name>.onrender.com/api/v1/predictions/BTC-USDT/history"
```
- `/health/ready` mein `"database": "ok"` aana chahiye.
- Pehli request so rahe server ko jagaati hai, to ~1 minute lag sakta hai.
- Prediction ke jawab mein `"saved": true` aana chahiye. `false` ka matlab hai ki database mein save nahi hua (logs dekho).
- Binance aam taur par US ke IP se block hota hai, aur Render ka default region Oregon (US) hai. Isliye `render.yaml`
  mein database aur service dono `region: frankfurt` mein hain (dono ka region same hona zaroori hai). Phir bhi agar
  prediction ya market par `503 "Market data provider is currently unavailable"` aaye, to Binance block ho raha hai:
  `APP_EXCHANGE_ID` environment variable mein koi aur exchange (jaise `bybit` ya `kraken`) try karo. Dhyan do ki model
  Binance ke data par train hua hai, doosre exchange ke daam thode alag ho sakte hain. Ye live test ke bina pakka
  nahi pata, isliye zaroor test karo.
- Agar Render ka Blueprint `region` ya koi aur field par error de, to Blueprint editor ka message padho aur
  [Render ki blueprint-spec](https://render.com/docs/blueprint-spec) se field ka naam match karo.

## 3. Vercel par frontend

1. Vercel Dashboard → **Add New** → **Project** → wahi GitHub repo import karo.
2. **Root Directory** ko `frontend` set karo (Project settings mein "Root Directory" naam ka setting; ye wahi folder hai jahan `package.json` hai).
3. Framework preset Vite apne aap pehchan lega. Build command `npm run build`, output `dist` hona chahiye.
4. **Environment Variables** mein jodo:
   - Name: `VITE_API_BASE_URL`
   - Value: `https://<service-name>.onrender.com` (Render ka URL, aakhir mein `/` nahi)
5. **Deploy**.

`VITE_` wale variables browser ke code mein chhap jaate hain, isliye yahan **kabhi** database URL ya koi secret mat
rakhna. Ye variable build ke waqt bhar jata hai, to isko badalne ke baad Vercel par **redeploy** karna padta hai.

## 4. CORS theek karo (Vercel URL milne ke baad)

Browser sirf wahi website API ko call kar sakti hai jo `APP_CORS_ORIGINS` mein likhi ho.
1. Render → `crypto-direction-api` → **Environment** → `APP_CORS_ORIGINS` ko badlo:
   `["https://<project>.vercel.app"]`
2. Save karo (service redeploy hogi).
3. Browser mein Vercel ka URL kholo. Upar "API ready" dikhna chahiye.

`*` allow nahi hai (code use reject kar deta hai). Agar custom domain bhi ho to dono likho:
`["https://<project>.vercel.app","https://yourdomain.com"]`.

## 5. Kuch galat ho to

| Dikkat | Matlab / kya karein |
|---|---|
| Dashboard par "API offline" | `VITE_API_BASE_URL` galat hai ya server so raha hai (1 minute ruko). Browser DevTools → Network dekho. |
| Console mein "blocked by CORS policy" | `APP_CORS_ORIGINS` mein aapka Vercel URL bilkul sahi (https, bina aakhri `/`) nahi hai. |
| "API online, not ready: Database is unavailable" | `APP_DATABASE_URL` ya database check karo. Free DB expire to nahi hua? |
| Render deploy fail, logs mein `APP_DATABASE_URL is required` | `APP_ENVIRONMENT=production` mein database URL zaroori hai; Blueprint ne database link kiya hai ya nahi dekho. |
| Render deploy fail, logs mein `alembic` error | Logs ki aakhri 20 lines padho; aksar database tak connection ka masla hota hai. |
| `503 ... too old` | Exchange se aaya data 3 candle se purana hai (ya exchange rukk gaya). Thodi der baad dobara. |
| Vercel build fail | Build log mein pehli error dekho; `npm run build` local par chalakar wahi error aati hai ya nahi. |

## 6. Model badalna

1. `ml_engine` mein dobara train karo (`python scripts/step12_final.py`).
2. `ml_engine/artifacts/*` ko `backend/artifacts/` mein copy karo.
3. `git add`, `git commit`, `git push`. Render khud redeploy kar dega.

Naya model tabhi use karo jab uska test result imaandari se dekh liya ho. Test set se model chunna ya tune karna galat hai.
