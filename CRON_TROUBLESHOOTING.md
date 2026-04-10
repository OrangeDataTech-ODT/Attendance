# Cron Job Troubleshooting Guide

## Common Issues and Solutions

### Issue 1: Cron Job Test Fails

If your cron job test fails on cron-job.org, check the following:

#### 1. Check the URL Format

Make sure you're using the correct URL format:

**Correct Format:**
```
https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=YOUR_CRON_SECRET_TOKEN
```

**Common Mistakes:**
- ❌ Missing `https://`
- ❌ Wrong path (should be `/cron/fetch-daily-punch-data/`)
- ❌ Missing trailing slash
- ❌ Token not included

#### 2. Verify Token Authentication

The endpoint requires a token. You can pass it in two ways:

**Option A: Query Parameter (Recommended for cron-job.org)**
```
https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=YOUR_TOKEN
```

**Option B: Bearer Token Header**
```
Authorization: Bearer YOUR_TOKEN
```

**To set up the token:**
1. Generate a secure token (e.g., using `openssl rand -hex 32`)
2. Add it to your Render environment variables as `CRON_SECRET_TOKEN`
3. Use the same token in your cron job URL

#### 3. Test the Health Check Endpoint First

Before testing the main endpoint, test the health check:

```
https://your-app.onrender.com/cron/health/
```

This endpoint doesn't require authentication and should return:
```json
{
  "status": "success",
  "message": "Cron endpoint is working",
  "service": "active"
}
```

If this fails, the issue is with your URL or service availability.

#### 4. Check Service Status

On Render free tier, the service might be sleeping. The first request after sleep can take 30-60 seconds. Make sure:

- Your cron job has a timeout of at least 60 seconds
- You're using the correct Render URL (check your Render dashboard)

#### 5. Check cron-job.org Settings

In cron-job.org, make sure:

1. **Request Method:** `GET` (not POST)
2. **URL:** Full URL with `https://`
3. **Timeout:** Set to at least 60 seconds
4. **Expected Status Code:** `200` (or leave blank)
5. **Follow Redirects:** Enabled (if your service redirects)

### Issue 2: 401 Unauthorized Error

If you get a 401 error:

1. **Check Environment Variable:**
   - Go to Render Dashboard → Your Service → Environment
   - Verify `CRON_SECRET_TOKEN` is set
   - Make sure there are no extra spaces or quotes

2. **Verify Token in URL:**
   - The token in the URL must match exactly
   - No URL encoding needed for simple tokens
   - If your token has special characters, URL encode them

3. **Test Without Token (Development Only):**
   - If `CRON_SECRET_TOKEN` is not set, the endpoint allows access (for development)
   - This is NOT recommended for production

### Issue 3: 500 Internal Server Error

If you get a 500 error, check:

1. **Check Render Logs:**
   - Go to Render Dashboard → Your Service → Logs
   - Look for error messages
   - The logs will show the actual error

2. **Common Causes:**
   - Database connection issues
   - Missing environment variables (e.g., `API_KEY_VALUE`)
   - External API failures
   - Timeout issues

3. **Check Response Body:**
   - The error response includes details
   - In DEBUG mode, you'll see full traceback
   - Check the `message` field for specific error

### Issue 4: Timeout Errors

If the cron job times out:

1. **Increase Timeout:**
   - In cron-job.org, set timeout to at least 120 seconds
   - Render free tier has cold starts (30-60 seconds)

2. **Check Command Execution Time:**
   - The `fetch_daily_punch_data` command might take time
   - Check how long it takes manually
   - Consider optimizing if it's too slow

3. **Use Async Processing:**
   - For long-running tasks, consider returning immediately
   - Process in background (future enhancement)

### Issue 5: Service Not Responding

If cron-job.org can't reach your service:

1. **Verify Service is Running:**
   - Check Render dashboard
   - Service should be "Live"
   - If sleeping, first request will wake it up

2. **Check URL:**
   - Verify the URL is correct
   - Test in browser first
   - Check for typos

3. **Check Firewall/Security:**
   - Render should allow external requests
   - Check if there are any IP restrictions

## Testing Steps

### Step 1: Test Health Check (No Auth Required)
```bash
curl https://your-app.onrender.com/cron/health/
```

Expected: `200 OK` with JSON response

### Step 2: Test with Token (Query Parameter)
```bash
curl "https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=YOUR_TOKEN"
```

Expected: `200 OK` with success message

### Step 3: Test with Bearer Token
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://your-app.onrender.com/cron/fetch-daily-punch-data/
```

Expected: `200 OK` with success message

### Step 4: Test Invalid Token
```bash
curl "https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=wrong_token"
```

Expected: `401 Unauthorized`

## cron-job.org Configuration

### Recommended Settings:

1. **Title:** Fetch Daily Punch Data
2. **URL:** `https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=YOUR_TOKEN`
3. **Schedule:** Custom (e.g., `0 11 * * *` for 11:00 AM IST)
4. **Request Method:** `GET`
5. **Timeout:** `120` seconds
6. **Expected Status Code:** `200`
7. **Follow Redirects:** `Yes`
8. **Save Response:** `Yes` (for debugging)

### Timezone Conversion

cron-job.org uses UTC. Convert IST to UTC:

- **11:00 AM IST** = `05:30 UTC` → Cron: `30 5 * * *`
- **3:00 PM IST** = `09:30 UTC` → Cron: `30 9 * * *`
- **11:59 PM IST** = `18:29 UTC` → Cron: `29 18 * * *`
- **Midnight IST** = `18:30 UTC` → Cron: `30 18 * * *`

**Note:** IST is UTC+5:30

## Debugging Tips

1. **Enable Logging:**
   - Check Render logs after each cron job run
   - Look for error messages

2. **Test Manually:**
   - Use curl or Postman to test endpoints
   - Verify responses before setting up cron

3. **Check Response:**
   - cron-job.org shows the response
   - Check if it's JSON or HTML error page
   - Look for error messages in response

4. **Monitor First Run:**
   - Watch Render logs during first cron execution
   - Check for cold start delays
   - Verify database connections

## Getting Help

If you're still having issues:

1. Check Render logs for detailed error messages
2. Test the endpoint manually with curl
3. Verify all environment variables are set
4. Check cron-job.org execution history
5. Review the response body from failed requests

## Example cron-job.org Setup

```
Title: Fetch Punch Data - 11 AM IST
URL: https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=abc123xyz
Schedule: 30 5 * * * (11:00 AM IST / 5:30 AM UTC)
Method: GET
Timeout: 120 seconds
Expected Status: 200
Follow Redirects: Yes
```

