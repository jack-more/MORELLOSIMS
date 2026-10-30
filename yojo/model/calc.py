import numpy as np, math
prof = [(0.0, 0.3), (0.0, 10.0), (0.4, 14.0), (1.3, 16.8), (2.86, 18.9), (4.53, 21.3), (6.2, 23.3), (7.9, 25.1), (9.5, 26.6),
        (11.2, 27.9), (12.9, 29.1), (14.6, 29.9), (16.2, 30.8), (17.9, 31.4), (19.6, 32.1), (21.3, 32.6), (24.6, 33.5), (27.9, 34.0),
        (31.3, 34.0), (34.6, 34.0), (38.0, 33.7), (41.3, 33.2), (44.7, 32.3), (48.0, 31.5), (51.4, 30.6), (54.7, 29.6), (58.1, 28.4),
        (61.4, 26.9), (64.7, 25.4), (67.2, 24.0), (69.0, 22.4), (70.1, 20.2), (70.55, 17.6), (70.45, 15.9)]
def catmull(points, n):
    P = np.array(points, float); P = np.vstack([P[0] * 2 - P[1], P, P[-1] * 2 - P[-2]]); out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2]); return np.array(out)
P = catmull([(r, z) for z, r in prof], 40)
seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = np.concatenate([[0], np.cumsum(seg)])
su = np.arange(0, s[-1], 0.1); Pu = np.stack([np.interp(su, s, P[:, 0]), np.interp(su, s, P[:, 1])], 1)
k = np.exp(-0.5 * (np.arange(-40, 41) / 12.0) ** 2); k /= k.sum(); pad = np.pad(Pu, ((40, 40), (0, 0)), mode='edge')
P = np.stack([np.convolve(pad[:, i], k, mode='valid') for i in range(2)], 1); P[:3] = Pu[:3]; P[-3:] = Pu[-3:]
pr, pz = P[:, 0], P[:, 1]
dr = np.gradient(pr); dz = np.gradient(pz); L = np.hypot(dr, dz) + 1e-12; nr, nz = dz / L, -dr / L
def revolve_volume(poly):
    p = np.asarray(poly, float); r, z = p[:, 0], p[:, 1]; r2, z2 = np.roll(r, -1), np.roll(z, -1)
    cross = r * z2 - r2 * z; A = cross.sum() / 2; cr = ((r + r2) * cross).sum() / (6 * A)
    return abs(2 * math.pi * A * cr)  # mm^3
outer = np.vstack([[[0, 0]], P, [[0, P[-1, 1]]]])
print('outer envelope volume ml', round(revolve_volume(outer) / 1000, 1), ' max dia', round(2 * pr.max(), 1), ' body height', round(pz.max(), 2))
si = np.stack([pr - 5.25 * nr, pz - 5.25 * nz], 1); si = si[si[:, 0] > 0.3]
bowl = si[si[:, 1] < 13.2]
w = np.vstack([[[0, bowl[0, 1]]], bowl, [[bowl[-1, 0], 13.2]], [[0, 13.2]]])
vw = revolve_volume(w)
print('weight: volume cc', round(vw / 1000, 2), ' steel g', round(vw / 1000 * 7.85, 0), ' zinc alloy g', round(vw / 1000 * 6.6, 0), ' max dia', round(2 * bowl[:, 0].max(), 1))
# skin volume: outer minus offset 3.5 (approx)
inn = np.stack([pr - 3.5 * nr, pz - 3.5 * nz], 1); inn = inn[(inn[:, 0] > 0.3)]
skin_v = revolve_volume(outer) - revolve_volume(np.vstack([[[0, inn[0, 1]]], inn, [[0, inn[-1, 1]]]]))
print('skin LSR g (approx)', round(skin_v / 1000 * 1.15, 0))
