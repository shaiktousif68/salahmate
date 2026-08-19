import requests, time, statistics, urllib3
urllib3.disable_warnings()

BASE = 'http://127.0.0.1:5000'
s = requests.Session()

# Login
s.post(BASE + '/login', data={'username': 'testuser', 'password': 'testpass'}, allow_redirects=True)

pages = ['Dashboard', 'Attendance', 'Salah', 'Calendar', 'Missed Salah', 'Quran', 'Reports']
paths = {
    'Dashboard': '/',
    'Attendance': '/attendance',
    'Salah': '/prayers',
    'Calendar': '/prayers/calendar',
    'Missed Salah': '/prayers/missed',
    'Quran': '/quran?view=surah',
    'Reports': '/reports',
}

# Measure server-side latency (ms) and page size (bytes; proxy for render weight)
server_times = {}
sizes = {}
for name, path in paths.items():
    t0 = time.perf_counter_ns()
    r = s.get(BASE + path, timeout=15)
    dt = (time.perf_counter_ns() - t0) / 1e6
    server_times.setdefault(name, []).append(dt)
    sizes[name] = len(r.content)
    print(f'{name:12s} {r.status_code} {dt:8.1f} ms  {len(r.content):8d} bytes')

print()
print('=== SLOWEST PAGES (server ms, higher=slower) ===')
for name, vals in sorted(server_times.items(), key=lambda kv: -statistics.mean(kv[1])):
    print(f'{name:12s} avg={statistics.mean(vals):7.1f} ms  (n={len(vals)})')