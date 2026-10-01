/* boot.js: start-up: first loads, onboarding check, routing, polling timers (runs last, after every function exists). Classic script; load order core, now, week, sessions, setup, onboarding, boot. */
loadView().then(() => { refreshSlow(); });
pollState(); loadHabits(); loadHealth(); startOnboarding();
addEventListener("hashchange", route); route();
setInterval(pollState, 1000);
setInterval(refreshSlow, 15000);
setInterval(loadHealth, 120000);
