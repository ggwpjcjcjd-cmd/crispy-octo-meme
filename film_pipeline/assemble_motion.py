#!/usr/bin/env python3
"""Assemble seven genuine generated video clips into exactly sixty seconds.

Missing or short footage is an error. This pipeline never creates source
motion from stills, loops, holds, interpolation, or slowed footage. Every
output video frame comes from one native 24-fps input video frame.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
FPS, WIDTH, HEIGHT = 24, 1280, 720
MUSIC = ROOT / 'assets' / 'soundtrack.wav'
FONT = Path(os.environ.get('EARTHFILM_FONT', '/usr/share/fonts/truetype/open-sans/OpenSans-Light.ttf'))
OUTPUT = ROOT.parent / 'ziemia_motion.mp4'
SHOTS = [
    ('dinos', 10, '70 mln lat temu'),
    ('impact', 6, '66 mln lat temu'),
    ('logging', 8, '8 tys. lat temu'),
    ('settlement', 8, '8 tys. lat temu'),
    ('bridge', 10, 'Około 1500 roku'),
    ('industrial', 8, 'Około 1900 roku'),
    ('modern', 10, 'Dzisiaj'),
]
assert sum(s[1] for s in SHOTS) == 60


def probe(path: Path, *, count_frames: bool = False) -> dict:
    command = ['ffprobe', '-v', 'error', '-threads', '1']
    if count_frames:
        command.append('-count_frames')
    command += ['-show_streams', '-show_format', '-of', 'json', str(path)]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode:
        raise ValueError(f'Cannot decode {path}: {result.stderr.strip()}')
    return json.loads(result.stdout)


def fps_fraction(value: str | None) -> Fraction:
    try:
        return Fraction(value or '0/1')
    except (ValueError, ZeroDivisionError):
        return Fraction(0)


def validate_clip(shot: tuple[str, int, str]) -> dict:
    name, duration, date = shot
    path = ROOT.parent / 'motion_sources' / name / 'clip.mp4'
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f'{name}: missing or empty real video: {path}')
    review_path = path.parent / 'qa.json'
    if not review_path.is_file():
        raise ValueError(f'{name}: missing semantic review {review_path}; technical validity alone is insufficient')
    try:
        review = json.loads(review_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f'{name}: cannot read semantic approval: {error}') from error
    if review.get('approved') is not True:
        findings = review.get('findings') or ['No explicit semantic approval']
        reason = ' '.join(str(item) for item in findings[:3])
        raise ValueError(f'{name}: semantic review rejected this source: {reason}')
    source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    if review.get('sha256') != source_sha256:
        raise ValueError(f'{name}: semantic review does not match this video SHA-256; a replacement clip needs a new review')
    data = probe(path, count_frames=True)
    if 'mp4' not in data.get('format', {}).get('format_name', ''):
        raise ValueError(f'{name}: source must be an actual MP4 video, not an image')
    videos = [s for s in data.get('streams', []) if s.get('codec_type') == 'video']
    if len(videos) != 1:
        raise ValueError(f'{name}: expected one video stream, found {len(videos)}')
    video = videos[0]
    average = fps_fraction(video.get('avg_frame_rate'))
    nominal = fps_fraction(video.get('r_frame_rate'))
    if average != FPS or nominal != FPS:
        raise ValueError(
            f'{name}: native constant 24 fps required; avg={average}, nominal={nominal}. '
            'Refusing to duplicate/drop/interpolate frames or change playback speed.'
        )
    if int(video.get('width', 0)) < 2 or int(video.get('height', 0)) < 2:
        raise ValueError(f'{name}: invalid video dimensions')
    source_duration = float(video.get('duration') or data['format'].get('duration') or 0)
    if source_duration < duration - 1 / FPS - 0.000001:
        raise ValueError(f'{name}: only {source_duration:.6f}s; need {duration}s of real footage')
    try:
        frames = int(video['nb_read_frames'])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f'{name}: could not verify the decoded frame count') from error
    target = duration * FPS
    # Duration metadata may round by one frame. The decoded frame count must
    # nevertheless contain every required real frame; a 239-frame ten-second
    # clip cannot be completed by freezing its last frame.
    if frames < target:
        raise ValueError(
            f'{name}: {frames} decoded frames, need {target}. '
            'No loop, hold, slowdown, interpolation, or synthetic padding is allowed.'
        )
    return {
        'name': name, 'path': str(path), 'target_seconds': duration,
        'target_frames': target, 'native_frames': frames,
        'native_duration': source_duration, 'native_fps': str(average),
        'width': video['width'], 'height': video['height'], 'caption': date,
        'source_audio_used': False,
        'semantic_approved': True, 'semantic_review_path': str(review_path),
        'source_sha256': source_sha256,
    }


def validate_inputs() -> list[dict]:
    rows, errors = [], []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(validate_clip, shot) for shot in SHOTS]
        for shot, future in zip(SHOTS, futures):
            try:
                row = future.result()
                rows.append(row)
                print(f"{row['name']}: verified {row['native_frames']} native frames; "
                      f"use exactly {row['target_frames']}", flush=True)
            except (ValueError, OSError, json.JSONDecodeError) as error:
                errors.append(str(error))
    if not MUSIC.is_file() or MUSIC.stat().st_size == 0:
        errors.append(f'Missing soundtrack: {MUSIC}')
    else:
        try:
            audio = probe(MUSIC)
            audio_duration = float(audio.get('format', {}).get('duration') or 0)
            if audio_duration < 59.999:
                errors.append(f'Soundtrack is short: {audio_duration:.6f}s; need 60s')
            if not any(s.get('codec_type') == 'audio' for s in audio.get('streams', [])):
                errors.append('Soundtrack has no audio stream')
        except (ValueError, OSError, json.JSONDecodeError) as error:
            errors.append(str(error))
    if not FONT.is_file():
        errors.append(f'Missing caption font: {FONT}')
    report = {
        'status': 'blocked' if errors else 'ready', 'shots': rows,
        'errors': errors, 'required_frames': 1440, 'required_seconds': 60,
        'transition': 'hard cuts', 'native_audio_used': False,
        'semantic_action_review': 'Every source requires an explicit qa.json approved=true and matching source SHA-256, in addition to technical checks.',
    }
    (ROOT / 'motion_input_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    if errors:
        raise ValueError('Cannot assemble incomplete footage:\n- ' + '\n- '.join(errors))
    return rows


def build_filter(rows: list[dict], work: Path) -> Path:
    filters = []
    for index, row in enumerate(rows):
        datefile = work / f"date_{row['name']}.txt"
        datefile.write_text(row['caption'], encoding='utf-8')
        alpha = (
            "if(lt(t,0.35),0,if(lt(t,0.9),(t-0.35)/0.55,"
            "if(lt(t,3.3),1,if(lt(t,3.9),(3.9-t)/0.6,0))))"
        )
        # Native 24-fps frames are only trimmed and timestamped from zero.
        # At the verified native rate, setpts=N does not alter playback speed.
        # A slight aspect-preserving crop avoids stretching either LTX size.
        filters.append(
            f'[{index}:v]trim=start_frame=0:end_frame={row["target_frames"]},'
            f'settb=1/{FPS},setpts=N,'
            f'scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,'
            f'crop={WIDTH}:{HEIGHT},setsar=1,format=yuv420p,'
            f"drawtext=fontfile='{FONT}':textfile='{datefile}':"
            'fontsize=20:fontcolor=white@0.90:x=52:y=h-65:'
            f"alpha='{alpha}':shadowcolor=black@0.65:shadowx=1:shadowy=2[v{index}]"
        )
    filters.append(''.join(f'[v{i}]' for i in range(len(rows))) +
                   f'concat=n={len(rows)}:v=1:a=0[outv]')
    filters.append(
        f'[{len(rows)}:a]atrim=duration=60,asetpts=PTS-STARTPTS,'
        'afade=t=in:st=0:d=0.8,afade=t=out:st=58.2:d=1.8[outa]'
    )
    graph = work / 'motion.ffgraph'
    graph.write_text(';\n'.join(filters), encoding='utf-8')
    return graph


def render(rows: list[dict], output: Path) -> None:
    work = ROOT / 'motion_edit_cache'
    work.mkdir(exist_ok=True)
    graph = build_filter(rows, work)
    temporary = output.with_name(output.stem + '.partial.mp4')
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-nostats', '-y']
    for row in rows:
        command += ['-threads', '1', '-i', row['path']]
    command += ['-i', str(MUSIC), '-filter_complex_threads', '2',
                '-filter_complex_script', str(graph), '-map', '[outv]', '-map', '[outa]',
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                '-maxrate', '8M', '-bufsize', '16M', '-threads', '3',
                '-pix_fmt', 'yuv420p', '-r', str(FPS), '-fps_mode', 'cfr',
                '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-ac', '2',
                '-t', '60', '-movflags', '+faststart',
                '-metadata', 'title=Ziemia — przez miliony lat',
                '-metadata', 'comment=Seven genuine AI-generated moving video shots; hard-cut editorial montage.',
                '-progress', 'pipe:1', str(temporary)]
    logpath = work / 'assemble_motion.log'
    last_report = -1
    print('Rendering 1440 native-motion frames with hard cuts; source audio excluded.', flush=True)
    with logpath.open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        assert process.stdout is not None
        for line in process.stdout:
            log.write(line)
            log.flush()
            if line.startswith('out_time_us='):
                try:
                    seconds = int(line.partition('=')[2]) / 1_000_000
                    report = int(seconds // 5)
                except ValueError:
                    continue
                if report > last_report:
                    print(f'{min(seconds,60):.1f}/60 seconds encoded', flush=True)
                    last_report = report
        code = process.wait()
    if code:
        tail = '\n'.join(logpath.read_text(errors='replace').splitlines()[-35:])
        raise RuntimeError(f'FFmpeg failed with exit status {code}:\n{tail}')
    temporary.replace(output)


def verify_output(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f'Missing output: {path}')
    data = probe(path, count_frames=True)
    video = next(s for s in data['streams'] if s.get('codec_type') == 'video')
    audio = next(s for s in data['streams'] if s.get('codec_type') == 'audio')
    checks = {
        'dimensions_1280x720': (video['width'], video['height']) == (WIDTH, HEIGHT),
        'h264': video.get('codec_name') == 'h264',
        'yuv420p': video.get('pix_fmt') == 'yuv420p',
        'fps_24': fps_fraction(video.get('avg_frame_rate')) == FPS,
        'frames_1440': int(video.get('nb_read_frames', 0)) == 1440,
        'duration_60': abs(float(data['format']['duration']) - 60) < .00001,
        'aac_stereo_48khz': audio.get('codec_name') == 'aac' and
            audio.get('channels') == 2 and audio.get('sample_rate') == '48000',
        'below_90MB': path.stat().st_size < 90_000_000,
    }
    if not all(checks.values()):
        raise ValueError(f'Output validation failed: {json.dumps(checks)}')
    decoded = subprocess.run(
        ['ffmpeg', '-v', 'error', '-threads', '2', '-i', str(path), '-f', 'null', '-'],
        capture_output=True, text=True,
    )
    if decoded.returncode or decoded.stderr.strip():
        raise ValueError(f'Full decoding failed ({decoded.returncode}): {decoded.stderr.strip()}')
    report = {
        'status': 'passed', 'path': str(path), 'checks': checks,
        'size': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'video': video, 'audio': audio, 'format': data['format'],
        'full_decode_exit_status': decoded.returncode,
        'semantic_action_review': 'not established by technical validation',
    }
    (ROOT / 'final_motion_qa.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'QA passed: 60.000s, 1440 frames, 1280x720/24fps, '
          f'H.264/AAC, {path.stat().st_size/1048576:.1f} MiB', flush=True)
    print(f'SHA256: {report["sha256"]}', flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-inputs', action='store_true', help='Validate native input media; never render')
    parser.add_argument('--qa-only', action='store_true', help='Validate and fully decode an existing final output')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        if args.qa_only:
            verify_output(args.output)
            return
        rows = validate_inputs()
        if args.check_inputs:
            print('All seven genuine-video inputs and the 60-second soundtrack are ready.', flush=True)
            return
        render(rows, args.output)
        verify_output(args.output)
        print(f'Finished: {args.output}', flush=True)
    except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
