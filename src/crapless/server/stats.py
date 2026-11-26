"""The public /stats page: totals since the last restart and nothing else."""

LABELS = {
    "tables_open": "Tables open",
    "players_connected": "Players connected",
    "tables_created": "Tables created",
    "joined": "Seats taken",
    "rolls": "Rolls",
    "rejected": "Requests rejected",
    "disconnects": "Disconnects",
    "errors": "Errors",
}


def page(stats: dict[str, int]) -> str:
    minutes = stats["uptime_seconds"] // 60
    hours, minutes = divmod(minutes, 60)
    rows = "".join(
        f"<tr><th>{label}</th><td>{stats[key]}</td></tr>" for key, label in LABELS.items()
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="light dark"><title>Crapless stats</title>'
        "<style>body{font-family:system-ui,sans-serif;margin:16px}"
        "th{text-align:left;font-weight:normal;padding:4px 24px 4px 0}td{text-align:right}</style>"
        "</head><body><h1>Crapless stats</h1>"
        f"<p>Since the server started, {hours} h {minutes} min ago.</p>"
        f"<table>{rows}</table></body></html>"
    )
