from __future__ import annotations
import json

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    RICH = True
except ImportError:
    RICH = False

from trace import Tracer

def print_plan(plan: dict, tracer: Tracer):
    if RICH:
        _rich_print(plan, tracer)
    else:
        _plain_print(plan, tracer)

def _rich_print(plan: dict, tracer: Tracer):
    console = Console()
    console.print("\n")
    console.rule("[bold cyan]HACKATHON PLAN[/bold cyan]")

    venue = plan.get("venue", {}).get("selected", {})
    if venue:
        console.print(Panel(
            f"[bold]{venue.get('name', 'TBD')}[/bold]\n"
            f"Capacity : {venue.get('capacity', '?')} seats\n"
            f"Cost     : Rs {venue.get('cost_rs', 0):,}\n"
            f"Generator: {'Yes' if venue.get('has_generator') else 'No'}\n"
            f"Reason   : {venue.get('reason', '')}",
            title="[yellow]VENUE[/yellow]", border_style="yellow"))

    schedule_data = plan.get("schedule", {})
    schedule = schedule_data.get("schedule", [])
    if schedule:
        t = Table(title="SCHEDULE", box=box.SIMPLE, header_style="bold magenta")
        t.add_column("Time", style="cyan", width=8)
        t.add_column("Event")
        for item in schedule:
            t.add_row(item.get("time", ""), item.get("event", ""))
        console.print(t)

    food = plan.get("food", {})
    if food:
        console.print(Panel(
            f"Price per head : Rs {food.get('standard_price_per_head', 0):,} (standard)\n"
            f"Total headcount: {food.get('total_headcount', 0)} "
            f"({food.get('headcount_breakdown', {})})\n"
            f"Total food cost: Rs {food.get('recommended_total', 0):,}\n"
            f"Delivery       : {'Free' if food.get('delivery_free') else 'Charged'}",
            title="[green]FOOD[/green]", border_style="green"))

    judging = plan.get("judging", {})
    if judging:
        ok = judging.get("capacity_sufficient", False)
        console.print(Panel(
            f"Judges available : {judging.get('judges_available', 0)}\n"
            f"Teams to cover   : {judging.get('teams_to_cover', 0)}\n"
            f"Max teams/judge  : {judging.get('max_teams_per_judge', 0)}\n"
            f"Mins per team    : {judging.get('minutes_per_team', 0)}\n"
            f"Total judging    : {judging.get('total_judging_hours', 0)}h\n"
            f"Honorarium each  : Rs {judging.get('honorarium_per_judge', 0):,}\n"
            f"Total honorarium : Rs {judging.get('total_honorarium', 0):,}\n"
            f"Capacity OK      : {'YES' if ok else 'NO - PROBLEM'}",
            title="[blue]JUDGING[/blue]", border_style="blue" if ok else "red"))

    budget = plan.get("budget", {})
    if budget:
        within = budget.get("within_budget", False)
        t = Table(title="BUDGET", box=box.SIMPLE, header_style="bold")
        t.add_column("Item", style="white")
        t.add_column("Amount (Rs)", justify="right", style="cyan")
        for c in budget.get("fixed_costs", []):
            t.add_row(f"[fixed] {c['item']}", f"{c['amount']:,}")
        var = budget.get("variable_costs", {})
        t.add_row("[variable] venue", f"{var.get('venue', 0):,}")
        t.add_row("[variable] food", f"{var.get('food', 0):,}")
        t.add_row("[variable] honorarium", f"{var.get('honorarium', 0):,}")
        t.add_row("", "")
        t.add_row("[bold]TOTAL[/bold]", f"[bold]{budget.get('grand_total', 0):,}[/bold]")
        t.add_row("[bold]BUDGET[/bold]", f"[bold]{budget.get('total_budget', 0):,}[/bold]")
        remaining = budget.get("remaining", 0)
        color = "green" if remaining >= 0 else "red"
        t.add_row("[bold]REMAINING[/bold]",
                  f"[{color}][bold]{remaining:,}[/bold][/{color}]")
        console.print(t)
        if not within:
            console.print("[bold red]WARNING: Plan exceeds total budget![/bold red]")

    if tracer.rejected:
        t = Table(title="REJECTED MESSAGES", box=box.SIMPLE, header_style="bold red")
        t.add_column("MSG", width=5)
        t.add_column("From", width=25)
        t.add_column("Reason")
        for r in tracer.rejected:
            t.add_row(r.msg_id, r.sender, r.reason)
        console.print(t)

    console.rule("[bold]EXECUTION TRACE[/bold]")
    for e in tracer.entries:
        console.print(
            f"  [dim][{e.call_num}][/dim] [cyan]{e.area}[/cyan] | "
            f"model={e.model} | tokens={e.total_tokens} "
            f"(p={e.prompt_tokens} c={e.completion_tokens})")
    console.print(f"\n[bold]TOTAL TOKENS: {tracer.total_tokens()}[/bold]")
    console.print(f"[bold]TOTAL CALLS : {len(tracer.entries)}[/bold]\n")

def _plain_print(plan: dict, tracer: Tracer):
    print("\n" + "=" * 60)
    print("HACKATHON PLAN")
    print("=" * 60)
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    tracer.print_trace()