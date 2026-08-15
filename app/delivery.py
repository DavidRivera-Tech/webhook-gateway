"""
Sends a webhook out to its target URL using httpx.

This is where OUR code makes an OUTGOING HTTP request (as opposed to receiving
one). Network calls are where things go wrong, so every failure mode is caught
and reported rather than allowed to crash the worker.
"""

import httpx


def deliver_event(target_url: str, payload: str) -> tuple[bool, str]:
    """
    Try to deliver one payload to one target URL.

    Returns (success, detail):
      - success: True if delivery worked, False otherwise.
      - detail:  a short human-readable note about what happened.
    """
    try:
        response = httpx.post(
            target_url,
            content=payload,
            headers={"Content-Type": "application/json"},
            timeout=5.0,
        )
        response.raise_for_status()
        return True, f"Delivered — target responded {response.status_code}"
    except httpx.TimeoutException:
        return False, "Failed — target timed out"
    except httpx.HTTPStatusError as e:
        return False, f"Failed — target responded {e.response.status_code}"
    except httpx.RequestError as e:
        return False, f"Failed — could not reach target ({type(e).__name__})"
