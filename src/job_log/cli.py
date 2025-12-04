"""CLI interface for job tracking."""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from typing import Optional
from pathlib import Path

from job_log.db import (
    init_db,
    add_job,
    apply_to_job,
    add_response,
    add_interview,
    update_status,
    set_application_url,
    update_applied_date,
    update_job,
    delete_job,
    get_job,
    get_events,
    get_activity,
    list_jobs,
    search_jobs,
    JobStatus,
)

app = typer.Typer(
    name="job",
    help="Track your job applications with ease.",
    no_args_is_help=True,
)
console = Console()


# Status colors for rich output
STATUS_COLORS = {
    "interested": "cyan",
    "applied": "yellow",
    "interviewing": "blue",
    "offered": "green",
    "rejected": "red",
    "withdrawn": "dim",
    "ghosted": "dim red",
}


def ensure_db():
    """Ensure the database is initialized."""
    init_db()


@app.command()
def add(
    company: str = typer.Argument(..., help="Company name"),
    title: str = typer.Argument(..., help="Job title"),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="Job posting URL (e.g. LinkedIn)"),
    location: Optional[str] = typer.Option(None, "--location", "-l", help="Job location"),
    salary: Optional[str] = typer.Option(None, "--salary", "-s", help="Salary range"),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="Job description"),
    ai: bool = typer.Option(False, "--ai", help="Mark as added by AI (e.g. from email scan)"),
):
    """Add a new job you're interested in."""
    ensure_db()

    job_id = add_job(
        company=company,
        title=title,
        posting_url=url,
        location=location,
        salary=salary,
        description=description,
        source="ai" if ai else "manual",
    )

    console.print(
        Panel(
            f"[bold green]Added job #{job_id}[/bold green]\n\n"
            f"[bold]{title}[/bold] at [cyan]{company}[/cyan]",
            title="Job Added",
            border_style="green",
        )
    )


@app.command()
def apply(
    job_id: int = typer.Argument(..., help="Job ID to mark as applied"),
    resume: Optional[Path] = typer.Option(None, "--resume", "-r", help="Path to resume file"),
    cover_letter: Optional[Path] = typer.Option(None, "--cover-letter", "-c", help="Path to cover letter"),
    app_url: Optional[str] = typer.Option(None, "--app-url", "-a", help="Application tracking URL (e.g. Workday)"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Application notes"),
    date: Optional[str] = typer.Option(None, "--date", "-d", help="Date applied (YYYY-MM-DD), defaults to today"),
):
    """Record that you applied to a job."""
    ensure_db()

    job = get_job(job_id)
    if not job:
        console.print(f"[red]Job #{job_id} not found[/red]")
        raise typer.Exit(1)

    resume_path = str(resume.resolve()) if resume else None
    cover_letter_path = str(cover_letter.resolve()) if cover_letter else None

    apply_to_job(
        job_id=job_id,
        resume_path=resume_path,
        cover_letter_path=cover_letter_path,
        application_url=app_url,
        notes=notes,
        applied_date=date,
    )

    console.print(
        Panel(
            f"[bold yellow]Applied to job #{job_id}[/bold yellow]\n\n"
            f"[bold]{job['title']}[/bold] at [cyan]{job['company']}[/cyan]",
            title="Application Recorded",
            border_style="yellow",
        )
    )


@app.command("app-url")
def app_url_cmd(
    job_id: int = typer.Argument(..., help="Job ID"),
    url: str = typer.Argument(..., help="Application tracking URL (e.g. Workday)"),
):
    """Set the application tracking URL for a job you've applied to."""
    ensure_db()

    job = get_job(job_id)
    if not job:
        console.print(f"[red]Job #{job_id} not found[/red]")
        raise typer.Exit(1)

    set_application_url(job_id=job_id, application_url=url)

    console.print(
        Panel(
            f"Application URL set for job #{job_id}\n\n"
            f"[bold]{job['title']}[/bold] at [cyan]{job['company']}[/cyan]\n"
            f"[underline blue]{url}[/underline blue]",
            title="Application URL Updated",
            border_style="yellow",
        )
    )


@app.command()
def update(
    job_id: int = typer.Argument(..., help="Job ID"),
    applied_date: Optional[str] = typer.Option(None, "--applied", "-a", help="Update applied date (YYYY-MM-DD)"),
    location: Optional[str] = typer.Option(None, "--location", "-l", help="Update location"),
    posting_url: Optional[str] = typer.Option(None, "--posting-url", "-p", help="Update job posting URL (e.g. LinkedIn)"),
):
    """Update fields on an existing job."""
    ensure_db()

    job = get_job(job_id)
    if not job:
        console.print(f"[red]Job #{job_id} not found[/red]")
        raise typer.Exit(1)

    if not applied_date and not location and not posting_url:
        console.print("[yellow]No updates specified. Use --applied, --location, or --posting-url.[/yellow]")
        raise typer.Exit(1)

    updates = []

    if location:
        update_job(job_id=job_id, location=location)
        updates.append(f"Location: [yellow]{location}[/yellow]")

    if posting_url:
        update_job(job_id=job_id, posting_url=posting_url)
        updates.append(f"Posting URL: [underline blue]{posting_url}[/underline blue]")

    if applied_date:
        updated = update_applied_date(job_id=job_id, applied_date=applied_date)
        if not updated:
            console.print(f"[red]Job #{job_id} has no applied event to update. Use 'apply' first.[/red]")
            raise typer.Exit(1)
        updates.append(f"Applied date: [yellow]{applied_date}[/yellow]")

    console.print(
        Panel(
            f"Updated job #{job_id}\n\n"
            f"[bold]{job['title']}[/bold] at [cyan]{job['company']}[/cyan]\n"
            + "\n".join(updates),
            title="Job Updated",
            border_style="green",
        )
    )


@app.command()
def delete(
    job_id: int = typer.Argument(..., help="Job ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a job and all its events."""
    ensure_db()

    job = get_job(job_id)
    if not job:
        console.print(f"[red]Job #{job_id} not found[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Delete '{job['title']}' at {job['company']}?")
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            raise typer.Exit(0)

    delete_job(job_id)
    console.print(
        Panel(
            f"Deleted job #{job_id}\n\n"
            f"[bold]{job['title']}[/bold] at [cyan]{job['company']}[/cyan]",
            title="Job Deleted",
            border_style="red",
        )
    )


@app.command()
def response(
    job_id: int = typer.Argument(..., help="Job ID"),
    interested: bool = typer.Option(True, "--interested/--rejected", "-i/-r", help="Whether they expressed interest"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Response details"),
):
    """Record a response from a company."""
    ensure_db()

    job = get_job(job_id)
    if not job:
        console.print(f"[red]Job #{job_id} not found[/red]")
        raise typer.Exit(1)

    add_response(job_id=job_id, interested=interested, notes=notes)

    if interested:
        console.print(
            Panel(
                f"[bold blue]Interest from {job['company']}![/bold blue]\n\n"
                f"[bold]{job['title']}[/bold]\n"
                f"Status updated to [blue]interviewing[/blue]",
                title="Response Recorded",
                border_style="blue",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold red]Rejection from {job['company']}[/bold red]\n\n"
                f"[bold]{job['title']}[/bold]",
                title="Response Recorded",
                border_style="red",
            )
        )


@app.command()
def interview(
    job_id: int = typer.Argument(..., help="Job ID"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Interview notes"),
):
    """Add interview notes for a job."""
    ensure_db()

    job = get_job(job_id)
    if not job:
        console.print(f"[red]Job #{job_id} not found[/red]")
        raise typer.Exit(1)

    add_interview(job_id=job_id, notes=notes)

    console.print(
        Panel(
            f"[bold blue]Interview recorded for job #{job_id}[/bold blue]\n\n"
            f"[bold]{job['title']}[/bold] at [cyan]{job['company']}[/cyan]",
            title="Interview Added",
            border_style="blue",
        )
    )


@app.command()
def status(
    job_id: int = typer.Argument(..., help="Job ID"),
    new_status: JobStatus = typer.Argument(..., help="New status"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Status change notes"),
):
    """Update the status of a job."""
    ensure_db()

    job = get_job(job_id)
    if not job:
        console.print(f"[red]Job #{job_id} not found[/red]")
        raise typer.Exit(1)

    update_status(job_id=job_id, status=new_status, notes=notes)

    color = STATUS_COLORS.get(new_status.value, "white")
    console.print(
        Panel(
            f"Status updated for job #{job_id}\n\n"
            f"[bold]{job['title']}[/bold] at [cyan]{job['company']}[/cyan]\n"
            f"New status: [{color}]{new_status.value}[/{color}]",
            title="Status Updated",
            border_style=color,
        )
    )


@app.command("list")
def list_cmd(
    status_filter: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
):
    """List all tracked jobs."""
    ensure_db()

    jobs = list_jobs(status=status_filter)

    if not jobs:
        console.print("[dim]No jobs found.[/dim]")
        return

    table = Table(
        title="Your Job Applications",
        box=box.ROUNDED,
        header_style="bold magenta",
    )
    table.add_column("ID", style="dim", width=4)
    table.add_column("Company", style="cyan")
    table.add_column("Title", style="bold")
    table.add_column("Location")
    table.add_column("Status")
    table.add_column("Src", width=3)
    table.add_column("Applied")
    table.add_column("Updated")

    for job in jobs:
        status_color = STATUS_COLORS.get(job["status"], "white")
        applied = job["applied_at"].strftime("%Y-%m-%d") if job["applied_at"] else "-"
        updated = job["updated_at"].strftime("%Y-%m-%d") if job["updated_at"] else "-"
        source = "[magenta]AI[/magenta]" if job.get("source") == "ai" else ""

        table.add_row(
            str(job["id"]),
            job["company"],
            job["title"],
            job["location"] or "-",
            f"[{status_color}]{job['status']}[/{status_color}]",
            source,
            applied,
            updated,
        )

    console.print(table)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search term (company or title)"),
    company_only: bool = typer.Option(False, "--company", "-c", help="Search company name only"),
    title_only: bool = typer.Option(False, "--title", "-t", help="Search job title only"),
    status_filter: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
):
    """Search for jobs by company or title."""
    ensure_db()

    if company_only:
        jobs = search_jobs(company=query, status=status_filter)
    elif title_only:
        jobs = search_jobs(title=query, status=status_filter)
    else:
        # Search both company and title
        company_matches = search_jobs(company=query, status=status_filter)
        title_matches = search_jobs(title=query, status=status_filter)
        # Combine and dedupe by ID
        seen_ids = set()
        jobs = []
        for job in company_matches + title_matches:
            if job["id"] not in seen_ids:
                seen_ids.add(job["id"])
                jobs.append(job)

    if not jobs:
        console.print(f"[dim]No jobs found matching '{query}'[/dim]")
        return

    table = Table(
        title=f"Search Results for '{query}'",
        box=box.ROUNDED,
        header_style="bold magenta",
    )
    table.add_column("ID", style="dim", width=4)
    table.add_column("Company", style="cyan")
    table.add_column("Title", style="bold")
    table.add_column("Location")
    table.add_column("Status")

    for job in jobs:
        status_color = STATUS_COLORS.get(job["status"], "white")
        table.add_row(
            str(job["id"]),
            job["company"],
            job["title"],
            job["location"] or "-",
            f"[{status_color}]{job['status']}[/{status_color}]",
        )

    console.print(table)


@app.command()
def show(
    job_id: int = typer.Argument(..., help="Job ID to show details for"),
):
    """Show detailed information about a job."""
    ensure_db()

    job = get_job(job_id)
    if not job:
        console.print(f"[red]Job #{job_id} not found[/red]")
        raise typer.Exit(1)

    events = get_events(job_id)

    # Job details panel
    status_color = STATUS_COLORS.get(job["status"], "white")

    details = Text()
    details.append(f"{job['title']}\n", style="bold")
    details.append(f"at {job['company']}\n\n", style="cyan")

    if job["location"]:
        details.append(f"Location: {job['location']}\n")
    if job["salary"]:
        details.append(f"Salary: {job['salary']}\n")
    if job["posting_url"]:
        details.append("Posting: ", style="dim")
        details.append(f"{job['posting_url']}\n", style="underline blue")
    if job["application_url"]:
        details.append("Application: ", style="dim")
        details.append(f"{job['application_url']}\n", style="underline blue")
    if job["description"]:
        details.append(f"\n{job['description']}\n")

    details.append(f"\nStatus: ", style="dim")
    details.append(f"{job['status']}", style=status_color)
    if job.get("source") == "ai":
        details.append("  (Added by AI)", style="magenta")

    console.print(Panel(details, title=f"Job #{job_id}", border_style=status_color))

    # Timeline
    if events:
        console.print("\n[bold]Timeline[/bold]")
        timeline_table = Table(box=box.SIMPLE, show_header=False)
        timeline_table.add_column("Date", style="dim")
        timeline_table.add_column("Event")
        timeline_table.add_column("Details")

        for event in events:
            date_str = event["event_date"].strftime("%Y-%m-%d %H:%M") if event["event_date"] else "-"
            event_type = event["event_type"]

            details_parts = []
            if event["notes"]:
                details_parts.append(event["notes"])
            if event["resume_path"]:
                details_parts.append(f"Resume: {event['resume_path']}")
            if event["cover_letter_path"]:
                details_parts.append(f"Cover Letter: {event['cover_letter_path']}")

            timeline_table.add_row(
                date_str,
                f"[bold]{event_type}[/bold]",
                "\n".join(details_parts) if details_parts else "-",
            )

        console.print(timeline_table)


@app.command()
def report(
    days: int = typer.Option(7, "--days", "-d", help="Number of days to include in report"),
):
    """Show activity report for the last N days."""
    ensure_db()

    activity = get_activity(days=days)

    # Header
    console.print(f"\n[bold]Activity Report - Last {days} Days[/bold]\n")

    # Summary stats
    summary = activity["summary"]
    total_added = len(activity["jobs_added"])
    total_applied = summary.get("applied", 0)
    total_interviews = summary.get("interview", 0)
    total_rejected = summary.get("rejected", 0)
    total_responses = summary.get("response", 0)

    stats_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    stats_table.add_column("Stat", style="dim")
    stats_table.add_column("Value", style="bold")

    stats_table.add_row("Jobs Added", f"[cyan]{total_added}[/cyan]")
    stats_table.add_row("Applications Sent", f"[yellow]{total_applied}[/yellow]")
    stats_table.add_row("Responses", f"[blue]{total_responses}[/blue]")
    stats_table.add_row("Interviews", f"[blue]{total_interviews}[/blue]")
    stats_table.add_row("Rejections", f"[red]{total_rejected}[/red]")

    console.print(Panel(stats_table, title="Summary", border_style="green"))

    # Jobs added
    if activity["jobs_added"]:
        console.print("\n[bold]Jobs Added[/bold]")
        jobs_table = Table(box=box.ROUNDED)
        jobs_table.add_column("ID", style="dim", width=4)
        jobs_table.add_column("Company", style="cyan")
        jobs_table.add_column("Title")
        jobs_table.add_column("Status")
        jobs_table.add_column("Src", width=3)
        jobs_table.add_column("Added")

        for job in activity["jobs_added"]:
            status_color = STATUS_COLORS.get(job["status"], "white")
            source = "[magenta]AI[/magenta]" if job.get("source") == "ai" else ""
            added = job["created_at"].strftime("%Y-%m-%d") if job["created_at"] else "-"

            jobs_table.add_row(
                str(job["id"]),
                job["company"],
                job["title"],
                f"[{status_color}]{job['status']}[/{status_color}]",
                source,
                added,
            )

        console.print(jobs_table)

    # Recent events (excluding 'added' since we show jobs added separately)
    other_events = [e for e in activity["events"] if e["event_type"] != "added"]
    if other_events:
        console.print("\n[bold]Activity Timeline[/bold]")
        events_table = Table(box=box.ROUNDED)
        events_table.add_column("Date", style="dim")
        events_table.add_column("Event")
        events_table.add_column("Company", style="cyan")
        events_table.add_column("Title")
        events_table.add_column("Notes")

        event_colors = {
            "applied": "yellow",
            "interview": "blue",
            "response": "blue",
            "rejected": "red",
            "offer": "green",
            "withdrawn": "dim",
        }

        for event in other_events:
            date_str = event["event_date"].strftime("%Y-%m-%d") if event["event_date"] else "-"
            event_type = event["event_type"]
            color = event_colors.get(event_type, "white")

            events_table.add_row(
                date_str,
                f"[{color}]{event_type}[/{color}]",
                event["company"],
                event["title"],
                event["notes"] or "-",
            )

        console.print(events_table)

    if not activity["jobs_added"] and not other_events:
        console.print("[dim]No activity in this period.[/dim]")


if __name__ == "__main__":
    app()
