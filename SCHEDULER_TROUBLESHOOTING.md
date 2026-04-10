# Scheduler Troubleshooting Guide

## Why Scheduled Jobs (lines 165-190) May Not Work in Deployment

### Common Issues on Deployed Environments

#### 1. **Service Sleep Mode (Render Free Tier)**
**Problem**: On Render.com free tier, services automatically spin down after 15 minutes of inactivity. When the service is sleeping:
- The scheduler process is not running
- Scheduled jobs cannot execute
- The service only wakes up when it receives an HTTP request

**Solution**: Use external cron jobs to call HTTP endpoints instead of relying on the internal scheduler.

#### 2. **Multiple Worker Processes**
**Problem**: In production (especially with Gunicorn), multiple worker processes may start:
- Each worker tries to start its own scheduler instance
- This can cause conflicts, duplicate executions, or scheduler failures
- The scheduler may not start properly in worker processes

**Solution**: The code now includes safeguards to prevent multiple schedulers from starting, but for production, external cron jobs are more reliable.

#### 3. **Scheduler Not Starting**
**Problem**: The scheduler might fail to start silently due to:
- Database connection issues
- Missing dependencies
- Configuration errors
- Process initialization timing

**Solution**: Check logs for scheduler startup messages. The improved code now logs more information about scheduler status.

#### 4. **Timezone Issues**
**Problem**: The scheduler uses IST (Asia/Kolkata) timezone. If the server timezone is different:
- Jobs may run at incorrect times
- Timezone conversion issues

**Solution**: The code explicitly sets IST timezone, but verify your server's timezone settings.

## Solutions

### Option 1: Use External Cron Jobs (Recommended for Production)

This is the **most reliable** solution for deployed environments, especially on free tiers.

#### Setup Steps:

1. **Disable Internal Scheduler**
   Set environment variable:
   ```
   USE_INTERNAL_SCHEDULER=False
   ```

2. **Set Cron Secret Token**
   ```
   CRON_SECRET_TOKEN=your-secret-token-here
   ```

3. **Set Up External Cron Jobs**
   
   Use one of these services:
   - **cron-job.org** (Free): https://cron-job.org
   - **EasyCron** (Free tier): https://www.easycron.com
   - **Render Cron Jobs** (Paid plans only)
   - **GitHub Actions** (Free)

4. **Create Cron Jobs for Each Schedule**

   **Job 1: 11:00 AM IST**
   - URL: `https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=YOUR_TOKEN`
   - Schedule: `0 5 * * *` (UTC) or `0 11 * * *` (IST if service supports it)

   **Job 2: 3:00 PM IST**
   - URL: `https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=YOUR_TOKEN`
   - Schedule: `30 9 * * *` (UTC) or `0 15 * * *` (IST if service supports it)

   **Job 3: 11:59 PM IST**
   - URL: `https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=YOUR_TOKEN`
   - Schedule: `29 18 * * *` (UTC) or `59 23 * * *` (IST if service supports it)

### Option 2: Keep Service Awake + Internal Scheduler

If you want to use the internal scheduler, you need to keep the service awake.

#### Steps:

1. **Keep Internal Scheduler Enabled**
   ```
   USE_INTERNAL_SCHEDULER=True
   ```

2. **Set Up Keep-Alive Ping**
   Use an external service to ping your health endpoint every 10 minutes:
   - URL: `https://your-app.onrender.com/cron/health/`
   - Schedule: Every 10 minutes
   - Service: cron-job.org, UptimeRobot, etc.

3. **Monitor Scheduler Status**
   Check logs to verify scheduler started:
   ```
   "APScheduler started successfully with all jobs registered"
   ```

### Option 3: Upgrade to Paid Plan

If you're on Render.com:
- **Paid plans** don't have sleep mode
- Scheduler will work reliably
- No need for external cron jobs

## How to Verify Scheduler is Working

### Check Logs

Look for these log messages:

1. **Scheduler Starting:**
   ```
   "Attempting to start internal scheduler..."
   "Scheduled job: fetch_daily_punch_data_11am (11:00 AM IST)"
   "Scheduled job: fetch_daily_punch_data_3pm (3:00 PM IST)"
   "Scheduled job: fetch_daily_punch_data_1159pm (11:59 PM IST)"
   "APScheduler started successfully with all jobs registered"
   "Total jobs registered: 7"
   ```

2. **Job Execution:**
   ```
   "Starting scheduled fetch_daily_punch_data job"
   "Completed scheduled fetch_daily_punch_data job"
   ```

3. **Errors:**
   ```
   "Error starting scheduler: ..."
   "Scheduler failed to start. Consider using external cron jobs instead."
   ```

### Check Database

Query the Django APScheduler tables:
```python
from django_apscheduler.models import DjangoJob, DjangoJobExecution

# Check registered jobs
jobs = DjangoJob.objects.all()
for job in jobs:
    print(f"{job.id}: {job.name} - Next run: {job.next_run_time}")

# Check recent executions
executions = DjangoJobExecution.objects.order_by('-run_time')[:10]
for exec in executions:
    print(f"{exec.job_id}: {exec.run_time} - Status: {exec.status}")
```

### Test Manually

You can test the endpoints manually:
```bash
# Test fetch daily punch data
curl "https://your-app.onrender.com/cron/fetch-daily-punch-data/?token=YOUR_TOKEN"

# Test health check
curl "https://your-app.onrender.com/cron/health/"
```

## Debugging Steps

1. **Check Environment Variables**
   - `USE_INTERNAL_SCHEDULER` is set correctly
   - `CRON_SECRET_TOKEN` is set (if using external cron)

2. **Check Application Logs**
   - Look for scheduler startup messages
   - Check for errors during startup
   - Verify jobs are registered

3. **Check Service Status**
   - Is the service awake? (Check last request time)
   - Are there any errors in service logs?
   - Is the database accessible?

4. **Test Endpoints**
   - Manually call the cron endpoints
   - Verify authentication works
   - Check response status

5. **Verify Timezone**
   - Confirm server timezone
   - Verify IST timezone is correct
   - Check job next_run_time in database

## Recommended Configuration for Production

### For Render Free Tier:
```bash
USE_INTERNAL_SCHEDULER=False
CRON_SECRET_TOKEN=<strong-random-token>
```

Then use external cron jobs (cron-job.org) to call:
- `/cron/fetch-daily-punch-data/` at 11:00 AM, 3:00 PM, and 11:59 PM IST

### For Paid Plans or Always-On Services:
```bash
USE_INTERNAL_SCHEDULER=True
```

The internal scheduler will work reliably when the service is always running.

## Summary

**Why it's not working:**
- Service is sleeping (free tier)
- Multiple worker processes causing conflicts
- Scheduler not starting properly

**Best solution:**
- Use external cron jobs with HTTP endpoints
- Set `USE_INTERNAL_SCHEDULER=False`
- Use cron-job.org or similar service

**Alternative:**
- Keep service awake with ping service
- Use internal scheduler with `USE_INTERNAL_SCHEDULER=True`
- Monitor logs to verify it's working

