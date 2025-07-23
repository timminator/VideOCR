# Compilation instructions
# nuitka-project: --standalone
# nuitka-project: --enable-plugin=tk-inter
# nuitka-project: --windows-console-mode=disable
# nuitka-project: --include-data-files=*.ico=VideOCR.ico
# nuitka-project: --include-data-files=*.png=VideOCR.png

# Windows-specific metadata for the executable
# nuitka-project-if: {OS} == "Windows":
#     nuitka-project: --file-description="VideOCR"
#     nuitka-project: --file-version="1.3.0"
#     nuitka-project: --product-name="VideOCR-GUI"
#     nuitka-project: --product-version="1.3.0"
#     nuitka-project: --copyright="timminator"
#     nuitka-project: --windows-icon-from-ico=VideOCR.ico

import configparser
import ctypes
import datetime
import io
import math
import os
import pathlib
import platform
import re
import subprocess
import threading
import tkinter.font as tkFont
import webbrowser

import cv2
import PySimpleGUI as sg
from pymediainfo import MediaInfo

if platform.system() == "Windows":
    import PyTaskbar
    from winotify import Notification, audio
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('VideOCR')
else:
    from plyer import notification


# -- Save errors to log file ---
def log_error(message: str, log_name="error_log.txt"):
    """Logs error messages to a platform-appropriate log file location."""
    if platform.system() == "Windows":
        log_dir = os.path.join(os.getenv('LOCALAPPDATA'), "VideOCR")
    else:
        log_dir = os.path.join(os.path.expanduser('~'), ".config", "VideOCR")

    os.makedirs(log_dir, exist_ok=True)

    log_path = os.path.join(log_dir, log_name)
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {message}\n")


# --- Make application DPI aware ---
def make_dpi_aware():
    """Makes the application DPI aware on Windows to prevent scaling issues."""
    if platform.system() == "Windows":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(True)
        except AttributeError:
            log_error("Could not set DPI awareness.")


make_dpi_aware()


# --- Determine DPI scaling factor ---
def get_dpi_scaling():
    """Determines DPI scaling factor for the current OS."""
    def round_to_quarter_step(scale):
        dpi_scaling_factors = [1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0]
        return min(dpi_scaling_factors, key=lambda x: abs(x - scale))

    if platform.system() == "Windows":
        try:
            dpi = ctypes.windll.shcore.GetScaleFactorForDevice(0)  # 0 = primary monitor
            return dpi / 100.0
        except Exception:
            return 1.0
    else:
        # Linux has no proper way of reporting scaling factor. Linespace is instead used as DPI proxy. Base linespace ~16px at 100% scaling is assumed.
        try:
            root = sg.tk.Tk()
            root.withdraw()
            default_font = tkFont.nametofont("TkDefaultFont")
            metrics = default_font.metrics()
            root.destroy()

            baseline_linespace = 16.0
            actual_linespace = metrics.get("linespace", baseline_linespace)
            scale = actual_linespace / baseline_linespace
            return round_to_quarter_step(scale)
        except Exception:
            return 1.0


dpi_scale = get_dpi_scaling()


# --- Check for Taskbar progress support --
def supports_taskbar_progress():
    """Checks if the current OS supports progress indication via the Taskbar."""
    return platform.system() == "Windows"


taskbar_progress_supported = supports_taskbar_progress()


# --- Send notification --
def send_notification(title, message):
    """Sends a notification via winotify on Windows and via Plyer on Linux."""
    if platform.system() == "Windows":
        toast = Notification(
            app_id="VideOCR",
            title=title,
            msg=message,
            icon=os.path.join(APP_DIR, 'VideOCR.ico')
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
    else:
        notification.notify(
            title=title,
            message=message,
            app_name='VideOCR',
            app_icon=os.path.join(APP_DIR, 'VideOCR.png')
        )


# --- Determine VideOCR location ---
def find_videocr_program():
    """Determines the path to the videocr-cli-sa executable (.exe or .bin)."""
    possible_folders = [f'videocr-cli-CPU-v{PROGRAM_VERSION}', f'videocr-cli-GPU-v{PROGRAM_VERSION}']
    program_name = 'videocr-cli'

    if platform.system() == "Windows":
        extensions = '.exe'
    else:
        extensions = '.bin'

    for folder in possible_folders:
        potential_path = os.path.join(APP_DIR, folder, f'{program_name}{extensions}')
        if os.path.exists(potential_path):
            return potential_path
    # Should never be reached
    return None


# --- Configuration ---
PROGRAM_VERSION = "1.3.0"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEOCR_PATH = find_videocr_program()
DEFAULT_OUTPUT_SRT = ""
DEFAULT_LANG = "en"
DEFAULT_SUBTITLE_POSITION = "center"
DEFAULT_CONF_THRESHOLD = 75
DEFAULT_SIM_THRESHOLD = 80
DEFAULT_MAX_MERGE_GAP = 0.1
DEFAULT_MIN_SUBTITLE_DURATION = 0.2
DEFAULT_SSIM_THRESHOLD = 92
DEFAULT_FRAMES_TO_SKIP = 1
DEFAULT_TIME_START = "0:00"
KEY_SEEK_STEP = 1
CONFIG_FILE = os.path.join(APP_DIR, 'videocr_gui_config.ini')
CONFIG_SECTION = 'Settings'
try:
    DEFAULT_DOCUMENTS_DIR = str(pathlib.Path.home() / "Documents")
except Exception:
    DEFAULT_DOCUMENTS_DIR = ""

# --- Language Data ---
languages_list = [
    ('Abaza', 'abq'), ('Adyghe', 'ady'), ('Afrikaans', 'af'), ('Albanian', 'sq'),
    ('Angika', 'ang'), ('Arabic', 'ar'), ('Avar', 'ava'), ('Azerbaijani', 'az'),
    ('Belarusian', 'be'), ('Bhojpuri', 'bho'), ('Bihari', 'bh'), ('Bosnian', 'bs'),
    ('Bulgarian', 'bg'), ('Chechen', 'che'), ('Chinese & English', 'ch'),
    ('Chinese Traditional', 'chinese_cht'), ('Croatian', 'hr'), ('Czech', 'cs'),
    ('Danish', 'da'), ('Dargwa', 'dar'), ('Dutch', 'nl'), ('English', 'en'),
    ('Estonian', 'et'), ('French', 'fr'), ('German', 'german'), ('Goan Konkani', 'gom'),
    ('Haryanvi', 'bgc'), ('Hindi', 'hi'), ('Hungarian', 'hu'), ('Icelandic', 'is'),
    ('Indonesian', 'id'), ('Ingush', 'inh'), ('Irish', 'ga'), ('Italian', 'it'),
    ('Japanese', 'japan'), ('Kabardian', 'kbd'), ('Korean', 'korean'), ('Kurdish', 'ku'),
    ('Lak', 'lbe'), ('Latin', 'la'), ('Latvian', 'lv'), ('Lezghian', 'lez'),
    ('Lithuanian', 'lt'), ('Magahi', 'mah'), ('Maithili', 'mai'), ('Malay', 'ms'),
    ('Maltese', 'mt'), ('Maori', 'mi'), ('Marathi', 'mr'), ('Mongolian', 'mn'),
    ('Nagpur', 'sck'), ('Nepali', 'ne'), ('Newari', 'new'), ('Norwegian', 'no'),
    ('Occitan', 'oc'), ('Pali', 'pi'), ('Persian', 'fa'), ('Polish', 'pl'),
    ('Portuguese', 'pt'), ('Romanian', 'ro'), ('Russian', 'ru'), ('Sanskrit', 'sa'),
    ('Serbian(cyrillic)', 'rs_cyrillic'), ('Serbian(latin)', 'rs_latin'),
    ('Slovak', 'sk'), ('Slovenian', 'sl'), ('Spanish', 'es'), ('Swahili', 'sw'),
    ('Swedish', 'sv'), ('Tabassaran', 'tab'), ('Tagalog', 'tl'), ('Tamil', 'ta'),
    ('Telugu', 'te'), ('Turkish', 'tr'), ('Ukranian', 'uk'), ('Urdu', 'ur'),
    ('Uyghur', 'ug'), ('Uzbek', 'uz'), ('Vietnamese', 'vi'), ('Welsh', 'cy'),
]
languages_list.sort(key=lambda x: x[0])
language_display_names = [lang[0] for lang in languages_list]
language_abbr_lookup = {name: abbr for name, abbr in languages_list}
default_display_language = 'English'

# --- Subtitle Position Data ---
subtitle_positions_list = [
    ('Center', 'center'),
    ('Left', 'left'),
    ('Right', 'right'),
    ('Any', 'any')
]
subtitle_position_display_names = [pos[0] for pos in subtitle_positions_list]
subtitle_pos_lookup = {name: value for name, value in subtitle_positions_list}
default_display_subtitle_position = 'Center'

# --- Global Variables ---
video_path = None
original_frame_width = 0
original_frame_height = 0
total_frames = 0
video_fps = 0
current_frame_num = 0
resized_frame_width = 0
resized_frame_height = 0
image_offset_x = 0
image_offset_y = 0
graph_size = (int(640 * dpi_scale), int(360 * dpi_scale))
current_image_bytes = None
previous_taskbar_state = None


# --- Helper Functions ---
def kill_process_tree(pid):
    """Kills the process with the given PID and its descendants."""
    if platform.system() == "Windows":
        try:
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.CalledProcessError as e:
            log_error(f"Error terminating process tree {pid}: {e.stderr}")
        except FileNotFoundError:
            log_error("taskkill command not found. Cannot terminate process tree.")
        except Exception as e:
            log_error(f"An unexpected error occurred during taskkill: {e}")
    else:
        try:
            os.killpg(os.getpgid(pid), 15)
        except OSError as e:
            log_error(f"Error terminating process group {pid}: {e}")
        except Exception as e:
            log_error(f"An unexpected error occurred during process kill: {e}")


def format_time(seconds):
    """Formats total seconds into HH:MM:SS or MM:SS string."""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    else:
        return f"{m:02d}:{s:02d}"


def update_frame_and_time_display(window, current_frame, total_frames, fps):
    """Updates the frame count and time text elements."""
    window["-FRAME_TEXT-"].update(f"Frame: {current_frame + 1} / {total_frames}")

    if total_frames > 0 and fps > 0:
        current_seconds = current_frame / fps
        total_seconds = total_frames / fps
        time_text = f"{format_time(current_seconds)} / {format_time(total_seconds)}"
        window["-TIME_TEXT-"].update(f"Time: {time_text}")
    else:
        window["-TIME_TEXT-"].update("Time: -/-")


def _parse_and_validate_time_parts(time_str: str) -> tuple[int, int, int] | None:
    """Internal helper to parse MM:SS or HH:MM:SS and validate parts."""
    if not time_str:
        return None

    parts = time_str.split(':')
    try:
        if len(parts) == 2:
            m = int(parts[0])
            s = int(parts[1])
            if m < 0 or s < 0 or s >= 60:
                return None
            return (0, m, s)
        elif len(parts) == 3:
            h = int(parts[0])
            m = int(parts[1])
            s = int(parts[2])
            if h < 0 or m < 0 or s < 0 or m >= 60 or s >= 60:
                return None
            return (h, m, s)
        else:
            return None
    except ValueError:
        return None


def is_valid_time_format(time_str: str) -> bool:
    """Checks if a string is in MM:SS or HH:MM:SS format with valid ranges."""
    if not time_str:
        return True

    return _parse_and_validate_time_parts(time_str) is not None


def time_string_to_seconds(time_str: str) -> int | None:
    """Converts MM:SS or HH:MM:SS string to total seconds. Returns None if invalid."""
    if not time_str:
        return None

    parsed_time = _parse_and_validate_time_parts(time_str)

    if parsed_time is None:
        return None

    h, m, s = parsed_time
    return h * 3600 + m * 60 + s


def center_popup(parent_window, popup_window):
    """Center a popup relative to the parent window."""
    x0, y0 = parent_window.current_location()
    w0, h0 = parent_window.current_size_accurate()
    w1, h1 = popup_window.current_size_accurate()
    x1 = x0 + (w0 - w1) // 2
    y1 = y0 + (h0 - h1) // 2
    popup_window.move(x1, y1)


def custom_popup(parent_window, title, message, icon=None, modal=True):
    """Create and show a centered popup relative to the parent window."""
    layout = [
        [sg.Text(message)],
        [sg.Push(), sg.Button('OK', bind_return_key=True), sg.Push()]
    ]
    popup_window = sg.Window(title, layout, alpha_channel=0, finalize=True, icon=icon, modal=modal)

    popup_window.refresh()
    center_popup(parent_window, popup_window)
    popup_window.refresh()
    popup_window.set_alpha(1)
    popup_window['OK'].set_focus()

    while True:
        popup_event, _ = popup_window.read()
        if popup_event in (sg.WIN_CLOSED, 'OK'):
            break
    popup_window.close()


# --- Settings Save/Load Functions ---
def get_default_settings():
    """Returns a dictionary of default settings."""
    return {
    '-LANG_COMBO-': default_display_language,
    '-SUBTITLE_POS_COMBO-': default_display_subtitle_position,
    '--time_start': DEFAULT_TIME_START,
    '--time_end': '',
    '--conf_threshold': str(DEFAULT_CONF_THRESHOLD),
    '--sim_threshold': str(DEFAULT_SIM_THRESHOLD),
    '--max_merge_gap': str(DEFAULT_MAX_MERGE_GAP),
    '--brightness_threshold': '',
    '--ssim_threshold': str(DEFAULT_SSIM_THRESHOLD),
    '--frames_to_skip': str(DEFAULT_FRAMES_TO_SKIP),
    '--use_fullframe': False,
    '--use_gpu': True,
    '--use_angle_cls': False,
    '--post_processing': True,
    '--min_subtitle_duration': str(DEFAULT_MIN_SUBTITLE_DURATION),
    '--use_server_model': False,
    '--use_dual_zone': False,
    '--keyboard_seek_step': str(KEY_SEEK_STEP),
    '--default_output_dir': DEFAULT_DOCUMENTS_DIR,
    '--save_in_video_dir': True,
    '--send_notification': True,
    }


def save_settings(values):
    """Saves current settings from GUI elements to the config file."""
    config = configparser.ConfigParser()
    config.add_section(CONFIG_SECTION)

    settings_to_save = {
        '-LANG_COMBO-': values.get('-LANG_COMBO-', get_default_settings().get('-LANG_COMBO-')),
        '-SUBTITLE_POS_COMBO-': values.get('-SUBTITLE_POS_COMBO-', get_default_settings().get('-SUBTITLE_POS_COMBO-')),
        '--time_start': values.get('--time_start', get_default_settings().get('--time_start')),
        '--time_end': values.get('--time_end', get_default_settings().get('--time_end')),
        '--conf_threshold': values.get('--conf_threshold', get_default_settings().get('--conf_threshold')),
        '--sim_threshold': values.get('--sim_threshold', get_default_settings().get('--sim_threshold')),
        '--max_merge_gap': values.get('--max_merge_gap', get_default_settings().get('--max_merge_gap')),
        '--brightness_threshold': values.get('--brightness_threshold', get_default_settings().get('--brightness_threshold')),
        '--ssim_threshold': values.get('--ssim_threshold', get_default_settings().get('--ssim_threshold')),
        '--frames_to_skip': values.get('--frames_to_skip', get_default_settings().get('--frames_to_skip')),
        '--use_fullframe': values.get('--use_fullframe', get_default_settings().get('--use_fullframe')),
        '--use_gpu': values.get('--use_gpu', get_default_settings().get('--use_gpu')),
        '--use_angle_cls': values.get('--use_angle_cls', get_default_settings().get('--use_angle_cls')),
        '--post_processing': values.get('--post_processing', get_default_settings().get('--post_processing')),
        '--min_subtitle_duration': values.get('--min_subtitle_duration', get_default_settings().get('--min_subtitle_duration')),
        '--use_server_model': values.get('--use_server_model', get_default_settings().get('--use_server_model')),
        '--use_dual_zone': values.get('--use_dual_zone', get_default_settings().get('--use_dual_zone')),
        '--keyboard_seek_step': values.get('--keyboard_seek_step', get_default_settings().get('--keyboard_seek_step')),
        '--default_output_dir': values.get('--default_output_dir', get_default_settings().get('--default_output_dir')),
        '--save_in_video_dir': values.get('--save_in_video_dir', get_default_settings().get('--save_in_video_dir')),
        '--send_notification': values.get('--send_notification', get_default_settings().get('--send_notification')),
    }

    # --- Write settings to the config object ---
    for key, value in settings_to_save.items():
        config.set(CONFIG_SECTION, key, str(value))
    try:
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
    except Exception as e:
        log_error(f"Error saving settings to {CONFIG_FILE}: {e}")


def load_settings(window):
    """Loads settings from the config file and updates GUI elements.
       Creates a default config if the file doesn't exist."""
    config = configparser.ConfigParser()

    if os.path.exists(CONFIG_FILE):
        try:
            config.read(CONFIG_FILE)
            if config.has_section(CONFIG_SECTION):
                settings_to_load = [
                    ('-LANG_COMBO-', 'combo_lang'),
                    ('-SUBTITLE_POS_COMBO-', 'combo_pos'),
                    ('--time_start', 'input'),
                    ('--time_end', 'input'),
                    ('--conf_threshold', 'input'),
                    ('--sim_threshold', 'input'),
                    ('--max_merge_gap', 'input'),
                    ('--brightness_threshold', 'input'),
                    ('--ssim_threshold', 'input'),
                    ('--frames_to_skip', 'input'),
                    ('--use_fullframe', 'checkbox'),
                    ('--use_gpu', 'checkbox'),
                    ('--use_angle_cls', 'checkbox'),
                    ('--post_processing', 'checkbox'),
                    ('--min_subtitle_duration', 'input'),
                    ('--use_server_model', 'checkbox'),
                    ('--use_dual_zone', 'checkbox'),
                    ('--keyboard_seek_step', 'input'),
                    ('--default_output_dir', 'input'),
                    ('--save_in_video_dir', 'checkbox'),
                    ('--send_notification', 'checkbox'),
                ]

                for key, elem_type in settings_to_load:
                    if config.has_option(CONFIG_SECTION, key):
                        try:
                            if elem_type == 'checkbox':
                                value = config.getboolean(CONFIG_SECTION, key)
                            elif elem_type == 'combo_lang':
                                value_str = config.get(CONFIG_SECTION, key)
                                if value_str in language_display_names:
                                    value = value_str
                                else:
                                    value = default_display_language
                            elif elem_type == 'combo_pos':
                                value_str = config.get(CONFIG_SECTION, key)
                                if value_str in subtitle_position_display_names:
                                    value = value_str
                                else:
                                    value = default_display_subtitle_position
                            elif elem_type == 'input':
                                value = config.get(CONFIG_SECTION, key)
                            else:
                                value = config.get(CONFIG_SECTION, key)

                            if key in window.AllKeysDict:
                                window[key].update(value)

                        except Exception as e:
                            log_error(f"Error loading setting '{key}' from {CONFIG_FILE}: {e}. Using default.")

            current_gui_values = window.read(timeout=0)[1]
            save_settings(current_gui_values)

        except configparser.Error as e:
            log_error(f"Error parsing config file {CONFIG_FILE}: {e}. Creating default config.")
        except Exception as e:
            log_error(f"An unexpected error occurred while loading settings: {e}. Creating default config.")

    else:
        # --- Config file doesn't exist, create it with default settings ---
        default_settings = get_default_settings()
        config.add_section(CONFIG_SECTION)
        for key, value in default_settings.items():
            config.set(CONFIG_SECTION, key, str(value))
        try:
            with open(CONFIG_FILE, 'w') as configfile:
                config.write(configfile)
        except Exception as e:
            log_error(f"Error creating default config file {CONFIG_FILE}: {e}")


def generate_output_path(video_path, values, default_dir=DEFAULT_DOCUMENTS_DIR):
    """Generates a unique output file path for the SRT file based on video path and settings."""
    video_file_path = pathlib.Path(video_path)
    video_filename_stem = video_file_path.stem

    save_in_video_dir = values.get('--save_in_video_dir', True)
    if save_in_video_dir:
        output_dir = video_file_path.parent
    else:
        output_dir_str = values.get('--default_output_dir', default_dir).strip()
        if not output_dir_str:
            output_dir = pathlib.Path(default_dir)
        else:
            output_dir = pathlib.Path(output_dir_str)

    base_output_path = output_dir / f"{video_filename_stem}.srt"
    output_path = base_output_path
    counter = 1
    while output_path.exists():
        output_path = output_dir / f"{video_filename_stem}({counter}).srt"
        counter += 1

    return output_path


def get_video_frame(video_path, frame_number, display_size):
    """Reads a specific frame from a video file using validated metadata,
    resizes it maintaining aspect ratio, and returns it in PNG bytes format
    with additional metadata."""

    # Using pymediainfo in addition to VideoCapture because there can be stream vs container discrepancies
    media_info = MediaInfo.parse(video_path)
    video_track = None

    for track in media_info.tracks:
        if track.track_type == "Video":
            video_track = track
            break

    if video_track:
        frame_count = getattr(video_track, "frame_count", None)
        source_frame_count = getattr(video_track, "source_frame_count", None)
    else:
        frame_count = source_frame_count = None

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None, 0, 0, 0, 0, 0, 0, 0, 0

    cv_reported_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cv_fps = cap.get(cv2.CAP_PROP_FPS)
    original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    total_frames_candidates = [cv_reported_frames]
    if frame_count is not None:
        total_frames_candidates.append(int(frame_count))
    if source_frame_count is not None:
        total_frames_candidates.append(int(source_frame_count))

    total_frames = min([f for f in total_frames_candidates if f > 0], default=0)

    frame_number = max(0, min(frame_number, total_frames - 1 if total_frames > 0 else 0))

    if total_frames <= 0 or original_width <= 0 or original_height <= 0 or cv_fps <= 0:
        cap.release()
        return None, 0, 0, 0, 0, 0, 0, 0, 0

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        return None, original_width, original_height, total_frames, cv_fps, 0, 0, 0, 0

    h, w = frame.shape[:2]
    scale = min(display_size[0] / w, display_size[1] / h)
    new_w, new_h = int(w * scale), int(h * scale)

    if new_w <= 0 or new_h <= 0:
        return None, original_width, original_height, total_frames, cv_fps, 0, 0, 0, 0

    resized_frame = cv2.resize(frame, (new_w, new_h))

    offset_x = (display_size[0] - new_w) // 2
    offset_y = (display_size[1] - new_h) // 2

    is_success, buffer = cv2.imencode(".png", resized_frame)
    if not is_success:
        return None, original_width, original_height, total_frames, cv_fps, new_w, new_h, offset_x, offset_y

    return io.BytesIO(buffer), original_width, original_height, total_frames, cv_fps, new_w, new_h, offset_x, offset_y


def handle_progress(match, label_format, last_percentage, threshold, taskbar_base=0, show_taskbar_progress=True):
    """Handles progress parsing and updating GUI."""
    current_item = int(match.group(1))
    total_items = int(match.group(2))
    percentage = int((current_item / total_items) * 100) if total_items > 0 else 0

    if current_item == 1 or percentage >= last_percentage + threshold or percentage == 100:
        message = f"{label_format.format(current=current_item, total=total_items, percent=percentage)}\n"
        window.write_event_value('-VIDEOCR_OUTPUT-', message)

        if taskbar_progress_supported and show_taskbar_progress and taskbar_base is not None:
            progress_value = taskbar_base + int(percentage * 0.5)
            window.write_event_value('-TASKBAR_STATE_UPDATE-', {'state': 'normal', 'progress': progress_value})

        return percentage
    return last_percentage


def run_videocr(args_dict, window):
    """Runs the videocr-cli tool in a separate process and streams output."""
    command = [VIDEOCR_PATH]

    for key, value in args_dict.items():
        if value is not None and value != '':
            arg_name = f"--{key}"
            if key != 'send_notification':
                command.append(arg_name)
                if isinstance(value, bool):
                    command.append(str(value).lower())
                else:
                    command.append(str(value))

    STEP1_PROGRESS_PATTERN = re.compile(r"Step 1: Processing image (\d+) of (\d+)")
    STEP2_PROGRESS_PATTERN = re.compile(r"Step 2: Performing OCR on image (\d+) of (\d+)")
    STARTING_OCR_PATTERN = re.compile(r"Starting PaddleOCR")
    GENERATING_SUBTITLES_PATTERN = re.compile(r"Generating subtitles")
    VFR_PATTERN = re.compile(r"Variable frame rate detected. Building timestamp map...")
    VFR_PROGRESS_PATTERN = re.compile(r"Mapping frame (\d+) of (\d+)")
    SEEK_PROGRESS_PATTERN = re.compile(r"Advancing to frame (\d+)/(\d+)")
    MAP_GENERATION_STOP_PATTERN = re.compile(r"Reached target time. Stopped map generation after frame \d+.")

    last_reported_percentage_step1 = -1
    last_reported_percentage_step2 = -1
    last_reported_percentage_vfr = -1
    last_reported_percentage_seek = -1

    taskbar_progress_started = False

    window.write_event_value('-VIDEOCR_OUTPUT-', "Starting subtitle extraction...\n")

    process = None

    try:
        process = subprocess.Popen(command,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,
                                   text=True,
                                   encoding='utf-8',
                                   errors='replace',
                                   bufsize=1,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                                   start_new_session=(os.name != 'nt')
                                   )

        window.write_event_value('-PROCESS_STARTED-', process.pid)

        if process.stdout:
            for line in iter(process.stdout.readline, ''):
                if process.poll() is not None and line == '':
                    break
                line = line.rstrip('\r\n')

                match1 = STEP1_PROGRESS_PATTERN.search(line)
                if match1:
                    last_reported_percentage_step1 = handle_progress(
                        match1, "Step 1: Processed image {current} of {total} ({percent}%)",
                        last_reported_percentage_step1, 5, taskbar_base=0)
                    continue

                match2 = STEP2_PROGRESS_PATTERN.search(line)
                if match2:
                    last_reported_percentage_step2 = handle_progress(
                        match2, "Step 2: Performed OCR on image {current} of {total} ({percent}%)",
                        last_reported_percentage_step2, 5, taskbar_base=50)
                    continue

                match3 = VFR_PROGRESS_PATTERN.search(line)
                if match3:
                    if taskbar_progress_supported and not taskbar_progress_started:
                        window.write_event_value('-TASKBAR_STATE_UPDATE-', {'state': 'normal', 'progress': 1})
                        taskbar_progress_started = True

                    last_reported_percentage_vfr = handle_progress(
                        match3, "Mapped frame {current} of {total} ({percent}%)",
                        last_reported_percentage_vfr, 20, show_taskbar_progress=False)
                    continue

                match4 = SEEK_PROGRESS_PATTERN.search(line)
                if match4:
                    if taskbar_progress_supported and not taskbar_progress_started:
                        window.write_event_value('-TASKBAR_STATE_UPDATE-', {'state': 'normal', 'progress': 1})
                        taskbar_progress_started = True

                    last_reported_percentage_seek = handle_progress(
                        match4, "Advanced to frame {current}/{total} ({percent}%)",
                        last_reported_percentage_seek, 20, show_taskbar_progress=False)
                    continue

                if STARTING_OCR_PATTERN.search(line) or GENERATING_SUBTITLES_PATTERN.search(line) or VFR_PATTERN.search(line) or MAP_GENERATION_STOP_PATTERN.search(line):
                    window.write_event_value('-VIDEOCR_OUTPUT-', f"{line}\n")
                    continue

        exit_code = process.wait()

        process_was_cancelled = getattr(window, 'cancelled_by_user', False)
        if exit_code != 0 and not process_was_cancelled:
            window.write_event_value('-VIDEOCR_OUTPUT-', f"\nProcess finished with non-zero exit code: {exit_code}\n")

        return exit_code == 0

    except FileNotFoundError:
        window.write_event_value('-VIDEOCR_OUTPUT-', f"\nError: '{VIDEOCR_PATH}' not found. Please check the path.\n")
        return False
    except Exception as e:
        window.write_event_value('-VIDEOCR_OUTPUT-', f"\nAn error occurred: {e}\n")
        return False


def run_ocr_thread(args, window):
    """Thread target for running the OCR process."""
    success = run_videocr(args, window)
    if success:
        window.write_event_value('-VIDEOCR_OUTPUT-', "\nSuccessfully generated subtitle file!\n")
        if args.get('send_notification', True):
            window.write_event_value('-NOTIFICATION_EVENT-', {'title': "Your Subtitle generation is done!", 'message': f"{os.path.basename(args['output'])}"})
    window.write_event_value('-PROCESS_FINISHED-', None)


# --- GUI Layout ---
sg.theme("Darkgrey13")

tab1_content = [
    [sg.Text("Video File:", size=(15, 1)), sg.Input(key="-VIDEO_PATH-", disabled_readonly_background_color=sg.theme_input_background_color(), readonly=True, enable_events=True, size=(40, 1)),
     sg.FileBrowse(file_types=(("Video Files", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.wmv"), ("All Files", "*.*")))],
    [sg.Text("Output SRT:", size=(15, 1)), sg.Input(key="--output", disabled_readonly_background_color=sg.theme_input_background_color(), readonly=True, disabled=True, size=(40, 1)),
     sg.Button('Save As...', key="-SAVE_AS_BTN-", disabled=True)],
    [sg.Text("Subtitle Language:", size=(15, 1)),
     sg.Combo(language_display_names, default_value=default_display_language, key="-LANG_COMBO-", size=(38, 1), readonly=True, enable_events=True)],
    [sg.Text("Subtitle Position:", size=(15, 1), tooltip="Select the alignment of subtitles in the video"),
     sg.Combo(subtitle_position_display_names, default_value=default_display_subtitle_position, key="-SUBTITLE_POS_COMBO-", size=(38, 1), readonly=True, enable_events=True, tooltip="Select the alignment of subtitles in the video"),
     sg.Push(),
     sg.Button("How to Use", key="-HELP-")],
    [sg.Graph(canvas_size=graph_size, graph_bottom_left=(0, graph_size[1]), graph_top_right=(graph_size[0], 0),
              key="-GRAPH-", change_submits=True, drag_submits=True, enable_events=True, background_color='black')],
    [sg.Text("Seek:"), sg.Slider(range=(0, 0), key="-SLIDER-", orientation='h', size=(45, 15), expand_x=True, enable_events=True, disable_number_display=True, disabled=True)],
    [
        sg.Push(),
        sg.Text("Frame: -/-", key="-FRAME_TEXT-"), sg.Text("|"), sg.Text("Time: -/-", key="-TIME_TEXT-")
    ],
    [sg.Text("Crop Box (X, Y, W, H):"), sg.Text("Not Set", key="-CROP_COORDS-", size=(45, 1), expand_x=True)],
    [sg.Button("Run", key="Run", disabled=True),
     sg.Button("Cancel", key="Cancel", disabled=True),
     sg.Button("Clear Crop", key="-CLEAR_CROP-", disabled=True)],
    [sg.Text("Progress Info:")],
    [sg.Multiline(key="-OUTPUT-", size=(None, 6), expand_x=True, autoscroll=True, reroute_stdout=False, reroute_stderr=False, write_only=True, disabled=True)]
]
tab1_layout = [[sg.Column(tab1_content,
                           size_subsample_height=1,
                           scrollable=True,
                           vertical_scroll_only=True,
                           expand_x=True,
                           expand_y=True)]]

tab2_content = [
    [sg.Text("OCR Settings:", font=('Arial', 10, 'bold'))],
    [sg.Text("Start Time (e.g., 0:00 or 1:23:45):", size=(30, 1), tooltip="Specify the starting time to begin processing."),
     sg.Input(DEFAULT_TIME_START, key="--time_start", size=(15, 1), enable_events=True, tooltip="Specify the starting time to begin processing.")],
    [sg.Text("End Time (e.g., 0:10 or 2:34:56):", size=(30, 1), tooltip="Specify the ending time to stop processing."),
     sg.Input("", key="--time_end", size=(15, 1), enable_events=True, tooltip="Specify the ending time to stop processing.")],
    [sg.Text("Confidence Threshold (0-100):", size=(30, 1), tooltip="Minimum confidence score for detected text."),
     sg.Input(DEFAULT_CONF_THRESHOLD, key="--conf_threshold", size=(10, 1), enable_events=True, tooltip="Minimum confidence score for detected text.")],
    [sg.Text("Similarity Threshold (0-100):", size=(30, 1), tooltip="Threshold for merging text lines based on content similarity."),
     sg.Input(DEFAULT_SIM_THRESHOLD, key="--sim_threshold", size=(10, 1), enable_events=True, tooltip="Threshold for merging text lines based on content similarity.")],
    [sg.Text("Max Merge Gap (seconds):", size=(30, 1), tooltip="Maximum allowed time gap to merge similar subtitles."),
     sg.Input(DEFAULT_MAX_MERGE_GAP, key="--max_merge_gap", size=(10, 1), enable_events=True, tooltip="Maximum allowed time gap to merge similar subtitles.")],
    [sg.Text("Brightness Threshold (0-255):", size=(30, 1), tooltip="Applies a brightness filter before OCR.\nPixels below the threshold are blacked out."),
     sg.Input("", key="--brightness_threshold", size=(10, 1), enable_events=True, tooltip="Applies a brightness filter before OCR.\nPixels below the threshold are blacked out. Leave empty to disable.")],
    [sg.Text("SSIM Threshold (0-100):", size=(30, 1), tooltip="If the SSIM between frames exceeds this threshold,\nthe frame is considered similar and skipped for OCR."),
     sg.Input(DEFAULT_SSIM_THRESHOLD, key="--ssim_threshold", size=(10, 1), enable_events=True, tooltip="If the SSIM between frames exceeds this threshold,\nthe frame is considered similar and skipped for OCR.")],
    [sg.Text("Frames to Skip:", size=(30, 1), tooltip="Process every Nth frame (e.g., 1 = every 2nd).\nHigher = faster but less accurate, lower = slower but more accurate."),
     sg.Input(DEFAULT_FRAMES_TO_SKIP, key="--frames_to_skip", size=(10, 1), enable_events=True, tooltip="Process every Nth frame (e.g., 1 = every 2nd).\nHigher = faster but less accurate, lower = slower but more accurate.")],
    [sg.Text("Minimum Subtitle Duration (seconds):", size=(30, 1), tooltip="Detected subtitles below this duration are omitted from the SRT file."),
     sg.Input(DEFAULT_MIN_SUBTITLE_DURATION, key="--min_subtitle_duration", size=(10, 1), enable_events=True, tooltip="Detected subtitles below this duration are omitted from the SRT file.")],
    [sg.Checkbox("Enable GPU Usage (Only affects GPU version)", default=True, key="--use_gpu", enable_events=True, tooltip="Attempt to use the GPU for OCR processing if available and supported.")],
    [sg.Checkbox("Use Full Frame OCR", default=False, key="--use_fullframe", enable_events=True, tooltip="Process the entire video frame instead of using a crop box.")],
    [sg.Checkbox("Enable Dual Zone OCR", default=False, key="--use_dual_zone", enable_events=True, tooltip="Allows selecting two separate crop boxes for OCR.")],
    [sg.Checkbox("Enable Angle Classification", default=False, key="--use_angle_cls", enable_events=True, tooltip="Detect and correct rotated text angles.")],
    [sg.Checkbox("Enable Post Processing", default=True, key="--post_processing", enable_events=True, tooltip="Checks the OCR result for missing spaces and tries to insert them automatically.\nDoes not support all languages, more info can be found online.")],
    [sg.Checkbox("Use Server Model", default=False, key="--use_server_model", enable_events=True, tooltip="Enables the server model with higher OCR capabilities.\nThis mode can deliver better results but requires also more computing power.\nA GPU is highly recommended when using this mode.")],
    [sg.HorizontalSeparator()],
    [sg.Text("VideOCR Settings:", font=('Arial', 10, 'bold'))],
    [sg.Checkbox("Save SRT in Video Directory", size=(30, 1), default=True, key="--save_in_video_dir", enable_events=True, tooltip="Save the output SRT file in the same directory as the video file.\nIf enabled, \"Output directory\" is disabled.")],
    [sg.Text("Output Directory:", size=(30, 1), tooltip="Folder where generated SRT files will be placed.\nDisabled when \"Save SRT in Video Directory\" is enabled."),
     sg.Input(DEFAULT_DOCUMENTS_DIR, key="--default_output_dir", disabled_readonly_background_color=sg.theme_input_background_color(), readonly=True, size=(40, 1), enable_events=True, tooltip="Folder where generated SRT files will be placed.\nDisabled when \"Save SRT in Video Directory\" is enabled."),
     sg.FolderBrowse(key="-FOLDER_BROWSE_BTN-", disabled=True)],
    [sg.Text("Keyboard Seek Step (frames):", size=(30, 1), tooltip="Number of frames to jump when using Left/Right arrows."),
     sg.Input(KEY_SEEK_STEP, key="--keyboard_seek_step", size=(10, 1), enable_events=True, tooltip="Number of frames to jump when using Left/Right arrows.")],
    [sg.Checkbox("Send Notification", default=True, key="--send_notification", enable_events=True, tooltip="Send notification when the process is complete.")],
]
tab2_layout = [[sg.Column(tab2_content,
                           size_subsample_height=1,
                           scrollable=True,
                           vertical_scroll_only=True,
                           expand_x=True,
                           expand_y=True)]]

tab3_layout = [
    [sg.Column([
        [sg.Text("")],
        [sg.Text("VideOCR", font=('Arial', 16, 'bold'))],
        [sg.Text(f"Version: {PROGRAM_VERSION}", font=('Arial', 11))],
        [sg.Text("")],
        [sg.Text("Get the newest version here:", font=('Arial', 11))],
        [sg.Text("https://github.com/timminator/VideOCR/releases", font=('Arial', 11, 'underline'), enable_events=True, key="-GITHUB_RELEASES_LINK-")],
        [sg.Text("")],
        [sg.Text("Found a bug or have a suggestion? Feel free to open an issue at:", font=('Arial', 11))],
        [sg.Text("https://github.com/timminator/VideOCR/issues", font=('Arial', 11, 'underline'), enable_events=True, key="-GITHUB_ISSUES_LINK-")],
        [sg.Text("")],
        [sg.HorizontalSeparator()],
    ], element_justification='c', expand_x=True, expand_y=True)]
]

layout = [
    [sg.TabGroup([
        [sg.Tab('Process Video', tab1_layout, key='-TAB-VIDEO-'),
         sg.Tab('Advanced Settings', tab2_layout, key='-TAB-ADVANCED-'),
         sg.Tab('About', tab3_layout, key='-TAB-ABOUT-')]
    ], key='-TABGROUP-', enable_events=True, expand_x=True, expand_y=True)]
]

if platform.system() == "Windows":
    ICON_PATH = os.path.join(APP_DIR, 'VideOCR.ico')
else:
    ICON_PATH = os.path.join(APP_DIR, 'VideOCR.png')

window = sg.Window("VideOCR", layout, icon=ICON_PATH, finalize=True, resizable=True)

if taskbar_progress_supported:
    prog = PyTaskbar.Progress(int(window.TKroot.wm_frame(), 16))
    prog.init()
    prog.setState('normal')

graph = window["-GRAPH-"]


# --- Initialize crop box state in the window object ---
def reset_crop_state():
    """Resets all variables related to crop boxes."""
    global graph
    for fig_id in getattr(window, 'drawn_rect_ids', []):
        graph.delete_figure(fig_id)
    window.drawn_rect_ids = []
    window.start_point_img = None
    window.end_point_img = None
    window.crop_boxes = []
    window['-CROP_COORDS-'].update("Not Set")
    window["-CLEAR_CROP-"].update(disabled=True)


reset_crop_state()


def redraw_canvas_and_boxes():
    """Erases the graph, redraws the current frame and all finalized crop boxes."""
    global graph, current_image_bytes, image_offset_x, image_offset_y, resized_frame_width, resized_frame_height

    graph.erase()
    if current_image_bytes:
        graph.draw_image(data=current_image_bytes, location=(image_offset_x, image_offset_y))

    window.drawn_rect_ids.clear()
    for crop_box in window.crop_boxes:
        start_img, end_img = crop_box['img_points']

        rect_x1_img = min(start_img[0], end_img[0])
        rect_y1_img = min(start_img[1], end_img[1])
        rect_x2_img = max(start_img[0], end_img[0])
        rect_y2_img = max(start_img[1], end_img[1])

        draw_x1 = max(0, rect_x1_img)
        draw_y1 = max(0, rect_y1_img)
        draw_x2 = min(resized_frame_width - 1, rect_x2_img)
        draw_y2 = min(resized_frame_height - 1, rect_y2_img)

        start_graph = (draw_x1 + image_offset_x, draw_y1 + image_offset_y)
        end_graph = (draw_x2 + image_offset_x, draw_y2 + image_offset_y)

        rect_id = graph.draw_rectangle(start_graph, end_graph, line_color='red')
        window.drawn_rect_ids.append(rect_id)


# --- Bind keyboard events to the graph element ---
window.bind('<Left>', '-GRAPH-<Left>')
window.bind('<Right>', '-GRAPH-<Right>')

# --- Bind window restore event ---
window.bind('<Map>', '-WINDOW_RESTORED-')

# --- Cursor Change Logic for -GITHUB_ISSUES_LINK- ---
issues_link_element = window['-GITHUB_ISSUES_LINK-']


def on_issues_enter(event):
    """Callback when mouse enters the Issues link text."""
    issues_link_element.Widget.config(cursor="hand2")


def on_issues_leave(event):
    """Callback when mouse leaves the Issues link text."""
    issues_link_element.Widget.config(cursor="")


issues_link_element.Widget.bind("<Enter>", on_issues_enter)
issues_link_element.Widget.bind("<Leave>", on_issues_leave)

# --- Cursor Change Logic for -GITHUB_RELEASES_LINK- ---
releases_link_element = window['-GITHUB_RELEASES_LINK-']


def on_releases_enter(event):
    """Callback when mouse enters the Releases link text."""
    releases_link_element.Widget.config(cursor="hand2")


def on_releases_leave(event):
    """Callback when mouse leaves the Releases link text."""
    releases_link_element.Widget.config(cursor="")


releases_link_element.Widget.bind("<Enter>", on_releases_enter)
releases_link_element.Widget.bind("<Leave>", on_releases_leave)

# --- Load settings when the application starts ---
load_settings(window)

save_in_video_dir_checked_at_start = window.find_element('--save_in_video_dir').get()
if not save_in_video_dir_checked_at_start:
    window['-FOLDER_BROWSE_BTN-'].update(disabled=False)

# --- Define the list of keys that, when changed, should trigger a settings save ---
KEYS_TO_AUTOSAVE = [
    '-LANG_COMBO-',
    '-SUBTITLE_POS_COMBO-',
    '--time_start',
    '--time_end',
    '--conf_threshold',
    '--sim_threshold',
    '--max_merge_gap',
    '--brightness_threshold',
    '--ssim_threshold',
    '--frames_to_skip',
    '--use_fullframe',
    '--use_gpu',
    '--use_dual_zone',
    '--use_angle_cls',
    '--post_processing',
    '--min_subtitle_duration',
    '--use_server_model',
    '--keyboard_seek_step',
    '--default_output_dir',
    '--save_in_video_dir',
    '--send_notification',
]

# --- Event Loop ---
while True:
    event, values = window.read(timeout=100)

    if event == sg.WIN_CLOSED:
        process_to_kill = getattr(window, '_videocr_process_pid', None)
        if process_to_kill:
            try:
                kill_process_tree(process_to_kill)
            except Exception as e:
                log_error(f"Exception during final process kill: {e}")
        break

    # --- Handle events sent from the worker thread ---
    if event in KEYS_TO_AUTOSAVE:
        if values is not None:
            save_settings(values)

        if event == '--use_dual_zone' or event == '--use_fullframe':
            reset_crop_state()
            if video_path and current_image_bytes:
                graph.erase()
                graph.draw_image(data=current_image_bytes, location=(image_offset_x, image_offset_y))

        # --- Handle possible output path change ---
        if event == '--save_in_video_dir':
            if (values.get('--save_in_video_dir', True)):
                window['-FOLDER_BROWSE_BTN-'].update(disabled=True)
            else:
                window['-FOLDER_BROWSE_BTN-'].update(disabled=False)

            if video_path:
                output_path = generate_output_path(video_path, values)
                window['--output'].update(str(output_path))

    elif event == '-TABGROUP-' and values.get('-TABGROUP-') == '-TAB-VIDEO-':
        if '-GRAPH-' in window.AllKeysDict:
            window['-GRAPH-'].set_focus()

    elif event == "-HELP-":
        custom_popup(window, "Cropping Info", (
            "Draw a crop box over the subtitle region in the video.\n"
            "Use click+drag to select.\n"
            "In 'Dual Zone' mode, you can draw two crop boxes.\n"
            "If no crop box is selected, the bottom third of the video\n"
            "will be used for OCR by default."),
            icon=ICON_PATH
        )

    elif event == "-GITHUB_ISSUES_LINK-":
        webbrowser.open("https://github.com/timminator/VideOCR/issues")

    elif event == "-GITHUB_RELEASES_LINK-":
        webbrowser.open("https://github.com/timminator/VideOCR/releases")

    elif event == '-SAVE_AS_BTN-':
        output_path = values["--output"]
        output_file_path = pathlib.Path(output_path)

        # Usage of tkinter.tkFileDialog instead of sg.popup_get_file because of the window placement on screen
        filename_chosen = sg.tk.filedialog.asksaveasfilename(
            defaultextension='srt',
            filetypes=(("SubRip Subtitle", "*.srt"), ("All Files", "*.*")),
            initialdir=output_file_path.parent,
            initialfile=output_file_path.stem,
            parent=window.TKroot,
            title="Save As"
        )

        if filename_chosen != "":
            window["--output"].update(filename_chosen)

    elif event == '-WINDOW_RESTORED-':
        if '-GRAPH-' in window.AllKeysDict:
            window['-GRAPH-'].set_focus()

    elif event == '-PROCESS_STARTED-':
        pid = values[event]
        window._videocr_process_pid = pid
        window['Run'].update(disabled=True)
        window['Cancel'].update(disabled=False)

    elif event == '-VIDEOCR_OUTPUT-':
        output_line = values[event]
        window['-OUTPUT-'].update(output_line, append=True)
        window.refresh()

    elif event == '-TASKBAR_STATE_UPDATE-':
        state_info = values[event]
        state = state_info.get('state')
        progress = state_info.get('progress')

        if state and state is not previous_taskbar_state:
            previous_taskbar_state = state
            prog.setState(state)
        if progress is not None:
            prog.setProgress(progress)

    elif event == '-PROCESS_FINISHED-':
        if hasattr(window, '_videocr_process_pid'):
            del window._videocr_process_pid
        if hasattr(window, 'cancelled_by_user'):
            del window.cancelled_by_user
        window['Run'].update(disabled=not video_path)
        window['--output'].update(disabled=not video_path)
        window['-SAVE_AS_BTN-'].update(disabled=not video_path)
        window['Cancel'].update(disabled=True)
        if taskbar_progress_supported:
            prog.setState('normal')
            prog.setProgress(0)

    if event == '-NOTIFICATION_EVENT-':
        notification_info = values[event]
        send_notification(
            notification_info['title'],
            notification_info['message'],
        )

    # --- Video File Selected ---
    elif event == "-VIDEO_PATH-" and values["-VIDEO_PATH-"]:
        video_path = values["-VIDEO_PATH-"]
        window["Run"].update(disabled=True)
        window["-SLIDER-"].update(disabled=True)
        window["-FRAME_TEXT-"].update("Frame -/-")
        window["-TIME_TEXT-"].update("Time: -/-")
        window['--output'].update("", disabled=True)
        window['-SAVE_AS_BTN-'].update(disabled=True)

        reset_crop_state()
        graph.erase()

        img_bytes, orig_w, orig_h, total_f, fps, res_w, res_h, off_x, off_y = get_video_frame(video_path, 0, graph_size)

        if img_bytes and total_f > 0 and fps > 0:
            original_frame_width = orig_w
            original_frame_height = orig_h
            total_frames = total_f
            video_fps = fps
            current_frame_num = 0
            resized_frame_width = res_w
            resized_frame_height = res_h
            image_offset_x = off_x
            image_offset_y = off_y
            current_image_bytes = img_bytes.getvalue()

            graph.draw_image(data=current_image_bytes, location=(image_offset_x, image_offset_y))

            slider_max = total_frames - 1
            window["-SLIDER-"].update(range=(0, slider_max), value=0, disabled=False)
            update_frame_and_time_display(window, current_frame_num, total_frames, video_fps)

            try:
                output_path = generate_output_path(video_path, values)

                window['--output'].update(str(output_path))
                window["Run"].update(disabled=False)
                window['-SAVE_AS_BTN-'].update(disabled=False)

                if '-GRAPH-' in window.AllKeysDict:
                    window['-GRAPH-'].set_focus()

            except Exception as e:
                custom_popup(window, "Unable to Set Output Path",
                    f"Could not automatically generate default output path.\nPlease specify one manually.\nError: {e}",
                    icon=ICON_PATH
                )
                window['--output'].update("", disabled=False)
                window['-SAVE_AS_BTN-'].update(disabled=False)

        else:
            custom_popup(window, "Invalid or Empty Video File",
                f"Could not load video, video has no frames, or FPS is zero:\n{video_path}",
                icon=ICON_PATH
            )
            video_path = None
            total_frames = 0
            video_fps = 0
            window["-VIDEO_PATH-"].update("")

    # --- Slider Moved ---
    elif event == "-SLIDER-" and video_path and total_frames > 0:
        new_frame_num = int(values["-SLIDER-"])
        if new_frame_num != current_frame_num:
            current_frame_num = new_frame_num
            img_bytes, _, _, _, _, res_w, res_h, off_x, off_y = get_video_frame(video_path, current_frame_num, graph_size)

            if img_bytes:
                resized_frame_width, resized_frame_height = res_w, res_h
                image_offset_x, image_offset_y = off_x, off_y
                current_image_bytes = img_bytes.getvalue()

                redraw_canvas_and_boxes()
                update_frame_and_time_display(window, current_frame_num, total_frames, video_fps)

    # --- Handle Keyboard Arrow Keys (Bound to Graph) ---
    elif event in ('-GRAPH-<Left>', '-GRAPH-<Right>'):
        if video_path and total_frames > 0:
            current_frame_num = int(values["-SLIDER-"])
            try:
                seek_step = int(values["--keyboard_seek_step"])
            except (ValueError, TypeError):
                seek_step = KEY_SEEK_STEP

            if event == '-GRAPH-<Left>':
                new_frame_num = max(0, current_frame_num - seek_step)
            else:  # '-GRAPH-<Right>'
                new_frame_num = min(total_frames - 1, current_frame_num + seek_step)

            if new_frame_num != current_frame_num:
                window["-SLIDER-"].update(value=new_frame_num)
                window.write_event_value("-SLIDER-", new_frame_num)

    # --- Graph Interaction ---
    elif event == "-GRAPH-":
        if not video_path or resized_frame_width == 0:
            continue

        graph_x, graph_y = values["-GRAPH-"]

        if not (image_offset_x <= graph_x < image_offset_x + resized_frame_width and
                image_offset_y <= graph_y < image_offset_y + resized_frame_height):
            if window.start_point_img is None:
                continue

        img_x = graph_x - image_offset_x
        img_y = graph_y - image_offset_y

        if window.start_point_img is None:
            max_boxes = 2 if values.get('--use_dual_zone') else 1
            if len(window.crop_boxes) >= max_boxes:
                reset_crop_state()
                redraw_canvas_and_boxes()

            window.start_point_img = (img_x, img_y)

        else:
            window.end_point_img = (img_x, img_y)

            redraw_canvas_and_boxes()

            start_graph_temp = (window.start_point_img[0] + image_offset_x, window.start_point_img[1] + image_offset_y)
            end_graph_temp = (img_x + image_offset_x, img_y + image_offset_y)
            graph.draw_rectangle(start_graph_temp, end_graph_temp, line_color='red')

    # --- Graph Interaction ---
    elif event == "-GRAPH-+UP":
        if window.start_point_img and window.end_point_img:

            rect_x1_img = max(0, min(window.start_point_img[0], window.end_point_img[0]))
            rect_y1_img = max(0, min(window.start_point_img[1], window.end_point_img[1]))
            rect_x2_img = min(resized_frame_width, max(window.start_point_img[0], window.end_point_img[0]))
            rect_y2_img = min(resized_frame_height, max(window.start_point_img[1], window.end_point_img[1]))

            window.start_point_img = None
            window.end_point_img = None

            min_draw_size = 7
            if (rect_x2_img - rect_x1_img) < min_draw_size or (rect_y2_img - rect_y1_img) < min_draw_size:
                redraw_canvas_and_boxes()
                continue

            crop_x = math.floor(rect_x1_img * original_frame_width / resized_frame_width)
            crop_y = math.floor(rect_y1_img * original_frame_height / resized_frame_height)
            crop_w = math.ceil((rect_x2_img - rect_x1_img) * original_frame_width / resized_frame_width)
            crop_h = math.ceil((rect_y2_img - rect_y1_img) * original_frame_height / resized_frame_height)

            new_box = {
                'coords': {'crop_x': crop_x, 'crop_y': crop_y, 'crop_width': crop_w, 'crop_height': crop_h},
                'img_points': ((rect_x1_img, rect_y1_img), (rect_x2_img, rect_y2_img))
            }
            window.crop_boxes.append(new_box)

            redraw_canvas_and_boxes()

            if not values.get('--use_dual_zone', False):
                b = window.crop_boxes[0]
                coord_text = f"({b['coords']['crop_x']}, {b['coords']['crop_y']}, {b['coords']['crop_width']}, {b['coords']['crop_height']})"
            else:
                coords_str_parts = []
                for i, b in enumerate(window.crop_boxes):
                    coords_str_parts.append(f"Zone {i + 1}: ({b['coords']['crop_x']}, {b['coords']['crop_y']}, {b['coords']['crop_width']}, {b['coords']['crop_height']})")
                coord_text = "  |  ".join(coords_str_parts)

            window['-CROP_COORDS-'].update(coord_text)
            window["-CLEAR_CROP-"].update(disabled=False)

    # --- Clear Crop Button ---
    elif event == "-CLEAR_CROP-":
        reset_crop_state()
        if video_path and current_image_bytes:
            graph.erase()
            graph.draw_image(data=current_image_bytes, location=(image_offset_x, image_offset_y))

    # --- Run Button Clicked ---
    elif event == "Run" and video_path:
        if hasattr(window, '_videocr_process_pid') and window._videocr_process_pid:
            window['-OUTPUT-'].update("Process is already running.\n", append=True)
            continue

        window.cancelled_by_user = False
        window['-OUTPUT-'].update("")

        # --- Input Validation ---
        errors = []

        time_start = values.get('--time_start', '').strip()
        time_end = values.get('--time_end', '').strip()

        if not is_valid_time_format(time_start):
            errors.append("Invalid Start Time format. Use MM:SS or HH:MM:SS.")
        if not is_valid_time_format(time_end):
            errors.append("Invalid End Time format. Use MM:SS or HH:MM:SS.")

        time_start_seconds = time_string_to_seconds(time_start)
        time_end_seconds = time_string_to_seconds(time_end)

        video_duration_seconds = 0
        if total_frames > 0 and video_fps > 0:
            video_duration_seconds = total_frames / video_fps

        if time_start_seconds is not None:
            if time_start_seconds > video_duration_seconds:
                errors.append(f"Start Time ({format_time(time_start_seconds)}) exceeds video duration ({format_time(video_duration_seconds)}).")

        if time_end and time_end_seconds is not None:
            if time_end_seconds > video_duration_seconds:
                errors.append(f"End Time ({format_time(time_end_seconds)}) exceeds video duration ({format_time(video_duration_seconds)}).")

        if time_start_seconds is not None and time_end_seconds is not None:
            if time_start_seconds > time_end_seconds:
                errors.append("Start Time cannot be after End Time.")

        numeric_params = {
            '--conf_threshold': (int, 0, 100, "Confidence Threshold"),
            '--sim_threshold': (int, 0, 100, "Similarity Threshold"),
            '--brightness_threshold': (int, 0, 255, "Brightness Threshold"),
            '--ssim_threshold': (int, 0, 100, "SSIM Threshold"),
            '--frames_to_skip': (int, 0, None, "Frames to Skip"),
            '--max_merge_gap': (float, 0.0, None, "Max Merge Gap"),
            '--min_subtitle_duration': (float, 0.0, None, "Minimum Subtitle Duration"),
        }

        for key, (cast_type, min_val, max_val, name) in numeric_params.items():
            value_str = values.get(key, '').strip()

            if not value_str:
                continue

            range_str_parts = []
            if min_val is not None:
                range_str_parts.append(f">={min_val}")
            if max_val is not None:
                range_str_parts.append(f"<={max_val}")
            range_str = " and ".join(range_str_parts)

            type_name = cast_type.__name__
            article = "an" if type_name.startswith(("i", "I")) else "a"

            try:
                value = cast_type(value_str)
                if (min_val is not None and value < min_val) or (max_val is not None and value > max_val):
                    raise ValueError
            except ValueError:
                errors.append(f"Invalid value for {name}. Must be {article} {type_name} {range_str}.")

        if errors:
            window['-OUTPUT-'].update("Validation Errors:\n", append=True)
            for error in errors:
                window['-OUTPUT-'].update(f"- {error}\n", append=True)
            window.refresh()
            continue

        use_dual_zone = values.get('--use_dual_zone', False)

        if use_dual_zone and len(window.crop_boxes) != 2:
            window['-OUTPUT-'].update("Dual Zone OCR is enabled, but 2 crop boxes have not been selected.\n")
            continue

        args = {}
        args['video_path'] = video_path

        selected_lang_name = values.get('-LANG_COMBO-', default_display_language)
        lang_abbr = language_abbr_lookup.get(selected_lang_name)
        if lang_abbr:
            args['lang'] = lang_abbr

        selected_pos_name = values.get('-SUBTITLE_POS_COMBO-', default_display_subtitle_position)
        pos_value = subtitle_pos_lookup.get(selected_pos_name)
        if pos_value:
            args['subtitle_position'] = pos_value

        for key in values:
            if key.startswith('--') and key not in ['--keyboard_seek_step', '--default_output_dir', '--save_in_video_dir', '--send_notification']:
                stripped_key = key.lstrip('-')
                value = values.get(key)
                if isinstance(value, bool):
                    args[stripped_key] = value
                elif value is not None and str(value).strip() != '':
                    args[stripped_key] = str(value).strip()

        # Handle send_notification specifically to store it as a boolean and not a string
        args['send_notification'] = values.get('--send_notification', True)

        # Add crop coordinates based on mode
        use_fullframe = values.get('--use_fullframe', False)

        if use_dual_zone:
            box1_coords = window.crop_boxes[0]['coords']
            args.update(box1_coords)

            box2_coords = window.crop_boxes[1]['coords']
            args.update({f"{k}2": v for k, v in box2_coords.items()})

        elif not use_fullframe:
            if window.crop_boxes:
                args.update(window.crop_boxes[0]['coords'])

        window['Run'].update(disabled=True)
        window['Cancel'].update(disabled=False)

        ocr_thread = threading.Thread(target=run_ocr_thread, args=(args, window), daemon=True)
        ocr_thread.start()

    # --- Cancel Button Clicked ---
    elif event == "Cancel":
        pid_to_kill = getattr(window, '_videocr_process_pid', None)
        if pid_to_kill:
            window.cancelled_by_user = True
            window['-OUTPUT-'].update("\nCancelling process...\n", append=True)
            window.refresh()
            try:
                kill_process_tree(pid_to_kill)
                window['-OUTPUT-'].update("\nProcess cancelled by user.\n", append=True)
            except Exception as e:
                window['-OUTPUT-'].update(f"\nError attempting to cancel process: {e}\n", append=True)
            finally:
                if hasattr(window, '_videocr_process_pid'):
                    del window._videocr_process_pid
        else:
            window['-OUTPUT-'].update("\nNo process is currently running to cancel.\n", append=True)
            window['Cancel'].update(disabled=True)
            window['Run'].update(disabled=not video_path)

# --- Cleanup ---
window.close()
