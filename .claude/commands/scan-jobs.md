# Scan Gmail for Job Application Emails

Scan my Gmail for recent job application confirmation emails and help me match them to my job log.

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
   - Job title (if mentioned)
   - Date of the email

3. **Search the job database** for matches:
   ```bash
   uv run python src/job_log/cli.py search "<company name>"
   ```

4. **Present results to me** for each email:
   - Show the email subject and sender
   - Show the extracted company/title
   - Indicate if this is an application confirmation (triggers apply command)
   - Show any application tracking URLs found in the email
   - Show any matching jobs from the database
   - Ask if I want to:
     - Confirm a match (and mark as applied if confirmation email)
     - Skip this email
     - Add as a new job if no match exists (and mark as applied if confirmation email)

5. **Add new jobs** with the AI flag:
   ```bash
   uv run python src/job_log/cli.py add "<company>" "<title>" --ai
   ```

6. **For application confirmation emails**, also mark as applied:
   ```bash
   uv run python src/job_log/cli.py apply <job_id> --date "YYYY-MM-DD" --app-url "<url>" --notes "<notes>"
   ```
   - `--date`: Use the email date as the applied date
   - `--app-url`: Extract application tracking URLs from the email body (look for links to Workday portals, Greenhouse status pages, "view your application", "check status", etc.)
   - `--notes`: Include useful context like "Applied via [ATS name]" or any reference/confirmation numbers found in the email

7. **Update jobs** when I provide a URL:
   ```bash
   uv run python src/job_log/cli.py update <job_id> --posting-url "<url>"
   ```

## Notes
- Be conversational and process one email at a time
- If you can't determine the company name with confidence, show me the email content and ask
- Common email patterns to look for:
  - LinkedIn: "[Name], your application was sent to [Company]" - body contains title, location, applied date
  - Workday: "Thank you for applying to [Title] at [Company]"
  - Greenhouse: "Thanks for your interest in [Company]!"
  - Lever: "Your application to [Company]"
  - Generic: "We received your application for [Title]"
  - Status updates: "[Company]: [Title] Application Update"
  - Rejections: "decided not to move forward", "other candidates"
  - Interview invites: "Interview for [Title]" - NOTE: company may only be in sender email domain
  - Direct from company: "[Company Name] <*@company.com>" (not via ATS)
- When company name isn't in subject/body, extract it from the sender's email domain (e.g., megan@acme.com → Acme)

## Detecting Application Confirmations
These email types indicate the user has APPLIED and should trigger the `apply` command after adding:
- "Thank you for applying", "Thanks for applying"
- "Application received", "We received your application"
- "Application confirmation"
- Emails from ATS systems (Workday, Greenhouse, Lever, iCIMS, etc.) confirming submission

## Extracting Application URLs
Look for these patterns in email bodies to populate `--app-url`:
- "View your application": extract the linked URL
- "Check your application status": extract the linked URL
- "Your candidate portal": extract the linked URL
- Links containing: `/application/`, `/candidate/`, `/status/`, `/profile/`
- Workday: links to `*.myworkday.com`
- Greenhouse: links to `*.greenhouse.io` or `boards.greenhouse.io`
- Lever: links to `jobs.lever.co`
- iCIMS: links to `*.icims.com`

## Notes Field Examples
- "Applied via Workday"
- "Applied via Greenhouse"
- "Confirmation #12345"
- "Req ID: ABC-123"
