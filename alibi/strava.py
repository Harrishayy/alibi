"""P5 — Strava runs -> events(source='strava', kind='activity').

  python -m alibi.strava exchange <code>   # once, after browser OAuth (see PLAN.md P5)
  python -m alibi.strava sync              # this week's activities
"""
# TODO (P5):
#   exchange(code): POST https://www.strava.com/oauth/token
#       {client_id, client_secret, code, grant_type: "authorization_code"} -> print refresh_token, paste into .env
#   access_token(): POST same URL with grant_type="refresh_token"
#   sync(): GET https://www.strava.com/api/v3/athlete/activities?after=<monday_epoch>&per_page=50
#       Authorization: Bearer <token>; keep type/sport_type == Run
#       add_event(con, "strava", "activity", {id, name, distance_km, moving_min, start_date}, ts=start epoch)
#       dedupe on activity id
