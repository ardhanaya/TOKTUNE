#!/usr/bin/env python3
"""
Lyrics Player - Command-line tool untuk menampilkan lirik dari file LRC dengan animasi realtime.

Usage:
    python play.py <file.lrc> <genre> [options]

(--- docstring as before ---)
"""
import re
import time
import sys
import os
import json
import platform
import argparse
from typing import Dict, List, Optional, Tuple

# Try import colorama for Windows ANSI support
try:
    import colorama
    colorama.init()
except Exception:
    colorama = None

# ============================================================================
# KONSTANTA WARNA TERMINAL
# ============================================================================
YELLOW = "\033[93m"
RED = "\033[91m"
GREEN = "\033[92m"
GRAY = "\033[90m"  # Dark gray / silver untuk loading (netral)
BOLD = "\033[1m"  # Bold text
DIM = "\033[2m"   # Dim / reduced brightness
RESET = "\033[0m"

# ============================================================================
# KONFIGURASI DEFAULT (fallback jika PyYAML tidak tersedia)
# ============================================================================

DEFAULT_CONFIG = {
    "wrap_width": 48,
    "margin_between_lines": 0.15,
    "block_margin": 0.4,
    "auto_close_seconds": 5.0,
    "loading_opening": 300,
    "loading_ending": 300,
    "lrc_start_minute": 0,
    "lrc_start_second": 0,
    "show_time_display": True,
    "default_genre": "hiphop",
    "genres": {
        "rnb_soul": {
            "color": "\033[95m",
            "speed": 0.035,
            "effect": "smooth_fade",
            "description": "R&B / Soul — smooth, warm, slow fade-in"
        },
        "jazz": {
            "color": "\033[94m",
            "speed": 0.06,
            "effect": "swing",
            "description": "Jazz — swing timing, subtle wander"
        },
        "blues": {
            "color": "\033[34m",
            "speed": 0.055,
            "effect": "wave",
            "description": "Blues — slow, mournful wave"
        },
        "childrens": {
            "color": "\033[96m",
            "speed": 0.045,
            "effect": "bounce",
            "description": "Children's — playful bounce and bright color"
        },
        "classical": {
            "color": "\033[97m",
            "speed": 0.085,
            "effect": "elegant_fade",
            "description": "Classical — slow and stately"
        },
        "country": {
            "color": "\033[33m",
            "speed": 0.05,
            "effect": "typewriter",
            "description": "Country — clear typewriter style"
        },
        "easy_listening": {
            "color": "\033[37m",
            "speed": 0.065,
            "effect": "smooth",
            "description": "Easy Listening — mellow and unobtrusive"
        },
        "electronic": {
            "color": "\033[96m",
            "speed": 0.01,
            "effect": "glitch",
            "description": "Electronic — fast, glitchy, bright"
        },
        "folk_world": {
            "color": "\033[92m",
            "speed": 0.05,
            "effect": "vibrate",
            "description": "Folk / World — organic, gentle vibrato"
        },
        "hiphop": {
            "color": "\033[93m",
            "speed": 0.012,
            "effect": "shake",
            "description": "Hip Hop — smooth, rhythmic, punchy"
        },
        "rap": {
            "color": "\033[91m",
            "speed": 0.008,
            "effect": "heavy_shake",
            "description": "Rap — fast, aggressive, intense"
        },
        "holiday_religious": {
            "color": "\033[33m",
            "speed": 0.04,
            "effect": "glow",
            "description": "Holiday / Religious — warm glow"
        },
        "latin": {
            "color": "\033[91m",
            "speed": 0.035,
            "effect": "salsa",
            "description": "Latin — rhythmic, lively"
        },
        "pop": {
            "color": "\033[95m",
            "speed": 0.02,
            "effect": "bounce",
            "description": "Pop — bright, per-word bounce"
        },
        "reggae": {
            "color": "\033[92m",
            "speed": 0.045,
            "effect": "reggae_wave",
            "description": "Reggae — laid-back, offbeat wave"
        },
        "rock": {
            "color": "\033[31m",
            "speed": 0.013,
            "effect": "heavy_shake",
            "description": "Rock — aggressive, strong hits"
        },
        "soundtrack_library": {
            "color": "\033[97m",
            "speed": 0.05,
            "effect": "cinematic",
            "description": "Soundtrack / Library — cinematic, neutral"
        }
    }
}


# ============================================================================
# FUNGSI UTILITAS
# ============================================================================

def lrc_time_to_seconds(t: str) -> float:
    """
    Mengkonversi format waktu LRC ([MM:SS.mm] atau MM:SS.mm) menjadi detik (float).
    Flexible untuk M atau MM menit, and 2-3 digit fractional seconds.
    """
    t = t.strip().strip("[]")
    if ":" in t:
        parts = t.split(":")
        minutes = int(parts[0])
        seconds_part = parts[1]
        if "." in seconds_part:
            seconds, frac = seconds_part.split(".")
            seconds = int(seconds)
            if len(frac) == 2:
                return minutes * 60 + seconds + int(frac) / 100.0
            else:
                return minutes * 60 + seconds + int(frac) / 1000.0
        else:
            return minutes * 60 + int(seconds_part)
    else:
        return float(t)


def seconds_to_lrc_time(sec: float) -> str:
    """
    Mengkonversi detik menjadi format waktu LRC (MM:SS.mm) dengan pembulatan centiseconds.
    """
    # Pastikan non-negatif
    if sec < 0:
        sec = 0.0
    minutes = int(sec // 60)
    seconds = int(sec % 60)
    centiseconds = int(round((sec - int(sec)) * 100))
    if centiseconds == 100:
        # rollover
        seconds += 1
        centiseconds = 0
        if seconds == 60:
            minutes += 1
            seconds = 0
    return f"{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def parse_time_input(time_str: str) -> float:
    """
    Parse input waktu yang bisa berupa detik (float) atau format mm:ss.mm.
    """
    if ":" in time_str:
        return lrc_time_to_seconds(time_str)
    else:
        return float(time_str)


def load_config() -> Dict:
    config_path = "config.yml"
    try:
        import yaml  # pyright: ignore[reportMissingModuleSource]
        yaml_available = True
    except ImportError:
        yaml_available = False
        print(f"{YELLOW}[!] PyYAML tidak tersedia. Menggunakan konfigurasi default.{RESET}")
        print(f"{YELLOW}  Install dengan: pip install pyyaml{RESET}\n")

    if not os.path.exists(config_path):
        if yaml_available:
            try:
                with open(config_path, "w", encoding="utf-8") as f:
                    yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
                print(f"{GREEN}[OK] File config.yml dibuat dengan konfigurasi default.{RESET}\n")
            except Exception as e:
                print(f"{RED}[WARN] Gagal menulis config.yml: {e}{RESET}")
        else:
            print(f"{YELLOW}[!] Membuat config.yml memerlukan PyYAML.{RESET}")
            print(f"{YELLOW}  Menggunakan konfigurasi default dalam memori.{RESET}\n")
        return DEFAULT_CONFIG

    if yaml_available:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            # Merge default + file config
            merged = DEFAULT_CONFIG.copy()
            merged.update({k: v for k, v in config.items() if k != "genres"})
            # merge genres separately
            merged["genres"] = {**DEFAULT_CONFIG["genres"], **config.get("genres", {})}
            return merged
        except Exception as e:
            print(f"{RED}[ERROR] Error membaca config.yml: {e}{RESET}")
            print(f"{YELLOW}Menggunakan konfigurasi default.{RESET}\n")
            return DEFAULT_CONFIG
    else:
        return DEFAULT_CONFIG


def parse_lrc(file: str) -> List[Dict]:
    """
    Membaca dan memparse file LRC menjadi list dictionary.
    Sekarang:
      - Menerima 1-2 digit menit
      - Jika satu baris memiliki beberapa timestamp, buat entry untuk tiap timestamp
      - Mengabaikan metadata [ti:], [ar:], dll.
    """
    try:
        with open(file, "r", encoding="utf-8") as f:
            raw = f.read()
    except FileNotFoundError:
        print(f"{RED}[ERROR] File tidak ditemukan: {file}{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"{RED}[ERROR] Error membaca file: {e}{RESET}")
        sys.exit(1)

    lines = raw.strip().splitlines()
    lyrics = []

    # Regex lebih fleksibel: menit 1-2 digit, detik 2 digit, fraksi 2-3 digit
    time_pattern = re.compile(r'\[(\d{1,2}):(\d{2})\.(\d{2,3})\]')
    meta_pattern = re.compile(r'^\[(ti|ar|al|by|offset|re|title|artist|album):', re.IGNORECASE)

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # skip metadata lines
        if meta_pattern.search(line):
            continue

        timestamps = time_pattern.findall(line)
        # remove timestamps from text
        text = time_pattern.sub('', line).strip()
        if not timestamps:
            # If no timestamp, try append to previous entry's text if exists
            if lyrics and text:
                # Append as continuation to last entry
                lyrics[-1]["text"] += "\n" + text
            continue

        # If text is empty (some LRC place timestamps only), set to empty string
        for (m, s, ms) in timestamps:
            minutes = int(m)
            seconds = int(s)
            if len(ms) == 2:
                frac = int(ms) / 100.0
            else:
                frac = int(ms) / 1000.0
            start_time = minutes * 60 + seconds + frac
            entry = {
                "start": start_time,
                "end": start_time + 3.0,  # will be updated later
                "text": text
            }
            lyrics.append(entry)

    # Sort by start (just in case)
    lyrics.sort(key=lambda x: x["start"])

    # Update end times based on next start
    for i in range(len(lyrics) - 1):
        lyrics[i]["end"] = lyrics[i + 1]["start"]

    # Last entry: estimate duration if end <= start
    if lyrics:
        last = lyrics[-1]
        if last["end"] <= last["start"]:
            estimated_duration = max(2.0, len(last["text"]) * 0.1)
            last["end"] = last["start"] + estimated_duration

    return lyrics


def wrap_text(text: str, width: int) -> List[str]:
    lines = text.split("\n")
    wrapped = []
    for line in lines:
        if len(line) <= width:
            wrapped.append(line)
        else:
            words = line.split()
            current_line = ""
            for word in words:
                if current_line:
                    candidate = current_line + " " + word
                else:
                    candidate = word
                if len(candidate) <= width:
                    current_line = candidate
                else:
                    if current_line:
                        wrapped.append(current_line)
                    current_line = word
            if current_line:
                wrapped.append(current_line)
    return wrapped


# ============================================================================ EFEK ANIMASI (sama, dengan perbaikan cursor erase)
def apply_effect(char: str, effect: str, index: int) -> str:
    if effect == "shake" or effect == "heavy_shake":
        if index % 3 == 0:
            return char + "\b" + char
        return char
    elif effect == "glitch":
        if index % 5 == 0:
            import random
            glitch_chars = "!@#$%^&*"
            return random.choice(glitch_chars) + "\b" + char
        return char
    elif effect == "bounce":
        return char
    elif effect == "wave":
        return char
    elif effect in ("smooth", "smooth_fade", "elegant_fade"):
        return char
    elif effect == "typewriter":
        return char
    elif effect == "swing":
        return char
    elif effect == "vibrate":
        if index % 4 == 0:
            return char + "\b" + char
        return char
    elif effect == "glow":
        return char
    elif effect in ("salsa", "reggae_wave"):
        return char
    elif effect == "cinematic":
        return char
    else:
        return char


def get_animation_delay(effect: str, base_speed: float, char_index: int) -> float:
    if effect == "bounce":
        import random
        return base_speed * (0.8 + random.random() * 0.4)
    elif effect == "wave":
        import math
        return base_speed * (1.0 + 0.3 * math.sin(char_index * 0.5))
    elif effect == "swing":
        import math
        return base_speed * (1.0 + 0.2 * math.sin(char_index * 0.3))
    elif effect in ("shake", "heavy_shake"):
        if char_index % 3 == 0:
            return base_speed * 0.5
        return base_speed
    elif effect == "glitch":
        import random
        return base_speed * (0.5 + random.random() * 1.0)
    elif effect == "vibrate":
        import math
        return base_speed * (1.0 + 0.15 * math.sin(char_index * 0.7))
    elif effect == "salsa":
        import math
        return base_speed * (1.0 + 0.25 * math.sin(char_index * 0.4))
    elif effect == "reggae_wave":
        import math
        return base_speed * (1.0 + 0.2 * math.sin(char_index * 0.35 + 0.5))
    else:
        return base_speed


def animate_text(text: str, color: str, speed: float, effect: str) -> None:
    print(color, end="", flush=True)
    cursor_chars = ["|", "/", "-", "\\"]
    cursor_frame = 0
    for i, ch in enumerate(text):
        char_with_effect = apply_effect(ch, effect, i)
        delay = get_animation_delay(effect, speed, i)
        print(char_with_effect, end="", flush=True)
        if i < len(text) - 1:
            cursor_frame += 1
            cursor_char = cursor_chars[cursor_frame % len(cursor_chars)]
            # show cursor
            print(f"{BOLD}{color}{cursor_char}{RESET}", end="", flush=True)
            # wait a little so cursor visible
            time.sleep(max(delay * 0.4, 0.06))
            # erase cursor reliably: backspace + space + backspace
            print("\b \b", end="", flush=True)
            # restore color
            print(color, end="", flush=True)
        time.sleep(delay)
        if ch == "\n" and i < len(text) - 1:
            cursor_frame += 1
            cursor_char = cursor_chars[cursor_frame % len(cursor_chars)]
            print(f"{BOLD}{color}{cursor_char}{RESET}", end="", flush=True)
            time.sleep(max(delay * 0.4, 0.06))
            print("\b \b", end="", flush=True)
            print(color, end="", flush=True)
    # ensure no leftover cursor
    print(" ", end="", flush=True)
    print("\b", end="", flush=True)
    print(RESET, end="", flush=True)


# VT323 banner
def get_vt323_style_text(text: str) -> str:
    return text


def print_vt323_banner() -> None:
    banner = """
╔═══════════════════════════════════════╗
║      L Y R I C S   P L A Y E R        ║
╚═══════════════════════════════════════╝
"""
    print(f"{GRAY}{banner}{RESET}", flush=True)


# LOADING & COMPLETION (sama behaviour)
def animate_loading(message: str = "TokTune @username", duration_ms: float = 800) -> None:
    duration = duration_ms / 1000.0
    if duration <= 0:
        bar = "#" * 20
        print(f"{GRAY}{message} [{bar}] 100%{RESET}\n", flush=True)
        return
    bar_width = 20
    update_interval = 0.05
    total_steps = max(1, int(duration / update_interval))
    for step in range(total_steps + 1):
        progress = step / total_steps
        filled = int(progress * bar_width)
        bar = "#" * filled + "-" * (bar_width - filled)
        percentage = int(progress * 100)
        print(f"\r{GRAY}{message} [{bar}] {percentage:3d}%{RESET}", end="", flush=True)
        time.sleep(update_interval)
    bar = "#" * bar_width
    print(f"\r{GRAY}{message} [{bar}] 100%{RESET}\n", flush=True)


def animate_completion(completion_duration_ms: float = 500) -> None:
    print("\n\n", end="", flush=True)
    duration = completion_duration_ms / 1000.0
    if duration <= 0:
        bar = "#" * 20
        print(f"{GRAY}[{bar}] 100%{RESET}\n", flush=True)
        return
    bar_width = 20
    update_interval = 0.05
    total_steps = max(1, int(duration / update_interval))
    for step in range(total_steps + 1):
        progress = step / total_steps
        filled = int(progress * bar_width)
        bar = "#" * filled + "-" * (bar_width - filled)
        percentage = int(progress * 100)
        print(f"\r{GRAY}[{bar}] {percentage:3d}%{RESET}", end="", flush=True)
        time.sleep(update_interval)
    bar = "#" * bar_width
    print(f"\r{GRAY}[{bar}] 100%{RESET}\n", flush=True)


# MAIN FUNCTIONALITY (schedule, realtime, export)
def export_json(lyrics: List[Dict], output_file: str, config: Dict) -> None:
    result = {
        "words": [],
        "captions": []
    }
    for caption in lyrics:
        words = caption["text"].split()
        duration = max(0.0001, caption["end"] - caption["start"])
        step = duration / len(words) if words else duration
        word_timings = []
        for idx, word in enumerate(words):
            word_start = caption["start"] + idx * step
            word_end = word_start + step
            wt = {
                "word": word,
                "start": word_start,
                "end": word_end,
                "start_time": seconds_to_lrc_time(word_start),
                "end_time": seconds_to_lrc_time(word_end)
            }
            word_timings.append(wt)
            result["words"].append(wt)
        result["captions"].append({
            "start": caption["start"],
            "end": caption["end"],
            "start_time": seconds_to_lrc_time(caption["start"]),
            "end_time": seconds_to_lrc_time(caption["end"]),
            "text": caption["text"],
            "words": word_timings
        })
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"{GREEN}[OK] JSON exported ke: {output_file}{RESET}")


def format_time_display(seconds: float, config: Dict) -> str:
    start_minute = config.get("lrc_start_minute", 0)
    start_second = config.get("lrc_start_second", 0)
    start_offset = start_minute * 60 + start_second
    total_seconds = seconds + start_offset
    minutes = int(total_seconds // 60)
    secs = int(total_seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def print_schedule(lyrics: List[Dict], genre_config: Dict, config: Dict, offset: float = 0, start_time: Optional[float] = None, speed_multiplier: float = 1.0) -> None:
    if not lyrics:
        print(f"{RED}[ERROR] LRC kosong atau format salah.{RESET}")
        return
    first_time = lyrics[0]["start"]
    baseline = start_time if start_time is not None else 0.0
    print(f"\n{YELLOW}=== SCHEDULE LIRIK ==={RESET}\n")
    if speed_multiplier != 1.0:
        print(f"{YELLOW}Speed multiplier: {speed_multiplier}x{RESET}\n")
    for line in lyrics:
        relative_start = (line["start"] - first_time) / speed_multiplier
        relative_end = (line["end"] - first_time) / speed_multiplier
        adjusted_start = baseline + relative_start + offset
        adjusted_end = baseline + relative_end + offset
        time_display = format_time_display(adjusted_start, config)
        print(f"[{seconds_to_lrc_time(adjusted_start)}] ({time_display})")
        for text_line in line["text"].split("\n"):
            print(f"  {text_line}")
        print()


def play_realtime(lyrics: List[Dict], genre_config: Dict, config: Dict, offset: float = 0, start_time: Optional[float] = None, wrap_width: Optional[int] = None, speed_multiplier: float = 1.0) -> None:
    if not lyrics:
        print(f"{RED}[ERROR] LRC kosong atau format salah.{RESET}")
        return
    color = genre_config["color"]
    base_speed = genre_config["speed"] / speed_multiplier
    effect = genre_config["effect"]
    margin_between_lines = config["margin_between_lines"]
    block_margin = config["block_margin"]
    wrap_w = wrap_width if wrap_width is not None else config["wrap_width"]
    show_time = config.get("show_time_display", True)
    first_time = lyrics[0]["start"]
    baseline = start_time if start_time is not None else 0.0
    playback_start = time.monotonic()
    for idx, line in enumerate(lyrics):
        relative_start = (line["start"] - first_time) / speed_multiplier
        absolute_start = baseline + relative_start + offset
        elapsed = time.monotonic() - playback_start
        wait_time = absolute_start - elapsed
        if wait_time > 0:
            time.sleep(wait_time)
        if show_time:
            time_display = format_time_display(absolute_start, config)
            print(f"{GRAY}[{time_display}]{RESET}", flush=True)
        text_lines = line["text"].split("\n")
        for text_line in text_lines:
            wrapped_lines = wrap_text(text_line, wrap_w)
            for wrapped_line in wrapped_lines:
                current_speed = base_speed
                current_drift = (time.monotonic() - playback_start) - absolute_start
                if current_drift > 0:
                    catchup = min(3.0, 1.0 + current_drift * 2.0)
                    current_speed = max(base_speed / catchup, 0.001)
                trimmed_line = wrapped_line.strip()
                dim_color = f"{DIM}{color}"
                if trimmed_line.startswith("-"):
                    animate_text(wrapped_line, dim_color, current_speed, effect)
                else:
                    last_idx = 0
                    has_parenthetical = False
                    for match in re.finditer(r"\([^)]*\)", wrapped_line):
                        has_parenthetical = True
                        start, end = match.span()
                        if start > last_idx:
                            animate_text(wrapped_line[last_idx:start], color, current_speed, effect)
                        animate_text(wrapped_line[start:end], dim_color, current_speed, effect)
                        last_idx = end
                    if not has_parenthetical:
                        animate_text(wrapped_line, color, current_speed, effect)
                    elif last_idx < len(wrapped_line):
                        animate_text(wrapped_line[last_idx:], color, current_speed, effect)
                print()
                time.sleep(margin_between_lines)
        print()
        if idx < len(lyrics) - 1:
            next_line = lyrics[idx + 1]
            next_relative_start = (next_line["start"] - first_time) / speed_multiplier
            next_absolute_start = baseline + next_relative_start + offset
            elapsed = time.monotonic() - playback_start
            remaining = next_absolute_start - elapsed
            extra_sleep = min(block_margin, max(0.0, remaining))
            if extra_sleep > 0:
                time.sleep(extra_sleep)
        elif block_margin > 0:
            time.sleep(block_margin)


def main():
    parser = argparse.ArgumentParser(
        description="Lyrics Player - Tampilkan lirik LRC dengan animasi realtime",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("file", help="Path ke file LRC")
    parser.add_argument("genre", nargs="?", help="Genre untuk animasi (default: dari config)")
    parser.add_argument("--realtime", action="store_true", help="Sinkronkan dengan timeline LRC")
    parser.add_argument("--offset", type=str, help="Offset waktu (detik atau mm:ss.mm)")
    parser.add_argument("--start", type=str, help="Waktu mulai (detik atau mm:ss.mm)")
    parser.add_argument("--wrap-width", type=int, help="Override lebar wrap dari config")
    parser.add_argument("--auto-close", type=float, help="Override waktu auto-close dari config")
    parser.add_argument("--export-json", type=str, help="Export per-word timings ke JSON")
    parser.add_argument("--speed", type=float, help="Multiplier kecepatan animasi DAN timing LRC (1.0=normal, 1.5=1.5x lebih cepat, 0.8=lebih lambat)")
    parser.add_argument("--banner", action="store_true", help="Display VT323-style banner at startup")
    args = parser.parse_args()

    config = load_config()
    genre_key = (args.genre or config.get("default_genre", "hiphop")).lower()
    if genre_key not in config["genres"]:
        print(f"{RED}[ERROR] Genre '{genre_key}' tidak ditemukan.{RESET}\n")
        print(f"{YELLOW}Genre yang tersedia:{RESET}")
        for key, genre_data in config["genres"].items():
            print(f"  {key:20s} - {genre_data['description']}")
        sys.exit(1)
    genre_config = config["genres"][genre_key]
    offset = 0.0
    if args.offset:
        offset = parse_time_input(args.offset)
    start_time = None
    if args.start:
        start_time = parse_time_input(args.start)
    speed_multiplier = args.speed if args.speed is not None else 1.0
    if speed_multiplier <= 0:
        print(f"{RED}[ERROR] Speed multiplier harus > 0{RESET}")
        sys.exit(1)
    if args.banner:
        print_vt323_banner()
    loading_duration_ms = config.get("loading_opening", config.get("loading_ending", 300))
    animate_loading("TokTune @username", duration_ms=loading_duration_ms)
    lyrics = parse_lrc(args.file)
    if not lyrics:
        print(f"{RED}[ERROR] LRC kosong atau format salah.{RESET}")
        sys.exit(1)
    if args.export_json:
        export_json(lyrics, args.export_json, config)
    try:
        if args.realtime:
            play_realtime(lyrics, genre_config, config, offset, start_time, args.wrap_width, speed_multiplier)
        else:
            print_schedule(lyrics, genre_config, config, offset, start_time, speed_multiplier)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[!] Terhenti oleh pengguna (Ctrl+C).{RESET}")
    # completion: use auto-close override if provided
    completion_ms = int((args.auto_close if args.auto_close is not None else config.get("loading_ending", 300)) * 1000)
    animate_completion(completion_ms)


if __name__ == "__main__":
    main()
