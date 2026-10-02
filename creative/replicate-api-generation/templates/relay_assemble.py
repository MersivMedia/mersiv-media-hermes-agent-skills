#!/usr/bin/env python3
"""Relay-reel assembler, v1 (2026-09-29 "Pass It On" 60 s sizzle).
!! SUPERSEDED FOR VIDEO RETIMING. The user REJECTED the output: "pauses from the same frames
being shown twice", and 3 rough seams. Even-sampling clips into fixed slots repeated 134 frames,
and a hard cut on the shared keyframe still jumped at 3 seams. For the video path, follow
"Assembly" in references/match-cut-relay-transitions.md: native speed, trim H3's holds, a
best-match cut plus a 4-frame dissolve, and slowing CALM shots with minterpolate to fill the
runtime. The AUDIO half below (bed at exact BPM, SFX peaks on the cut times, loudnorm -14) and
the streaming Decoder are still good to reuse; place HITS on the ACTUAL cut times.
Copy into the project dir and edit SEQ / LOOK_ORDER / HITS / BED. Frame-exact and streaming, so
it fits in ~2 GB RAM at 1080p.

Video:
- Each clip is retimed to its slot by sampling frame indices evenly (first..last). This is
  frame-exact; setpts drifts by about a frame per clip.
- Frame 0 of every clip after the first is DROPPED: at a relay seam it duplicates the previous
  clip's last frame, and keeping it gives a visible hold. The measured seam PSNR afterwards
  was 29-39 dB, against a 27 dB median between neighbouring frames within a shot.
- The RAPID slot takes len(LOOK_ORDER) equal chunks from the look clips, over the BASE
  timeline, so the walk keeps moving forward across the outfit cuts.
- END = the last frame of the final shot, with a white logo/tagline mask
  (endcard/overlay_<variant>.png, a W x H 'L' image) fading in on a smoothstep.
- x264 CRF 17, yuv420p, 24 fps, 1920x1080. H3's own audio track is discarded.
Audio:
- The bed is stretched to the exact BPM (atempo = target/detected), started on a detected beat,
  ducked under a calm shot, and faded out under the end card.
- Impacts/risers are placed in code: each SFX is delayed so that ITS PEAK lands on the cut time.
- amix normalize=0, then loudnorm I=-14 TP=-1 (measured -14.3 LUFS integrated).
Harmless noise: "Broken pipe / Error muxing" lines from the decoders closed early after their
12 frames are read.
Verify the result with a reel-QC pass: the frame count, the seam PSNR before and after every
cut, and a contact sheet of the frame before and after each cut."""
import argparse, json, os, subprocess
import numpy as np
from PIL import Image
here = os.path.dirname(os.path.abspath(__file__)); V = os.path.join(here, "videos"); M = os.path.join(here, "music")
W, H, FPS = 1920, 1080, 24
# (clip id, seconds in the reel). "RAPID" = the look sequence; "END" = the end card.
SEQ = [("S1", 6.0), ("S2", 5.0), ("S3", 5.0), ("RAPID", 4.5), ("S5", 5.0), ("S6", 4.0), ("S7", 4.0),
       ("S8", 5.0), ("S9", 5.0), ("S10", 4.0), ("S11", 5.0), ("S12", 4.0), ("END", 3.5)]
LOOK_ORDER = ["L1", "L2", "L3", "L4", "L9", "L5", "L6", "L7", "L8"]
HITS = [6.0, 16.0, 25.5, 33.5, 47.5, 56.5]          # reel seconds where an impact's PEAK lands
RISER_PEAK_AT = 47.5
# tempo = target_bpm / detected_bpm; start = first detected beat (source seconds) / tempo
BED = dict(tempo=120 / 120.2, start=4.18 / (120 / 120.2), duck=(29.5, 33.5, 0.35), fade_out=(56.5, 3.5))
IMPACT_PEAK, RISER_PEAK = 0.18, 3.96                # seconds into each SFX file where it peaks

def nframes(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                        "stream=nb_read_frames", "-of", "csv=p=0", p], capture_output=True, text=True)
    return int(r.stdout.strip())

class Decoder:
    """Sequential frame reader; get(i) must be called with non-decreasing i."""
    def __init__(self, p):
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", p, "-vf", f"scale={W}:{H}:flags=lanczos",
                                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.j = -1; self.buf = None
    def get(self, idx):
        while self.j < idx:
            b = self.p.stdout.read(W * H * 3)
            if len(b) < W * H * 3: break
            self.buf = b; self.j += 1
        return self.buf
    def close(self):
        self.p.stdout.close(); self.p.kill(); self.p.wait()

def sample(n_src, n_out, drop_first):
    return np.round(np.linspace(1 if drop_first else 0, n_src - 1, n_out)).astype(int)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--variant", default="caps"); ap.add_argument("--out", default="reel_v1.mp4")
    a = ap.parse_args()
    vid = os.path.join(V, "_reel_video.mp4")
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                            "-pix_fmt", "yuv420p", vid], stdin=subprocess.PIPE)
    written = 0; last_shot = None
    for k, (sid, secs) in enumerate(SEQ):
        n_out = int(round(secs * FPS))
        if sid == "RAPID":
            idx = sample(nframes(os.path.join(V, "S4-base.mp4")), n_out, True); chunk = n_out // len(LOOK_ORDER)
            for s, lid in enumerate(LOOK_ORDER):
                d = Decoder(os.path.join(V, f"S4-{lid}.mp4"))
                for i in idx[s * chunk:(s + 1) * chunk]:
                    enc.stdin.write(d.get(int(i))); written += 1
                d.close()
        elif sid == "END":
            ov = Image.open(os.path.join(here, "endcard", f"overlay_{a.variant}.png")).convert("L").resize((W, H), Image.LANCZOS)
            ov = np.asarray(ov, np.float32)[..., None] / 255.0
            base = np.frombuffer(last_shot, np.uint8).reshape(H, W, 3).astype(np.float32)
            for f in range(n_out):
                t = min(1.0, max(0.0, (f - 6) / 30.0)); t = t * t * (3 - 2 * t)   # fade 0.25 s -> 1.5 s
                enc.stdin.write((base * (1 - ov * t) + 255.0 * ov * t).clip(0, 255).astype(np.uint8).tobytes()); written += 1
        else:
            p = os.path.join(V, f"{sid}.mp4"); n_src = nframes(p); d = Decoder(p)
            for i in sample(n_src, n_out, k > 0):
                enc.stdin.write(d.get(int(i))); written += 1
            last_shot = d.get(n_src - 1); d.close()
        print(f"{sid:<6} {n_out:>4} frames -> total {written}", flush=True)
    enc.stdin.close(); enc.wait()

    aud = os.path.join(V, "_reel_audio.m4a"); dur = written / FPS
    d0, d1, g = BED["duck"]; fo, fd = BED["fade_out"]
    vol = f"1-{1 - g}*min(1,max(0,(t-{d0 - 0.3})/0.3))*min(1,max(0,({d1}-t)/0.2))"
    fc = [f"[0:a]atempo={BED['tempo']:.5f},atrim=start={BED['start']:.3f},asetpts=PTS-STARTPTS,apad,"
          f"atrim=0:{dur},volume='{vol}':eval=frame,afade=t=out:st={fo}:d={fd}[bed]",
          f"[1:a]asplit={len(HITS)}" + "".join(f"[i{n}]" for n in range(len(HITS)))]
    fc += [f"[i{n}]adelay={int((h - IMPACT_PEAK) * 1000)}:all=1,volume=0.9[h{n}]" for n, h in enumerate(HITS)]
    fc.append(f"[2:a]adelay={int((RISER_PEAK_AT - RISER_PEAK) * 1000)}:all=1,volume=0.8[rs]")
    fc.append("[bed]" + "".join(f"[h{n}]" for n in range(len(HITS))) + f"[rs]amix=inputs={len(HITS) + 2}:normalize=0,"
              f"atrim=0:{dur},loudnorm=I=-14:TP=-1.0:LRA=11[out]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(M, "bed_v2.mp3"), "-i", os.path.join(M, "sfx_impact.mp3"),
                    "-i", os.path.join(M, "sfx_riser.mp3"), "-filter_complex", ";".join(fc), "-map", "[out]",
                    "-ar", "48000", "-c:a", "aac", "-b:a", "256k", aud], check=True)
    out = os.path.join(here, a.out)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", vid, "-i", aud, "-map", "0:v", "-map", "1:a", "-c", "copy",
                    "-shortest", "-movflags", "+faststart", out], check=True)
    json.dump(dict(frames=written, secs=dur, variant=a.variant), open(out + ".json", "w"), indent=1)
    print("DONE", out, written, "frames", dur, "s")

if __name__ == "__main__":
    main()
