"""Route optimization engine (Nearest Neighbour + 2-opt).

Solves the delivery-stop sequencing problem for a vehicle based at a hub:
minimise total distance of the tour hub -> stops -> hub.

This is a classical TSP-style heuristic pipeline:
  1. Nearest Neighbour construction  (fast, decent)
  2. 2-opt local search improvement  (removes crossings, ~10-25% gain)
"""

import math


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def route_length_km(depot, order, stops):
    """Total tour length depot -> stops(in `order`) -> depot."""
    pts = [depot] + [stops[i] for i in order] + [depot]
    total = 0.0
    for a, b in zip(pts, pts[1:]):
        total += haversine_km(a["lat"], a["lng"], b["lat"], b["lng"])
    return total


def nearest_neighbor(depot, stops):
    unvisited = set(range(len(stops)))
    cur = depot
    order = []
    while unvisited:
        best = min(unvisited, key=lambda i: haversine_km(
            cur["lat"], cur["lng"], stops[i]["lat"], stops[i]["lng"]))
        order.append(best)
        unvisited.remove(best)
        cur = stops[best]
    return order


def two_opt(depot, order, stops):
    order = list(order)
    improved = True
    while improved:
        improved = False
        for i in range(len(order) - 1):
            for j in range(i + 1, len(order)):
                cand = order[:i + 1] + order[i:j + 1][::-1] + order[j + 1:]
                if route_length_km(depot, cand, stops) < route_length_km(depot, order, stops) - 1e-9:
                    order = cand
                    improved = True
    return order


def optimize_route(depot, stops, speed_kmh=26.0, service_min=6.0):
    """Optimize stop sequence.

    depot : {"lat","lng"}           hub
    stops : list of {"lat","lng",...} in their CURRENT (given) order
    Returns dict with the optimized order (indices into `stops`), distances
    and time estimates before/after.
    """
    n = len(stops)
    base_order = list(range(n))
    d0 = route_length_km(depot, base_order, stops)

    if n <= 2:
        opt = base_order
    else:
        nn = nearest_neighbor(depot, stops)
        opt = two_opt(depot, nn, stops)

    d1 = route_length_km(depot, opt, stops)
    t0 = d0 / speed_kmh * 60 + n * service_min
    t1 = d1 / speed_kmh * 60 + n * service_min
    return {
        "order": opt,
        "stops": n,
        "km_before": round(d0, 2),
        "km_after": round(d1, 2),
        "km_saved": round(d0 - d1, 2),
        "pct_saved": round((d0 - d1) / d0 * 100, 1) if d0 else 0.0,
        "min_before": round(t0),
        "min_after": round(t1),
        "min_saved": round(t0 - t1),
    }
