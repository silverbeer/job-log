# Parse Job Application Email

Parse a job application confirmation email and extract key information.

## What to Extract

From the email content provided, extract:
1. **Company name** - The company you applied to
2. **Job title** - The position you applied for
3. **Application date** - When the application was submitted (if mentioned)
4. **Application portal** - The ATS system used (Workday, Greenhouse, Lever, etc.)

## Common Email Patterns

### Workday
- Subject: "Your application was received" or "Application Confirmation"
- Body: "Thank you for applying to [Job Title] at [Company]"
- Body: "Your application for [Job Title] has been received"

### Greenhouse
- Subject: "Thanks for applying!" or "Application received"
- Body: "Thanks for your interest in [Company]!"
- Body: "We received your application for [Job Title]"

### Lever
- Subject: "Your application to [Company]"
- Body: "Thanks for applying to [Job Title] at [Company]"

### iCIMS / Workday-based
- Subject: "Application Received - [Job Title]"
- Body: "Thank you for your interest in [Company]"

### Generic Company Emails
- Look for patterns like "applied for", "application for", "interest in"
- Company name often in "at [Company]" or "with [Company]"

## Output Format

After parsing, provide:
```
Company: [extracted company name]
Job Title: [extracted job title or "Not specified"]
Application Date: [date or "Not specified"]
ATS System: [detected system or "Unknown"]
Confidence: [High/Medium/Low]
```

Then suggest the search command:
```bash
uv run python src/job_log/cli.py search "[company name]"
```
