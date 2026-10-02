#!/usr/bin/env python3
"""Optical-flow cross-dissolve worker for stitching AI video clips (needs cv2 + numpy only).

Why: a plain cross-dissolve between two clips of moving content shows DOUBLE images (two cranes, two trains,
doubled light trails). Warping both frames toward each other along optical flow inside the dissolve keeps one
crisp object. Measured on a 0.5 s overlap (future city -> forest dive): flow carried 85% of pixels, and a
full-res mid-frame crop showed one crane instead of two. Part of the user's stitching method:
  1. trim 2-3 extra frames off the end of clip A and the start of clip B (the model's deceleration zone),
  2. overlap 0.5-1 s,
  3. cross-dissolve with smoothstep weights,
  4. run each blended frame through this worker.

Usage: launch once as a subprocess and stream frames through it, so the main assembler can stay on a Python
without cv2:
  proc = subprocess.Popen([CV2_PYTHON, "flowblend_worker.py", "1920", "1080"], stdin=PIPE, stdout=PIPE)
  per frame:  proc.stdin.write(struct.pack("<d", w) + frameA_rgb24 + frameB_rgb24); proc.stdin.flush()
              out = proc.stdout.read(W * H * 3)
  w = smoothstep((t + 1) / (N + 1)) for t in range(N) overlap frames.

Algorithm: Farneback flow at 480x270 both ways, scaled up. A is warped forward by w*flow(A->B), B back by
(1-w)*flow(B->A), then mixed (1-w)*A' + w*B'. Pixels whose forward/backward flow disagree by more than 3 px
(occlusions, new content) fall back per pixel to a plain dissolve, so unreliable flow can't smear.
Cost: ~2 s CPU per 1080p frame on a 2-core box (7 seams x 12 frames ~ 3 min).
Judge results by eye on a full-res mid-overlap crop (plain vs flow side by side); edge-energy metrics barely move.
"""
import struct, sys
import numpy as np, cv2

W, H = int(sys.argv[1]), int(sys.argv[2])
FW, FH = 480, 270                       # flow is computed at quarter res, then scaled up
S = W / FW
GX, GY = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
gx, gy = np.meshgrid(np.arange(FW, dtype=np.float32), np.arange(FH, dtype=np.float32))
FB = dict(pyr_scale=0.5, levels=4, winsize=21, iterations=3, poly_n=5, poly_sigma=1.2, flags=0)


def small_gray(img):
    return cv2.cvtColor(cv2.resize(img, (FW, FH), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)


def blend(A, B, w):
    ga, gb = small_gray(A), small_gray(B)
    fab = cv2.calcOpticalFlowFarneback(ga, gb, None, **FB)
    fba = cv2.calcOpticalFlowFarneback(gb, ga, None, **FB)
    back = cv2.remap(fba, gx + fab[..., 0], gy + fab[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    err = np.sqrt(((fab + back) ** 2).sum(axis=2))              # forward-backward mismatch, small-res pixels
    conf = np.clip(1.0 - (err - 1.0) / 2.0, 0.0, 1.0)           # 1 below 1 px, 0 above 3 px
    Fab = cv2.resize(fab, (W, H)) * S
    Fba = cv2.resize(fba, (W, H)) * S
    conf = cv2.resize(conf, (W, H))[..., None]
    Aw = cv2.remap(A, GX - w * Fab[..., 0], GY - w * Fab[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    Bw = cv2.remap(B, GX - (1 - w) * Fba[..., 0], GY - (1 - w) * Fba[..., 1], cv2.INTER_LINEAR,
                   borderMode=cv2.BORDER_REPLICATE)
    Af, Bf = A.astype(np.float32), B.astype(np.float32)
    flow_mix = (1 - w) * Aw.astype(np.float32) + w * Bw.astype(np.float32)
    plain = (1 - w) * Af + w * Bf
    return (conf * flow_mix + (1 - conf) * plain).clip(0, 255).astype(np.uint8)


if __name__ == "__main__":
    inp, out = sys.stdin.buffer, sys.stdout.buffer
    N = W * H * 3
    while True:
        hdr = inp.read(8)
        if len(hdr) < 8:
            break
        w = struct.unpack("<d", hdr)[0]
        a = inp.read(N)
        b = inp.read(N)
        if len(b) < N:
            break
        A = np.frombuffer(a, np.uint8).reshape(H, W, 3)
        B = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        out.write(blend(A, B, w).tobytes())
        out.flush()
