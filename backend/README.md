# AL-HUDA Backend — Deployment Guide

Ye chhota FastAPI server hai jo sirf ek kaam karta hai: account
register/login/verify/reset-password ke email codes bhejta hai
(Brevo ke through) aur user accounts store karta hai.

**Note:** Render ka free plan advertise to karta hai, lekin bohat se
users ko Web Service banate waqt card maangta hai (Render ki taraf se
ye inconsistent hai). Is liye neeche **Vercel + Neon** ka tareeqa diya
hai — dono **bilkul free, koi card nahi** — chahen to Render bhi try
kar sakte hain (`render.yaml` maujood hai), lekin agar card maange to
niche wala tareeqa istemal karein.

## Step 1 — Brevo account (email bhejne ke liye) — [agar pehle nahi kiya]

1. https://www.brevo.com par free account banayein
2. **Senders, Domains & Dedicated IPs** → **Senders** → apni koi bhi
   email add karein → us email par aaye confirmation link ko verify
   karein
3. **SMTP & API** → **API Keys** → **Generate a new API key** → key
   copy kar lein (sirf ek dafa dikhti hai)

## Step 2 — Neon par free database banayein (koi card nahi)

1. https://neon.tech par GitHub account se sign up karein
2. **Create a project** → naam kuch bhi de dein (jaise "al-huda")
3. Project banne ke baad **Connection String** copy kar lein — kuch
   is tarah dikhegi:
   `postgresql://user:password@ep-xxxx.neon.tech/dbname?sslmode=require`
4. Ye string sambhal kar rakh lein, agle step mein chahiye hogi

## Step 3 — Vercel par backend deploy karein (koi card nahi)

1. https://vercel.com par GitHub account se sign up karein
2. **Add New** → **Project** → apna GitHub repo select karein
3. **Root Directory** ko `backend` set karein (zaroori hai — warna
   Vercel poore repo ko backend samajh lega)
4. **Environment Variables** mein ye add karein:
   - `JWT_SECRET` — koi bhi lamba random string
   - `BREVO_API_KEY` — Step 1 wali key
   - `SENDER_EMAIL` — Step 1 mein verify ki hui email
   - `SENDER_NAME` — `AL-HUDA`
   - `DATABASE_URL` — Step 2 wali Neon connection string
5. **Deploy** dabayein. Kuch minute mein ek URL milega, jaise:
   `https://al-huda-backend.vercel.app`

## Step 4 — App ko backend se connect karein

`lib/services/auth_service.dart` file mein ye line dhoondein:

```dart
const String kApiBaseUrl = "https://your-backend-url.example.com";
```

Isay apne asal Vercel URL se replace kar dein, phir app dobara build
karein.

## Testing without email (optional)

Agar `BREVO_API_KEY` set nahi hai, server email bhejne ki koshish
nahi karega — is ki jagah code Vercel ke **Logs** (Deployments →
apna deployment → Logs) mein print ho jayega, taake bina email setup
ke bhi test kar sakein.

## File structure note

Backend ka asal code `app_core.py` mein hai. `main.py` (local/Render
ke liye) aur `api/index.py` (Vercel ke liye) dono usi se import karte
hain — matlab kabhi bhi code change karna ho to sirf `app_core.py`
edit karein, baaki dono files khud-ba-khud update ho jayengi.
