"""Parsing for DevTools "Export Timeline" files, which are Chrome Trace Event Format JSON."""


def load_trace_events(data: dict | list) -> list[dict]:
    """Normalizes a Chrome Trace Event Format payload into a flat list of event dicts.

    Accepts either a bare JSON array of events or an object with a "traceEvents" array (the two
    shapes DevTools' timeline export can produce).
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("traceEvents"), list):
        return data["traceEvents"]
    raise ValueError(
        "Not a recognizable Chrome Trace Event Format payload: expected a JSON array of "
        "events, or an object with a 'traceEvents' array."
    )
