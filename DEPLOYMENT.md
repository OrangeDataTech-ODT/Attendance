# Deployment Instructions

## Static Files Configuration

This project uses **WhiteNoise** to serve static files in production.

## Required Steps for Deployment

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Collect Static Files
**IMPORTANT**: You must run this command before deployment:
```bash
python manage.py collectstatic --noinput
```

This will collect all static files from `dj_app/static/` into `staticfiles/` directory.

### 3. Environment Variables
Make sure these are set in your deployment environment:
- `DJANGO_SECRET_KEY`
- `API_KEY_VALUE`
- `DEBUG` (set to `False` for production)
- `ALLOWED_HOSTS` (comma-separated list of your domain)
- `USE_INTERNAL_SCHEDULER` (set to `False` for Render free tier - see Scheduled Tasks section)
- `CRON_SECRET_TOKEN` (required for scheduled task endpoints - see Scheduled Tasks section)

### 4. For Render.com Deployment

Add this to your **Build Command**:
```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput
```

### 5. Verify Static Files

After deployment, check that these URLs work:
- `/static/dj_app/css/home_style.css`
- `/static/dj_app/js/home_main.js`
- `/static/dj_app/css/inout_style.css`
- `/static/dj_app/js/inout_main.js`
- `/static/dj_app/js/sidebar.js`

## Troubleshooting

If static files still return 404:

1. **Check if collectstatic ran**: Verify `staticfiles/` directory exists and contains files
2. **Check WhiteNoise middleware**: Should be right after `SecurityMiddleware`
3. **Check STATIC_ROOT**: Should point to `BASE_DIR / 'staticfiles'`
4. **Check STATIC_URL**: Should be `/static/`
5. **Restart the server** after running collectstatic

## Scheduled Tasks / Cron Jobs

### Problem: Render Free Tier Sleep Mode

On Render's free tier, services automatically spin down after 15 minutes of inactivity. This means the internal APScheduler won't work because the service isn't running when scheduled tasks need to execute.

### Solution: External Cron Jobs

We've created HTTP endpoints that can be called by external cron services. This way, the service wakes up when the cron job calls the endpoint, executes the task, and then can go back to sleep.

### Setup Instructions

#### Step 1: Configure Environment Variables

In your Render dashboard, add these environment variables:

1. **Disable Internal Scheduler:**
   ```
   USE_INTERNAL_SCHEDULER=False
   ```

2. **Set Cron Secret Token** (for security):
   ```
   CRON_SECRET_TOKEN=your-secret-token-here
   ```
   Generate a strong random token (e.g., using `openssl rand -hex 32`)

#### Step 2: Set Up Render Cron Jobs

Render provides a Cron Jobs feature. Here's how to set it up:

1. **Go to Render Dashboard** → Your Service → Cron Jobs
2. **Create 4 Cron Jobs** with the following schedules (IST timezone):

   **Job 1: Fetch Daily Punch Data at 11:00 AM IST**
   - Schedule: `0 11 * * *` (11:00 AM IST daily)
   - Command: 
     ```bash
     curl -X GET "https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=YOUR_CRON_SECRET_TOKEN"
     ```

   **Job 2: Fetch Daily Punch Data at 3:00 PM IST**
   - Schedule: `0 15 * * *` (3:00 PM IST daily)
   - Command:
     ```bash
     curl -X GET "https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=YOUR_CRON_SECRET_TOKEN"
     ```

   **Job 3: Fetch Daily Punch Data at 11:59 PM IST**
   - Schedule: `59 23 * * *` (11:59 PM IST daily)
   - Command:
     ```bash
     curl -X GET "https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=YOUR_CRON_SECRET_TOKEN"
     ```

   **Job 4: Cleanup Job Executions at Midnight IST**
   - Schedule: `0 0 * * *` (Midnight IST daily)
   - Command:
     ```bash
     curl -X GET "https://your-app.onrender.com/cron/cleanup-job-executions/?token=YOUR_CRON_SECRET_TOKEN"
     ```

   **Note:** Replace `YOUR_CRON_SECRET_TOKEN` with the actual token you set in environment variables.

#### Alternative: Using External Cron Services

If Render Cron Jobs aren't available on your plan, you can use external services:

**Option 1: cron-job.org (Free)**
1. Sign up at https://cron-job.org
2. Create cron jobs with the same schedules
3. Use the same curl commands as above

**Option 2: EasyCron (Free tier available)**
1. Sign up at https://www.easycron.com
2. Create cron jobs pointing to your endpoints

**Option 3: GitHub Actions (Free)**
Create a `.github/workflows/cron.yml` file:
```yaml
name: Scheduled Tasks

on:
  schedule:
    - cron: '0 5 * * *'  # 11:00 AM IST (UTC+5:30)
    - cron: '30 9 * * *'  # 3:00 PM IST
    - cron: '29 18 * * *' # 11:59 PM IST
    - cron: '30 18 * * *' # Midnight IST
  workflow_dispatch:

jobs:
  fetch-punch-data:
    runs-on: ubuntu-latest
    steps:
      - name: Call API
        run: |
          curl -X GET "https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=${{ secrets.CRON_SECRET_TOKEN }}"
```

### API Endpoints

The following endpoints are available for cron jobs:

1. **Fetch Daily Punch Data**
   - URL: `/cron/fetch-daily-punch-data/`
   - Method: `GET`
   - Authentication: Token via query parameter `?token=YOUR_TOKEN` or Bearer token in header

2. **Cleanup Job Executions**
   - URL: `/cron/cleanup-job-executions/`
   - Method: `GET`
   - Authentication: Token via query parameter `?token=YOUR_TOKEN` or Bearer token in header

### Testing the Endpoints

You can test the endpoints manually:

```bash
# Test fetch daily punch data
curl -X GET "https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=YOUR_CRON_SECRET_TOKEN"

# Test cleanup
curl -X GET "https://your-app.onrender.com/cron/cleanup-job-executions/?token=YOUR_CRON_SECRET_TOKEN"
```

### Troubleshooting

1. **401 Unauthorized Error:**
   - Check that `CRON_SECRET_TOKEN` is set correctly
   - Verify the token in the URL matches the environment variable

2. **Tasks Not Running:**
   - Check Render logs to see if cron jobs are executing
   - Verify the cron schedule is correct (Render uses UTC, so convert IST to UTC)
   - Check that `USE_INTERNAL_SCHEDULER=False` is set

3. **Service Not Waking Up:**
   - The first request after sleep may take 30-60 seconds (cold start)
   - This is normal for Render free tier

## File Structure

```
dj_project/
├── dj_app/
│   ├── static/
│   │   └── dj_app/
│   │       ├── css/
│   │       └── js/
│   ├── views/
│   │   └── scheduled_tasks_views.py  (new)
│   ├── urls/
│   │   └── scheduled_tasks_urls.py   (new)
│   └── templates/
│       └── dj_app/
├── staticfiles/  (created by collectstatic)
└── manage.py
```

