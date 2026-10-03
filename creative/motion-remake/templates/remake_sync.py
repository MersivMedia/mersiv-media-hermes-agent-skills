# remake_sync.py — deliverables from full-render frames out/full/o_fNNNN.png.
#   python3 remake_sync.py encode   -> out/remake_silent.mp4 (h264 BT.709 TV range) + out/remake.mp4 (muxed with out/mix.wav if present)
#   python3 remake_sync.py split    -> out/split_screen.mp4: REF left | OURS right, black labels (project.json label_left/right),
#                                      setsar=1 (or X stretches it). The post format.
#   python3 remake_sync.py stacked  -> out/sync_check.mp4: REF top / OURS bottom, frame-locked, for QA
# Encode checks the frame count. No -shortest on the silent encode. Adapted from howseen-ai/claude-motion-design (MIT).
import json
import subprocess
import sys
from pathlib import Path

H = Path.cwd()
P = json.loads((H / "project.json").read_text())
OUT, FULL, REF = H / "out", H / "out/full", H / "ref/reference.mp4"
FPS = str(P["fps"])
ENC = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "medium", "-colorspace", "bt709",
       "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", "-movflags", "+faststart"]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
mode = sys.argv[1]


def count(p):
    return int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                               "stream=nb_read_frames", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip())


if mode == "encode":
    n = len(list(FULL.glob("o_f*.png")))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", FPS, "-start_number", "0", "-i", str(FULL / "o_f%04d.png"),
                    "-vf", "scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p", *ENC,
                    str(OUT / "remake_silent.mp4")], check=True)
    got = count(OUT / "remake_silent.mp4")
    print(f"remake_silent.mp4: {got} frames ({'OK' if got == n else f'MISMATCH vs {n} PNGs'})")
    if (OUT / "mix.wav").exists():
        # no -shortest: the video defines the length. Warn if the mix is shorter (it would leave a silent tail).
        vd = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                   str(OUT / "remake_silent.mp4")], capture_output=True, text=True).stdout)
        ad = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                   str(OUT / "mix.wav")], capture_output=True, text=True).stdout)
        if abs(vd - ad) > 0.05:
            print(f"WARNING: mix.wav is {ad:.3f}s but the video is {vd:.3f}s: set sound.json dur to the film length")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(OUT / "remake_silent.mp4"), "-i", str(OUT / "mix.wav"),
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-t", f"{vd:.3f}",
                        "-movflags", "+faststart", str(OUT / "remake.mp4")], check=True)
        print("remake.mp4 (with mix.wav)")
elif mode == "split":
    L, R = P.get("label_left", "original"), P.get("label_right", "code remake")
    lab = lambda txt, x: (f"drawbox=x={x}:y=246:w={len(txt) * 14 + 24}:h=36:color=black@1:t=fill,"
                          f"drawtext=fontfile={FONT}:text='{txt}':x={x + 12}:y=253:fontsize=22:fontcolor=white")
    vf = (f"[0:v]fps={FPS},scale=880:-2,setsar=1,pad=920:496:0:0:0xF3F4F6[a];[1:v]scale=880:-2,setsar=1,pad=880:496:0:0:white[b];"
          "[a][b]hstack=inputs=2:shortest=1,pad=1920:1080:60:292:0xF3F4F6[s];"
          f"[s]{lab(L, 60)},{lab(R, 980)},setsar=1[v]")
    src = OUT / ("remake.mp4" if (OUT / "remake.mp4").exists() else "remake_silent.mp4")
    audio = ["-map", "1:a?", "-c:a", "aac", "-b:a", "256k"] if src.name == "remake.mp4" else []
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(REF), "-i", str(src), "-filter_complex", vf, "-map", "[v]",
                    *audio, *ENC, str(OUT / "split_screen.mp4")], check=True)
    print("split ->", OUT / "split_screen.mp4")
elif mode == "stacked":
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(REF), "-i", str(OUT / "remake_silent.mp4"), "-filter_complex",
                    f"[0:v]fps={FPS},scale=960:540,setsar=1[a];[1:v]scale=960:540,setsar=1[b];[a][b]vstack=inputs=2:shortest=1[v]",
                    "-map", "[v]", *ENC, str(OUT / "sync_check.mp4")], check=True)
    print("stacked ->", OUT / "sync_check.mp4")
else:
    sys.exit("modes: encode | split | stacked")
