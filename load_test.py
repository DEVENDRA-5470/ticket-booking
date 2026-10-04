#!/usr/bin/env python3
"""
TicketFlow Load Lab
===================

A standalone, product-style load-test console for the TicketFlow API.

Default benchmark:
    10,000 users
    10 events
    20 target seats per event
    1 booking attempt per user
    500 concurrent booking requests

The tool deliberately does NOT belong in the TicketFlow application repo.
It creates real users and real bookings, so use a dedicated test dataset.

Install:
    python3 -m pip install flask requests

Run:
    python3 ticketflow_load_test.py

Open:
    http://127.0.0.1:5000
"""

from __future__ import annotations

import csv
import html
import json
import math
import os
import random
import statistics
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify, render_template_string, request, send_file


APP = Flask(__name__)
REPORT_DIR = Path(__file__).resolve().parent / "ticketflow_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

LOCK = threading.Lock()
STOP_EVENT = threading.Event()
RUN_THREAD: threading.Thread | None = None
THREAD_LOCAL = threading.local()

DEFAULTS = {
    "base_url": "http://34.0.5.74/api",
    "users": 10_000,
    "events": 10,
    "seats_per_event": 20,
    "booking_concurrency": 500,
    "registration_concurrency": 100,
    "timeout": 15.0,
    "scenario": "distributed",
    "email_domain": "example.com",
    "email_prefix": "ticketflow-load",
    "password": "LoadTest@2026!",
}

STATE: dict[str, Any] = {
    "running": False,
    "phase": "IDLE",
    "started_at": None,
    "finished_at": None,
    "config": {},
    "catalog": [],
    "registration": {
        "attempts": 0,
        "success": 0,
        "conflict": 0,
        "client_error": 0,
        "server_error": 0,
        "timeout": 0,
        "network_error": 0,
        "other_error": 0,
        "latencies_ms": [],
        "status_codes": Counter(),
        "duration_seconds": 0.0,
    },
    "booking": {
        "attempts": 0,
        "success": 0,
        "conflict": 0,
        "client_error": 0,
        "server_error": 0,
        "timeout": 0,
        "network_error": 0,
        "other_error": 0,
        "latencies_ms": [],
        "status_codes": Counter(),
        "event_stats": defaultdict(
            lambda: {
                "event_name": "",
                "attempts": 0,
                "success": 0,
                "conflict": 0,
                "errors": 0,
            }
        ),
        "failures_sample": [],
        "duration_seconds": 0.0,
    },
    "integrity": {
        "checked": False,
        "expected_success": 0,
        "actual_booked_seats": 0,
        "mismatches": [],
    },
    "users_prepared": 0,
    "report_json": None,
    "report_csv": None,
    "report_html": None,
    "error": None,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def reset_state(config: dict[str, Any]) -> None:
    with LOCK:
        STATE["running"] = True
        STATE["phase"] = "STARTING"
        STATE["started_at"] = time.time()
        STATE["finished_at"] = None
        STATE["config"] = dict(config)
        STATE["catalog"] = []
        STATE["registration"] = {
            "attempts": 0,
            "success": 0,
            "conflict": 0,
            "client_error": 0,
            "server_error": 0,
            "timeout": 0,
            "network_error": 0,
            "other_error": 0,
            "latencies_ms": [],
            "status_codes": Counter(),
            "duration_seconds": 0.0,
        }
        STATE["booking"] = {
            "attempts": 0,
            "success": 0,
            "conflict": 0,
            "client_error": 0,
            "server_error": 0,
            "timeout": 0,
            "network_error": 0,
            "other_error": 0,
            "latencies_ms": [],
            "status_codes": Counter(),
            "event_stats": defaultdict(
                lambda: {
                    "event_name": "",
                    "attempts": 0,
                    "success": 0,
                    "conflict": 0,
                    "errors": 0,
                }
            ),
            "failures_sample": [],
            "duration_seconds": 0.0,
        }
        STATE["integrity"] = {
            "checked": False,
            "expected_success": 0,
            "actual_booked_seats": 0,
            "mismatches": [],
        }
        STATE["users_prepared"] = 0
        STATE["report_json"] = None
        STATE["report_csv"] = None
        STATE["report_html"] = None
        STATE["error"] = None


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile_value / 100
    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return ordered[lower]

    return ordered[lower] + (
        ordered[upper] - ordered[lower]
    ) * (position - lower)


def latency_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {
            "avg_ms": 0.0,
            "min_ms": 0.0,
            "p50_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
            "max_ms": 0.0,
        }

    return {
        "avg_ms": statistics.mean(values),
        "min_ms": min(values),
        "p50_ms": percentile(values, 50),
        "p95_ms": percentile(values, 95),
        "p99_ms": percentile(values, 99),
        "max_ms": max(values),
    }


def safe_rate(success: int, attempts: int) -> float:
    return (success / attempts * 100) if attempts else 0.0


def get_session() -> requests.Session:
    """
    One persistent HTTP connection pool per worker thread.
    This is substantially more representative than creating a new
    TCP connection for every request.
    """
    session = getattr(THREAD_LOCAL, "session", None)

    if session is None:
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=100,
            pool_maxsize=100,
            max_retries=0,
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        THREAD_LOCAL.session = session

    return session


def api_request(
    method: str,
    url: str,
    *,
    timeout: float,
    **kwargs: Any,
) -> tuple[requests.Response | None, float | None, str | None]:
    started = time.perf_counter()

    try:
        response = get_session().request(
            method,
            url,
            timeout=timeout,
            **kwargs,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        return response, elapsed_ms, None

    except requests.Timeout:
        return None, None, "TIMEOUT"

    except requests.RequestException as exc:
        return None, None, f"NETWORK_ERROR: {exc}"


def classify_response(
    metrics: dict[str, Any],
    response: requests.Response | None,
    latency_ms: float | None,
    error: str | None,
) -> str:
    with LOCK:
        metrics["attempts"] += 1

        if latency_ms is not None:
            metrics["latencies_ms"].append(latency_ms)

        if response is not None:
            code = response.status_code
            metrics["status_codes"][str(code)] += 1

            if 200 <= code < 300:
                metrics["success"] += 1
                return "success"

            if code == 409:
                metrics["conflict"] += 1
                return "conflict"

            if 400 <= code < 500:
                metrics["client_error"] += 1
                return "client_error"

            if code >= 500:
                metrics["server_error"] += 1
                return "server_error"

            metrics["other_error"] += 1
            return "other_error"

        metrics["status_codes"][error or "UNKNOWN"] += 1

        if error == "TIMEOUT":
            metrics["timeout"] += 1
            return "timeout"

        if error and error.startswith("NETWORK_ERROR"):
            metrics["network_error"] += 1
            return "network_error"

        metrics["other_error"] += 1
        return "other_error"


def get_catalog(
    base_url: str,
    events_count: int,
    seats_per_event: int,
    timeout: float,
) -> list[dict[str, Any]]:
    response, _, error = api_request(
        "GET",
        f"{base_url}/v1/events/",
        timeout=timeout,
    )

    if response is None:
        raise RuntimeError(f"Cannot reach events API: {error}")

    response.raise_for_status()
    events = response.json()

    if len(events) < events_count:
        raise RuntimeError(
            f"Requested {events_count} events, but API returned {len(events)}."
        )

    catalog = []

    for event in events[:events_count]:
        event_id = event["id"]

        response, _, error = api_request(
            "GET",
            f"{base_url}/v1/seats/event/{event_id}",
            timeout=timeout,
        )

        if response is None:
            raise RuntimeError(
                f"Cannot read seats for event {event_id}: {error}"
            )

        response.raise_for_status()

        seats = response.json()
        available = [
            seat
            for seat in seats
            if seat.get("status") == "AVAILABLE"
        ]

        if len(available) < seats_per_event:
            raise RuntimeError(
                f"Event {event_id} ({event.get('name')}) has "
                f"{len(available)} available seats; "
                f"{seats_per_event} required."
            )

        catalog.append(
            {
                "event_id": event_id,
                "event_name": event.get(
                    "name",
                    f"Event {event_id}",
                ),
                "seats": available[:seats_per_event],
            }
        )

    return catalog


def register_user(
    base_url: str,
    index: int,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    email = (
        f"{config['email_prefix']}-{index:05d}"
        f"@{config['email_domain']}"
    )

    response, latency_ms, error = api_request(
        "POST",
        f"{base_url}/v1/auth/register",
        timeout=config["timeout"],
        json={
            "name": f"Load Test User {index:05d}",
            "email": email,
            "password": config["password"],
        },
    )

    classify_response(
        STATE["registration"],
        response,
        latency_ms,
        error,
    )

    with LOCK:
        STATE["registration"]["duration_seconds"] = (
            time.time() - STATE["started_at"]
        )

    if response is None or response.status_code != 201:
        return None

    try:
        body = response.json()
        return {
            "user_id": body["user_id"],
            "email": email,
            "token": body["access_token"],
        }
    except (ValueError, KeyError):
        return None


def choose_target(
    user_index: int,
    catalog: list[dict[str, Any]],
    scenario: str,
) -> dict[str, Any]:
    if scenario == "hotspot":
        return catalog[0]

    if scenario == "random":
        return random.choice(catalog)

    # distributed:
    # user 1..N is deterministically spread across events.
    return catalog[user_index % len(catalog)]


def book_user(
    user: dict[str, Any],
    user_index: int,
    catalog: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    target = choose_target(
        user_index,
        catalog,
        config["scenario"],
    )

    # One user makes exactly one booking attempt.
    # The seat is selected from the configured contention pool.
    seat = random.choice(target["seats"])

    response, latency_ms, error = api_request(
        "POST",
        f"{config['base_url']}/v1/bookings/",
        timeout=config["timeout"],
        headers={
            "Authorization": f"Bearer {user['token']}",
            "Content-Type": "application/json",
        },
        json={
            "event_id": target["event_id"],
            "seat_ids": [seat["id"]],
        },
    )

    classification = classify_response(
        STATE["booking"],
        response,
        latency_ms,
        error,
    )

    with LOCK:
        event_metrics = STATE["booking"]["event_stats"][
            target["event_id"]
        ]
        event_metrics["event_name"] = target["event_name"]
        event_metrics["attempts"] += 1

        if classification == "success":
            event_metrics["success"] += 1
        elif classification == "conflict":
            event_metrics["conflict"] += 1
        else:
            event_metrics["errors"] += 1

        if (
            classification not in {"success", "conflict"}
            and len(STATE["booking"]["failures_sample"]) < 100
        ):
            body = response.text[:500] if response is not None else ""
            STATE["booking"]["failures_sample"].append(
                {
                    "user_id": user["user_id"],
                    "event_id": target["event_id"],
                    "event_name": target["event_name"],
                    "seat_id": seat["id"],
                    "classification": classification,
                    "status_code": (
                        response.status_code
                        if response is not None
                        else error
                    ),
                    "latency_ms": latency_ms,
                    "response": body,
                }
            )

    return {
        "event_id": target["event_id"],
        "seat_id": seat["id"],
        "classification": classification,
    }


def verify_data_integrity(
    catalog: list[dict[str, Any]],
    config: dict[str, Any],
) -> None:
    expected_success = STATE["booking"]["success"]
    actual_booked = 0
    mismatches = []

    for target in catalog:
        response, _, error = api_request(
            "GET",
            f"{config['base_url']}/v1/seats/event/{target['event_id']}",
            timeout=config["timeout"],
        )

        if response is None or response.status_code != 200:
            mismatches.append(
                {
                    "event_id": target["event_id"],
                    "error": error
                    or f"HTTP {response.status_code}",
                }
            )
            continue

        seats = response.json()

        # Only inspect the target contention pool. Other seats may already
        # be booked by previous tests or normal application usage.
        target_ids = {seat["id"] for seat in target["seats"]}

        booked = sum(
            1
            for seat in seats
            if seat["id"] in target_ids
            and seat.get("status") == "BOOKED"
        )

        actual_booked += booked

        expected_event_success = (
            STATE["booking"]["event_stats"][target["event_id"]]["success"]
        )

        if booked != expected_event_success:
            mismatches.append(
                {
                    "event_id": target["event_id"],
                    "event_name": target["event_name"],
                    "expected_booked": expected_event_success,
                    "actual_booked": booked,
                }
            )

    with LOCK:
        STATE["integrity"] = {
            "checked": True,
            "expected_success": expected_success,
            "actual_booked_seats": actual_booked,
            "mismatches": mismatches,
        }


def build_snapshot() -> dict[str, Any]:
    with LOCK:
        started = STATE["started_at"]
        finished = STATE["finished_at"]
        now = finished or time.time()

        elapsed = (now - started) if started else 0.0
        booking = STATE["booking"]
        registration = STATE["registration"]

        booking_attempts = booking["attempts"]
        booking_latency = latency_summary(
            list(booking["latencies_ms"])
        )
        registration_latency = latency_summary(
            list(registration["latencies_ms"])
        )

        errors = (
            booking["client_error"]
            + booking["server_error"]
            + booking["timeout"]
            + booking["network_error"]
            + booking["other_error"]
        )

        return {
            "running": STATE["running"],
            "phase": STATE["phase"],
            "started_at": STATE["started_at"],
            "finished_at": STATE["finished_at"],
            "elapsed_seconds": elapsed,
            "config": {
                **STATE["config"],
                "password": "***",
            },
            "users_prepared": STATE["users_prepared"],
            "registration": {
                **{
                    k: v
                    for k, v in registration.items()
                    if k not in {"latencies_ms", "status_codes"}
                },
                "status_codes": dict(registration["status_codes"]),
                "latency": registration_latency,
                "success_rate": safe_rate(
                    registration["success"],
                    registration["attempts"],
                ),
            },
            "booking": {
                **{
                    k: v
                    for k, v in booking.items()
                    if k
                    not in {
                        "latencies_ms",
                        "status_codes",
                        "event_stats",
                        "failures_sample",
                    }
                },
                "status_codes": dict(booking["status_codes"]),
                "latency": booking_latency,
                "success_rate": safe_rate(
                    booking["success"],
                    booking_attempts,
                ),
                "throughput_rps": (
                    booking_attempts / booking["duration_seconds"]
                    if booking["duration_seconds"]
                    else 0.0
                ),
                "errors": errors,
                "event_stats": {
                    str(event_id): dict(stats)
                    for event_id, stats
                    in booking["event_stats"].items()
                },
            },
            "integrity": dict(STATE["integrity"]),
            "report_json": STATE["report_json"],
            "report_csv": STATE["report_csv"],
            "report_html": STATE["report_html"],
            "error": STATE["error"],
        }


def create_reports(
    catalog: list[dict[str, Any]],
) -> None:
    with LOCK:
        snapshot = build_snapshot()

        raw_report = {
            "report": {
                "name": "TicketFlow Load Lab Report",
                "generated_at_utc": now_utc(),
                "tool": "ticketflow_load_test.py",
            },
            "configuration": snapshot["config"],
            "catalog": [
                {
                    "event_id": x["event_id"],
                    "event_name": x["event_name"],
                    "target_seat_count": len(x["seats"]),
                    "target_seat_ids": [
                        seat["id"] for seat in x["seats"]
                    ],
                }
                for x in catalog
            ],
            "results": snapshot,
            "failure_sample": list(
                STATE["booking"]["failures_sample"]
            ),
        }

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = REPORT_DIR / f"ticketflow_{stamp}.json"
    csv_path = REPORT_DIR / f"ticketflow_{stamp}.csv"
    html_path = REPORT_DIR / f"ticketflow_{stamp}.html"

    json_path.write_text(
        json.dumps(raw_report, indent=2),
        encoding="utf-8",
    )

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.writer(file)

        writer.writerow(
            [
                "event_id",
                "event_name",
                "attempts",
                "success",
                "conflict_409",
                "errors",
            ]
        )

        for event_id, stats in snapshot["booking"][
            "event_stats"
        ].items():
            writer.writerow(
                [
                    event_id,
                    stats["event_name"],
                    stats["attempts"],
                    stats["success"],
                    stats["conflict"],
                    stats["errors"],
                ]
            )

        writer.writerow([])
        writer.writerow(["metric", "value"])

        booking = snapshot["booking"]

        writer.writerow(
            [
                "booking_success_rate_percent",
                booking["success_rate"],
            ]
        )
        writer.writerow(
            ["booking_throughput_rps", booking["throughput_rps"]]
        )

        for key, value in booking["latency"].items():
            writer.writerow([f"booking_{key}", value])

        writer.writerow(
            [
                "actual_booked_seats",
                snapshot["integrity"]["actual_booked_seats"],
            ]
        )
        writer.writerow(
            [
                "expected_successful_bookings",
                snapshot["integrity"]["expected_success"],
            ]
        )

    html_report = render_report_html(raw_report)
    html_path.write_text(
        html_report,
        encoding="utf-8",
    )

    with LOCK:
        STATE["report_json"] = json_path.name
        STATE["report_csv"] = csv_path.name
        STATE["report_html"] = html_path.name


def render_report_html(report: dict[str, Any]) -> str:
    results = report["results"]
    booking = results["booking"]
    registration = results["registration"]
    integrity = results["integrity"]

    event_rows = "".join(
        f"""
        <tr>
            <td>{html.escape(str(event_id))}</td>
            <td>{html.escape(str(stats["event_name"]))}</td>
            <td>{stats["attempts"]}</td>
            <td>{stats["success"]}</td>
            <td>{stats["conflict"]}</td>
            <td>{stats["errors"]}</td>
        </tr>
        """
        for event_id, stats in booking["event_stats"].items()
    )

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>TicketFlow Load Lab Report</title>
<style>
body {{
    margin: 0;
    background: #f4f7fb;
    color: #162033;
    font-family: Inter, Arial, sans-serif;
}}
main {{
    max-width: 1180px;
    margin: 40px auto;
    padding: 0 24px;
}}
header {{
    background: #111a2e;
    color: white;
    padding: 28px;
    border-radius: 16px;
}}
.grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin: 18px 0;
}}
.card {{
    background: white;
    border: 1px solid #dfe5ef;
    border-radius: 12px;
    padding: 18px;
}}
.value {{
    font-size: 28px;
    font-weight: 700;
    margin-top: 7px;
}}
.muted {{
    color: #68758a;
    font-size: 13px;
}}
.panel {{
    background: white;
    border: 1px solid #dfe5ef;
    border-radius: 12px;
    padding: 20px;
    margin: 18px 0;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th, td {{
    padding: 10px;
    border-bottom: 1px solid #e7ebf2;
    text-align: left;
}}
.ok {{ color: #14804a; font-weight: 700; }}
.bad {{ color: #c73737; font-weight: 700; }}
</style>
</head>
<body>
<main>
<header>
    <h1>TicketFlow Load Lab</h1>
    <div>Concurrent booking benchmark report</div>
    <div class="muted" style="color:#aeb9cc;margin-top:8px">
        Generated: {html.escape(report["report"]["generated_at_utc"])}
    </div>
</header>

<section class="grid">
    <div class="card">
        <div class="muted">Users prepared</div>
        <div class="value">{results["users_prepared"]:,}</div>
    </div>
    <div class="card">
        <div class="muted">Booking attempts</div>
        <div class="value">{booking["attempts"]:,}</div>
    </div>
    <div class="card">
        <div class="muted">Successful bookings</div>
        <div class="value">{booking["success"]:,}</div>
    </div>
    <div class="card">
        <div class="muted">409 conflicts</div>
        <div class="value">{booking["conflict"]:,}</div>
    </div>
</section>

<section class="grid">
    <div class="card">
        <div class="muted">Throughput</div>
        <div class="value">{booking["throughput_rps"]:.2f} req/s</div>
    </div>
    <div class="card">
        <div class="muted">P50</div>
        <div class="value">{booking["latency"]["p50_ms"]:.1f} ms</div>
    </div>
    <div class="card">
        <div class="muted">P95</div>
        <div class="value">{booking["latency"]["p95_ms"]:.1f} ms</div>
    </div>
    <div class="card">
        <div class="muted">P99</div>
        <div class="value">{booking["latency"]["p99_ms"]:.1f} ms</div>
    </div>
</section>

<section class="panel">
    <h2>Data Integrity</h2>
    <p>
        Expected successful bookings:
        <strong>{integrity["expected_success"]}</strong>
    </p>
    <p>
        Actual booked seats in target pools:
        <strong>{integrity["actual_booked_seats"]}</strong>
    </p>
    <p class="{"ok" if not integrity["mismatches"] else "bad"}">
        {"PASS — booking result matches seat state"
         if not integrity["mismatches"]
         else "FAIL — seat-state mismatches detected"}
    </p>
</section>

<section class="panel">
    <h2>Latency</h2>
    <table>
        <tr><th>Metric</th><th>Value</th></tr>
        <tr><td>Average</td><td>{booking["latency"]["avg_ms"]:.2f} ms</td></tr>
        <tr><td>Minimum</td><td>{booking["latency"]["min_ms"]:.2f} ms</td></tr>
        <tr><td>P50</td><td>{booking["latency"]["p50_ms"]:.2f} ms</td></tr>
        <tr><td>P95</td><td>{booking["latency"]["p95_ms"]:.2f} ms</td></tr>
        <tr><td>P99</td><td>{booking["latency"]["p99_ms"]:.2f} ms</td></tr>
        <tr><td>Maximum</td><td>{booking["latency"]["max_ms"]:.2f} ms</td></tr>
    </table>
</section>

<section class="panel">
    <h2>Per Event</h2>
    <table>
        <tr>
            <th>Event ID</th>
            <th>Event</th>
            <th>Attempts</th>
            <th>Success</th>
            <th>409</th>
            <th>Errors</th>
        </tr>
        {event_rows}
    </table>
</section>

<section class="panel">
    <h2>Registration Phase</h2>
    <p>
        {registration["success"]:,} successful registrations out of
        {registration["attempts"]:,} attempts.
    </p>
    <p>
        Average: {registration["latency"]["avg_ms"]:.2f} ms |
        P95: {registration["latency"]["p95_ms"]:.2f} ms |
        P99: {registration["latency"]["p99_ms"]:.2f} ms
    </p>
</section>

<section class="panel">
    <h2>HTTP Status Codes</h2>
    <pre>{html.escape(json.dumps(booking["status_codes"], indent=2))}</pre>
</section>

</main>
</body>
</html>
"""


def run_test(config: dict[str, Any]) -> None:
    try:
        with LOCK:
            STATE["phase"] = "CATALOG"

        catalog = get_catalog(
            config["base_url"],
            config["events"],
            config["seats_per_event"],
            config["timeout"],
        )

        with LOCK:
            STATE["catalog"] = catalog
            STATE["phase"] = "REGISTERING"

        users: list[dict[str, Any]] = []
        registration_started = time.perf_counter()

        with ThreadPoolExecutor(
            max_workers=config["registration_concurrency"]
        ) as executor:
            futures = {
                executor.submit(
                    register_user,
                    config["base_url"],
                    index,
                    config,
                ): index
                for index in range(1, config["users"] + 1)
            }

            for future in as_completed(futures):
                if STOP_EVENT.is_set():
                    break

                result = future.result()

                with LOCK:
                    STATE["users_prepared"] += 1

                if result is not None:
                    users.append(result)

        with LOCK:
            STATE["registration"]["duration_seconds"] = (
                time.perf_counter() - registration_started
            )

        if STOP_EVENT.is_set():
            raise RuntimeError("Test stopped by operator.")

        if len(users) != config["users"]:
            raise RuntimeError(
                f"Only {len(users):,} / {config['users']:,} users "
                "were authenticated. Booking phase aborted."
            )

        with LOCK:
            STATE["phase"] = "BOOKING_BURST"

        booking_started = time.perf_counter()

        # Submit the complete burst. ThreadPoolExecutor limits actual
        # in-flight requests while all users are queued immediately.
        with ThreadPoolExecutor(
            max_workers=config["booking_concurrency"]
        ) as executor:
            futures = [
                executor.submit(
                    book_user,
                    user,
                    index,
                    catalog,
                    config,
                )
                for index, user in enumerate(users)
            ]

            for future in as_completed(futures):
                if STOP_EVENT.is_set():
                    break

                future.result()

        with LOCK:
            STATE["booking"]["duration_seconds"] = (
                time.perf_counter() - booking_started
            )
            STATE["phase"] = "VERIFYING"

        verify_data_integrity(catalog, config)

        with LOCK:
            STATE["phase"] = "COMPLETED"

        create_reports(catalog)

    except Exception as exc:
        with LOCK:
            STATE["phase"] = "FAILED"
            STATE["error"] = str(exc)

    finally:
        with LOCK:
            STATE["running"] = False
            STATE["finished_at"] = time.time()


PAGE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TicketFlow Load Lab</title>
<style>
:root {
    --bg: #080d18;
    --panel: #101827;
    --panel2: #0c1422;
    --border: #22304a;
    --text: #edf3ff;
    --muted: #8492aa;
    --green: #37d99a;
    --red: #ff6b6b;
    --yellow: #f4c95d;
    --blue: #66a3ff;
}
* { box-sizing: border-box; }
body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif;
}
.shell {
    max-width: 1450px;
    margin: auto;
    padding: 28px;
}
.topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
}
.brand {
    display: flex;
    align-items: center;
    gap: 12px;
}
.logo {
    width: 42px;
    height: 42px;
    border-radius: 11px;
    display: grid;
    place-items: center;
    background: #18243a;
    border: 1px solid var(--border);
    font-weight: 800;
}
h1, h2, h3 { margin: 0; }
h1 { font-size: 24px; }
h2 { font-size: 16px; margin-bottom: 16px; }
.subtitle, .muted { color: var(--muted); }
.badge {
    padding: 7px 12px;
    border: 1px solid var(--border);
    border-radius: 999px;
    font-size: 12px;
    color: var(--muted);
}
.panel {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 18px;
}
.grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0,1fr));
    gap: 12px;
}
.kpis {
    display: grid;
    grid-template-columns: repeat(6, minmax(0,1fr));
    gap: 10px;
}
.kpi {
    background: var(--panel2);
    border: 1px solid var(--border);
    border-radius: 11px;
    padding: 15px;
}
.kpi .label {
    color: var(--muted);
    font-size: 12px;
}
.kpi .value {
    font-size: 23px;
    font-weight: 750;
    margin-top: 7px;
}
.field label {
    display: block;
    color: var(--muted);
    font-size: 12px;
    margin-bottom: 7px;
}
input, select {
    width: 100%;
    border: 1px solid #2a3a57;
    border-radius: 9px;
    padding: 11px 12px;
    background: #0a1220;
    color: var(--text);
    outline: none;
}
input:focus, select:focus {
    border-color: var(--blue);
}
.actions {
    display: flex;
    gap: 10px;
    margin-top: 18px;
}
button {
    border: 0;
    border-radius: 9px;
    padding: 11px 17px;
    font-weight: 700;
    cursor: pointer;
}
.primary { background: var(--green); color: #06140e; }
.danger { background: #a93645; color: white; }
.secondary { background: #1a2941; color: var(--text); }
button:disabled { opacity: .45; cursor: not-allowed; }
.notice {
    padding: 13px 15px;
    border-radius: 9px;
    background: #171b18;
    border: 1px solid #514b2a;
    color: #d8ca86;
    font-size: 13px;
    line-height: 1.5;
    margin-bottom: 18px;
}
.progress {
    height: 8px;
    border-radius: 999px;
    background: #172237;
    overflow: hidden;
}
.progress > div {
    height: 100%;
    width: 0%;
    background: var(--green);
    transition: width .2s;
}
.two {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 18px;
}
table {
    width: 100%;
    border-collapse: collapse;
}
th, td {
    padding: 10px 8px;
    border-bottom: 1px solid var(--border);
    text-align: left;
    font-size: 13px;
}
th { color: var(--muted); font-weight: 600; }
pre {
    background: #080e19;
    border: 1px solid var(--border);
    border-radius: 9px;
    padding: 13px;
    overflow: auto;
    max-height: 260px;
    color: #b9c7df;
}
.links a {
    color: #80b5ff;
    text-decoration: none;
    margin-right: 18px;
}
.ok { color: var(--green); }
.bad { color: var(--red); }
.warn { color: var(--yellow); }
@media(max-width:1100px) {
    .kpis { grid-template-columns: repeat(3,1fr); }
    .grid { grid-template-columns: repeat(2,1fr); }
}
@media(max-width:700px) {
    .kpis, .grid, .two { grid-template-columns: 1fr; }
    .shell { padding: 16px; }
}
</style>
</head>
<body>
<div class="shell">

<div class="topbar">
    <div class="brand">
        <div class="logo">TF</div>
        <div>
            <h1>TicketFlow Load Lab</h1>
            <div class="subtitle">Concurrent booking benchmark console</div>
        </div>
    </div>
    <div id="status" class="badge">IDLE</div>
</div>

<div class="notice">
    <strong>Real-data test.</strong>
    This tool creates real test users and real bookings. It changes seat state
    in the target database and does not perform automatic cleanup.
    Use a dedicated test dataset.
</div>

<section class="panel">
    <h2>Test Configuration</h2>
    <div class="grid">
        <div class="field">
            <label>API base URL</label>
            <input id="base_url" value="__BASE_URL__">
        </div>
        <div class="field">
            <label>Virtual users</label>
            <input id="users" type="number" value="10000" min="1" max="10000">
        </div>
        <div class="field">
            <label>Events</label>
            <input id="events" type="number" value="10" min="1" max="10">
        </div>
        <div class="field">
            <label>Target seats / event</label>
            <input id="seats" type="number" value="20" min="1" max="100">
        </div>
        <div class="field">
            <label>Booking concurrency</label>
            <input id="booking_concurrency" type="number" value="500" min="1" max="2000">
        </div>
        <div class="field">
            <label>Registration concurrency</label>
            <input id="registration_concurrency" type="number" value="100" min="1" max="500">
        </div>
        <div class="field">
            <label>Request timeout (seconds)</label>
            <input id="timeout" type="number" value="15" min="1" max="120">
        </div>
        <div class="field">
            <label>Traffic scenario</label>
            <select id="scenario">
                <option value="distributed">Distributed — 10 events</option>
                <option value="hotspot">Hotspot — one event</option>
                <option value="random">Random — all events</option>
            </select>
        </div>
        <div class="field">
            <label>Test email domain</label>
            <input id="email_domain" value="example.com">
        </div>
        <div class="field">
            <label>Test email prefix</label>
            <input id="email_prefix" value="ticketflow-load">
        </div>
    </div>
    <div class="actions">
        <button id="start" class="primary" onclick="startTest()">START BENCHMARK</button>
        <button id="stop" class="danger" onclick="stopTest()" disabled>STOP</button>
    </div>
</section>

<section class="panel">
    <h2>Execution</h2>
    <div id="phase" class="muted">Waiting for benchmark...</div>
    <div style="margin-top:10px" class="progress">
        <div id="progress"></div>
    </div>
    <div style="margin-top:9px" class="muted" id="progress_text">0%</div>
</section>

<section class="panel">
    <h2>Booking Results</h2>
    <div class="kpis">
        <div class="kpi"><div class="label">Attempts</div><div id="attempts" class="value">0</div></div>
        <div class="kpi"><div class="label">Success</div><div id="success" class="value">0</div></div>
        <div class="kpi"><div class="label">409 Conflict</div><div id="conflict" class="value">0</div></div>
        <div class="kpi"><div class="label">5xx</div><div id="server_error" class="value">0</div></div>
        <div class="kpi"><div class="label">Timeouts</div><div id="timeout" class="value">0</div></div>
        <div class="kpi"><div class="label">Throughput</div><div id="throughput" class="value">0 req/s</div></div>
    </div>
</section>

<section class="panel">
    <h2>Latency</h2>
    <div class="kpis">
        <div class="kpi"><div class="label">Average</div><div id="avg" class="value">0 ms</div></div>
        <div class="kpi"><div class="label">P50</div><div id="p50" class="value">0 ms</div></div>
        <div class="kpi"><div class="label">P95</div><div id="p95" class="value">0 ms</div></div>
        <div class="kpi"><div class="label">P99</div><div id="p99" class="value">0 ms</div></div>
        <div class="kpi"><div class="label">Minimum</div><div id="min" class="value">0 ms</div></div>
        <div class="kpi"><div class="label">Maximum</div><div id="max" class="value">0 ms</div></div>
    </div>
</section>

<div class="two">
<section class="panel">
    <h2>HTTP Status</h2>
    <pre id="codes">{}</pre>
</section>

<section class="panel">
    <h2>Data Integrity</h2>
    <div id="integrity" class="muted">Not checked yet.</div>
</section>
</div>

<section class="panel">
    <h2>Per Event</h2>
    <table>
        <thead>
            <tr>
                <th>Event</th>
                <th>Attempts</th>
                <th>Success</th>
                <th>409</th>
                <th>Errors</th>
            </tr>
        </thead>
        <tbody id="events"></tbody>
    </table>
</section>

<section class="panel">
    <h2>Reports</h2>
    <div id="reports" class="links muted">Reports will appear after completion.</div>
    <div id="error" class="bad" style="margin-top:12px"></div>
</section>

</div>

<script>
let timer = null;

const $ = id => document.getElementById(id);
const n = id => Number($(id).value);

function formatNumber(value) {
    return Number(value || 0).toLocaleString();
}

function formatMs(value) {
    return Number(value || 0).toFixed(1) + " ms";
}

async function startTest() {
    const payload = {
        base_url: $("base_url").value.trim(),
        users: n("users"),
        events: n("events"),
        seats_per_event: n("seats"),
        booking_concurrency: n("booking_concurrency"),
        registration_concurrency: n("registration_concurrency"),
        timeout: n("timeout"),
        scenario: $("scenario").value,
        email_domain: $("email_domain").value.trim(),
        email_prefix: $("email_prefix").value.trim()
    };

    const response = await fetch("/api/start", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    });

    const body = await response.json();

    if (!response.ok) {
        alert(body.error || "Unable to start benchmark");
        return;
    }

    $("start").disabled = true;
    $("stop").disabled = false;
    poll();
}

async function stopTest() {
    await fetch("/api/stop", {method: "POST"});
    $("stop").disabled = true;
}

function render(s) {
    $("status").textContent = s.phase;
    $("phase").textContent =
        s.phase + " · " + s.users_prepared.toLocaleString() +
        " / " + s.config.users.toLocaleString() + " users prepared";

    const users = Number(s.config.users || 1);
    const prepared = Number(s.users_prepared || 0);
    $("progress").style.width =
        Math.min(100, prepared / users * 100) + "%";
    $("progress_text").textContent =
        Math.min(100, prepared / users * 100).toFixed(1) + "%";

    const b = s.booking;

    $("attempts").textContent = formatNumber(b.attempts);
    $("success").textContent = formatNumber(b.success);
    $("conflict").textContent = formatNumber(b.conflict);
    $("server_error").textContent = formatNumber(b.server_error);
    $("timeout").textContent = formatNumber(b.timeout);
    $("throughput").textContent =
        Number(b.throughput_rps || 0).toFixed(2) + " req/s";

    $("avg").textContent = formatMs(b.latency.avg_ms);
    $("p50").textContent = formatMs(b.latency.p50_ms);
    $("p95").textContent = formatMs(b.latency.p95_ms);
    $("p99").textContent = formatMs(b.latency.p99_ms);
    $("min").textContent = formatMs(b.latency.min_ms);
    $("max").textContent = formatMs(b.latency.max_ms);

    $("codes").textContent =
        JSON.stringify(b.status_codes, null, 2);

    const integrity = s.integrity;

    if (integrity.checked) {
        if (integrity.mismatches.length === 0) {
            $("integrity").innerHTML =
                '<span class="ok">PASS</span> — ' +
                integrity.expected_success +
                ' successful booking responses match ' +
                integrity.actual_booked_seats +
                ' booked seats in the target pools.';
        } else {
            $("integrity").innerHTML =
                '<span class="bad">FAIL</span> — ' +
                integrity.mismatches.length +
                ' event-level mismatch(es) detected.';
        }
    } else {
        $("integrity").textContent = "Verification pending...";
    }

    const tbody = $("events");
    tbody.innerHTML = "";

    for (const [id, e] of Object.entries(b.event_stats || {})) {
        const row = document.createElement("tr");
        row.innerHTML =
            "<td>" + id + " · " + e.event_name + "</td>" +
            "<td>" + formatNumber(e.attempts) + "</td>" +
            "<td>" + formatNumber(e.success) + "</td>" +
            "<td>" + formatNumber(e.conflict) + "</td>" +
            "<td>" + formatNumber(e.errors) + "</td>";
        tbody.appendChild(row);
    }

    $("error").textContent = s.error || "";

    if (s.report_json) {
        $("reports").innerHTML =
            '<a href="/report/json" target="_blank">JSON</a>' +
            '<a href="/report/csv">CSV</a>' +
            '<a href="/report/html" target="_blank">HTML report</a>';
    }

    $("start").disabled = s.running;
    $("stop").disabled = !s.running;
}

async function poll() {
    try {
        const response = await fetch("/api/status");
        const state = await response.json();
        render(state);

        if (state.running) {
            timer = setTimeout(poll, 800);
        }
    } catch (error) {
        timer = setTimeout(poll, 1500);
    }
}

poll();
</script>
</body>
</html>
"""


@APP.get("/")
def index():
    return render_template_string(
        PAGE,
        BASE_URL=DEFAULTS["base_url"],
    )


@APP.post("/api/start")
def start_test():
    global RUN_THREAD

    with LOCK:
        if STATE["running"]:
            return jsonify({"error": "A benchmark is already running."}), 409

    payload = request.get_json(silent=True) or {}

    try:
        config = {
            "base_url": str(
                payload.get("base_url", DEFAULTS["base_url"])
            ).strip().rstrip("/"),
            "users": int(payload.get("users", DEFAULTS["users"])),
            "events": int(payload.get("events", DEFAULTS["events"])),
            "seats_per_event": int(
                payload.get(
                    "seats_per_event",
                    DEFAULTS["seats_per_event"],
                )
            ),
            "booking_concurrency": int(
                payload.get(
                    "booking_concurrency",
                    DEFAULTS["booking_concurrency"],
                )
            ),
            "registration_concurrency": int(
                payload.get(
                    "registration_concurrency",
                    DEFAULTS["registration_concurrency"],
                )
            ),
            "timeout": float(
                payload.get("timeout", DEFAULTS["timeout"])
            ),
            "scenario": str(
                payload.get("scenario", DEFAULTS["scenario"])
            ),
            "email_domain": str(
                payload.get(
                    "email_domain",
                    DEFAULTS["email_domain"],
                )
            ).strip(),
            "email_prefix": str(
                payload.get(
                    "email_prefix",
                    DEFAULTS["email_prefix"],
                )
            ).strip(),
            "password": DEFAULTS["password"],
        }

        if not config["base_url"]:
            raise ValueError("API base URL is required.")

        if not 1 <= config["users"] <= 10_000:
            raise ValueError("Users must be between 1 and 10,000.")

        if not 1 <= config["events"] <= 10:
            raise ValueError("Events must be between 1 and 10.")

        if not 1 <= config["seats_per_event"] <= 100:
            raise ValueError(
                "Target seats/event must be between 1 and 100."
            )

        if not 1 <= config["booking_concurrency"] <= 2_000:
            raise ValueError(
                "Booking concurrency must be between 1 and 2,000."
            )

        if not 1 <= config["registration_concurrency"] <= 500:
            raise ValueError(
                "Registration concurrency must be between 1 and 500."
            )

        if not 1 <= config["timeout"] <= 120:
            raise ValueError("Timeout must be between 1 and 120 seconds.")

        if config["scenario"] not in {
            "distributed",
            "hotspot",
            "random",
        }:
            raise ValueError("Invalid traffic scenario.")

        if not config["email_domain"]:
            raise ValueError("Email domain is required.")

        if not config["email_prefix"]:
            raise ValueError("Email prefix is required.")

        reset_state(config)
        STOP_EVENT.clear()

        RUN_THREAD = threading.Thread(
            target=run_test,
            args=(config,),
            name="ticketflow-load-test",
            daemon=True,
        )
        RUN_THREAD.start()

        return jsonify({"status": "started"})

    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@APP.post("/api/stop")
def stop_test():
    STOP_EVENT.set()

    with LOCK:
        if STATE["running"]:
            STATE["phase"] = "STOPPING"

    return jsonify({"status": "stop requested"})


@APP.get("/api/status")
def status():
    return jsonify(build_snapshot())


def report_file(key: str):
    with LOCK:
        filename = STATE[key]

    if not filename:
        return jsonify({"error": "Report is not available yet."}), 404

    return send_file(REPORT_DIR / filename)


@APP.get("/report/json")
def report_json():
    return report_file("report_json")


@APP.get("/report/csv")
def report_csv():
    return report_file("report_csv")


@APP.get("/report/html")
def report_html():
    return report_file("report_html")


if __name__ == "__main__":
    print("=" * 72)
    print("TicketFlow Load Lab")
    print("=" * 72)
    print("Dashboard : http://127.0.0.1:5000")
    print(f"Reports   : {REPORT_DIR}")
    print()
    print("Install:")
    print("  python3 -m pip install flask requests")
    print()
    print("This tool creates real users/bookings. Use a test database.")
    print("=" * 72)

    APP.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        threaded=True,
    )
