# Scan Gmail for Job Application Emails

Scan my Gmail for recent job application confirmation emails and automatically add them to my job log.

## Mode: Automatic (No Prompts)

Process all emails automatically:
- Add new jobs without asking
- Mark application confirmations as applied
- Only pause if company name cannot be determined with confidence

## Workflow

1. **Search for job application emails** using the Gmail MCP tools:
   - Search for emails with subjects containing:
     - Confirmations: "application received", "thank you for applying", "application confirmation", "we received your application"
     - LinkedIn: "your application was sent", "application was submitted"
     - Status updates: "application update", "application status", "regarding your application"
     - Rejections: "decided not to move forward", "other candidates", "not moving forward"
     - Interview-related: "interview", "next steps", "schedule a call", "like to schedule"
   - Look for emails from common ATS domains: workday, greenhouse, lever, icims, smartrecruiters, ashbyhq, successfactors, silkroad, linkedin.com
   - Focus on emails from the last 7 days

2. **For each email found**, extract:
   - Company name (check subject, body, AND sender email domain if not obvious)
   - Job title (if mentioned, use "Unknown Role" if not found)
   - Date of the email

3. **Search the job database** for existing matches:
   ```bash
   uv run python src/job_log/cli.py search "<company name>"
   ```

4. **Automatically process each email**:
   - If job already exists in database: skip (don't duplicate)
   - If new job: add it automatically
   - If application confirmation: also mark as applied
   - If rejection/status update for existing job: update status
   - **Only ask** if company name cannot be confidently determined

5. **Add new jobs** with the AI flag:
   ```bash
   uv run python src/job_log/cli.py add "<company>" "<title>" --ai
   ```

6. **For application confirmation emails**, also mark as applied:
   ```bash
   uv run python src/job_log/cli.py apply <job_id> --date "YYYY-MM-DD" --app-url "<url>" --notes "<notes>"
   ```

7. **For rejections**, update status:
   ```bash
   uv run python src/job_log/cli.py response <job_id> --rejected --notes "Rejection email received"
   ```

8. **Print a summary** at the end showing:
   - Jobs added
   - Jobs marked as applied
   - Jobs updated (rejections, status changes)
   - Jobs skipped (already in database)

## Email Pattern Recognition

- LinkedIn: "[Name], your application was sent to [Company]" - body contains title, location, applied date
- Workday: "Thank you for applying to [Title] at [Company]"
- Greenhouse: "Thanks for your interest in [Company]!"
- Lever: "Your application to [Company]"
- Generic: "We received your application for [Title]"
- Status updates: "[Company]: [Title] Application Update"
- Rejections: "decided not to move forward", "other candidates"
- Interview invites: "Interview for [Title]" - company may only be in sender email domain
- Direct from company: "[Company Name] <*@company.com>" (not via ATS)

When company name isn't in subject/body, extract it from the sender's email domain (e.g., megan@acme.com -> Acme)

## Detecting Application Confirmations
These email types indicate APPLIED status:
- "Thank you for applying", "Thanks for applying"
- "Application received", "We received your application"
- "Application confirmation"
- Emails from ATS systems (Workday, Greenhouse, Lever, iCIMS, etc.) confirming submission

## Extracting Application URLs
Look for these patterns in email bodies to populate `--app-url`:
- "View your application": extract the linked URL
- "Check your application status": extract the linked URL
- Links containing: `/application/`, `/candidate/`, `/status/`, `/profile/`
- Workday: links to `*.myworkday.com`
- Greenhouse: links to `*.greenhouse.io`
- Lever: links to `jobs.lever.co`
- iCIMS: links to `*.icims.com`
