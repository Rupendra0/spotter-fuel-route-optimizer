import math
import time

def test_grid():
    # Generate dummy 5000-point polyline from (40.7, -74.0) to (41.8, -87.6)
    n_pts = 5000
    coords = [
        [-74.0 + (i / n_pts) * (-87.6 - -74.0), 40.7 + (i / n_pts) * (41.8 - 40.7)]
        for i in range(n_pts)
    ]
    
    # 500 stations
    stations = [
        (40.7 + (i / 500) * (41.8 - 40.7) + 0.05, -74.0 + (i / 500) * (-87.6 - -74.0) + 0.05)
        for i in range(500)
    ]
    
    grid_size = 0.25
    grid = {}
    for i in range(len(coords) - 1):
        a_lon, a_lat = coords[i]
        b_lon, b_lat = coords[i + 1]
        min_gx = int(min(a_lon, b_lon) / grid_size)
        max_gx = int(max(a_lon, b_lon) / grid_size)
        min_gy = int(min(a_lat, b_lat) / grid_size)
        max_gy = int(max(a_lat, b_lat) / grid_size)
        for gx in range(min_gx, max_gx + 1):
            for gy in range(min_gy, max_gy + 1):
                cell = (gx, gy)
                if cell not in grid:
                    grid[cell] = []
                grid[cell].append(i)
                
    t0 = time.time()
    tested_segments = 0
    for s_lat, s_lon in stations:
        gx = int(s_lon / grid_size)
        gy = int(s_lat / grid_size)
        # Check cell and 8 neighbors
        candidate_segs = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                c = (gx + dx, gy + dy)
                if c in grid:
                    candidate_segs.update(grid[c])
        tested_segments += len(candidate_segs)
    t1 = time.time()
    print(f"500 stations indexed query time: {(t1 - t0)*1000:.2f} ms")
    print(f"Average candidate segments per station: {tested_segments / 500:.1f} vs 5000 unindexed")

test_grid()
