# Keep Render.com Service Awake - Setup Guide (FREE PLAN)

## Your Render Service URL
**Backend URL**: `https://check-your-time.onrender.com`  
**Health Endpoint**: `https://check-your-time.onrender.com/cron/health/`

## Problem
Render.com **FREE** services automatically sleep after 15 minutes of inactivity. When sleeping, your Django scheduler won't run. Render cron jobs are only available on paid plans.

## Quick Setup (2 Minutes)

**Easiest Solution**: Use **cron-job.org** (100% FREE)

1. Go to https://cron-job.org and sign up (free, no credit card)
2. Click "Create cronjob"
3. Enter:
   - **Title**: `Keep Render Service Awake`
   - **Address**: `https://check-your-time.onrender.com/cron/health/`
   - **Schedule**: Every 10 minutes
4. Activate and save
5. Done! Your service will stay awake.

## Solution: Use FREE External Services to Ping Your Service

> **Note**: All options below are **100% FREE** and work with Render's free plan.

### Option 1: cron-job.org (Recommended - Easiest & Free)

1. **Sign up at**: https://cron-job.org (100% free, no credit card needed)

2. **Create a new cron job:**
   - Click "Create cronjob"
   - **Title**: `Keep Render Service Awake`
   - **Address**: `https://check-your-time.onrender.com/cron/health/`
   - **Schedule**: 
     - Select "Every X minutes"
     - Enter `10` (pings every 10 minutes)
   - **Activate**: Yes (toggle switch)
   - Click "Create cronjob"

3. **Verify it's working:**
   - Check "Last execution" shows recent pings
   - Your Render service should stay awake

**Why this works**: Pinging every 10 minutes keeps your service active (it sleeps after 15 minutes of inactivity)

### Option 2: UptimeRobot (Free - 50 monitors)

1. **Sign up at**: https://uptimerobot.com (free account, no credit card)

2. **Add a new monitor:**
   - Click "Add New Monitor"
   - **Monitor Type**: HTTP(s)
   - **Friendly Name**: `Render Keep Alive`
   - **URL**: `https://check-your-time.onrender.com/cron/health/`
   - **Monitoring Interval**: 5 minutes (free tier allows 5-minute intervals)
   - Click "Create Monitor"

3. **Benefits**: 
   - Free tier: 50 monitors
   - 5-minute ping interval (keeps service very active)
   - Email alerts if service goes down

### Option 3: EasyCron (Free tier available)

1. **Sign up at**: https://www.easycron.com (free tier: 1 job, 1 execution per minute)

2. **Create a new cron job:**
   - Click "Add Cron Job"
   - **URL**: `https://check-your-time.onrender.com/cron/health/`
   - **Schedule**: Every 10 minutes (`*/10 * * * *`)
   - **HTTP Method**: GET
   - Click "Save"

3. **Note**: Free tier is limited but sufficient for keep-alive

### Option 4: GitHub Actions (Free for Public Repos)

Create `.github/workflows/keep-alive.yml`:

```yaml
name: Keep Render Service Awake

on:
  schedule:
    - cron: '*/10 * * * *'  # Every 10 minutes
  workflow_dispatch:  # Allow manual trigger

jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Ping Health Endpoint
        run: |
          curl -f https://check-your-time.onrender.com/cron/health/ || exit 1
```

### Option 5: PythonAnywhere (Free tier available)

If you have a PythonAnywhere account:
1. Create a scheduled task
2. Run every 10 minutes: `curl https://check-your-time.onrender.com/cron/health/`

### Option 6: Upgrade Render Plan (Paid - Optional)

If you want to upgrade later:
- **Starter Plan**: $7/month - Services don't sleep, includes cron jobs
- **Standard Plan**: $25/month - Better performance

**But you don't need this!** The free options above work perfectly.

## Environment Variable Setup (Optional but Recommended)

For the scheduler jobs to work correctly in production, set this environment variable in Render:

1. **Go to Render Dashboard** → Your Service → Environment
2. **Add Environment Variable**:
   - **Key**: `RENDER_EXTERNAL_URL`
   - **Value**: `https://check-your-time.onrender.com`
3. **Save**

This allows the scheduler jobs (`fetch_id_only_job`, `process_id_only_job`, `keep_alive_job`) to use the correct URL in production instead of localhost.

**Note**: This is optional - the jobs will still work, but they'll try to call localhost URLs which won't work in production. Setting this variable fixes that.

## Health Check Endpoint

Your service already has a health check endpoint:
- **URL**: `https://check-your-time.onrender.com/cron/health/`
- **Method**: GET
- **Response**: `{"status": "success", "message": "Cron endpoint is working", "service": "active"}`

## Testing

Test your health endpoint:
```bash
curl https://check-your-time.onrender.com/cron/health/
```

Expected response:
```json
{
  "status": "success",
  "message": "Cron endpoint is working",
  "service": "active"
}
```

## Important Notes for FREE Plan Users

1. **Ping Frequency**: 
   - **Recommended**: Every 5-10 minutes
   - Render free services sleep after **15 minutes** of inactivity
   - Pinging every 10 minutes ensures it stays awake
   - UptimeRobot (5 minutes) is even better but uses more of your free quota

2. **Scheduler Jobs**: 
   - Your Django scheduler jobs will run normally when the service is awake
   - The external keep-alive ping ensures the service stays awake
   - **Important**: The internal keep-alive job in scheduler.py only works when service is already awake

3. **Cost**: 
   - ✅ **cron-job.org**: 100% FREE (unlimited jobs on free tier)
   - ✅ **UptimeRobot**: 100% FREE (50 monitors, 5-min intervals)
   - ✅ **EasyCron**: FREE tier available (1 job)
   - ✅ **GitHub Actions**: FREE for public repos
   - ❌ **Render Cron Jobs**: Paid plans only ($7+/month)

4. **Service URL**: 
   - **Your Render URL**: `https://check-your-time.onrender.com`
   - **Health Endpoint**: `https://check-your-time.onrender.com/cron/health/`

## Recommended Setup for FREE Plan

**Best approach**: Use **cron-job.org** (Option 1) because:
- ✅ 100% FREE (no credit card needed)
- ✅ Very easy to set up (2 minutes)
- ✅ Reliable and stable
- ✅ No external dependencies
- ✅ Works perfectly with Render free plan

**Alternative**: **UptimeRobot** (Option 2) if you also want uptime monitoring:
- ✅ FREE (50 monitors)
- ✅ 5-minute ping interval (keeps service very active)
- ✅ Bonus: Get alerts if your service goes down

## Troubleshooting

If your service still goes to sleep:
1. Check that the cron job is actually running (check logs)
2. Verify the URL is correct (no typos)
3. Make sure the health endpoint is accessible (test with curl)
4. Check Render service logs for any errors
5. Ensure cron job schedule is correct (every 10 minutes or less)

