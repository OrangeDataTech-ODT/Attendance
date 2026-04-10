# Quick Setup Guide for cron-job.org

## Step-by-Step Setup

### Step 1: Set Environment Variables in Render

1. Go to your Render Dashboard
2. Select your service
3. Go to **Environment** tab
4. Add these variables:

```
USE_INTERNAL_SCHEDULER=False
CRON_SECRET_TOKEN=your-secret-token-here
```

**Generate a secure token:**
```bash
# On Linux/Mac:
openssl rand -hex 32

# Or use any random string generator
```

### Step 2: Get Your Render URL

1. In Render Dashboard, go to your service
2. Copy the service URL (e.g., `https://your-app.onrender.com`)

### Step 3: Create Cron Job on cron-job.org

1. **Sign up/Login** at https://cron-job.org
2. Click **"Create cronjob"**
3. Fill in the form:

   **Title:** `Fetch Daily Punch Data`
   
   **Address (URL):** 
   ```
   https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=YOUR_CRON_SECRET_TOKEN
   ```
   *(Replace `YOUR_CRON_SECRET_TOKEN` with the token you set in Step 1)*
   
   **Schedule:** 
   - For every hour: `0 * * * *`
   - For 11 AM IST: `30 5 * * *` (5:30 AM UTC)
   - For 3 PM IST: `30 9 * * *` (9:30 AM UTC)
   - For 11:59 PM IST: `29 18 * * *` (6:29 PM UTC)
   
   **Request Method:** `GET`
   
   **Timeout:** `120` seconds
   
   **Expected Status Code:** `200`
   
   **Follow Redirects:** `Yes`

4. Click **"Create cronjob"**

### Step 4: Test the Cron Job

1. In cron-job.org, click on your cron job
2. Click **"Execute now"** or **"Test"**
3. Check the result:
   - ✅ **Success:** Status 200, response shows `"status": "success"`
   - ❌ **Failed:** Check the error message

### Step 5: Verify It's Working

1. **Check cron-job.org execution history:**
   - Go to your cron job
   - Click **"Executions"** tab
   - See if jobs are running successfully

2. **Check Render logs:**
   - Go to Render Dashboard → Your Service → Logs
   - Look for log entries when cron job runs
   - Should see: "Starting fetch_daily_punch_data via API endpoint"

## Common Issues

### ❌ Test Failed - 401 Unauthorized

**Problem:** Token is missing or incorrect

**Solution:**
1. Check that `CRON_SECRET_TOKEN` is set in Render environment variables
2. Verify the token in the URL matches exactly (no spaces, no quotes)
3. Test the health endpoint first (no auth required):
   ```
   https://your-app.onrender.com/cron/health/
   ```

### ❌ Test Failed - Connection Timeout

**Problem:** Service is sleeping or URL is wrong

**Solution:**
1. Verify your Render service URL is correct
2. Test the URL in a browser first
3. Increase timeout to 120 seconds in cron-job.org
4. The first request after sleep takes 30-60 seconds (cold start)

### ❌ Test Failed - 500 Internal Server Error

**Problem:** There's an error in the command execution

**Solution:**
1. Check Render logs for detailed error messages
2. Verify all required environment variables are set:
   - `API_KEY_VALUE`
   - `DJANGO_SECRET_KEY`
   - Database connection variables
3. Test the endpoint manually with curl:
   ```bash
   curl "https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=YOUR_TOKEN"
   ```

### ❌ Test Failed - 404 Not Found

**Problem:** URL path is incorrect

**Solution:**
1. Verify the URL path is exactly: `/cron/fetch-daily-punch-data/`
2. Make sure there's a trailing slash
3. Test the health endpoint: `/cron/health/`

## Testing Commands

### Test Health Check (No Auth Required)
```bash
curl https://your-app.onrender.com/cron/health/
```

### Test with Token
```bash
curl "https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=YOUR_TOKEN"
```

### Test with Bearer Token
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://your-app.onrender.com/cron/fetch-daily-punch-data/
```

## Schedule Examples

### Every Hour
```
0 * * * *
```

### Every 30 Minutes
```
*/30 * * * *
```

### Specific Times (IST to UTC conversion)
- **11:00 AM IST** = `30 5 * * *` (5:30 AM UTC)
- **3:00 PM IST** = `30 9 * * *` (9:30 AM UTC)
- **11:59 PM IST** = `29 18 * * *` (6:29 PM UTC)
- **Midnight IST** = `30 18 * * *` (6:30 PM UTC)

**Note:** IST is UTC+5:30

## Multiple Cron Jobs

Create separate cron jobs for different schedules:

1. **11 AM IST Job:**
   - Schedule: `30 5 * * *`
   - Same URL as above

2. **3 PM IST Job:**
   - Schedule: `30 9 * * *`
   - Same URL as above

3. **11:59 PM IST Job:**
   - Schedule: `29 18 * * *`
   - Same URL as above

4. **Cleanup Job (Midnight IST):**
   - URL: `https://your-app.onrender.com/cron/cleanup-job-executions/?token=YOUR_TOKEN`
   - Schedule: `30 18 * * *`

## Monitoring

1. **cron-job.org Dashboard:**
   - View execution history
   - See success/failure rates
   - Check response times

2. **Render Logs:**
   - Real-time logs during execution
   - Error messages and stack traces
   - Command output

3. **Email Notifications (cron-job.org):**
   - Enable email alerts for failures
   - Get notified when jobs fail

## Need More Help?

See `CRON_TROUBLESHOOTING.md` for detailed troubleshooting steps.

