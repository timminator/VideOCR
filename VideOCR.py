import PySimpleGUI as sg
import subprocess
import os
import cv2
import io
import re
import threading
import math
import configparser
import ctypes
import platform
import pathlib
import datetime
from pymediainfo import MediaInfo

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
    """Determines DPI scaling factor on Windows, returns 1.0 otherwise."""
    if platform.system() == "Windows":
        try:
            dpi = ctypes.windll.shcore.GetScaleFactorForDevice(0)  # 0 = primary monitor
            return dpi / 100.0
        except:
            return 1.0
    else:
        return 1.0
dpi_scale = get_dpi_scaling()

# --- Determine VideOCR location ---
def find_videocr_program():
    """Determines the path to the videocr-cli-sa executable (.exe or .bin)."""
    possible_folders = ['videocr-cli-sa-CPU-v1.2.1', 'videocr-cli-sa-GPU-v1.2.1']
    program_name = 'videocr-cli-sa'

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
APP_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEOCR_PATH = find_videocr_program()
DEFAULT_OUTPUT_SRT = ""
DEFAULT_LANG = "en"
DEFAULT_CONF_THRESHOLD = 75
DEFAULT_SIM_THRESHOLD = 80
DEFAULT_MAX_MERGE_GAP = 0.09
DEFAULT_SIM_IMAGE_THRESHOLD = 100
DEFAULT_SIM_PIXEL_THRESHOLD = 25
DEFAULT_FRAMES_TO_SKIP = 1
DEFAULT_TIME_START = "0:00"
KEY_SEEK_STEP = 1
CONFIG_FILE = 'videocr_gui_config.ini'
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
            os.killpg(pid, 15)
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
    '--time_start': DEFAULT_TIME_START,
    '--time_end': '',
    '--conf_threshold': str(DEFAULT_CONF_THRESHOLD),
    '--sim_threshold': str(DEFAULT_SIM_THRESHOLD),
    '--max_merge_gap': str(DEFAULT_MAX_MERGE_GAP),
    '--brightness_threshold': '',
    '--similar_image_threshold': str(DEFAULT_SIM_IMAGE_THRESHOLD),
    '--similar_pixel_threshold': str(DEFAULT_SIM_PIXEL_THRESHOLD),
    '--frames_to_skip': str(DEFAULT_FRAMES_TO_SKIP),
    '--use_fullframe': False,
    '--use_gpu': True,
    '--use_angle_cls': True,
    '--keyboard_seek_step': str(KEY_SEEK_STEP),
    '--default_output_dir': DEFAULT_DOCUMENTS_DIR,
    '--save_in_video_dir': True,
    }

def save_settings(values):
    """Saves current settings from GUI elements to the config file."""
    config = configparser.ConfigParser()
    config.add_section(CONFIG_SECTION)

    settings_to_save = {
        '-LANG_COMBO-': values.get('-LANG_COMBO-', get_default_settings().get('-LANG_COMBO-')),
        '--time_start': values.get('--time_start', get_default_settings().get('--time_start')),
        '--time_end': values.get('--time_end', get_default_settings().get('--time_end')),
        '--conf_threshold': values.get('--conf_threshold', get_default_settings().get('--conf_threshold')),
        '--sim_threshold': values.get('--sim_threshold', get_default_settings().get('--sim_threshold')),
        '--max_merge_gap': values.get('--max_merge_gap', get_default_settings().get('--max_merge_gap')),
        '--brightness_threshold': values.get('--brightness_threshold', get_default_settings().get('--brightness_threshold')),
        '--similar_image_threshold': values.get('--similar_image_threshold', get_default_settings().get('--similar_image_threshold')),
        '--similar_pixel_threshold': values.get('--similar_pixel_threshold', get_default_settings().get('--similar_pixel_threshold')),
        '--frames_to_skip': values.get('--frames_to_skip', get_default_settings().get('--frames_to_skip')),
        '--use_fullframe': values.get('--use_fullframe', get_default_settings().get('--use_fullframe')),
        '--use_gpu': values.get('--use_gpu', get_default_settings().get('--use_gpu')),
        '--use_angle_cls': values.get('--use_angle_cls', get_default_settings().get('--use_angle_cls')),
        '--keyboard_seek_step': values.get('--keyboard_seek_step', get_default_settings().get('--keyboard_seek_step')),
        '--default_output_dir': values.get('--default_output_dir', get_default_settings().get('--default_output_dir')),
        '--save_in_video_dir': values.get('--save_in_video_dir', get_default_settings().get('--save_in_video_dir')),
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
                    ('-LANG_COMBO-', 'combo'),
                    ('--time_start', 'input'),
                    ('--time_end', 'input'),
                    ('--conf_threshold', 'input'),
                    ('--sim_threshold', 'input'),
                    ('--max_merge_gap', 'input'),
                    ('--brightness_threshold', 'input'),
                    ('--similar_image_threshold', 'input'),
                    ('--similar_pixel_threshold', 'input'),
                    ('--frames_to_skip', 'input'),
                    ('--use_fullframe', 'checkbox'),
                    ('--use_gpu', 'checkbox'),
                    ('--use_angle_cls', 'checkbox'),
                    ('--keyboard_seek_step', 'input'),
                    ('--default_output_dir', 'input'),
                    ('--save_in_video_dir', 'checkbox'),
                ]

                for key, elem_type in settings_to_load:
                    if config.has_option(CONFIG_SECTION, key):
                        try:
                            if elem_type == 'checkbox':
                                value = config.getboolean(CONFIG_SECTION, key)
                            elif elem_type == 'combo':
                                value_str = config.get(CONFIG_SECTION, key)
                                if value_str in language_display_names:
                                    value = value_str
                                else:
                                    value = default_display_language
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

def run_videocr(args_dict, window):
    """Runs the videocr.exe tool in a separate thread and streams output."""
    command = [VIDEOCR_PATH]

    for key, value in args_dict.items():
        if value is not None and value != '':
            arg_name = f"--{key}"
            command.append(arg_name)
            if isinstance(value, bool):
                command.append(str(value).lower())
            else:
                command.append(str(value))

    STEP1_PROGRESS_PATTERN = re.compile(r"Step 1: Processing image (\d+) of (\d+)")
    STEP2_PROGRESS_PATTERN = re.compile(r"Step 2: Performing OCR on image (\d+) of (\d+)")
    STARTING_OCR_PATTERN = re.compile(r"Starting PaddleOCR")
    GENERATING_SUBTITLES_PATTERN = re.compile(r"Generating subtitles")

    last_reported_percentage_step1 = -1
    last_reported_percentage_step2 = -1

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
                                   start_new_session=True if os.name != 'nt' else False
                                   )

        window._videocr_process = process
        window.write_event_value('-PROCESS_STARTED-', process.pid)

        if process.stdout:
            for line in iter(process.stdout.readline, ''):
                if process.poll() is not None:
                    if process.returncode is not None and process.returncode != 0:
                        break
                    break

                line = line.rstrip('\r\n')

                match1 = STEP1_PROGRESS_PATTERN.search(line)
                if match1:
                    current_item = int(match1.group(1))
                    total_items = int(match1.group(2))
                    percentage = 0
                    if total_items > 0:
                        percentage = int((current_item / total_items) * 100)

                    if current_item == 1 or percentage >= last_reported_percentage_step1 + 5 or percentage == 100:
                        window.write_event_value('-VIDEOCR_OUTPUT-', f"Step 1: Processed image {current_item} of {total_items} ({percentage}%)\n")
                        last_reported_percentage_step1 = percentage
                    continue

                match2 = STEP2_PROGRESS_PATTERN.search(line)
                if match2:
                    current_item = int(match2.group(1))
                    total_items = int(match2.group(2))
                    percentage = 0
                    if total_items > 0:
                        percentage = int((current_item / total_items) * 100)

                    if current_item == 1 or percentage >= last_reported_percentage_step2 + 5 or percentage == 100:
                        window.write_event_value('-VIDEOCR_OUTPUT-', f"Step 2: Performed OCR on image {current_item} of {total_items} ({percentage}%)\n")
                        last_reported_percentage_step2 = percentage
                    continue

                if STARTING_OCR_PATTERN.search(line):
                    window.write_event_value('-VIDEOCR_OUTPUT-', f"{line}\n")
                    continue

                if GENERATING_SUBTITLES_PATTERN.search(line):
                    window.write_event_value('-VIDEOCR_OUTPUT-', f"{line}\n")
                    continue

        if process and process.poll() is None:
            process.wait()

        if process:
            exit_code = process.returncode
            if exit_code == 0:
                window.write_event_value('-VIDEOCR_OUTPUT-', "\nSuccessfully generated subtitle file!\n")
            elif exit_code is not None:
                window.write_event_value('-VIDEOCR_OUTPUT-', f"\nProcess finished with exit code: {exit_code}\n")

    except FileNotFoundError:
        window.write_event_value('-VIDEOCR_OUTPUT-', f"\nError: '{VIDEOCR_PATH}' not found. Please check the path.\n")
    except Exception as e:
        window.write_event_value('-VIDEOCR_OUTPUT-', f"\nAn error occurred: {e}\n")

    finally:
        if hasattr(window, '_videocr_process'):
            del window._videocr_process
        window.write_event_value('-PROCESS_FINISHED-', None)

# --- GUI Layout ---
sg.theme("Darkgrey13")

tab1_content = [
    [sg.Text("Video File:", size=(15,1)), sg.Input(key="-VIDEO_PATH-", disabled_readonly_background_color=sg.theme_input_background_color(), readonly=True, enable_events=True, size=(40,1)),
     sg.FileBrowse(file_types=(("Video Files", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.wmv"), ("All Files", "*.*")))],
    [sg.Text("Output SRT:", size=(15,1)), sg.Input(key="--output", disabled_readonly_background_color=sg.theme_input_background_color(), readonly=True, disabled=True, size=(40,1)),
     sg.Button('Save As...', key="-SAVE_AS_BTN-", disabled=True)],
    [sg.Text("Subtitle Language:", size=(15,1)),
     sg.Combo(language_display_names, default_value=default_display_language, key="-LANG_COMBO-", size=(38,1), readonly=True, enable_events=True),
     sg.Push(),
     sg.Button("How to Use", key="-HELP-")],
    [sg.Graph(canvas_size=graph_size, graph_bottom_left=(0, graph_size[1]), graph_top_right=(graph_size[0], 0),
              key="-GRAPH-", change_submits=True, drag_submits=True, enable_events=True, background_color='black')],
    [sg.Text("Seek:"), sg.Slider(range=(0, 0), key="-SLIDER-", orientation='h', size=(45, 15), expand_x=True, enable_events=True, disable_number_display=True, disabled=True)],
    [
        sg.Push(),
        sg.Text("Frame: -/-", key="-FRAME_TEXT-"), sg.Text("|"), sg.Text("Time: -/-", key="-TIME_TEXT-")
    ],
    [sg.Text("Crop Box (X, Y, W, H):"), sg.Text("Not Set", key="-CROP_COORDS-", size=(30,1))],
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
    [sg.Text("Start Time (e.g., 0:00 or 1:23:45):", size=(28,1), tooltip="Specify the starting time to begin processing."),
     sg.Input(DEFAULT_TIME_START, key="--time_start", size=(15,1), enable_events=True, tooltip="Specify the starting time to begin processing.")],
    [sg.Text("End Time (e.g., 0:10 or 2:34:56):", size=(28,1), tooltip="Specify the ending time to stop processing."),
     sg.Input("", key="--time_end", size=(15,1), enable_events=True, tooltip="Specify the ending time to stop processing.")],
    [sg.Text("Confidence Threshold (0-100):", size=(28,1), tooltip="Minimum confidence score for detected text."),
     sg.Input(DEFAULT_CONF_THRESHOLD, key="--conf_threshold", size=(10,1), enable_events=True, tooltip="Minimum confidence score for detected text.")],
    [sg.Text("Similarity Threshold (0-100):", size=(28,1), tooltip="Threshold for merging text lines based on content similarity."),
     sg.Input(DEFAULT_SIM_THRESHOLD, key="--sim_threshold", size=(10,1), enable_events=True, tooltip="Threshold for merging text lines based on content similarity.")],
    [sg.Text("Max Merge Gap (seconds):", size=(28,1), tooltip="Maximum allowed time gap to merge similar subtitles."),
     sg.Input(DEFAULT_MAX_MERGE_GAP, key="--max_merge_gap", size=(10,1), enable_events=True, tooltip="Maximum allowed time gap to merge similar subtitles.")],
    [sg.Text("Brightness Threshold (0-255):", size=(28,1), tooltip="Applies a brightness filter before OCR.\nPixels below the threshold are blacked out."),
     sg.Input("", key="--brightness_threshold", size=(10,1), enable_events=True, tooltip="Applies a brightness filter before OCR.\nPixels below the threshold are blacked out. Leave empty to disable.")],
    [sg.Text("Similar Image Threshold:", size=(28,1), tooltip="Maximum number of different pixels between frames to skip OCR"),
     sg.Input(DEFAULT_SIM_IMAGE_THRESHOLD, key="--similar_image_threshold", size=(10,1), enable_events=True, tooltip="Maximum number of different pixels between frames to skip OCR")],
    [sg.Text("Similar Pixel Threshold (0-255):", size=(28,1), tooltip="Tolerance level for considering pixels as similar when comparing images (0-255)."),
     sg.Input(DEFAULT_SIM_PIXEL_THRESHOLD, key="--similar_pixel_threshold", size=(10,1), enable_events=True, tooltip="Tolerance level for considering pixels as similar when comparing images (0-255).")],
    [sg.Text("Frames to Skip:", size=(28,1), tooltip="Process only every Nth frame (e.g., 1 = process every 2nd frame)."),
     sg.Input(DEFAULT_FRAMES_TO_SKIP, key="--frames_to_skip", size=(10,1), enable_events=True, tooltip="Process only every Nth frame (e.g., 1 = process every 2nd frame).")],
    [sg.Checkbox("Enable GPU Usage (Only affects GPU version)", default=True, key="--use_gpu", enable_events=True, tooltip="Attempt to use the GPU for OCR processing if available and supported.")],
    [sg.Checkbox("Use Full Frame OCR", default=False, key="--use_fullframe", enable_events=True, tooltip="Process the entire video frame instead of using a crop box.")],
    [sg.Checkbox("Enable Angle Classification", default=True, key="--use_angle_cls", enable_events=True, tooltip="Detect and correct rotated text angles.")],
    [sg.HorizontalSeparator()],
    [sg.Text("VideOCR Settings:", font=('Arial', 10, 'bold'))],
    [sg.Checkbox("Save SRT in Video Directory", size=(28,1), default=True, key="--save_in_video_dir", enable_events=True, tooltip="Save the output SRT file in the same directory as the video file.\nIf enabled, \"Output directory\" is disabled.")],
    [sg.Text("Output Directory:", size=(28,1), tooltip="Folder where generated SRT files will be placed.\nDisabled when \"Save SRT in Video Directory\" is enabled."),
     sg.Input(DEFAULT_DOCUMENTS_DIR, key="--default_output_dir", disabled_readonly_background_color=sg.theme_input_background_color(), readonly=True, size=(40,1), enable_events=True, tooltip="Folder where generated SRT files will be placed.\nDisabled when \"Save SRT in Video Directory\" is enabled."),
     sg.FolderBrowse(key="-FOLDER_BROWSE_BTN-", disabled=True)],
    [sg.Text("Keyboard Seek Step (frames):", size=(28,1), tooltip="Number of frames to jump when using Left/Right arrows."),
     sg.Input(KEY_SEEK_STEP, key="--keyboard_seek_step", size=(10,1), enable_events=True, tooltip="Number of frames to jump when using Left/Right arrows.")],
]
tab2_layout = [[sg.Column(tab2_content,
                           size_subsample_height=1,
                           scrollable=True,
                           vertical_scroll_only=True,
                           expand_x=True,
                           expand_y=True)]]

layout = [
    [sg.TabGroup([[sg.Tab('Process Video', tab1_layout, key='-TAB-VIDEO-'),
                    sg.Tab('Advanced Settings', tab2_layout, key='-TAB-ADVANCED-')]], key='-TABGROUP-', enable_events=True, expand_x=True, expand_y=True)]
]

if platform.system() == "Windows":
    ICON_PATH = os.path.join(APP_DIR, 'VideOCR.ico')
else:
    ICON_PATH = os.path.join(APP_DIR, 'VideOCR.png')

window = sg.Window("VideOCR", layout, icon=ICON_PATH, finalize=True, resizable=True)

graph = window["-GRAPH-"]

# --- Initialize crop box state in the window object ---
window.drawing_rectangle_id = None
window.start_point_img = None
window.end_point_img = None
window.final_start_point_img = None
window.final_end_point_img = None
window.crop_box_coords = {}

# --- Bind keyboard events to the graph element ---
window.bind('<Left>', '-GRAPH-<Left>')
window.bind('<Right>', '-GRAPH-<Right>')

# --- Bind window restore event ---
window.bind('<Map>', '-WINDOW_RESTORED-')

# --- Load settings when the application starts ---
load_settings(window)

save_in_video_dir_checked_at_start = window.find_element('--save_in_video_dir').get()
if not save_in_video_dir_checked_at_start:
    window['-FOLDER_BROWSE_BTN-'].update(disabled=False)

# --- Define the list of keys that, when changed, should trigger a settings save ---
KEYS_TO_AUTOSAVE = [
    '-LANG_COMBO-',
    '--time_start',
    '--time_end',
    '--conf_threshold',
    '--sim_threshold',
    '--max_merge_gap',
    '--brightness_threshold',
    '--similar_image_threshold',
    '--similar_pixel_threshold',
    '--frames_to_skip',
    '--use_fullframe',
    '--use_gpu',
    '--use_angle_cls',
    '--keyboard_seek_step',
    '--default_output_dir',
    '--save_in_video_dir',
]

# --- Event Loop ---
while True:
    event, values = window.read(timeout=100)

    if event == sg.WIN_CLOSED:
        if values is not None:
            pass

        process_to_kill = getattr(window, '_videocr_process', None)
        if process_to_kill is not None and process_to_kill.poll() is None:
            try:
                kill_process_tree(process_to_kill.pid)
                process_to_kill.wait(timeout=2)
            except:
                pass
        break

    # --- Auto-save settings when a relevant element changes and switch focus back ---
    if event in KEYS_TO_AUTOSAVE:
        if values is not None:
            save_settings(values)
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

    # --- Save As Button Click ---
    if event == '-SAVE_AS_BTN-':
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

    # --- Handle events sent from the worker thread ---
    if event == "-HELP-":
        custom_popup(window, "Cropping Info", (
            "Draw a crop box over the subtitle region in the video.\n"
            "Use click+drag to select.\n"
            "If no crop box is selected, the bottom third of the video\n"
            "will be used for OCR by default."),
            icon=ICON_PATH
        )

    elif event == '-WINDOW_RESTORED-':
        if '-GRAPH-' in window.AllKeysDict:
            window['-GRAPH-'].set_focus()

    elif event == '-PROCESS_STARTED-':
        pid = values[event]
        window['Run'].update(disabled=True)
        window['Cancel'].update(disabled=False)

    elif event == '-VIDEOCR_OUTPUT-':
        output_line = values[event]
        window['-OUTPUT-'].update(output_line, append=True)
        window.refresh()

    elif event == '-PROCESS_FINISHED-':
        window['Run'].update(disabled=False)
        window['--output'].update(disabled=False if video_path else True)
        window['-SAVE_AS_BTN-'].update(disabled=False if video_path else True)
        window['Cancel'].update(disabled=True)

    # --- Video File Selected ---
    elif event == "-VIDEO_PATH-" and values["-VIDEO_PATH-"]:
        video_path = values["-VIDEO_PATH-"]
        window["Run"].update(disabled=True)
        window["-CLEAR_CROP-"].update(disabled=True)
        window["-SLIDER-"].update(disabled=True)
        window["-FRAME_TEXT-"].update("Frame -/-")
        window["-TIME_TEXT-"].update("Time: -/-")
        window['--output'].update("", disabled=True)
        window['-SAVE_AS_BTN-'].update(disabled=True)

        # --- Reset crop box state in the window object ---
        if window.drawing_rectangle_id is not None:
            graph.delete_figure(window.drawing_rectangle_id)
        window.drawing_rectangle_id = None
        window.start_point_img = None
        window.end_point_img = None
        window.final_start_point_img = None
        window.final_end_point_img = None
        window.crop_box_coords.clear()
        window['-CROP_COORDS-'].update("Not Set")

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
                resized_frame_width = res_w
                resized_frame_height = res_h
                image_offset_x = off_x
                image_offset_y = off_y
                current_image_bytes = img_bytes.getvalue()

                graph.erase()
                graph.draw_image(data=current_image_bytes, location=(image_offset_x, image_offset_y))

                # --- Redraw the rectangle IF finalized points are stored ---
                if window.final_start_point_img is not None and window.final_end_point_img is not None:
                    graph_start_x = min(window.final_start_point_img[0], window.final_end_point_img[0]) + image_offset_x
                    graph_start_y = min(window.final_start_point_img[1], window.final_end_point_img[1]) + image_offset_y
                    graph_end_x = max(window.final_start_point_img[0], window.final_end_point_img[0]) + image_offset_x
                    graph_end_y = max(window.final_end_point_img[1], window.final_end_point_img[1]) + image_offset_y

                    window.drawing_rectangle_id = graph.draw_rectangle((graph_start_x, graph_start_y), (graph_end_x, graph_end_y), line_color='red')

                update_frame_and_time_display(window, current_frame_num, total_frames, video_fps)

    # --- Handle Keyboard Arrow Keys (Bound to Graph) ---
    elif event in ('-GRAPH-<Left>', '-GRAPH-<Right>'):
        if video_path and total_frames > 0:
            if values is not None and "-SLIDER-" in values:
                current_frame_num = int(values["-SLIDER-"])
            else:
                continue

            try:
                if values is not None and "--keyboard_seek_step" in values:
                    seek_step = int(values["--keyboard_seek_step"])
                    if seek_step <= 0:
                        seek_step = KEY_SEEK_STEP
                else:
                    seek_step = KEY_SEEK_STEP
            except (ValueError, TypeError):
                seek_step = KEY_SEEK_STEP

            if event == '-GRAPH-<Left>':
                new_frame_num = max(0, current_frame_num - seek_step)
            elif event == '-GRAPH-<Right>':
                new_frame_num = min(total_frames - 1, current_frame_num + seek_step)

            if new_frame_num != current_frame_num:
                current_frame_num = new_frame_num
                window["-SLIDER-"].update(value=current_frame_num)

                img_bytes, _, _, _, _, res_w, res_h, off_x, off_y = get_video_frame(video_path, current_frame_num, graph_size)

                if img_bytes:
                    resized_frame_width = res_w
                    resized_frame_height = res_h
                    image_offset_x = off_x
                    image_offset_y = off_y
                    current_image_bytes = img_bytes.getvalue()

                    graph.erase()
                    graph.draw_image(data=current_image_bytes, location=(image_offset_x, image_offset_y))

                    if window.final_start_point_img is not None and window.final_end_point_img is not None:
                        graph_start_x = min(window.final_start_point_img[0], window.final_end_point_img[0]) + image_offset_x
                        graph_start_y = min(window.final_start_point_img[1], window.final_end_point_img[1]) + image_offset_y
                        graph_end_x = max(window.final_start_point_img[0], window.final_end_point_img[0]) + image_offset_x
                        graph_end_y = max(window.final_end_point_img[1], window.final_end_point_img[1]) + image_offset_y
                        window.drawing_rectangle_id = graph.draw_rectangle((graph_start_x, graph_start_y), (graph_end_x, graph_end_y), line_color='red')

                    update_frame_and_time_display(window, current_frame_num, total_frames, video_fps)

    # --- Graph Interaction (Cropping) ---
    elif event == "-GRAPH-":
        if not video_path or resized_frame_width == 0: continue

        graph_x, graph_y = values["-GRAPH-"]

        if not (image_offset_x <= graph_x < image_offset_x + resized_frame_width and
                image_offset_y <= graph_y < image_offset_y + resized_frame_height):
            if window.start_point_img is None: continue

        img_x = graph_x - image_offset_x
        img_y = graph_y - image_offset_y

        if window.start_point_img is None:
            if window.drawing_rectangle_id is not None:
                graph.delete_figure(window.drawing_rectangle_id)
                window.drawing_rectangle_id = None
            window.final_start_point_img = None
            window.final_end_point_img = None
            window.crop_box_coords.clear()
            window['-CROP_COORDS-'].update("Not Set")
            window["-CLEAR_CROP-"].update(disabled=True)

            window.start_point_img = (img_x, img_y)
            window.end_point_img = None

        elif window.start_point_img:
            current_drag_img_x = img_x
            current_drag_img_y = img_y
            window.end_point_img = (current_drag_img_x, current_drag_img_y)

            graph.erase()
            graph.draw_image(data=current_image_bytes, location=(image_offset_x, image_offset_y))

            graph_start_x = window.start_point_img[0] + image_offset_x
            graph_start_y = window.start_point_img[1] + image_offset_y
            current_graph_x = img_x + image_offset_x
            current_graph_y = img_y + image_offset_y

            draw_start_graph = (min(graph_start_x, current_graph_x), min(graph_start_y, current_graph_y))
            draw_end_graph = (max(graph_start_x, current_graph_x), max(graph_start_y, current_graph_y))

            graph.draw_rectangle(draw_start_graph, draw_end_graph, line_color='red')

    elif event == "-GRAPH-+UP":
        if window.start_point_img is not None and window.end_point_img is not None and resized_frame_width > 0 and resized_frame_height > 0:

            graph.erase()
            graph.draw_image(data=current_image_bytes, location=(image_offset_x, image_offset_y))

            if window.drawing_rectangle_id is not None:
                graph.delete_figure(window.drawing_rectangle_id)
                window.drawing_rectangle_id = None

            rect_x1_img_raw = window.start_point_img[0]
            rect_y1_img_raw = window.start_point_img[1]
            rect_x2_img_raw = window.end_point_img[0]
            rect_y2_img_raw = window.end_point_img[1]

            rect_x1_img = min(rect_x1_img_raw, rect_x2_img_raw)
            rect_y1_img = min(rect_y1_img_raw, rect_y2_img_raw)
            rect_x2_img = max(rect_x1_img_raw, rect_x2_img_raw)
            rect_y2_img = max(rect_y1_img_raw, rect_y2_img_raw)

            rect_x1_img_clamped = max(0, min(rect_x1_img, resized_frame_width))
            rect_y1_img_clamped = max(0, min(rect_y1_img, resized_frame_height))
            rect_x2_img_clamped = max(0, min(rect_x2_img, resized_frame_width))
            rect_y2_img_clamped = max(0, min(rect_y2_img, resized_frame_height))

            rect_x1_img_draw = max(0, min(rect_x1_img, resized_frame_width - 1))
            rect_y1_img_draw = max(0, min(rect_y1_img, resized_frame_height - 1))
            rect_x2_img_draw = max(0, min(rect_x2_img, resized_frame_width - 1))
            rect_y2_img_draw = max(0, min(rect_y2_img, resized_frame_height - 1))

            min_size_img = 5
            if abs(rect_x2_img_clamped - rect_x1_img_clamped) < min_size_img or abs(rect_y2_img_clamped - rect_y1_img_clamped) < min_size_img:
                window.final_start_point_img = None
                window.final_end_point_img = None
                window.crop_box_coords.clear()
                window['-CROP_COORDS-'].update("Not Set")
                window["-CLEAR_CROP-"].update(disabled=True)
                window.start_point_img = None
                window.end_point_img = None
                continue

            crop_x = int(math.floor(rect_x1_img_clamped * original_frame_width / resized_frame_width))
            crop_y = int(math.floor(rect_y1_img_clamped * original_frame_height / resized_frame_height))
            crop_w = int(math.ceil((rect_x2_img_clamped - rect_x1_img_clamped) * original_frame_width / resized_frame_width))
            crop_h = int(math.ceil((rect_y2_img_clamped - rect_y1_img_clamped) * original_frame_height / resized_frame_height))

            crop_w = max(1, crop_w)
            crop_h = max(1, crop_h)

            crop_x = max(0, min(crop_x, original_frame_width - crop_w if original_frame_width > 0 else 0))
            crop_y = max(0, min(crop_y, original_frame_height - crop_h if original_frame_height > 0 else 0))

            window.crop_box_coords = {
                '--crop_x': crop_x,
                '--crop_y': crop_y,
                '--crop_width': crop_w,
                '--crop_height': crop_h
            }
            window['-CROP_COORDS-'].update(f"({crop_x}, {crop_y}, {crop_w}, {crop_h})")
            window["-CLEAR_CROP-"].update(disabled=False)

            window.final_start_point_img = (rect_x1_img_draw, rect_y1_img_draw)
            window.final_end_point_img = (rect_x2_img_draw, rect_y2_img_draw)

            graph_start_x = window.final_start_point_img[0] + image_offset_x
            graph_start_y = window.final_start_point_img[1] + image_offset_y
            graph_end_x = window.final_end_point_img[0] + image_offset_x
            graph_end_y = window.final_end_point_img[1] + image_offset_y

            window.drawing_rectangle_id = graph.draw_rectangle((graph_start_x, graph_start_y), (graph_end_x, graph_end_y), line_color='red')

        window.start_point_img = None
        window.end_point_img = None

    # --- Clear Crop Button ---
    elif event == "-CLEAR_CROP-":
        if window.drawing_rectangle_id is not None:
            graph.delete_figure(window.drawing_rectangle_id)
            window.drawing_rectangle_id = None
        window.start_point_img = None
        window.end_point_img = None
        window.final_start_point_img = None
        window.final_end_point_img = None
        window.crop_box_coords.clear()
        window['-CROP_COORDS-'].update("Not Set")
        window["-CLEAR_CROP-"].update(disabled=True)

        if video_path and current_image_bytes:
            graph.erase()
            graph.draw_image(data=current_image_bytes, location=(image_offset_x, image_offset_y))

    # --- Run Button Clicked ---
    elif event == "Run" and video_path:
        if hasattr(window, '_videocr_process') and window._videocr_process.poll() is None:
            window['-OUTPUT-'].update("Process is already running.\n", append=True)
            continue

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
                errors.append(f"Start Time ({format_time(time_start_seconds)}) exceeds video duration ({format_time(video_duration_seconds)}). Video duration is {format_time(video_duration_seconds)}.")

        if time_end and time_end_seconds is not None:
            if time_end_seconds > video_duration_seconds:
                errors.append(f"End Time ({format_time(time_end_seconds)}) exceeds video duration ({format_time(video_duration_seconds)}). Video duration is {format_time(video_duration_seconds)}.")

        if time_start_seconds is not None and time_end_seconds is not None:
            if time_start_seconds > time_end_seconds:
                errors.append("Start Time cannot be after End Time.")

        numeric_params = {
            '--conf_threshold': (int, 0, 100, "Confidence Threshold"),
            '--sim_threshold': (int, 0, 100, "Similarity Threshold"),
            '--brightness_threshold': (int, 0, 255, "Brightness Threshold"),
            '--similar_image_threshold': (int, 0, None, "Similar Image Threshold"),
            '--similar_pixel_threshold': (int, 0, 255, "Similar Pixel Threshold"),
            '--frames_to_skip': (int, 0, None, "Frames to Skip"),
            '--max_merge_gap': (float, 0.0, None, "Max Merge Gap"),
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

        window['Run'].update(disabled=True)
        window['Cancel'].update(disabled=False)

        args = {}
        args['video_path'] = video_path

        selected_lang_name = values.get('-LANG_COMBO-', default_display_language)
        lang_abbr = language_abbr_lookup.get(selected_lang_name)
        if lang_abbr:
            args['lang'] = lang_abbr

        for key in values:
            if key.startswith('--') and key not in ['--keyboard_seek_step', '--default_output_dir', '--save_in_video_dir']:
                value = values.get(key)
                if isinstance(value, bool):
                    args[key.lstrip('-')] = str(value).lower()
                elif value is not None and str(value).strip() != '':
                    args[key.lstrip('-')] = str(value).strip()

        if not values.get('--use_fullframe', False) and window.crop_box_coords:
            args.update({k.lstrip('-'): v for k, v in window.crop_box_coords.items()})
            args['use_fullframe'] = 'false'
        elif values.get('--use_fullframe', False):
            for crop_key in ['crop_x', 'crop_y', 'crop_width', 'crop_height']:
                args.pop(crop_key, None)
            args['use_fullframe'] = 'true'
        else:
            if 'use_fullframe' not in args:
                args['use_fullframe'] = 'false'

        thread = threading.Thread(target=run_videocr, args=(args, window), daemon=True)
        thread.start()

    # --- Cancel Button Clicked ---
    elif event == "Cancel":
        process_to_kill = getattr(window, '_videocr_process', None)

        if process_to_kill is not None and process_to_kill.poll() is None:
            pid_to_kill = process_to_kill.pid

            window['-OUTPUT-'].update("\nCancelling process...\n", append=True)
            window.refresh()
            try:
                kill_process_tree(pid_to_kill)
                if process_to_kill and process_to_kill.poll() is None:
                    try:
                        process_to_kill.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        window['-OUTPUT-'].update("\nProcess did not terminate promptly after kill signal.\n", append=True)

                window['-OUTPUT-'].update("\nProcess cancelled by user.\n", append=True)

            except Exception as e:
                window['-OUTPUT-'].update(f"\nError attempting to cancel process: {e}\n", append=True)

            finally:
                if hasattr(window, '_videocr_process'):
                    del window._videocr_process
                window['Run'].update(disabled=False)
                window['--output'].update(disabled=False)
                window['-SAVE_AS_BTN-'].update(disabled=False)
                window['Cancel'].update(disabled=True)
        else:
            window['-OUTPUT-'].update("\nNo process is currently running to cancel.\n", append=True)

# --- Cleanup ---
window.close()