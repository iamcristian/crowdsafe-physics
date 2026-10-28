"""Static clearance-aware grid routing to any reachable exit (SI units).

Eight-neighbor Dijkstra uses checked edges; steering shortcuts are also checked.
The grid is conservative and may reject passages near its resolution limit.
Routes minimize distance, not congestion or predicted travel time.
"""
import heapq
import numpy as np
from src.physics.geometry import wall_segments, segment_distances


class Router:
    def __init__(self, room, clearance, spacing=.25):
        self.room, self.clearance = room, clearance
        self.walls = wall_segments(room)
        self.spacing = spacing
        self.nx = int(np.ceil(room.width/spacing))+1
        self.ny = int(np.ceil(room.height/spacing))+1
        self.points = np.array([(x, y) for x in np.linspace(0, room.width, self.nx)
                                for y in np.linspace(0, room.height, self.ny)])
        self.free = self.clear(self.points)
        self.distance = np.full(len(self.points), np.inf)
        self.next = np.full(len(self.points), -1, dtype=int)
        self.targets = np.zeros_like(self.points)
        heap = []
        for i, p in enumerate(self.points):
            if not self.free[i]:
                continue
            for e in room.openings:
                axis = 0 if e.side in ('left', 'right') else 1
                boundary = (room.width if e.side == 'right' else room.height) if e.side in ('right', 'top') else 0
                if abs(p[axis]-boundary) > spacing*1.1 or abs(p[1-axis]-e.center) > e.width/2-clearance:
                    continue
                target = p.copy()
                target[axis] = boundary + (1 if e.side in ('right', 'top') else -1)
                if self.visible(p, target):
                    self.distance[i] = 0
                    self.targets[i] = target
                    heapq.heappush(heap, (0, i))
                    break
        while heap:
            cost, i = heapq.heappop(heap)
            if cost != self.distance[i]:
                continue
            x, y = divmod(i, self.ny)
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                xx, yy = x+dx, y+dy
                if not (0 <= xx < self.nx and 0 <= yy < self.ny):
                    continue
                j = xx*self.ny+yy
                candidate = cost + np.linalg.norm(self.points[j]-self.points[i])
                if self.free[j] and candidate < self.distance[j] and self.visible(self.points[i], self.points[j]):
                    self.distance[j], self.next[j] = candidate, i
                    self.targets[j] = self.targets[i]
                    heapq.heappush(heap, (candidate, j))

    def clear(self, points):
        distance, _, _ = segment_distances(points, self.walls)
        valid = np.all(distance >= self.clearance, axis=1)
        for pillar in self.room.pillars:
            valid &= np.linalg.norm(points-[pillar.x,pillar.y], axis=1) >= pillar.radius+self.clearance
        return valid

    def visible(self, a, b):
        # Distance is 1-Lipschitz: half the sample spacing bounds the
        # possible missed minimum between samples, including wall endpoints.
        samples = np.linspace(a, b, max(3, int(np.linalg.norm(b-a)/.02)+2))
        distance, _, _ = segment_distances(samples, self.walls)
        bound = np.linalg.norm(samples[1]-samples[0])/2
        if np.any(distance < self.clearance+bound):
            return False
        return all(np.all(np.linalg.norm(samples-[p.x,p.y],axis=1) >= p.radius+self.clearance+bound) for p in self.room.pillars)

    def waypoint(self, p):
        distances = np.linalg.norm(self.points-p, axis=1)
        candidates = np.flatnonzero((distances < self.spacing*2.5) & np.isfinite(self.distance))
        candidates = sorted(candidates, key=lambda i: distances[i]+self.distance[i])
        for i in candidates:
            if not self.visible(p, self.points[i]):
                continue
            if self.visible(p, self.targets[i]):
                return self.targets[i]
            target = self.points[i]
            for _ in range(12):
                j = self.next[i]
                if j < 0 or not self.visible(p, self.points[j]):
                    break
                target, i = self.points[j], j
            return target
        return None

    def directions(self, positions):
        result = np.zeros_like(positions)
        for i, p in enumerate(positions):
            target = self.waypoint(p)
            if target is not None:
                delta = target-p
                result[i] = delta/max(np.linalg.norm(delta), 1e-12)
        return result

    def cost(self, p):
        distances=np.linalg.norm(self.points-p,axis=1)
        candidates=np.flatnonzero((distances<self.spacing*2.5)&np.isfinite(self.distance))
        for i in sorted(candidates,key=lambda i:distances[i]+self.distance[i]):
            if self.visible(p,self.points[i]):
                return float(distances[i]+self.distance[i])
        return float('inf')
