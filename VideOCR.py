# Compilation instructions
# nuitka-project: --standalone
# nuitka-project: --enable-plugin=tk-inter
# nuitka-project: --windows-console-mode=disable
# nuitka-project: --include-windows-runtime-dlls=yes
# nuitka-project: --include-data-files=Installer/*.ico=VideOCR.ico
# nuitka-project: --include-data-files=Installer/*.png=VideOCR.png
# nuitka-project: --include-data-dir=languages=languages

# Windows-specific metadata for the executable
# nuitka-project-if: {OS} == "Windows":
#     nuitka-project-set: APP_VERSION = __import__("_version").__version__
#     nuitka-project: --file-description="VideOCR"
#     nuitka-project: --file-version={APP_VERSION}
#     nuitka-project: --product-name="VideOCR-GUI"
#     nuitka-project: --product-version={APP_VERSION}
#     nuitka-project: --copyright="timminator"
#     nuitka-project: --windows-icon-from-ico=Installer/VideOCR.ico

from __future__ import annotations

import ast
import configparser
import contextlib
import ctypes
import datetime
import io
import json
import math
import os
import pathlib
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter.font as tkFont
import urllib.request
import webbrowser
from typing import IO, Any, cast

import av
import numpy as np
import psutil  # type: ignore
import PySimpleGUI as sg  # type: ignore
from PIL import Image
from wakepy import keep

if sys.platform == "win32":
    import PyTaskbar  # type: ignore
    from winotify import Notification, audio  # type: ignore
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('VideOCR')
else:
    from plyer import notification  # type: ignore

from _version import __version__


# -- Save errors to log file ---
def log_error(message: str, log_name: str = "error_log.txt") -> str:
    """Logs error messages to a platform-appropriate log file location."""
    portable_flag = os.path.join(APP_DIR, 'portable_mode.txt')

    if os.path.exists(portable_flag):
        log_dir = APP_DIR
    else:
        if sys.platform == "win32":
            log_dir = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.join(str(pathlib.Path.home()), 'AppData', 'Local'), "VideOCR")
        else:
            xdg_state = os.environ.get("XDG_STATE_HOME")
            if xdg_state:
                log_dir = os.path.join(xdg_state, "VideOCR")
            else:
                log_dir = os.path.join(str(pathlib.Path.home()), ".local", "state", "VideOCR")

    os.makedirs(log_dir, exist_ok=True)

    log_path = os.path.join(log_dir, log_name)
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {message}\n")

    return log_path


# --- Make application DPI aware ---
def make_dpi_aware() -> None:
    """Makes the application DPI aware on Windows to prevent scaling issues."""
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(True)
        except AttributeError:
            log_error("Could not set DPI awareness.")


# --- Determine DPI scaling factor ---
def get_dpi_scaling() -> float:
    """Determines DPI scaling factor for the current OS."""
    def round_to_quarter_step(scale: float) -> float:
        dpi_scaling_factors = [1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0]
        return min(dpi_scaling_factors, key=lambda x: abs(x - scale))

    if sys.platform == "win32":
        try:
            dpi = int(ctypes.windll.shcore.GetScaleFactorForDevice(0))  # 0 = primary monitor
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


def get_gui_scaling_multiplier() -> float | None:
    """Reads the custom GUI scaling multiplier from the config file."""
    if os.path.exists(CONFIG_FILE):
        temp_config = configparser.ConfigParser()
        try:
            temp_config.read(CONFIG_FILE)
            if temp_config.has_option(CONFIG_SECTION, 'gui_scaling'):
                val = temp_config.get(CONFIG_SECTION, 'gui_scaling')
                if val != 'System Default':
                    return float(val)
        except Exception:
            pass
    return None


def get_scaled_graph_size(custom_scale: float | None, base_w: int, base_h: int) -> tuple[int, int]:
    """Calculates graph size using a custom scale, falling back to OS DPI if None."""
    scale = custom_scale if custom_scale is not None else get_dpi_scaling()
    return int(base_w * scale), int(base_h * scale)


# --- Send notification --
def send_notification(title: str, message: str) -> None:
    """Sends a notification via winotify on Windows and via Plyer on Linux."""
    if sys.platform == "win32":
        try:
            toast = Notification(
                app_id="VideOCR",
                title=title,
                msg=message,
                icon=os.path.join(APP_DIR, 'VideOCR.ico')
            )
            toast.set_audio(audio.Default, loop=False)
            toast.show()
        except Exception as e:
            log_error(f"Failed to send notification. Error: {e}")
    else:
        try:
            notification.notify(
                title=title,
                message=message,
                app_name='VideOCR',
                app_icon=os.path.join(APP_DIR, 'VideOCR.png')
            )
        except Exception as e:
            log_error(f"Failed to send notification. Error: {e}")


# --- Determine VideOCR location ---
def find_videocr_program() -> str | None:
    """Determines the path to the videocr-cli executable (.exe or .bin)."""
    program_name = 'videocr-cli'
    extension = ".exe" if sys.platform == "win32" else ".bin"

    root_path = os.path.join(APP_DIR, f'{program_name}{extension}')
    if os.path.exists(root_path):
        return root_path

    return None


# --- Determine Config file location ---
def get_config_file_path() -> str:
    """Determines the correct path for the config file depending on installation mode."""
    portable_flag = os.path.join(APP_DIR, 'portable_mode.txt')

    if os.path.exists(portable_flag):
        config_dir = APP_DIR
    else:
        if sys.platform == "win32":
            config_dir = os.path.join(os.environ.get('APPDATA') or os.path.join(str(pathlib.Path.home()), 'AppData', 'Roaming'), 'VideOCR')
        else:
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config:
                config_dir = os.path.join(xdg_config, "VideOCR")
            else:
                config_dir = os.path.join(str(pathlib.Path.home()), ".config", "VideOCR")

        os.makedirs(config_dir, exist_ok=True)

    return os.path.join(config_dir, 'videocr_gui_config.ini')


# --- Configuration ---
PROGRAM_VERSION = __version__
APP_DIR = os.path.dirname(os.path.abspath(__file__))
LANGUAGES_DIR = os.path.join(APP_DIR, 'languages')
VIDEOCR_PATH = find_videocr_program()
DEFAULT_OUTPUT_SRT = ""
DEFAULT_LANG = "en"
DEFAULT_OCR_ENGINE = "PaddleOCR (Det. + Rec.)"
DEFAULT_SUBTITLE_LANGUAGE = 'English'
DEFAULT_SUBTITLE_POSITION = "center"
DEFAULT_SUBTITLE_ALIGNMENT = "bottom-center"
DEFAULT_CONF_THRESHOLD = 75
DEFAULT_SIM_THRESHOLD = 80
DEFAULT_MAX_MERGE_GAP = 0.1
DEFAULT_MIN_SUBTITLE_DURATION = 0.2
DEFAULT_SSIM_THRESHOLD = 92
DEFAULT_OCR_IMAGE_MAX_WIDTH = 720
DEFAULT_FRAMES_TO_SKIP = 1
DEFAULT_TIME_START = "0:00"
KEY_SEEK_STEP = 1
CONFIG_FILE = get_config_file_path()
CONFIG_SECTION = 'Settings'
try:
    DEFAULT_DOCUMENTS_DIR = str(pathlib.Path.home() / "Documents")
except Exception:
    DEFAULT_DOCUMENTS_DIR = ""

# --- Language Data ---
LANGUAGE_CODE_TO_NATIVE_NAME = {
    'en': 'English',
    'de': 'Deutsch',
    'ch': '中文',
    'es': 'Español',
    'fr': 'Français',
    'pt': 'Português',
    'it': 'Italiano',
    'ar': 'العربية',
    'ru': 'Русский',
    'id': 'Bahasa Indonesia',
    'th': 'ไทย',
    'ko': '한국어',
    'ja': '日本語',
    'vi': 'Tiếng Việt',
}

# --- Language Data ---
PADDLEOCR_LANGUAGES_LIST = [
    ('Abaza', 'abq'), ('Adyghe', 'ady'), ('Afrikaans', 'af'), ('Albanian', 'sq'),
    ('Angika', 'ang'), ('Arabic', 'ar'), ('Avar', 'ava'), ('Azerbaijani', 'az'),
    ('Baluchi', 'bal'), ('Bashkir', 'ba'), ('Basque', 'eu'), ('Belarusian', 'be'),
    ('Bhojpuri', 'bho'), ('Bihari', 'bh'), ('Bosnian', 'bs'), ('Bulgarian', 'bg'),
    ('Buryat', 'bua'), ('Catalan', 'ca'), ('Chechen', 'che'), ('Chinese & English', 'ch'),
    ('Chinese Traditional', 'chinese_cht'), ('Chuvash', 'cv'), ('Croatian', 'hr'),
    ('Czech', 'cs'), ('Danish', 'da'), ('Dargwa', 'dar'), ('Dutch', 'nl'),
    ('English', 'en'), ('Estonian', 'et'), ('Finnish', 'fi'), ('French', 'fr'),
    ('Galician', 'gl'), ('Georgian', 'ka'), ('German', 'german'), ('Goan Konkani', 'gom'),
    ('Greek', 'el'), ('Haryanvi', 'bgc'), ('Hindi', 'hi'), ('Hungarian', 'hu'),
    ('Icelandic', 'is'), ('Indonesian', 'id'), ('Ingush', 'inh'), ('Irish', 'ga'),
    ('Italian', 'it'), ('Japanese', 'japan'), ('Kabardian', 'kbd'), ('Kalmyk', 'xal'),
    ('Karakalpak', 'kaa'), ('Kazakh', 'kk'), ('Komi', 'kv'), ('Korean', 'korean'),
    ('Kurdish', 'ku'), ('Kyrgyz', 'ky'), ('Lak', 'lbe'), ('Latin', 'la'),
    ('Latvian', 'lv'), ('Lezghian', 'lez'), ('Lithuanian', 'lt'), ('Luxembourgish', 'lb'),
    ('Macedonian', 'mk'), ('Magahi', 'mah'), ('Maithili', 'mai'), ('Malay', 'ms'),
    ('Maltese', 'mt'), ('Maori', 'mi'), ('Marathi', 'mr'), ('Meadow Mari', 'mhr'),
    ('Moldovan', 'mo'), ('Mongolian', 'mn'), ('Nagpuri', 'sck'), ('Nepali', 'ne'),
    ('Newari', 'new'), ('Norwegian', 'no'), ('Occitan', 'oc'), ('Ossetian', 'os'),
    ('Pali', 'pi'), ('Pashto', 'ps'), ('Persian', 'fa'), ('Polish', 'pl'),
    ('Portuguese', 'pt'), ('Quechua', 'qu'), ('Romansh', 'rm'), ('Romanian', 'ro'),
    ('Russian', 'ru'), ('Sanskrit', 'sa'), ('Serbian(cyrillic)', 'rs_cyrillic'),
    ('Serbian(latin)', 'rs_latin'), ('Sindhi', 'sd'), ('Slovak', 'sk'),
    ('Slovenian', 'sl'), ('Spanish', 'es'), ('Swahili', 'sw'), ('Swedish', 'sv'),
    ('Tabassaran', 'tab'), ('Tagalog', 'tl'), ('Tajik', 'tg'), ('Tamil', 'ta'),
    ('Tatar', 'tt'), ('Telugu', 'te'), ('Thai', 'th'), ('Turkish', 'tr'),
    ('Tuvan', 'tyv'), ('Udmurt', 'udm'), ('Ukrainian', 'uk'), ('Urdu', 'ur'),
    ('Uyghur', 'ug'), ('Uzbek', 'uz'), ('Vietnamese', 'vi'), ('Welsh', 'cy'),
    ('Sakha', 'sah'),
]
PADDLEOCR_LANGUAGES_LIST.sort(key=lambda x: x[0])
paddle_display_names = [lang[0] for lang in PADDLEOCR_LANGUAGES_LIST]
paddle_abbr_lookup = {name: abbr for name, abbr in PADDLEOCR_LANGUAGES_LIST}

GOOGLE_LENS_LANGUAGES_LIST = [
    ("Afrikaans", "af"), ("Albanian", "sq"), ("Arabic", "ar"), ("Armenian", "hy"),
    ("Belarusian", "be"), ("Bengali", "bn"), ("Bulgarian", "bg"), ("Catalan", "ca"),
    ("Chinese", "zh"), ("Croatian", "hr"), ("Czech", "cs"), ("Danish", "da"),
    ("Dutch", "nl"), ("English", "en"), ("Estonian", "et"), ("Filipino", "fil"),
    ("Finnish", "fi"), ("French", "fr"), ("German", "de"), ("Greek", "el"),
    ("Gujarati", "gu"), ("Hebrew", "iw"), ("Hindi", "hi"), ("Hungarian", "hu"),
    ("Icelandic", "is"), ("Indonesian", "id"), ("Italian", "it"), ("Japanese", "ja"),
    ("Kannada", "kn"), ("Khmer", "km"), ("Korean", "ko"), ("Lao", "lo"),
    ("Latvian", "lv"), ("Lithuanian", "lt"), ("Macedonian", "mk"), ("Malay", "ms"),
    ("Malayalam", "ml"), ("Marathi", "mr"), ("Nepali", "ne"), ("Norwegian", "no"),
    ("Persian", "fa"), ("Polish", "pl"), ("Portuguese", "pt"), ("Punjabi", "pa"),
    ("Romanian", "ro"), ("Russian", "ru"), ("Russian (PETR1708)", "ru-PETR1708"),
    ("Serbian", "sr"), ("Serbian (Latin)", "sr-Latn"), ("Slovak", "sk"), ("Slovenian", "sl"),
    ("Spanish", "es"), ("Swedish", "sv"), ("Tagalog", "tl"), ("Tamil", "ta"),
    ("Telugu", "te"), ("Thai", "th"), ("Turkish", "tr"), ("Ukrainian", "uk"),
    ("Vietnamese", "vi"), ("Yiddish", "yi"), ("Amharic", "am"), ("Ancient Greek", "grc"),
    ("Assamese", "as"), ("Azerbaijani", "az"), ("Azerbaijani (Cyrl)", "az-Cyrl"), ("Basque", "eu"),
    ("Bosnian", "bs"), ("Burmese", "my"), ("Cebuano", "ceb"), ("Cherokee", "chr"),
    ("Dhivehi", "dv"), ("Dzonkha", "dz"), ("Esperanto", "eo"), ("Galician", "gl"),
    ("Georgian", "ka"), ("Haitian Creole", "ht"), ("Irish", "ga"), ("Javanese", "jv"),
    ("Kazakh", "kk"), ("Kirghiz", "ky"), ("Latin", "la"), ("Maltese", "mt"),
    ("Mongolian", "mn"), ("Oriya", "or"), ("Pashto", "ps"), ("Sanskrit", "sa"),
    ("Sinhala", "si"), ("Swahili", "sw"), ("Syriac", "syr"), ("Tibetan", "bo"),
    ("Tigirinya", "ti"), ("Urdu", "ur"), ("Uzbek", "uz"), ("Uzbek (Cyrl)", "uz-Cyrl"),
    ("Welsh", "cy"), ("Zulu", "zu"), ("Acehnese", "ace"), ("Acholi", "ach"),
    ("Adangme", "ada"), ("Akan", "ak"), ("Algonquinian", "alg"), ("Araucanian/Mapuche", "arn"),
    ("Asturian", "ast"), ("Athabaskan", "ath"), ("Aymara", "ay"), ("Balinese", "ban"),
    ("Bambara", "bm"), ("Bantu", "bnt"), ("Bashkir", "ba"), ("Batak", "btk"),
    ("Bemba", "bem"), ("Bikol", "bik"), ("Bislama", "bi"), ("Breton", "br"),
    ("Chechen", "ce"), ("Chinese (Simplified)", "zh-Hans"), ("Chinese (Traditional)", "zh-Hant"), ("Chinese (Hong Kong)", "zh-Hant-HK"),
    ("Choctaw", "cho"), ("Chuvash", "cv"), ("Cree", "cr"), ("Creek", "mus"),
    ("Crimean Tatar", "crh"), ("Dakota", "dak"), ("Duala", "dua"), ("Efik", "efi"),
    ("English (British)", "en-GB"), ("Ewe", "ee"), ("Faroese", "fo"), ("Fijian", "fj"),
    ("Fon", "fon"), ("French (Canadian)", "fr-CA"), ("Fulah", "ff"), ("Ga", "gaa"),
    ("Ganda", "lg"), ("Gayo", "gay"), ("Gilbertese", "gil"), ("Gothic", "got"),
    ("Guarani", "gn"), ("Hausa", "ha"), ("Hawaiian", "haw"), ("Herero", "hz"),
    ("Hiligaynon", "hil"), ("Iban", "iba"), ("Igbo", "ig"), ("Iloko", "ilo"),
    ("Kabyle", "kab"), ("Kachin", "kac"), ("Kalaallisut", "kl"), ("Kamba", "kam"),
    ("Kanuri", "kr"), ("Kara-Kalpak", "kaa"), ("Khasi", "kha"), ("Kikuyu", "ki"),
    ("Kinyarwanda", "rw"), ("Komi", "kv"), ("Kongo", "kg"), ("Kosraean", "kos"),
    ("Kuanyama", "kj"), ("Lingala", "ln"), ("Low German", "nds"), ("Lozi", "loz"),
    ("Luba-Katanga", "lu"), ("Luo", "luo"), ("Madurese", "mad"), ("Malagasy", "mg"),
    ("Mandingo", "man"), ("Manx", "gv"), ("Maori", "mi"), ("Marshallese", "mh"),
    ("Mende", "men"), ("Middle English", "enm"), ("Middle High German", "gmh"), ("Minangkabau", "min"),
    ("Mohawk", "moh"), ("Mongo", "lol"), ("Nahuatl", "nah"), ("Navajo", "nv"),
    ("Ndonga", "ng"), ("Niuean", "niu"), ("North Ndebele", "nd"), ("Northern Sotho", "nso"),
    ("Nyanja", "ny"), ("Nyankole", "nyn"), ("Nyasa Tonga", "tog"), ("Nzima", "nzi"),
    ("Occitan", "oc"), ("Ojibwa", "oj"), ("Old English", "ang"), ("Old French", "fro"),
    ("Old High German", "goh"), ("Old Norse", "non"), ("Old Provencal", "pro"), ("Ossetic", "os"),
    ("Pampanga", "pam"), ("Pangasinan", "pag"), ("Papiamento", "pap"), ("Portuguese (European)", "pt-PT"),
    ("Quechua", "qu"), ("Romansh", "rm"), ("Romany", "rom"), ("Rundi", "rn"),
    ("Sakha", "sah"), ("Samoan", "sm"), ("Sango", "sg"), ("Scots", "sco"),
    ("Scottish Gaelic", "gd"), ("Shona", "sn"), ("Songhai", "son"), ("Southern Sotho", "st"),
    ("Spanish (Latin American)", "es-419"), ("Sundanese", "su"), ("Swati", "ss"), ("Tahitian", "ty"),
    ("Tajik", "tg"), ("Tatar", "tt"), ("Temne", "tem"), ("Tongan", "to"),
    ("Tsonga", "ts"), ("Tswana", "tn"), ("Turkmen", "tk"), ("Udmurt", "udm"),
    ("Venda", "ve"), ("Votic", "vot"), ("Western Frisian", "fy"), ("Wolof", "wo"),
    ("Xhosa", "xh"), ("Yoruba", "yo"), ("Zapotec", "zap")
]
GOOGLE_LENS_LANGUAGES_LIST.sort(key=lambda x: x[0])
lens_display_names = [lang[0] for lang in GOOGLE_LENS_LANGUAGES_LIST]
lens_abbr_lookup = {name: abbr for name, abbr in GOOGLE_LENS_LANGUAGES_LIST}

OCR_ENGINES = [
    'PaddleOCR (Det. + Rec.)',
    'PaddleOCR (Det.) + Google Lens (Rec.)'
]

# Mapping from PaddleOCR internal codes to standard ISO 639 codes for deviating abbreviations
PADDLE_TO_ISO_MAP = {
    'ch': 'zh',
    'chinese_cht': 'zh',
    'german': 'de',
    'japan': 'ja',
    'korean': 'ko',
    'rs_cyrillic': 'sr',
    'rs_latin': 'sr',
    'ang': 'anp',
    'mah': 'mag',
    'mo': 'ro',
    # Prefer 2-Letter Codes
    'ava': 'av',
    'che': 'ce',
}

# --- Subtitle Position Data ---
SUBTITLE_POSITIONS_LIST = [
    ('pos_center', 'center'),
    ('pos_left', 'left'),
    ('pos_right', 'right'),
    ('pos_any', 'any')
]
DEFAULT_INTERNAL_SUBTITLE_POSITION = 'center'

# --- Subtitle Alignment Data ---
SUBTITLE_ALIGNMENT_LIST = [
    ('align_bottom_center', 'bottom-center'),
    ('align_bottom_left', 'bottom-left'),
    ('align_bottom_right', 'bottom-right'),
    ('align_top_center', 'top-center'),
    ('align_top_left', 'top-left'),
    ('align_top_right', 'top-right'),
    ('align_middle_center', 'middle-center'),
    ('align_middle_left', 'middle-left'),
    ('align_middle_right', 'middle-right')
]

# --- Post-Action Master List ---
if sys.platform == "win32":
    POST_ACTION_KEYS = ['action_none', 'action_sleep', 'action_hibernate', 'action_shutdown', 'action_lock']
else:
    POST_ACTION_KEYS = ['action_none', 'action_sleep', 'action_shutdown']

DEFAULT_ACTION_TEXTS = {
    'action_none': 'Do Nothing',
    'action_sleep': 'Sleep',
    'action_hibernate': 'Hibernate',
    'action_shutdown': 'Shutdown',
    'action_lock': 'Lock'
}

# --- Status Translation Helpers ---
INTERNAL_STATUS_TO_LANG_KEY = {
    'Pending': 'status_pending',
    'Processing': 'status_processing',
    'Completed': 'status_completed',
    'Cancelled': 'status_cancelled_queue',
    'Error': 'status_error',
    'Paused': 'status_paused'
}

DEFAULT_STATUS_TEXTS = {
    'status_pending': 'Pending',
    'status_processing': 'Processing',
    'status_completed': 'Completed',
    'status_cancelled_queue': 'Cancelled',
    'status_error': 'Error',
    'status_paused': 'Paused'
}

# --- GUI Scaling Data ---
GUI_SCALING_LIST = [
    ('system_default', 'System Default'),
    ('scale_1_0', '1.0'),
    ('scale_1_25', '1.25'),
    ('scale_1_5', '1.5'),
    ('scale_1_75', '1.75'),
    ('scale_2_0', '2.0')
]
DEFAULT_GUI_SCALING = 'System Default'

# --- Cross-Platform Cursor Mapping ---
if sys.platform == "win32":
    CURSORS = {
        'vertical': 'size_ns',
        'horizontal': 'size_we',
        'diag_nw_se': 'size_nw_se',
        'diag_ne_sw': 'size_ne_sw',
        'move': 'fleur',
        'crosshair': 'crosshair',
    }
else:
    CURSORS = {
        'vertical': 'sb_v_double_arrow',
        'horizontal': 'sb_h_double_arrow',
        'diag_nw_se': 'bottom_right_corner',
        'diag_ne_sw': 'bottom_left_corner',
        'move': 'fleur',
        'crosshair': 'crosshair',
    }

# --- Global Variables ---
video_path = None
original_frame_width = 0
original_frame_height = 0
video_duration_ms = 0.0
current_time_ms = 0.0
resized_frame_width = 0
resized_frame_height = 0
image_offset_x = 0
image_offset_y = 0
gui_scale_multiplier = get_gui_scaling_multiplier()
graph_size = get_scaled_graph_size(custom_scale=gui_scale_multiplier, base_w=672, base_h=378)
current_image_bytes = None
prog = None
previous_taskbar_state = None
LANG: dict[str, str] = {}
current_wake_lock: Any = None
batch_queue: list[dict[str, Any]] = []
gui_queue: queue.Queue[tuple[str, Any]] = queue.Queue()


# --- i18n Language Functions ---
def get_available_languages() -> dict[str, str]:
    """Scans the 'languages' directory and returns a dict mapping native names to language codes."""
    langs: dict[str, str] = {}
    if not os.path.isdir(LANGUAGES_DIR):
        log_error(f"Languages directory not found at {LANGUAGES_DIR}")
        return {'English': 'en'}

    for filename in os.listdir(LANGUAGES_DIR):
        if filename.endswith('.json'):
            lang_code = filename[:-5]
            native_name = LANGUAGE_CODE_TO_NATIVE_NAME.get(lang_code, lang_code.capitalize())
            langs[native_name] = lang_code

    return langs if langs else {'English': 'en'}


def load_language(lang_code: str) -> None:
    """Loads a language JSON file into a dictionary. Falls back to 'en'."""
    global LANG

    def load_file(code: str) -> dict[str, str] | None:
        lang_path = os.path.join(LANGUAGES_DIR, f"{code}.json")
        if os.path.exists(lang_path):
            try:
                with open(lang_path, encoding='utf-8') as f:
                    return cast(dict[str, str], json.load(f))
            except json.JSONDecodeError as e:
                log_error(f"Syntax error in language file {code}.json: {e}")
        return None

    loaded = load_file(lang_code)
    if loaded is None:
        log_error(f"Language file for '{lang_code}' not found or invalid. Falling back to English.")
        loaded = load_file('en')
        if loaded is None:
            log_error("CRITICAL: English language file 'en.json' is missing or invalid.")
            sg.popup_error("Critical Error: Default language file 'en.json' is missing or corrupt.\nPlease reinstall the application.", title="Fatal Error")
            sys.exit()

    LANG = loaded


def update_gui_text(window: sg.Window, is_paused: bool = False) -> None:
    """Updates all text elements in the GUI based on the loaded LANG dictionary."""
    if not LANG:
        return

    key_map = {
        # Tab 1
        '-SAVE_AS_BTN-': {'text': 'btn_save_as'},
        '-BTN-OPEN-FILE-': {'text': 'btn_browse'},
        '-BTN-OPEN-FOLDER-': {'text': 'btn_browse_folder'},
        '-TAB-VIDEO-': {'text': 'tab_video'},
        '-LBL-SOURCE-': {'text': 'lbl_source'},
        '-LBL-OUTPUT_SRT-': {'text': 'lbl_output_srt'},
        '-LBL-OCR_ENGINE-': {'text': 'lbl_ocr_engine', 'tooltip': 'tip_ocr_engine'},
        '-OCR_ENGINE_COMBO-': {'tooltip': 'tip_ocr_engine'},
        '-LBL-SUB_LANG-': {'text': 'lbl_sub_lang'},
        '-LBL-SUB_POS-': {'text': 'lbl_sub_pos', 'tooltip': 'tip_sub_pos'},
        '-SUBTITLE_POS_COMBO-': {'tooltip': 'tip_sub_pos'},
        '-BTN-HELP-': {'text': 'btn_how_to_use'},
        '-LBL-SEEK-': {'text': 'lbl_seek'},
        '-LBL-CROP_BOX-': {'text': 'lbl_crop_box'},
        '-CROP_COORDS-': {'text': 'crop_not_set'},
        '-TIME_TEXT-': {'text': 'time_text_empty'},
        '-BTN-RUN-': {'text': 'btn_run'},
        '-BTN-CANCEL-': {'text': 'btn_cancel'},
        '-BTN-CLEAR_CROP-': {'text': 'btn_clear_crop'},
        '-LBL-PROGRESS-': {'text': 'lbl_progress'},
        '-LBL-LOG-': {'text': 'lbl_log'},
        '-LBL-WHEN_READY-': {'text': 'lbl_when_ready'},
        '-BTN-ADD-BATCH-': {'text': 'btn_add_to_queue'},
        '-BTN-BATCH-ADD-ALL-': {'text': 'btn_add_all_to_queue'},

        # Queue Tab
        '-TAB-BATCH-': {'text': 'tab_batch'},
        '-LBL-QUEUE-TITLE-': {'text': 'lbl_queue_title'},
        '-BTN-BATCH-START-': {'text': 'btn_start_queue'},
        '-BTN-BATCH-STOP-': {'text': 'btn_stop_queue'},
        '-BTN-BATCH-UP-': {'tooltip': 'tip_batch_up'},
        '-BTN-BATCH-DOWN-': {'tooltip': 'tip_batch_down'},
        '-BTN-BATCH-RESET-': {'text': 'btn_reset', 'tooltip': 'tip_batch_reset'},
        '-BTN-BATCH-EDIT-': {'text': 'btn_edit', 'tooltip': 'tip_batch_edit'},
        '-BTN-BATCH-REMOVE-': {'text': 'btn_remove', 'tooltip': 'tip_batch_remove'},
        '-BTN-BATCH-CLEAR-': {'text': 'btn_clear_queue', 'tooltip': 'tip_batch_clear'},

        # Tab 2
        '-TAB-ADVANCED-': {'text': 'tab_advanced'},
        '-LBL-OCR_SETTINGS-': {'text': 'lbl_ocr_settings'},
        '-LBL-TIME_START-': {'text': 'lbl_time_start', 'tooltip': 'tip_time_start'},
        '--time_start': {'tooltip': 'tip_time_start'},
        '-LBL-TIME_END-': {'text': 'lbl_time_end', 'tooltip': 'tip_time_end'},
        '--time_end': {'tooltip': 'tip_time_end'},
        '-LBL-CONF_THRESHOLD-': {'text': 'lbl_conf_threshold', 'tooltip': 'tip_conf_threshold'},
        '--conf_threshold': {'tooltip': 'tip_conf_threshold'},
        '-LBL-SIM_THRESHOLD-': {'text': 'lbl_sim_threshold', 'tooltip': 'tip_sim_threshold'},
        '--sim_threshold': {'tooltip': 'tip_sim_threshold'},
        '-LBL-MERGE_GAP-': {'text': 'lbl_merge_gap', 'tooltip': 'tip_merge_gap'},
        '--max_merge_gap': {'tooltip': 'tip_merge_gap'},
        '-LBL-BRIGHTNESS-': {'text': 'lbl_brightness', 'tooltip': 'tip_brightness'},
        '--brightness_threshold': {'tooltip': 'tip_brightness'},
        '-LBL-SSIM-': {'text': 'lbl_ssim', 'tooltip': 'tip_ssim'},
        '--ssim_threshold': {'tooltip': 'tip_ssim'},
        '-LBL-OCR_WIDTH-': {'text': 'lbl_ocr_width', 'tooltip': 'tip_ocr_width'},
        '--ocr_image_max_width': {'tooltip': 'tip_ocr_width'},
        '-LBL-FRAMES_SKIP-': {'text': 'lbl_frames_skip', 'tooltip': 'tip_frames_skip'},
        '--frames_to_skip': {'tooltip': 'tip_frames_skip'},
        '-LBL-MIN_DURATION-': {'text': 'lbl_min_duration', 'tooltip': 'tip_min_duration'},
        '--min_subtitle_duration': {'tooltip': 'tip_min_duration'},
        '--use_gpu': {'text': 'chk_use_gpu', 'tooltip': 'tip_use_gpu'},
        '--use_fullframe': {'text': 'chk_full_frame', 'tooltip': 'tip_full_frame'},
        '--use_dual_zone': {'text': 'chk_dual_zone', 'tooltip': 'tip_dual_zone'},
        'enable_subtitle_alignment': {'text': 'chk_enable_subtitle_alignment', 'tooltip': 'tip_enable_subtitle_alignment'},
        '-LBL-SUBTITLE-ALIGNMENT-': {'text': 'lbl_subtitle_alignment1', 'tooltip': 'tip_subtitle_alignment1'},
        '--subtitle_alignment': {'tooltip': 'tip_subtitle_alignment1'},
        '-LBL-SUBTITLE-ALIGNMENT2-': {'text': 'lbl_subtitle_alignment2', 'tooltip': 'tip_subtitle_alignment2'},
        '--subtitle_alignment2': {'tooltip': 'tip_subtitle_alignment2'},
        '--use_angle_cls': {'text': 'chk_angle_cls', 'tooltip': 'tip_angle_cls'},
        '--post_processing': {'text': 'chk_post_processing', 'tooltip': 'tip_post_processing'},
        '--use_server_model': {'text': 'chk_server_model', 'tooltip': 'tip_server_model'},
        '-LBL-VIDEOCR_SETTINGS-': {'text': 'lbl_videocr_settings'},
        '-LBL-UI_LANG-': {'text': 'lbl_ui_lang', 'tooltip': 'tip_ui_lang'},
        '-UI_LANG_COMBO-': {'tooltip': 'tip_ui_lang'},
        '-LBL-GUI_SCALING-': {'text': 'lbl_gui_scaling', 'tooltip': 'tip_gui_scaling'},
        'gui_scaling': {'tooltip': 'tip_gui_scaling'},
        '--save_crop_box': {'text': 'chk_save_crop_box', 'tooltip': 'tip_save_crop_box'},
        '--save_in_video_dir': {'text': 'chk_save_in_video_dir', 'tooltip': 'tip_save_in_video_dir'},
        '-LBL-OUTPUT_DIR-': {'text': 'lbl_output_dir', 'tooltip': 'tip_output_dir'},
        '-BTN-FOLDER_BROWSE-': {'text': 'btn_browse_folder'},
        '-LBL-SEEK_STEP-': {'text': 'lbl_seek_step', 'tooltip': 'tip_seek_step'},
        '--keyboard_seek_step': {'tooltip': 'tip_seek_step'},
        '--send_notification': {'text': 'chk_send_notification', 'tooltip': 'tip_send_notification'},
        '--check_for_updates': {'text': 'chk_check_updates', 'tooltip': 'tip_check_updates'},
        'prevent_system_sleep': {'text': 'chk_prevent_sleep', 'tooltip': 'tip_prevent_sleep'},
        '--normalize_to_simplified_chinese': {'text': 'chk_normalize_chinese', 'tooltip': 'tip_normalize_chinese'},
        '-BTN-CHECK_UPDATE_MANUAL-': {'text': 'btn_check_now'},

        # Tab 3
        '-TAB-ABOUT-': {'text': 'tab_about'},
        '-LBL-ABOUT_VERSION-': {'text': 'lbl_about_version'},
        '-LBL-GET_NEWEST-': {'text': 'lbl_get_newest'},
        '-LBL-BUG_REPORT-': {'text': 'lbl_bug_report'},
    }

    tab_group = window['-TABGROUP-']

    for key, lang_keys in key_map.items():
        if key.startswith('-TAB-'):
            if 'text' in lang_keys and lang_keys['text'] in LANG:
                tab_element_widget = window[key].Widget
                tab_group.Widget.tab(tab_element_widget, text=LANG[lang_keys['text']])
            continue

        if key in window.AllKeysDict:
            element = window[key]

            if 'text' in lang_keys and lang_keys['text'] in LANG:
                new_content = LANG[lang_keys['text']]
                if lang_keys['text'] == 'lbl_about_version':
                    new_content = new_content.format(version=PROGRAM_VERSION)
                if isinstance(element, (sg.Button, sg.Checkbox)):
                    element.update(text=new_content)
                else:
                    element.update(value=new_content)

            if 'tooltip' in lang_keys and lang_keys['tooltip'] in LANG:
                element.SetTooltip(LANG[lang_keys['tooltip']])

    if is_paused:
        pause_btn_text = LANG.get('btn_resume', "Resume")
    else:
        pause_btn_text = LANG.get('btn_pause', "Pause")

    if '-BTN-PAUSE-' in window.AllKeysDict:
        window['-BTN-PAUSE-'].update(text=pause_btn_text)
    if '-BTN-BATCH-PAUSE-' in window.AllKeysDict:
        window['-BTN-BATCH-PAUSE-'].update(text=pause_btn_text)

    if '-BATCH-TABLE-' in window.AllKeysDict:
        try:
            table_widget = window['-BATCH-TABLE-'].Widget
            table_widget.heading('#1', text=LANG.get('col_video_file', 'Video File'))
            table_widget.heading('#2', text=LANG.get('col_output_file', 'Output File'))
            table_widget.heading('#3', text=LANG.get('col_status', 'Status'))
        except Exception as e:
            log_error(f"Failed to update table headings: {e}")

        refresh_batch_table(window)

    current_idx = window['-POST_ACTION-'].Widget.current()
    update_post_action_combo(window, current_idx)

    current_idx1 = window['--subtitle_alignment'].Widget.current()
    current_idx2 = window['--subtitle_alignment2'].Widget.current()
    update_alignment_combos(window, current_idx1, current_idx2)

    current_scale_idx = window['gui_scaling'].Widget.current()
    update_gui_scaling_combo(window, current_scale_idx)


# --- Helper Functions ---
def kill_process_tree(pid: int) -> None:
    """Kills the process with the given PID and its descendants."""
    if sys.platform == "win32":
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


def format_time(seconds: float | int) -> str:
    """Formats total seconds into HH:MM:SS or MM:SS string."""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    else:
        return f"{m:02d}:{s:02d}"


def format_seconds(seconds: float | int | None) -> str:
    """Converts seconds to '1h 05m' or '05m 30s' format."""
    if seconds is None or seconds < 0:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m:02d}m {s:02d}s"


def update_time_display(window: sg.Window, current_ms: float, total_ms: float) -> None:
    """Updates the time text elements."""
    time_text_format = LANG.get('time_text_format', 'Time: {} / {}')

    if total_ms > 0:
        current_sec = current_ms / 1000.0
        total_sec = total_ms / 1000.0
        time_text = f"{format_time(current_sec)} / {format_time(total_sec)}"
        window["-TIME_TEXT-"].update(time_text_format.format(time_text))
    else:
        time_text_empty = LANG.get('time_text_empty', 'Time: -/-')
        window["-TIME_TEXT-"].update(time_text_empty)


def _parse_and_validate_time_parts(time_str: str | None) -> tuple[int, int, int] | None:
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


def is_valid_time_format(time_str: str | None) -> bool:
    """Checks if a string is in MM:SS or HH:MM:SS format with valid ranges."""
    if not time_str:
        return True

    return _parse_and_validate_time_parts(time_str) is not None


def time_string_to_seconds(time_str: str | None) -> int | None:
    """Converts MM:SS or HH:MM:SS string to total seconds. Returns None if invalid."""
    if not time_str:
        return None

    parsed_time = _parse_and_validate_time_parts(time_str)

    if parsed_time is None:
        return None

    h, m, s = parsed_time
    return h * 3600 + m * 60 + s


def parse_srt_time_to_seconds(time_str: str) -> float:
    """Parses a timestamp string like '00:00:01,500' or '00:01:00' into seconds (float)."""
    try:
        parts = time_str.replace(',', '.').split(':')
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    except Exception:
        return 0.0
    return 0.0


def center_popup(parent_window: sg.Window, popup_window: sg.Window) -> None:
    """Center a popup relative to the parent window."""
    x0, y0 = parent_window.current_location()
    w0, h0 = parent_window.current_size_accurate()
    w1, h1 = popup_window.current_size_accurate()
    x1 = x0 + (w0 - w1) // 2
    y1 = y0 + (h0 - h1) // 2
    popup_window.move(x1, y1)


def custom_popup(parent_window: sg.Window, title: str, message: str, icon: str | bytes | None = None, modal: bool = True) -> None:
    """Create and show a centered popup relative to the parent window."""
    layout = [
        [sg.Text(message)],
        [sg.Push(), sg.Button(LANG.get('btn_ok', 'OK'), key='OK', bind_return_key=True), sg.Push()]
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


def update_popup(parent_window: sg.Window, version_info: dict[str, str], current_version: str, icon: str | bytes | None = None) -> None:
    """Creates and shows a centered popup to notify the user of a new version relative to the parent window."""
    url = version_info['url']
    new_version = version_info['version']

    popup_layout = [
        [sg.Text(LANG.get('update_available_1', 'A new version of VideOCR ({}) is available!').format(new_version))],
        [sg.Text(LANG.get('update_available_2', 'You are currently using version {}.').format(current_version))],
        [sg.Text(LANG.get('update_available_3', 'Click the link below to visit the download page:'))],
        [sg.Text(url, font=("Arial", scale_font_size(11), 'underline'), enable_events=True, key='-UPDATE_LINK-')],
        [sg.Push(), sg.Button(LANG.get('btn_dismiss', 'Dismiss'), key='Dismiss'), sg.Push()]
    ]
    update_window = sg.Window(LANG.get('update_title', "Update Available"), popup_layout, alpha_channel=0, finalize=True, modal=True, icon=icon)

    update_window.refresh()
    center_popup(parent_window, update_window)
    update_window.refresh()
    update_window.set_alpha(1)

    update_window['-UPDATE_LINK-'].Widget.config(cursor="hand2")

    while True:
        popup_event, _ = update_window.read()
        if popup_event in (sg.WIN_CLOSED, 'Dismiss'):
            break
        elif popup_event == '-UPDATE_LINK-':
            webbrowser.open(url)
            break
    update_window.close()


def custom_popup_yes_no(parent_window: sg.Window, title: str, message: str, icon: str | bytes | None = None) -> str:
    """Creates and shows a centered Yes/No popup relative to the parent window."""
    layout = [
        [sg.Text(message)],
        [sg.Push(),
         sg.Button(LANG.get('btn_yes', 'Yes'), key='Yes', size=(10, 1), bind_return_key=True),
         sg.Button(LANG.get('btn_no', 'No'), key='No', size=(10, 1)),
         sg.Push()]
    ]
    popup_window = sg.Window(title, layout, alpha_channel=0, finalize=True, icon=icon, modal=True)

    popup_window.refresh()
    center_popup(parent_window, popup_window)
    popup_window.refresh()
    popup_window.set_alpha(1)
    popup_window['No'].set_focus()

    choice = 'No'
    while True:
        popup_event, _ = popup_window.read()
        if popup_event in (sg.WIN_CLOSED, 'No'):
            choice = 'No'
            break
        elif popup_event == 'Yes':
            choice = 'Yes'
            break

    popup_window.close()
    return choice


def popup_post_action_countdown(parent_window: sg.Window, action_text: str, icon: str | bytes | None = None) -> bool:
    """Displays a countdown popup relative to the parent window."""
    timeout_seconds = 60

    layout = [
        [sg.Text(LANG.get('title_countdown', "Action Required"), font=("Arial", scale_font_size(12), "bold"), pad=(0, 10))],
        [sg.Text(LANG.get('lbl_action_countdown', "System will execute '{}' in {} seconds.").format(action_text, timeout_seconds),
                 key='-LBL-COUNTDOWN-', font=("Arial", scale_font_size(10)), pad=(10, 10))],
        [sg.Push(),
         sg.Button(LANG.get('btn_proceed', "Proceed Now"), key='-BTN-PROCEED-', size=(12, 1)),
         sg.Button(LANG.get('btn_cancel', "Cancel"), key='-BTN-CANCEL-', size=(10, 1)),
         sg.Push()]
    ]
    popup_window = sg.Window(LANG.get('title_countdown', "Action Required"), layout, keep_on_top=True, modal=True, finalize=True, icon=icon)

    popup_window.refresh()
    center_popup(parent_window, popup_window)
    popup_window.refresh()
    popup_window.set_alpha(1)

    counter = timeout_seconds
    should_proceed = False

    while True:
        event, _ = popup_window.read(timeout=1000)

        if event in (sg.WIN_CLOSED, '-BTN-CANCEL-'):
            should_proceed = False
            break

        if event == '-BTN-PROCEED-':
            should_proceed = True
            break

        if event == sg.TIMEOUT_EVENT:
            counter -= 1
            if counter <= 0:
                should_proceed = True
                break

            new_text = LANG.get('lbl_action_countdown', "System will execute '{}' in {} seconds.").format(action_text, counter)
            popup_window['-LBL-COUNTDOWN-'].update(new_text)

    popup_window.close()
    return should_proceed


def check_for_updates(window: sg.Window, manual_check: bool = False) -> None:
    """Checks GitHub for a new release."""
    try:
        headers = {'User-Agent': 'VideOCR-GUI'}
        req = urllib.request.Request("https://api.github.com/repos/timminator/VideOCR/releases/latest", headers=headers)

        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                latest_version_str = data['tag_name']

                current_version_tuple = tuple(map(int, (PROGRAM_VERSION.split('.'))))
                latest_version_tuple = tuple(map(int, (latest_version_str.lstrip('v').split('.'))))

                if latest_version_tuple > current_version_tuple:
                    release_url = data['html_url']
                    window.write_event_value('-NEW_VERSION_FOUND-', {'version': latest_version_str, 'url': release_url})
                elif manual_check:
                    window.write_event_value('-NO_UPDATE_FOUND-', None)
    except Exception as e:
        log_error(f"Failed to check for updates: {e}")
        if manual_check:
            window.write_event_value('-UPDATE_CHECK_FAILED-', None)


def update_subtitle_pos_combo(window: sg.Window, selected_internal_pos: str | None = None) -> None:
    """Updates the Subtitle Position combo box with translated values and sets the selected item."""
    pos_to_select = selected_internal_pos if selected_internal_pos is not None else DEFAULT_INTERNAL_SUBTITLE_POSITION

    internal_to_display_name_map = {internal_val: LANG.get(lang_key, lang_key) for lang_key, internal_val in SUBTITLE_POSITIONS_LIST}
    display_pos = internal_to_display_name_map.get(pos_to_select, internal_to_display_name_map[DEFAULT_INTERNAL_SUBTITLE_POSITION])
    translated_pos_names = [internal_to_display_name_map[internal_val] for lang_key, internal_val in SUBTITLE_POSITIONS_LIST]

    window['-SUBTITLE_POS_COMBO-'].update(value=display_pos, values=translated_pos_names, size=(38, 4))


def get_alignment_index(key: str) -> int:
    """Returns the index for a given alignment key"""
    return next((i for i, (_, v) in enumerate(SUBTITLE_ALIGNMENT_LIST) if v == key), 0)


def update_alignment_combos(window: sg.Window, selected_index1: int | None = None, selected_index2: int | None = None) -> None:
    internal_to_display_map = {internal_val: LANG.get(lang_key, internal_val) for lang_key, internal_val in SUBTITLE_ALIGNMENT_LIST}
    translated_names = list(internal_to_display_map.values())

    idx1 = selected_index1 if selected_index1 is not None else 0
    display_val1 = translated_names[idx1] if 0 <= idx1 < len(translated_names) else translated_names[0]
    window['--subtitle_alignment'].update(value=display_val1, values=translated_names)

    idx2 = selected_index2 if selected_index2 is not None else 0
    display_val2 = translated_names[idx2] if 0 <= idx2 < len(translated_names) else translated_names[0]
    window['--subtitle_alignment2'].update(value=display_val2, values=translated_names)


def update_alignment_controls(window: sg.Window, values: dict[str, Any]) -> None:
    """Updates the subtitle alignment combo boxes based on current settings."""
    is_checked = values.get('enable_subtitle_alignment', False)
    is_dual_zone = values.get('--use_dual_zone', False)
    window['--subtitle_alignment'].update(disabled=not is_checked)
    window['--subtitle_alignment2'].update(disabled=not (is_checked and is_dual_zone))


def update_post_action_combo(window: sg.Window, selected_index: int = 0) -> None:
    """Refreshes the Post Action combo text and selects by numeric index."""
    display_values = [LANG.get(key, DEFAULT_ACTION_TEXTS[key]) for key in POST_ACTION_KEYS]
    window['-POST_ACTION-'].update(values=display_values)

    if 0 <= selected_index < len(display_values):
        window['-POST_ACTION-'].update(value=display_values[selected_index])
    else:
        window['-POST_ACTION-'].update(value=display_values[0])


def get_gui_scaling_index(key: str) -> int:
    """Returns the index for a given GUI scaling key"""
    return next((i for i, (_, v) in enumerate(GUI_SCALING_LIST) if v == key), 0)


def update_gui_scaling_combo(window: sg.Window, selected_index: int | None = None) -> None:
    """Updates the GUI Scaling combo box with translated values."""
    internal_to_display_map = {internal_val: LANG.get(lang_key, internal_val) for lang_key, internal_val in GUI_SCALING_LIST}
    translated_names = list(internal_to_display_map.values())

    idx = selected_index if selected_index is not None else 0
    display_val = translated_names[idx] if 0 <= idx < len(translated_names) else translated_names[0]

    if 'gui_scaling' in window.AllKeysDict:
        window['gui_scaling'].update(value=display_val, values=translated_names)


def get_translated_status(internal_status: str) -> str:
    """Translates internal status codes to display language."""
    lang_key = INTERNAL_STATUS_TO_LANG_KEY.get(internal_status)
    if lang_key:
        return LANG.get(lang_key, DEFAULT_STATUS_TEXTS.get(lang_key, internal_status))
    return internal_status


# --- Settings Save/Load Functions ---
def get_default_settings() -> dict[str, Any]:
    """Returns a dictionary of default settings."""
    return {
    '--language': 'en',
    '-OCR_ENGINE_COMBO-': DEFAULT_OCR_ENGINE,
    '-LANG_COMBO-': DEFAULT_SUBTITLE_LANGUAGE,
    '-SUBTITLE_POS_COMBO-': DEFAULT_INTERNAL_SUBTITLE_POSITION,
    '-POST_ACTION-': 0,
    '--time_start': DEFAULT_TIME_START,
    '--time_end': '',
    '--conf_threshold': str(DEFAULT_CONF_THRESHOLD),
    '--sim_threshold': str(DEFAULT_SIM_THRESHOLD),
    '--max_merge_gap': str(DEFAULT_MAX_MERGE_GAP),
    '--brightness_threshold': '',
    '--ssim_threshold': str(DEFAULT_SSIM_THRESHOLD),
    '--ocr_image_max_width': str(DEFAULT_OCR_IMAGE_MAX_WIDTH),
    '--frames_to_skip': str(DEFAULT_FRAMES_TO_SKIP),
    '--use_fullframe': False,
    '--use_gpu': True,
    '--use_angle_cls': False,
    '--post_processing': False,
    '--min_subtitle_duration': str(DEFAULT_MIN_SUBTITLE_DURATION),
    '--use_server_model': False,
    '--use_dual_zone': False,
    'enable_subtitle_alignment': False,
    '--subtitle_alignment': DEFAULT_SUBTITLE_ALIGNMENT,
    '--subtitle_alignment2': DEFAULT_SUBTITLE_ALIGNMENT,
    '--keyboard_seek_step': str(KEY_SEEK_STEP),
    '--default_output_dir': DEFAULT_DOCUMENTS_DIR,
    '--save_in_video_dir': True,
    '--send_notification': True,
    '--save_crop_box': True,
    '--saved_crop_boxes': '[]',
    '--check_for_updates': True,
    'prevent_system_sleep': True,
    '--normalize_to_simplified_chinese': True,
    'gui_scaling': 'System Default',
    }


def save_settings(window: sg.Window, values: dict[str, Any]) -> None:
    """Saves current settings from GUI elements to the config file."""
    config = configparser.ConfigParser()
    config.add_section(CONFIG_SECTION)

    settings_to_save = {key: values.get(key, get_default_settings().get(key)) for key in get_default_settings() if key != '--saved_crop_boxes'}

    display_name_to_internal_map = {LANG.get(lang_key, lang_key): internal_val for lang_key, internal_val in SUBTITLE_POSITIONS_LIST}
    selected_display_name = values.get('-SUBTITLE_POS_COMBO-', "")
    internal_pos_value = display_name_to_internal_map.get(selected_display_name, DEFAULT_INTERNAL_SUBTITLE_POSITION)
    settings_to_save['-SUBTITLE_POS_COMBO-'] = internal_pos_value

    current_idx = window['-POST_ACTION-'].Widget.current()
    settings_to_save['-POST_ACTION-'] = current_idx

    selected_lang_display_name = values.get('-UI_LANG_COMBO-')
    if selected_lang_display_name in available_languages:
        settings_to_save['--language'] = available_languages[selected_lang_display_name]

    align_display_to_internal_map = {LANG.get(lang_key, internal_val): internal_val for lang_key, internal_val in SUBTITLE_ALIGNMENT_LIST}
    for key in ['--subtitle_alignment', '--subtitle_alignment2']:
        selected_display = values.get(key, "")
        internal_val = align_display_to_internal_map.get(selected_display, DEFAULT_SUBTITLE_ALIGNMENT)
        settings_to_save[key] = internal_val

    scale_display_to_internal_map = {LANG.get(lang_key, internal_val): internal_val for lang_key, internal_val in GUI_SCALING_LIST}
    selected_scale_display = values.get('gui_scaling', "")
    settings_to_save['gui_scaling'] = scale_display_to_internal_map.get(selected_scale_display, DEFAULT_GUI_SCALING)

    crop_boxes_to_save: list[dict[str, Any]] = []
    if original_frame_width == 0 and original_frame_height == 0:
        crop_boxes_to_save = getattr(window, 'saved_crop_boxes_from_config', [])
    else:
        if values.get('--save_crop_box'):
            for box in getattr(window, 'crop_boxes', []):
                abs_coords = box['coords']
                relative_coords = {
                    'crop_x': abs_coords['crop_x'] / original_frame_width,
                    'crop_y': abs_coords['crop_y'] / original_frame_height,
                    'crop_width': abs_coords['crop_width'] / original_frame_width,
                    'crop_height': abs_coords['crop_height'] / original_frame_height,
                }
                crop_boxes_to_save.append({'coords': relative_coords})

    settings_to_save['--saved_crop_boxes'] = repr(crop_boxes_to_save)
    window.saved_crop_boxes_from_config = crop_boxes_to_save

    # --- Write settings to the config object ---
    for key, value in settings_to_save.items():
        config.set(CONFIG_SECTION, key, str(value))
    try:
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
    except Exception as e:
        log_error(f"Error saving settings to {CONFIG_FILE}: {e}")


def load_settings(window: sg.Window) -> None:
    """
    Loads settings from the config file and updates GUI elements.
    Creates a default config if the file doesn't exist.
    """
    config = configparser.ConfigParser()

    if os.path.exists(CONFIG_FILE):
        try:
            config.read(CONFIG_FILE)
            if config.has_section(CONFIG_SECTION):
                saved_lang_code = config.get(CONFIG_SECTION, '--language', fallback='en')
                load_language(saved_lang_code)

                saved_internal_pos = config.get(CONFIG_SECTION, '-SUBTITLE_POS_COMBO-', fallback=DEFAULT_INTERNAL_SUBTITLE_POSITION)
                update_subtitle_pos_combo(window, saved_internal_pos)

                saved_idx = config.getint(CONFIG_SECTION, '-POST_ACTION-', fallback=0)
                update_post_action_combo(window, saved_idx)

                code_to_native_name_map = {v: k for k, v in available_languages.items()}
                display_lang = code_to_native_name_map.get(saved_lang_code, 'English')
                window['-UI_LANG_COMBO-'].update(value=display_lang)

                saved_align1 = config.get(CONFIG_SECTION, '--subtitle_alignment', fallback=DEFAULT_SUBTITLE_ALIGNMENT)
                saved_align2 = config.get(CONFIG_SECTION, '--subtitle_alignment2', fallback=DEFAULT_SUBTITLE_ALIGNMENT)
                update_alignment_combos(window, get_alignment_index(saved_align1), get_alignment_index(saved_align2))

                saved_scaling = config.get(CONFIG_SECTION, 'gui_scaling', fallback=DEFAULT_GUI_SCALING)
                update_gui_scaling_combo(window, get_gui_scaling_index(saved_scaling))

                saved_engine = config.get(CONFIG_SECTION, '-OCR_ENGINE_COMBO-', fallback=DEFAULT_OCR_ENGINE)
                window['-OCR_ENGINE_COMBO-'].update(value=saved_engine)

                active_lang_list = lens_display_names if "Google Lens" in saved_engine else paddle_display_names
                window['-LANG_COMBO-'].update(values=active_lang_list)

                settings_to_load = [
                    ('-LANG_COMBO-', 'combo_lang'),
                    ('--time_start', 'input'),
                    ('--time_end', 'input'),
                    ('--conf_threshold', 'input'),
                    ('--sim_threshold', 'input'),
                    ('--max_merge_gap', 'input'),
                    ('--brightness_threshold', 'input'),
                    ('--ssim_threshold', 'input'),
                    ('--ocr_image_max_width', 'input'),
                    ('--frames_to_skip', 'input'),
                    ('--use_fullframe', 'checkbox'),
                    ('--use_gpu', 'checkbox'),
                    ('--use_angle_cls', 'checkbox'),
                    ('--post_processing', 'checkbox'),
                    ('--min_subtitle_duration', 'input'),
                    ('--use_server_model', 'checkbox'),
                    ('--use_dual_zone', 'checkbox'),
                    ('enable_subtitle_alignment', 'checkbox'),
                    ('--keyboard_seek_step', 'input'),
                    ('--default_output_dir', 'input'),
                    ('--save_in_video_dir', 'checkbox'),
                    ('--send_notification', 'checkbox'),
                    ('--save_crop_box', 'checkbox'),
                    ('--check_for_updates', 'checkbox'),
                    ('prevent_system_sleep', 'checkbox'),
                    ('--normalize_to_simplified_chinese', 'checkbox'),
                ]

                for key, elem_type in settings_to_load:
                    if config.has_option(CONFIG_SECTION, key):
                        try:
                            value: Any = None
                            if elem_type == 'checkbox':
                                value = config.getboolean(CONFIG_SECTION, key)
                            elif elem_type == 'combo_lang':
                                value_str = config.get(CONFIG_SECTION, key)
                                if value_str in active_lang_list:
                                    value = value_str
                                else:
                                    value = DEFAULT_SUBTITLE_LANGUAGE
                            else:
                                value = config.get(CONFIG_SECTION, key)

                            if key in window.AllKeysDict:
                                window[key].update(value)

                        except Exception as e:
                            log_error(f"Error loading setting '{key}' from {CONFIG_FILE}: {e}. Using default.")

                saved_boxes_str = config.get(CONFIG_SECTION, '--saved_crop_boxes', fallback='[]')
                try:
                    window.saved_crop_boxes_from_config = ast.literal_eval(saved_boxes_str)
                except (ValueError, SyntaxError):
                    window.saved_crop_boxes_from_config = []
                    log_error(f"Could not parse saved_crop_boxes: {saved_boxes_str}")

            current_gui_values = window.read(timeout=0)[1]
            update_alignment_controls(window, current_gui_values)
            save_settings(window, current_gui_values)

        except configparser.Error as e:
            log_error(f"Error parsing config file {CONFIG_FILE}: {e}. Creating default config.")
        except Exception as e:
            log_error(f"An unexpected error occurred while loading settings: {e}. Creating default config.")

    else:
        # --- Config file doesn't exist, create it with default settings ---
        load_language('en')
        window['-UI_LANG_COMBO-'].update(value='English')

        update_subtitle_pos_combo(window)
        update_post_action_combo(window)
        update_alignment_combos(window)
        update_gui_scaling_combo(window)

        default_settings = get_default_settings()
        config.add_section(CONFIG_SECTION)
        for key, value in default_settings.items():
            config.set(CONFIG_SECTION, key, str(value))
        try:
            with open(CONFIG_FILE, 'w') as configfile:
                config.write(configfile)
        except Exception as e:
            log_error(f"Error creating default config file {CONFIG_FILE}: {e}")


def generate_output_path(video_path: str, values: dict[str, Any], default_dir: str = DEFAULT_DOCUMENTS_DIR) -> pathlib.Path:
    """Generates a unique output file path for the SRT file based on video path, settings and language."""
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

    selected_lang_name = values.get('-LANG_COMBO-', DEFAULT_SUBTITLE_LANGUAGE)
    selected_engine_display = values.get('-OCR_ENGINE_COMBO-', "")

    if "Google Lens" in selected_engine_display:
        iso_code = lens_abbr_lookup.get(selected_lang_name, 'en')
    else:
        paddle_code = paddle_abbr_lookup.get(selected_lang_name, 'en')
        iso_code = PADDLE_TO_ISO_MAP.get(paddle_code, paddle_code)

    base_output_path = output_dir / f"{video_filename_stem}.{iso_code}.srt"
    output_path = base_output_path
    counter = 1
    while output_path.exists():
        output_path = output_dir / f"{video_filename_stem}({counter}).{iso_code}.srt"
        counter += 1

    return output_path


class VideoHandler:
    def __init__(self) -> None:
        self.container: av.container.InputContainer | None = None
        self.stream: av.video.stream.VideoStream | None = None
        self.path: str | None = None
        self.width: int = 0
        self.height: int = 0
        self.duration_ms: int = 0

        self.last_pts: int | None = None

        self.graph: av.filter.Graph | None = None
        self.buffer_node: Any = None
        self.sink_node: Any = None
        self.last_display_size: tuple[int, int] = (0, 0)
        self.current_new_w: int = 0
        self.current_new_h: int = 0

        self._supports_threads = True

    def _frame_to_array(self, frame: av.VideoFrame, fmt: str) -> np.ndarray[Any, Any]:
        """Converts a frame to an array, safely falls back if threads arg is unsupported."""
        if self._supports_threads:
            try:
                return frame.to_ndarray(format=fmt, threads=1)
            except TypeError:
                self._supports_threads = False

        return frame.to_ndarray(format=fmt)

    def _get_cached_properties(self) -> dict[str, int]:
        """Returns internal properties without re-parsing the file."""
        return {'width': self.width, 'height': self.height, 'duration_ms': self.duration_ms}

    def _setup_filter_graph(self, template_frame: av.VideoFrame, display_size: tuple[int, int]) -> None:
        """Initializes the FFmpeg filter graph for fast resizing and format conversion."""
        scale = min(display_size[0] / self.width, display_size[1] / self.height)
        self.current_new_w, self.current_new_h = int(self.width * scale) & ~1, int(self.height * scale) & ~1

        self.graph = av.filter.Graph()
        self.buffer_node = self.graph.add_buffer(template=cast(Any, template_frame))
        scale_node = self.graph.add("scale", f"{self.current_new_w}:{self.current_new_h}:flags=bicubic")
        self.sink_node = self.graph.add("buffersink")

        self.buffer_node.link_to(scale_node)
        scale_node.link_to(self.sink_node)
        self.graph.configure()
        self.last_display_size = display_size

    def open(self, path: str) -> dict[str, int]:
        if self.path == path and self.container:
            return self._get_cached_properties()

        self.close()
        try:
            self.container = av.open(path)
            self.stream = self.container.streams.video[0]
            self.stream.thread_type = 'FRAME'
            self.path = path
            self.width = int(self.stream.width)
            self.height = int(self.stream.height)

            if self.container.duration is not None:
                self.duration_ms = int(self.container.duration / 1000.0)
            elif self.stream.duration is not None and self.stream.time_base is not None:
                self.duration_ms = int(self.stream.duration * float(self.stream.time_base) * 1000.0)

            return self._get_cached_properties()

        except (av.error.FFmpegError, Exception) as e:
            log_error(f"VideoHandler Open Error: {e}")
            self.close()
            return {'width': 0, 'height': 0, 'duration_ms': 0}

    def get_frame(self, timestamp_ms: float, display_size: tuple[int, int], brightness_threshold: int | None = None) -> tuple[io.BytesIO | None, int, int, int, int]:
        """Seeks or decodes forward to provide a frame at the requested timestamp."""
        if not self.container or not self.stream:
            return None, 0, 0, 0, 0

        try:
            if self.stream.time_base is None:
                raise ValueError("Stream time_base is None")

            tb = float(self.stream.time_base)
            container_start_ms = (self.container.start_time / 1000.0) if self.container.start_time is not None else 0.0
            target_ms = timestamp_ms + container_start_ms
            target_pts = int(target_ms / 1000.0 / tb)
            seek_threshold = int(1.5 / tb)

            should_seek = True
            if self.last_pts is not None:
                if self.last_pts <= target_pts <= (self.last_pts + seek_threshold):
                    should_seek = False

            if should_seek:
                self.container.seek(target_pts, stream=self.stream)
                self.last_pts = None

            frame: av.VideoFrame | None = None
            for f in self.container.decode(self.stream):
                if f.pts is not None and f.pts >= target_pts:
                    frame = f
                    self.last_pts = f.pts
                    break

            if not frame:
                return None, 0, 0, 0, 0

            if self.graph is None or self.last_display_size != display_size:
                self._setup_filter_graph(frame, display_size)

            off_x = (display_size[0] - self.current_new_w) // 2
            off_y = (display_size[1] - self.current_new_h) // 2

            self.buffer_node.push(frame)
            processed_frame: av.VideoFrame = self.sink_node.pull()

            img_np = self._frame_to_array(processed_frame, fmt='rgb24')

            if brightness_threshold is not None:
                gray = (
                    (img_np[..., 0].astype(np.uint16) * 77 +
                    img_np[..., 1].astype(np.uint16) * 150 +
                    img_np[..., 2].astype(np.uint16) * 29) >> 8
                ).astype(np.uint8)
                mask = gray > brightness_threshold
                img_np *= mask[..., None]

            pil_img = Image.fromarray(img_np)
            img_byte_arr = io.BytesIO()
            pil_img.save(img_byte_arr, format='PNG')

            return io.BytesIO(img_byte_arr.getvalue()), self.current_new_w, self.current_new_h, off_x, off_y

        except Exception as e:
            log_error(f"VideoHandler Seek Error: {e}")
            return None, 0, 0, 0, 0

    def close(self) -> None:
        """Closes the video container and resets all persistent objects and cached metadata."""
        if self.container:
            self.container.close()
        self.container = self.stream = self.path = self.graph = self.buffer_node = self.sink_node = None
        self.width = self.height = 0
        self.duration_ms = 0
        self.last_display_size = (0, 0)
        self.current_new_w = self.current_new_h = 0


def handle_progress(match: re.Match[str], label_format_key: str, last_percentage: float, log_threshold: int, step_num: int, show_taskbar_progress: bool = True) -> float:
    """Handles progress parsing, ETA calculation, and GUI updates."""
    if not hasattr(handle_progress, "last_key"):
        handle_progress.last_key = None  # type: ignore
    if not hasattr(handle_progress, "start_time"):
        handle_progress.start_time = None  # type: ignore
    if not hasattr(handle_progress, "last_update_time"):
        handle_progress.last_update_time = 0  # type: ignore
    if not hasattr(handle_progress, "start_percent"):
        handle_progress.start_percent = 0.0  # type: ignore
    if not hasattr(handle_progress, "last_eta"):
        handle_progress.last_eta = ""  # type: ignore
    if not hasattr(handle_progress, "last_taskbar_val"):
        handle_progress.last_taskbar_val = -1  # type: ignore

    current_time = time.time()
    is_time_based = label_format_key == "progress_step1"

    if is_time_based:
        curr_ts_str = match.group(2)
        target_ts_str = match.group(3)
        frame_num = match.group(4)

        curr_sec = parse_srt_time_to_seconds(curr_ts_str)
        target_sec = parse_srt_time_to_seconds(target_ts_str)

        current_percent = 0.0
        if target_sec > 0:
            current_percent = (curr_sec / target_sec) * 100.0
            current_percent = min(max(current_percent, 0.0), 100.0)

        current_item_display = curr_ts_str
        display_total = target_ts_str
    else:
        current_item = int(match.group(2))
        total_str = match.group(3)

        if total_str == 'Unknown':
            total_items = 0
            display_total = LANG.get('unknown', 'unknown')
            current_percent = 0.0
        else:
            total_items = int(total_str)
            display_total = str(total_items)
            current_percent = (current_item / total_items) * 100.0 if total_items > 0 else 0.0

        current_item_display = str(current_item)

    if handle_progress.last_key != label_format_key:  # type: ignore
        handle_progress.last_key = label_format_key  # type: ignore
        handle_progress.start_time = current_time  # type: ignore
        handle_progress.last_update_time = 0  # type: ignore
        handle_progress.start_percent = current_percent  # type: ignore

    time_delta = current_time - handle_progress.last_update_time  # type: ignore
    percent_threshold = last_percentage + 0.1

    should_update = False
    if current_percent >= 100 or current_percent >= percent_threshold or time_delta >= 0.2:
        should_update = True

    if not should_update:
        return last_percentage

    handle_progress.last_update_time = current_time  # type: ignore

    global_percent = ((step_num - 1) * (100.0 / 3.0)) + (current_percent / 3.0)

    step_word = LANG.get('lbl_step', 'Step')
    prefix = f"{step_word} {step_num}/3:"

    if label_format_key == "progress_step1":
        action_text = LANG.get('progress_step1_action', 'Processing video...')
        frame_lbl = LANG.get('lbl_frame', 'Frame')
        msg_template = f"{prefix} {action_text} {curr_ts_str} / {target_ts_str}, {frame_lbl}: {frame_num} ({{percent}}%)"
    elif label_format_key == "progress_step2":
        default_raw = "Performing Text-Detection on image {current} of {total} ({percent}%)"
        raw_msg = LANG.get('progress_step2_action', default_raw)
        action_text = raw_msg.replace('{current}', current_item_display).replace('{total}', display_total)
        msg_template = f"{prefix} {action_text}"
    elif label_format_key == "progress_step3":
        default_raw = "Performing OCR on image {current} of {total} ({percent}%)"
        raw_msg = LANG.get('progress_step3_action', default_raw)
        action_text = raw_msg.replace('{current}', current_item_display).replace('{total}', display_total)
        msg_template = f"{prefix} {action_text}"

    eta_prefix = f"{LANG.get('eta_step', 'ETA Step')} {step_num}/3"

    if log_threshold > 0:
        prev_step = -1 if last_percentage < 0 else int(last_percentage) // log_threshold
        curr_step = int(current_percent) // log_threshold

        if last_percentage < 0 or curr_step > prev_step or (current_percent >= 100 and last_percentage < 100):
            log_msg = msg_template.format(percent=int(current_percent))
            gui_queue.put(('-VIDEOCR_OUTPUT-', log_msg + "\n"))

    eta_str = handle_progress.last_eta  # type: ignore
    elapsed = current_time - handle_progress.start_time  # type: ignore
    percent_done_this_phase = current_percent - handle_progress.start_percent  # type: ignore

    if percent_done_this_phase > 0 and elapsed > 0:
        rate = percent_done_this_phase / elapsed
        remaining_percent = 100.0 - current_percent
        remaining_seconds = remaining_percent / rate
        eta_str = f"{eta_prefix}: {format_seconds(remaining_seconds)}"
        handle_progress.last_eta = eta_str  # type: ignore

    display_text = msg_template.format(percent=f"{current_percent:.1f}")

    gui_queue.put(('-PROGRESS-SMOOTH-', {
        'text': display_text,
        'percent': current_percent,
        'eta': eta_str
    }))

    if show_taskbar_progress:
        progress_value = max(1, int(global_percent))

        if last_percentage < 0 or handle_progress.last_taskbar_val != progress_value:  # type: ignore
            gui_queue.put(('-TASKBAR_STATE_UPDATE-', {'state': 'normal', 'progress': progress_value}))
            handle_progress.last_taskbar_val = progress_value  # type: ignore

    return current_percent


def read_pipe(pipe: IO[str], output_list: list[str]) -> None:
    """Reads lines from a pipe and appends them to a list."""
    try:
        for line in iter(pipe.readline, ''):
            output_list.append(line)
    finally:
        pipe.close()


def scan_video_folder(folder_path: str) -> list[str]:
    """Scans a folder for common video files and returns a sorted list of full paths."""
    video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv', '.wmv', '.ts', '.m2ts'}
    video_files: list[str] = []
    if not os.path.isdir(folder_path):
        return []
    for entry in os.listdir(folder_path):
        full_path = os.path.join(folder_path, entry)
        if os.path.isfile(full_path):
            if os.path.splitext(entry)[1].lower() in video_extensions:
                video_files.append(full_path)
    return sorted(video_files)


# --- Argument Extraction and Validation ---
def get_processing_args(values: dict[str, Any], window: sg.Window) -> tuple[dict[str, Any] | None, list[str] | None]:
    """
    Validates inputs and generates the argument dictionary for the CLI.
    Returns (args_dict, None) if successful, or (None, errors_list) if validation fails.
    """
    errors: list[str] = []

    time_start = values.get('--time_start', '').strip()
    time_end = values.get('--time_end', '').strip()

    if not is_valid_time_format(time_start):
        errors.append(LANG.get('val_err_start_time', "Invalid Start Time format."))
    if not is_valid_time_format(time_end):
        errors.append(LANG.get('val_err_end_time', "Invalid End Time format."))

    time_start_seconds = time_string_to_seconds(time_start)
    time_end_seconds = time_string_to_seconds(time_end)

    video_duration_seconds = 0.0
    if video_duration_ms > 0:
        video_duration_seconds = video_duration_ms / 1000.0

    if time_start_seconds is not None:
        if time_start_seconds > video_duration_seconds:
            errors.append(LANG.get('val_err_start_exceeds', "Start Time ({}) exceeds video duration ({}).").format(format_time(time_start_seconds), format_time(video_duration_seconds)))

    if time_end and time_end_seconds is not None:
        if time_end_seconds > video_duration_seconds:
            errors.append(LANG.get('val_err_end_exceeds', "End Time ({}) exceeds video duration ({}).").format(format_time(time_end_seconds), format_time(video_duration_seconds)))

    if time_start_seconds is not None and time_end_seconds is not None:
        if time_start_seconds > time_end_seconds:
            errors.append(LANG.get('val_err_start_after_end', "Start Time cannot be after End Time."))

    use_dual_zone = values.get('--use_dual_zone', False)
    if use_dual_zone and len(window.crop_boxes) != 2:
        errors.append(LANG.get('val_err_dual_zone', "Dual Zone OCR is enabled, but 2 crop boxes have not been selected."))

    numeric_params = {
        '--conf_threshold': (int, 0, 100, "Confidence Threshold"),
        '--sim_threshold': (int, 0, 100, "Similarity Threshold"),
        '--brightness_threshold': (int, 0, 255, "Brightness Threshold"),
        '--ssim_threshold': (int, 0, 100, "SSIM Threshold"),
        '--ocr_image_max_width': (int, 0, None, "Max OCR Image Width"),
        '--frames_to_skip': (int, 0, None, "Frames to Skip"),
        '--max_merge_gap': (float, 0.0, None, "Max Merge Gap"),
        '--min_subtitle_duration': (float, 0.0, None, "Minimum Subtitle Duration"),
    }

    for key, (cast_type, min_val, max_val, name) in numeric_params.items():
        value_str = values.get(key, '').strip()

        if not value_str:
            continue

        range_str_parts: list[str] = []
        if min_val is not None:
            range_str_parts.append(f">={min_val}")
        if max_val is not None:
            range_str_parts.append(f"<={max_val}")
        range_str = " and ".join(range_str_parts)

        type_name = cast_type.__name__
        article = "an" if type_name.startswith(("i", "I")) else "a"

        error_format = LANG.get('val_err_numeric', "Invalid value for {}. Must be {} {} {}.")

        try:
            value = cast_type(value_str)
            if (min_val is not None and value < min_val) or (max_val is not None and value > max_val):
                raise ValueError
        except ValueError:
            errors.append(error_format.format(name, article, type_name, range_str))

    if errors:
        return None, errors

    args: dict[str, Any] = {}
    args['video_path'] = video_path

    selected_engine_display = values.get('-OCR_ENGINE_COMBO-', "")
    if "Google Lens" in selected_engine_display:
        args['ocr_engine'] = 'google_lens'
        lang_abbr = lens_abbr_lookup.get(values.get('-LANG_COMBO-', DEFAULT_SUBTITLE_LANGUAGE))
    else:
        args['ocr_engine'] = 'paddleocr'
        lang_abbr = paddle_abbr_lookup.get(values.get('-LANG_COMBO-', DEFAULT_SUBTITLE_LANGUAGE))

    if lang_abbr:
        args['lang'] = lang_abbr

    selected_display_name = values.get('-SUBTITLE_POS_COMBO-', "")
    display_name_to_internal_map = {LANG.get(lang_key, lang_key): internal_val for lang_key, internal_val in SUBTITLE_POSITIONS_LIST}
    pos_value = display_name_to_internal_map.get(selected_display_name)
    if pos_value:
        args['subtitle_position'] = pos_value

    for key in values:
        if key.startswith('--') and key not in ['--keyboard_seek_step', '--default_output_dir', '--save_in_video_dir', '--send_notification', '--save_crop_box', '--check_for_updates', '--language', '--use_dual_zone', '--subtitle_alignment', '--subtitle_alignment2']:
            stripped_key = key.lstrip('-')
            value = values.get(key)
            if isinstance(value, bool):
                args[stripped_key] = value
            elif value is not None and str(value).strip() != '':
                args[stripped_key] = str(value).strip()

    # Conditionally add subtitle alignment args if the feature is enabled
    if values.get('enable_subtitle_alignment'):
        align_display_to_internal_map = {LANG.get(lang_key, internal_val): internal_val for lang_key, internal_val in SUBTITLE_ALIGNMENT_LIST}

        align1_display = values.get('--subtitle_alignment', "")
        args['subtitle_alignment'] = align_display_to_internal_map.get(align1_display, DEFAULT_SUBTITLE_ALIGNMENT)

        if use_dual_zone:
            align2_display = values.get('--subtitle_alignment2', "")
            args['subtitle_alignment2'] = align_display_to_internal_map.get(align2_display, DEFAULT_SUBTITLE_ALIGNMENT)

    # Handle send_notification specifically to store it as a boolean and not a string
    args['send_notification'] = values.get('--send_notification', True)

    # Handle sleep by GUI and not by CLI
    args['allow_system_sleep'] = True

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

    # Explicit Output Path (needed for batch snapshots)
    out_path = values.get('--output')
    if not out_path and video_path:
        out_path = generate_output_path(video_path, values)
    args['output'] = str(out_path)

    return args, None


def get_valid_brightness_threshold(value: Any) -> int | None:
    """Validates that the brightness threshold is an integer between 0 and 255."""
    if value is None or str(value).strip() == '':
        return None
    try:
        val = int(str(value).strip())
        if 0 <= val <= 255:
            return val
    except (ValueError, TypeError):
        pass
    return None


def run_videocr(args_dict: dict[str, Any], window: sg.Window) -> bool:
    """Runs the videocr-cli tool in a separate process and streams output."""
    if not VIDEOCR_PATH:
        error_msg = LANG.get('error_cli_not_found', "\nError: videocr-cli not found. Please check the path.\n")
        gui_queue.put(('-VIDEOCR_OUTPUT-', error_msg))
        return False

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

    UNSUPPORTED_HARDWARE_ERROR_PATTERN = re.compile(r"Unsupported Hardware Error: (.*)")
    WARNING_HARDWARE_PATTERN = re.compile(r"Hardware Check Warning: (.*)")
    PROCESS_ERROR_PATTERN = re.compile(r"Error: Process failed.")
    STEP1_PROGRESS_PATTERN = re.compile(r"Step (\d+)/\d+: Processing video\.\.\. Current: ([\d:]+) / ([\d:]+|Unknown), Frame: (\d+)")
    STEP_IMAGE_PROGRESS_PATTERN = re.compile(r"Step (\d+)/\d+: Performing (?:Text-Detection|OCR) on image (\d+) of (\d+)")
    REPACKING_PATTERN = re.compile(r"Analyzing and repacking frame (\d+) of (\d+)")
    STARTING_PADDLEOCR_PATTERN = re.compile(r"Starting PaddleOCR\.\.\.")
    STARTING_LENS_PATTERN = re.compile(r"Starting Google Lens CLI\.\.\.")
    INFO_PASS_PATTERN = re.compile(r"Running Text-Detection-Only pass on (\d+) filtered frame\(s\) stitched into (\d+) image grid\(s\)\.\.\.")
    FILTERED_PATTERN = re.compile(r"Filtered out (\d+) redundant frame\(s\) via Text-Detection and tight-box SSIM analysis\.")
    STITCHED_PATTERN = re.compile(r"Stitched (\d+) remaining frame\(s\) down to (\d+) image grid\(s\)\.")
    GENERATING_SUBTITLES_PATTERN = re.compile(r"Generating subtitles\.\.\.")
    REACHED_END_TIME_PATTERN = re.compile(r"Reached end time\. Stopping\.")

    last_reported_percentage_step1 = -1.0
    last_reported_percentage_step2 = -1.0
    last_reported_percentage_step3 = -1.0
    last_repacking_pct = -1.0

    expecting_log_path = False
    process_error_message = ""

    gui_queue.put(('-VIDEOCR_OUTPUT-', LANG.get('status_starting', "Starting subtitle extraction...\n")))
    gui_queue.put(('-PROGRESS-SMOOTH-', {'text': LANG.get('status_starting', "Starting subtitle extraction..."), 'percent': None}))

    process = None
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    try:
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        process = subprocess.Popen(command,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   text=True,
                                   encoding='utf-8',
                                   errors='replace',
                                   bufsize=1,
                                   creationflags=creationflags,
                                   start_new_session=(sys.platform != "win32")
                                   )

        gui_queue.put(('-PROCESS_STARTED-', process.pid))

        stderr_thread = threading.Thread(target=read_pipe, args=(process.stderr, stderr_lines))
        stderr_thread.start()

        if process.stdout:
            for line in iter(process.stdout.readline, ''):
                stdout_lines.append(line)

                if process.poll() is not None and line == '':
                    break
                line = line.rstrip('\r\n')

                if expecting_log_path:
                    log_path = line.strip()
                    full_error_output = f"\n{process_error_message}\n{log_path}\n"
                    gui_queue.put(('-VIDEOCR_OUTPUT-', full_error_output))
                    expecting_log_path = False
                    process_error_message = ""
                    continue

                if PROCESS_ERROR_PATTERN.search(line):
                    process_error_message = line.strip()
                    expecting_log_path = True
                    continue

                fatal_error_match = UNSUPPORTED_HARDWARE_ERROR_PATTERN.search(line)
                if fatal_error_match:
                    error_message = fatal_error_match.group(1)
                    output = (f"\n{LANG.get('fatal_error_header', '--- FATAL ERROR ---')}\n"
                            f"{LANG.get('fatal_error_reason_1', 'Your system does not meet the hardware requirements.')}\n\n"
                            f"{LANG.get('fatal_error_reason_2', 'Reason:')} {error_message}\n")
                    gui_queue.put(('-VIDEOCR_OUTPUT-', output))
                    continue

                warning_match = WARNING_HARDWARE_PATTERN.search(line)
                if warning_match:
                    warning_message = warning_match.group(1)
                    output = (f"\n{LANG.get('warning_header', 'WARNING:')} {warning_message}\n")
                    gui_queue.put(('-VIDEOCR_OUTPUT-', output))
                    continue

                match1 = STEP1_PROGRESS_PATTERN.search(line)
                if match1:
                    step_num = int(match1.group(1))
                    last_reported_percentage_step1 = handle_progress(
                        match1, "progress_step1",
                        last_reported_percentage_step1, 5, step_num)
                    continue

                match2 = STEP_IMAGE_PROGRESS_PATTERN.search(line)
                if match2:
                    step_num = int(match2.group(1))

                    if step_num == 2:
                        last_reported_percentage_step2 = handle_progress(
                            match2, "progress_step2",
                            last_reported_percentage_step2, 5, step_num)
                    elif step_num == 3:
                        last_reported_percentage_step3 = handle_progress(
                            match2, "progress_step3",
                            last_reported_percentage_step3, 5, step_num)
                    continue

                info_pass_match = INFO_PASS_PATTERN.search(line)
                if info_pass_match:
                    frames = info_pass_match.group(1)
                    grids = info_pass_match.group(2)
                    raw_msg = LANG.get('cli_info_pass', "Running Text-Detection-Only pass on {} filtered frame(s) stitched into {} image grid(s)...")
                    msg = raw_msg.format(frames, grids)
                    gui_queue.put(('-VIDEOCR_OUTPUT-', msg + '\n'))
                    gui_queue.put(('-PROGRESS-SMOOTH-', {'text': msg, 'percent': None}))
                    continue

                filtered_match = FILTERED_PATTERN.search(line)
                if filtered_match:
                    frames = filtered_match.group(1)
                    raw_msg = LANG.get('cli_filtered', "Filtered out {} redundant frame(s) via Text-Detection and tight-box SSIM analysis.")
                    msg = raw_msg.format(frames)
                    gui_queue.put(('-VIDEOCR_OUTPUT-', msg + '\n'))
                    gui_queue.put(('-PROGRESS-SMOOTH-', {'text': msg, 'percent': None}))
                    continue

                repack_match = REPACKING_PATTERN.search(line)
                if repack_match:
                    curr_frame = int(repack_match.group(1))
                    tot_frame = int(repack_match.group(2))
                    if tot_frame > 0:
                        pct = (curr_frame / tot_frame) * 100
                        if pct >= last_repacking_pct + 20.0 or curr_frame == tot_frame:
                            raw_msg = LANG.get('cli_repacking', "Analyzing and repacking frame {} of {}")
                            msg = f"{raw_msg.format(curr_frame, tot_frame)} ({int(pct)}%)"
                            gui_queue.put(('-VIDEOCR_OUTPUT-', msg + "\n"))
                            gui_queue.put(('-PROGRESS-SMOOTH-', {'text': msg, 'percent': None}))
                            last_repacking_pct = pct
                    continue

                stitched_match = STITCHED_PATTERN.search(line)
                if stitched_match:
                    frames = stitched_match.group(1)
                    grids = stitched_match.group(2)
                    raw_msg = LANG.get('cli_stitched', "Stitched {} remaining frame(s) down to {} image grid(s).")
                    msg = raw_msg.format(frames, grids)
                    gui_queue.put(('-VIDEOCR_OUTPUT-', msg + '\n'))
                    gui_queue.put(('-PROGRESS-SMOOTH-', {'text': msg, 'percent': None}))
                    continue

                if REACHED_END_TIME_PATTERN.search(line):
                    gui_queue.put(('-VIDEOCR_OUTPUT-', LANG.get('log_reached_end', line) + '\n'))
                    gui_queue.put(('-PROGRESS-SMOOTH-', {'text': LANG.get('log_reached_end', line), 'percent': None}))
                    continue
                if STARTING_PADDLEOCR_PATTERN.search(line):
                    gui_queue.put(('-VIDEOCR_OUTPUT-', LANG.get('cli_starting_paddleocr', line) + '\n'))
                    gui_queue.put(('-PROGRESS-SMOOTH-', {'text': LANG.get('cli_starting_paddleocr', line), 'percent': None}))
                    continue
                if STARTING_LENS_PATTERN.search(line):
                    gui_queue.put(('-VIDEOCR_OUTPUT-', LANG.get('cli_starting_lens', line) + '\n'))
                    gui_queue.put(('-PROGRESS-SMOOTH-', {'text': LANG.get('cli_starting_lens', line), 'percent': None}))
                    continue
                if GENERATING_SUBTITLES_PATTERN.search(line):
                    gui_queue.put(('-VIDEOCR_OUTPUT-', LANG.get('cli_generating_subs', line) + '\n'))
                    gui_queue.put(('-PROGRESS-SMOOTH-', {'text': LANG.get('cli_generating_subs', line), 'percent': None}))
                    continue

        exit_code = process.wait()
        stderr_thread.join()

        process_was_cancelled = getattr(window, 'cancelled_by_user', False)
        if exit_code != 0 and not process_was_cancelled:
            full_stdout = "".join(stdout_lines)
            full_stderr = "".join(stderr_lines)

            if ("Error: Process failed" not in full_stdout and "Unsupported Hardware Error:" not in full_stdout):
                log_message = (
                    f"The videocr-cli process crashed with exit code {exit_code}.\n\n"
                    f"--- COMMAND ---\n{' '.join(command)}\n\n"
                    f"--- STDOUT ---\n{full_stdout}\n\n"
                    f"--- STDERR ---\n{full_stderr}\n"
                )

                log_file_path = log_error(log_message, log_name="videocr-cli_crash.log")

                error_display_message = (
                    f"\n{LANG.get('unexpected_error_header', '--- UNEXPECTED ERROR ---')}\n"
                    f"{LANG.get('unexpected_error_1', 'The subtitle extraction process failed unexpectedly.')}\n"
                    f"{LANG.get('unexpected_error_2', 'A detailed crash report has been saved to:')}\n{log_file_path}\n"
                )
                gui_queue.put(('-VIDEOCR_OUTPUT-', error_display_message))

        return exit_code == 0

    except Exception as e:
        error_msg = LANG.get('error_generic_exception', "\nAn error occurred: {}\n")
        gui_queue.put(('-VIDEOCR_OUTPUT-', error_msg.format(e)))
        return False


def start_queue(window: sg.Window, queue_data: list[dict[str, Any]]) -> None:
    """Common logic to start the batch processor."""
    window.is_processing = True

    pending_items = [j for j in queue_data if j['status'] == 'Pending']

    if not pending_items:
        return

    for btn in ['-BTN-BATCH-START-', '-BTN-RUN-']:
        window[btn].update(disabled=True)
    window['-BTN-CANCEL-'].update(disabled=False)
    window['-BTN-BATCH-STOP-'].update(disabled=False)
    window['-BTN-BATCH-PAUSE-'].update(disabled=False, text=LANG.get('btn_pause', "Pause"))
    window['-BTN-PAUSE-'].update(disabled=False, text=LANG.get('btn_pause', "Pause"))

    window.cancelled_by_user = False
    threading.Thread(target=run_batch_thread, args=(window, queue_data), daemon=True).start()


def run_batch_thread(window: sg.Window, queue_data: list[dict[str, Any]]) -> None:
    """Worker thread that dynamically pulls the next 'Pending' job from the queue."""
    success_count = 0
    last_processed_args = None

    while True:
        if getattr(window, 'cancelled_by_user', False):
            break

        current_job = next((j for j in queue_data if j['status'] == 'Pending'), None)

        if not current_job:
            break

        current_job['status'] = 'Processing'
        gui_queue.put(('-BATCH-REFRESH-', None))

        args = current_job['args']
        last_processed_args = args
        processing_text = LANG.get('batch_processing_file', 'Processing')
        header = f"{'=' * 10} {processing_text}: {os.path.basename(args['video_path'])} {'=' * 10}\n"
        gui_queue.put(('-VIDEOCR_OUTPUT-', '\n'))
        gui_queue.put(('-VIDEOCR_OUTPUT-', header))

        success = run_videocr(args, window)

        if getattr(window, 'cancelled_by_user', False):
            current_job['status'] = 'Cancelled'
        else:
            if success:
                current_job['status'] = 'Completed'
                success_count += 1

                gui_queue.put(('-VIDEOCR_OUTPUT-', '\n'))
                gui_queue.put(('-VIDEOCR_OUTPUT-', LANG.get('status_success', "Successfully generated subtitle file!\n")))
            else:
                current_job['status'] = 'Error'

        gui_queue.put(('-BATCH-REFRESH-', None))
        time.sleep(0.1)

    if not getattr(window, 'cancelled_by_user', False) and last_processed_args and success_count > 0:
        if last_processed_args.get('send_notification', True):
            notification_title = LANG.get('notification_title', "Your Subtitle generation is done!")
            if success_count == 1:
                msg = f"{os.path.basename(last_processed_args['output'])}"
            else:
                msg = LANG.get('batch_finished_count', "Batch finished: {} files processed.").format(success_count)
            gui_queue.put(('-NOTIFICATION_EVENT-', {'title': notification_title, 'message': msg}))

    gui_queue.put(('-BATCH-FINISHED-', None))


def update_queue_tab_count(window: sg.Window, queue: list[dict[str, Any]]) -> None:
    """Updates the Queue tab title. Counts Pending, Processing, Cancelled, Paused."""
    active_count = len([j for j in queue if j['status'] in ('Pending', 'Processing', 'Cancelled', 'Paused')])

    base_title = LANG.get('tab_batch', 'Queue')
    if active_count > 0:
        new_title = f"{base_title} ({active_count})"
    else:
        new_title = base_title

    try:
        window['-TABGROUP-'].Widget.tab(window['-TAB-BATCH-'].Widget, text=new_title)
    except Exception as e:
        log_error(f"Failed to update tab title: {e}")


def refresh_batch_table(window: sg.Window) -> None:
    """Refreshes the batch table with translated status text."""
    data: list[list[str]] = []
    for item in batch_queue:
        display_status = get_translated_status(item['status'])
        data.append([item['filename'], item['output'], display_status])

    window['-BATCH-TABLE-'].update(values=data)
    update_queue_tab_count(window, batch_queue)


def set_process_pause_state(pid: int, pause: bool = True) -> bool:
    """
    Pauses (suspends) or Resumes the process with the given PID
    and its entire child process tree.
    """
    try:
        parent = psutil.Process(pid)

        if pause:
            parent.suspend()

            children = parent.children(recursive=True)
            for child in children:
                with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                    child.suspend()

        else:
            children = parent.children(recursive=True)
            for child in children:
                with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                    child.resume()

            parent.resume()

        return True

    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        log_error(f"Failed to change pause state: {e}")
        return False


def set_system_awake(should_be_awake: bool) -> None:
    """Acquires or releases the system wake lock safely."""
    global current_wake_lock

    if should_be_awake:
        if current_wake_lock is None:
            try:
                current_wake_lock = keep.running()
                current_wake_lock.__enter__()
            except Exception as e:
                log_error(f"Failed to acquire wake lock: {e}")
    else:
        if current_wake_lock:
            try:
                current_wake_lock.__exit__(None, None, None)
            except Exception as e:
                log_error(f"Failed to release wake lock: {e}")
            finally:
                current_wake_lock = None


def execute_post_completion_action(window: sg.Window, icon: str | bytes | None = None) -> None:
    """Executes the selected system action based on the Combo box index."""
    if getattr(window, 'cancelled_by_user', False):
        return

    selected_index = window['-POST_ACTION-'].Widget.current()
    if selected_index <= 0:
        return

    action_key = POST_ACTION_KEYS[selected_index]
    display_text = LANG.get(action_key, DEFAULT_ACTION_TEXTS[action_key])

    proceed = popup_post_action_countdown(window, display_text, icon=icon)

    if not proceed:
        cancel_msg = LANG.get('log_action_cancelled', "Post-completion action cancelled by user.")
        window['-OUTPUT-'].update(f'\n{cancel_msg}\n', append=True)
        return

    log_msg = LANG.get('log_post_action', "Executing post-completion action: {}").format(display_text)
    window['-OUTPUT-'].update(f'\n{log_msg}\n', append=True)

    if action_key == 'action_shutdown':
        if sys.platform == "win32":
            os.system("shutdown /s /t 0")
        else:
            os.system("systemctl poweroff")
    elif action_key == 'action_sleep':
        if sys.platform == "win32":
            ctypes.windll.powrprof.SetSuspendState(False, False, False)
        else:
            os.system("systemctl suspend")
    elif action_key == 'action_hibernate':
        if sys.platform == "win32":
            ctypes.windll.powrprof.SetSuspendState(True, False, False)
    elif action_key == 'action_lock':
        if sys.platform == "win32":
            ctypes.windll.user32.LockWorkStation()


def update_run_and_cancel_button_state(window: sg.Window, queue: list[dict[str, Any]]) -> None:
    """Updates the Run and Cancel button text based on whether there are PENDING items."""
    has_pending = any(item['status'] == 'Pending' for item in queue)

    if has_pending:
        window['-BTN-RUN-'].update(text=LANG.get('btn_start_queue', "Start Queue"))
        window['-BTN-CANCEL-'].update(text=LANG.get('btn_stop_queue', "Stop Queue"))
    else:
        window['-BTN-RUN-'].update(text=LANG.get('btn_run', 'Run'))
        window['-BTN-CANCEL-'].update(text=LANG.get('btn_cancel', "Cancel"))


def update_taskbar(state: str | None = None, progress: int | None = None) -> None:
    """Updates the taskbar progress and state, checking for OS support."""
    global previous_taskbar_state, prog
    if prog is None:
        return

    if state and state != previous_taskbar_state:
        previous_taskbar_state = state
        prog.setState(state)

    if progress is not None:
        prog.setProgress(progress)


def check_crop_validity(video_path: str, args: dict[str, Any]) -> tuple[bool, str | None]:
    """Checks if the crop coordinates in 'args' fit within the video dimensions."""
    width, height, _ = video_manager.open(video_path).values()
    if width == 0 or height == 0:
        return False, "Could not determine video dimensions."

    def check_zone(x: int, y: int, w: int, h: int, zone_name: str = "") -> str | None:
        if x >= width:
            return LANG.get('err_crop_x_out', "{} X ({}) is outside video width ({}).").format(zone_name, x, width)
        if y >= height:
            return LANG.get('err_crop_y_out', "{} Y ({}) is outside video height ({}).").format(zone_name, y, height)
        if x + w > width:
            return LANG.get('err_crop_w_out', "{} extends out of bounds (X+W > Width).").format(zone_name)
        if y + h > height:
            return LANG.get('err_crop_h_out', "{} extends out of bounds (Y+H > Height).").format(zone_name)
        return None

    if 'crop_x' in args:
        err = check_zone(int(args['crop_x']), int(args['crop_y']),
                         int(args['crop_width']), int(args['crop_height']), "Zone 1")
        if err:
            return False, err

    if 'crop_x2' in args:
        err = check_zone(int(args['crop_x2']), int(args['crop_y2']),
                         int(args['crop_width2']), int(args['crop_height2']), "Zone 2")
        if err:
            return False, err

    return True, None


available_languages = get_available_languages()
ui_language_display_names = sorted(list(available_languages.keys()))


# Apply Global GUI Options before defining layout so all elements inherit them
if gui_scale_multiplier is not None:
    # Standard OS 100% zoom is 96 DPI. Tkinter 1.0 scaling is 72 DPI.
    # Base Tkinter scaling for 100% is therefore 96 / 72 = 1.333...
    sg.set_options(scaling=gui_scale_multiplier * (96 / 72))

    # Manually scale fonts on Linux
    if sys.platform != "win32":
        default_font_name = sg.DEFAULT_FONT[0]
        default_font_size = sg.DEFAULT_FONT[1]
        scaled_font_size = int(default_font_size * gui_scale_multiplier)
        sg.set_options(font=(default_font_name, scaled_font_size))
else:
    sg.set_options(scaling=None)


def scale_font_size(base_size: int) -> int:
    """Scales a hardcoded font size integer for Linux to match Windows DPI behavior."""
    if sys.platform != "win32" and gui_scale_multiplier is not None:
        return int(base_size * gui_scale_multiplier)
    return base_size


_strut_counter = 0


def VerticalStrut() -> sg.Element:
    """
    Cross-platform: Creates an empty Canvas for a strict 0-width vertical strut.
    Starts at 0 height and is resized dynamically after window creation to sync row heights.
    """
    global _strut_counter
    _strut_counter += 1

    return sg.Canvas(
        size=(0, 0),
        background_color=sg.theme_background_color(),
        pad=(0, 3),  # Default top/bottom padding for elements is 3
        key=f"-STRUT_{_strut_counter}-"
    )


# --- GUI Layout ---
sg.theme("Darkgrey13")

tab1_content = [
    [
        sg.Column([
            [sg.Text("Source:", size=(17, 1), key='-LBL-SOURCE-'),
            sg.Combo([], key="-VIDEO-LIST-", size=(38, 1), enable_events=True, readonly=True, disabled=True, expand_x=True), VerticalStrut()],
            [sg.Text("Output SRT:", size=(17, 1), key='-LBL-OUTPUT_SRT-'),
            sg.Input(key="--output", disabled_readonly_background_color=sg.theme_input_background_color(), readonly=True, disabled=True, size=(40, 1)), VerticalStrut()],
            [sg.Text("OCR Engine:", size=(17, 1), key='-LBL-OCR_ENGINE-'),
            sg.Combo(OCR_ENGINES, default_value=DEFAULT_OCR_ENGINE, key="-OCR_ENGINE_COMBO-", size=(38, 1), readonly=True, enable_events=True, expand_x=True), VerticalStrut()],
            [sg.Text("Subtitle Language:", size=(17, 1), key='-LBL-SUB_LANG-'),
            sg.Combo(paddle_display_names, default_value=DEFAULT_SUBTITLE_LANGUAGE, key="-LANG_COMBO-", size=(38, 1), readonly=True, enable_events=True, expand_x=True), VerticalStrut()],
            [sg.Text("Subtitle Position:", size=(17, 1), key='-LBL-SUB_POS-'),
            sg.Combo([], key="-SUBTITLE_POS_COMBO-", size=(38, 4), readonly=True, enable_events=True, expand_x=True), VerticalStrut()],
        ], pad=(0, None)),
        sg.Column([
            [sg.Button("Open File...", key="-BTN-OPEN-FILE-"), sg.Button("Open Folder...", key="-BTN-OPEN-FOLDER-")],
            [sg.Button('Save As...', key="-SAVE_AS_BTN-", disabled=True)],
            [sg.Button("Info", key="-BTN-OCR-INFO-")],
            [VerticalStrut()],
            [sg.Push(), sg.Button("How to Use", key="-BTN-HELP-")],
        ], pad=(0, None), expand_x=True)
    ],
    [sg.Graph(canvas_size=graph_size, graph_bottom_left=(0, graph_size[1]), graph_top_right=(graph_size[0], 0),
              key="-GRAPH-", change_submits=True, drag_submits=True, enable_events=True, motion_events=True, background_color='black')],
    [sg.Text("Seek:", key='-LBL-SEEK-'), sg.Slider(range=(0, 0), key="-SLIDER-", orientation='h', size=(45, 15), expand_x=True, enable_events=True, disable_number_display=True, disabled=True)],
    [
        sg.Push(),
        sg.Text("Time: -/-", key="-TIME_TEXT-")
    ],
    [sg.Text("Crop Box (X, Y, W, H):", key='-LBL-CROP_BOX-'), sg.Text("Not Set", key="-CROP_COORDS-", size=(45, 1), expand_x=True)],
    [sg.Button("Run", key="-BTN-RUN-"),
     sg.Button("Pause", key="-BTN-PAUSE-", disabled=True),
     sg.Button("Cancel", key="-BTN-CANCEL-", disabled=True),
     sg.Button("Clear Crop", key="-BTN-CLEAR_CROP-", disabled=True)],
    [sg.Button("Add to Queue", key="-BTN-ADD-BATCH-"),
     sg.Button("Add All to Queue", key="-BTN-BATCH-ADD-ALL-")],
    [sg.Text("Progress Info:", key='-LBL-PROGRESS-')],
    [
        sg.Text("", key="-STATUS-LINE-", size=(None, 1), expand_x=True),
        sg.Text("", key="-ETA-LINE-", size=(25, 1), justification='right')
    ],
    [sg.ProgressBar(100, orientation='h', size=(1, 20), key="-PROGRESS-BAR-", expand_x=True)],
    [sg.Text("Log:", key='-LBL-LOG-')],
    [sg.Multiline(key="-OUTPUT-", size=(None, 7), expand_x=True, autoscroll=True, reroute_stdout=False, reroute_stderr=False, write_only=True, disabled=True)],
    [sg.Push(),
     sg.Text("When ready:", key='-LBL-WHEN_READY-'),
     sg.Combo([], key='-POST_ACTION-', readonly=True, enable_events=True, size=(20, 1))]
]
tab1_layout = [[sg.Column(tab1_content,
                           key='-TAB1_COL-',
                           size_subsample_height=1,
                           scrollable=True,
                           vertical_scroll_only=True,
                           expand_x=True,
                           expand_y=True)]]

# -- Tab Batch: Queue Management --
tab_batch_content = [
    [sg.Text("Queue", font=("Arial", scale_font_size(12), "bold"), key='-LBL-QUEUE-TITLE-')],
    [sg.Table(values=[], headings=['Video File', 'Output File', 'Status'], key='-BATCH-TABLE-',
              col_widths=[25, 25, 15], auto_size_columns=False, justification='left',
              expand_x=True, expand_y=True, enable_events=True, select_mode=sg.TABLE_SELECT_MODE_EXTENDED)],

    [sg.Button("Start Queue", key="-BTN-BATCH-START-"),
     sg.Button("Stop Queue", key="-BTN-BATCH-STOP-", disabled=True),
     sg.Button("Pause", key="-BTN-BATCH-PAUSE-", disabled=True)],
    [sg.Button("▲", key="-BTN-BATCH-UP-", size=(3, 1)),
     sg.Button("▼", key="-BTN-BATCH-DOWN-", size=(3, 1)),
     sg.VerticalSeparator(),
     sg.Button("Reset", key="-BTN-BATCH-RESET-"),
     sg.Button("Edit", key="-BTN-BATCH-EDIT-"),
     sg.Button("Remove", key="-BTN-BATCH-REMOVE-"),
     sg.Button("Clear Queue", key="-BTN-BATCH-CLEAR-")]
]
tab_batch_layout = [[sg.Column(tab_batch_content, expand_x=True, expand_y=True)]]

tab2_content = [
    [sg.Text("OCR Settings:", font=("Arial", scale_font_size(10), "bold"), key='-LBL-OCR_SETTINGS-')],
    [sg.Text("Start Time (e.g., 0:00 or 1:23:45):", size=(38, 1), key='-LBL-TIME_START-'),
     sg.Input(DEFAULT_TIME_START, key="--time_start", size=(15, 1), enable_events=True)],
    [sg.Text("End Time (e.g., 0:10 or 2:34:56):", size=(38, 1), key='-LBL-TIME_END-'),
     sg.Input("", key="--time_end", size=(15, 1), enable_events=True)],
    [sg.Text("Confidence Threshold (0-100):", size=(38, 1), key='-LBL-CONF_THRESHOLD-'),
     sg.Input(DEFAULT_CONF_THRESHOLD, key="--conf_threshold", size=(10, 1), enable_events=True)],
    [sg.Text("Similarity Threshold (0-100):", size=(38, 1), key='-LBL-SIM_THRESHOLD-'),
     sg.Input(DEFAULT_SIM_THRESHOLD, key="--sim_threshold", size=(10, 1), enable_events=True)],
    [sg.Text("Max Merge Gap (seconds):", size=(38, 1), key='-LBL-MERGE_GAP-'),
     sg.Input(DEFAULT_MAX_MERGE_GAP, key="--max_merge_gap", size=(10, 1), enable_events=True)],
    [sg.Text("Brightness Threshold (0-255):", size=(38, 1), key='-LBL-BRIGHTNESS-'),
     sg.Input("", key="--brightness_threshold", size=(10, 1), enable_events=True)],
    [sg.Text("SSIM Threshold (0-100):", size=(38, 1), key='-LBL-SSIM-'),
     sg.Input(DEFAULT_SSIM_THRESHOLD, key="--ssim_threshold", size=(10, 1), enable_events=True)],
    [sg.Text("Max OCR Image Width (pixel):", size=(38, 1), key='-LBL-OCR_WIDTH-'),
     sg.Input(DEFAULT_OCR_IMAGE_MAX_WIDTH, key="--ocr_image_max_width", size=(10, 1), enable_events=True)],
    [sg.Text("Frames to Skip:", size=(38, 1), key='-LBL-FRAMES_SKIP-'),
     sg.Input(DEFAULT_FRAMES_TO_SKIP, key="--frames_to_skip", size=(10, 1), enable_events=True)],
    [sg.Text("Minimum Subtitle Duration (seconds):", size=(38, 1), key='-LBL-MIN_DURATION-'),
     sg.Input(DEFAULT_MIN_SUBTITLE_DURATION, key="--min_subtitle_duration", size=(10, 1), enable_events=True)],
    [sg.Checkbox("Enable GPU Usage", default=True, key="--use_gpu", enable_events=True)],
    [sg.Checkbox("Use Full Frame OCR", default=False, key="--use_fullframe", enable_events=True)],
    [sg.Checkbox("Enable Dual Zone OCR", default=False, key="--use_dual_zone", enable_events=True)],
    [sg.Checkbox("Enable Subtitle Alignment", default=False, key="enable_subtitle_alignment", enable_events=True)],
    [sg.Text("Zone 1 Alignment:", size=(38, 1), key='-LBL-SUBTITLE-ALIGNMENT-'),
     sg.Combo([], key="--subtitle_alignment", size=(15, 1), readonly=True, enable_events=True, disabled=True)],
    [sg.Text("Zone 2 Alignment:", size=(38, 1), key='-LBL-SUBTITLE-ALIGNMENT2-'),
     sg.Combo([], key="--subtitle_alignment2", size=(15, 1), readonly=True, enable_events=True, disabled=True)],
    [sg.Checkbox("Enable Angle Classification", default=False, key="--use_angle_cls", enable_events=True)],
    [sg.Checkbox("Enable Post Processing", default=False, key="--post_processing", enable_events=True)],
    [sg.Checkbox("Normalize Traditional to Simplified Chinese", default=True, key="--normalize_to_simplified_chinese", enable_events=True)],
    [sg.Checkbox("Use Server Model", default=False, key="--use_server_model", enable_events=True)],
    [sg.HorizontalSeparator()],
    [sg.Text("VideOCR Settings:", font=("Arial", scale_font_size(10), "bold"), key='-LBL-VIDEOCR_SETTINGS-')],
    [
        sg.Column([
            [sg.Text("UI Language:", size=(30, 1), key='-LBL-UI_LANG-'), VerticalStrut()],
            [sg.Text("GUI Scaling:", size=(30, 1), key='-LBL-GUI_SCALING-'), VerticalStrut()],
            [sg.Checkbox("Save Crop Box Selection", default=True, key="--save_crop_box", enable_events=True), VerticalStrut()],
            [sg.Checkbox("Save SRT in Video Directory", default=True, key="--save_in_video_dir", enable_events=True), VerticalStrut()],
            [sg.Text("Output Directory:", size=(30, 1), key='-LBL-OUTPUT_DIR-'), VerticalStrut()],
            [sg.Text("Keyboard Seek Step (seconds):", size=(30, 1), key='-LBL-SEEK_STEP-'), VerticalStrut()],
            [sg.Checkbox("Send Notification", default=True, key="--send_notification", enable_events=True), VerticalStrut()],
            [sg.Checkbox("Prevent System Sleep", default=True, key="prevent_system_sleep", enable_events=True), VerticalStrut()],
            [sg.Checkbox("Check for Updates On Startup", default=True, key="--check_for_updates", enable_events=True), VerticalStrut()],
        ], pad=(0, None)),
        sg.Column([
            [sg.Combo(ui_language_display_names, key='-UI_LANG_COMBO-', size=(32, 1), readonly=True, enable_events=True, expand_x=True), VerticalStrut()],
            [sg.Combo([], key='gui_scaling', size=(32, 1), readonly=True, enable_events=True, expand_x=True), VerticalStrut()],
            [VerticalStrut()],
            [VerticalStrut()],
            [sg.Input(DEFAULT_DOCUMENTS_DIR, key="--default_output_dir", disabled_readonly_background_color=sg.theme_input_background_color(), readonly=True, size=(34, 1), enable_events=True), VerticalStrut()],
            [sg.Input(KEY_SEEK_STEP, key="--keyboard_seek_step", size=(10, 1), enable_events=True), VerticalStrut()],
            [VerticalStrut()],
            [VerticalStrut()],
            [sg.Button("Check Now", key="-BTN-CHECK_UPDATE_MANUAL-")],
        ], pad=(0, None)),
        sg.Column([
            [VerticalStrut()],
            [VerticalStrut()],
            [VerticalStrut()],
            [VerticalStrut()],
            [sg.Button("Open Folder...", key="-BTN-FOLDER_BROWSE-", disabled=True)],
            [VerticalStrut()],
            [VerticalStrut()],
            [VerticalStrut()],
            [VerticalStrut()],
        ], pad=(0, None), expand_x=True),
    ]
]
tab2_layout = [[sg.Column(tab2_content,
                           key='-TAB2_COL-',
                           size_subsample_height=1,
                           scrollable=True,
                           vertical_scroll_only=True,
                           expand_x=True,
                           expand_y=True)]]

tab3_layout = [
    [sg.Column([
        [sg.Text("")],
        [sg.Text("VideOCR", font=("Arial", scale_font_size(16), "bold"))],
        [sg.Text(f"Version: {PROGRAM_VERSION}", font=("Arial", scale_font_size(11)), key='-LBL-ABOUT_VERSION-')],
        [sg.Text("")],
        [sg.Text("Get the newest version here:", font=("Arial", scale_font_size(11)), key='-LBL-GET_NEWEST-')],
        [sg.Text("https://github.com/timminator/VideOCR/releases", font=("Arial", scale_font_size(11), 'underline'), enable_events=True, key="-GITHUB_RELEASES_LINK-")],
        [sg.Text("")],
        [sg.Text("Found a bug or have a suggestion? Feel free to open an issue at:", font=("Arial", scale_font_size(11)), key='-LBL-BUG_REPORT-')],
        [sg.Text("https://github.com/timminator/VideOCR/issues", font=("Arial", scale_font_size(11), 'underline'), enable_events=True, key="-GITHUB_ISSUES_LINK-")],
        [sg.Text("")],
        [sg.HorizontalSeparator()],
    ], element_justification='c', expand_x=True, expand_y=True)]
]

layout = [
    [sg.TabGroup([
        [sg.Tab('Process Video', tab1_layout, key='-TAB-VIDEO-'),
         sg.Tab('Queue', tab_batch_layout, key='-TAB-BATCH-'),
         sg.Tab('Advanced Settings', tab2_layout, key='-TAB-ADVANCED-'),
         sg.Tab('About', tab3_layout, key='-TAB-ABOUT-')]
    ], key='-TABGROUP-', enable_events=True, expand_x=True, expand_y=True)]
]

if sys.platform == "win32":
    ICON_PATH = os.path.join(APP_DIR, 'VideOCR.ico')
else:
    ICON_PATH = os.path.join(APP_DIR, 'VideOCR.png')

y_offset = 0
decorations_height = 0

if sys.platform == "win32":
    SM_CYCAPTION = 4
    SM_CYFRAME = 33
    SM_CXPADDEDBORDER = 92
    SM_CYBORDER = 6

    caption = ctypes.windll.user32.GetSystemMetrics(SM_CYCAPTION)
    frame = ctypes.windll.user32.GetSystemMetrics(SM_CYFRAME)
    padding = ctypes.windll.user32.GetSystemMetrics(SM_CXPADDEDBORDER)
    border = ctypes.windll.user32.GetSystemMetrics(SM_CYBORDER)

    y_offset = -(caption + frame) // 2
    decorations_height = caption + (frame * 2) + padding - (border * 2)


def get_work_area() -> tuple[int, int]:
    """Returns the exact usable screen width and height, excluding the taskbar."""
    if sys.platform == "win32":
        class RECT(ctypes.Structure):
            _fields_ = [
                ('left', ctypes.c_long),
                ('top', ctypes.c_long),
                ('right', ctypes.c_long),
                ('bottom', ctypes.c_long)
            ]

        rect = RECT()
        SPI_GETWORKAREA = 48
        ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)

        work_width = rect.right - rect.left
        work_height = rect.bottom - rect.top
        return work_width, work_height
    else:
        width, height = sg.Window.get_screen_size()
        return width, int(height * 0.90)


def stretch_scrollable_col(col_key: str) -> None:
    """
    Unlocks a PySimpleGUI scrollable column, stretches its hidden canvas viewport
    to fit the dynamically resized contents, and restores its original propagation state.
    """
    col: sg.Element = window[col_key]

    if hasattr(col, 'TKColFrame') and col.TKColFrame:
        original_propagate: bool = col.TKColFrame.pack_propagate()

        col.TKColFrame.pack_propagate(True)

        for child in col.TKColFrame.winfo_children():
            if child.winfo_class() == 'Canvas':
                scrollregion = child.cget("scrollregion")
                if scrollregion:
                    true_inner_height: int = int(scrollregion.split()[3])

                    child.config(height=true_inner_height)
                    col.TKColFrame.config(height=true_inner_height)
                break

        col.TKColFrame.pack_propagate(original_propagate)


make_dpi_aware()

window = sg.Window("VideOCR", layout, relative_location=(0, y_offset), icon=ICON_PATH, finalize=True, resizable=True)

# Resize vertical struts and resize window with new total height
scaled_btn_height = window["-BTN-OPEN-FILE-"].Widget.winfo_reqheight()
for key in window.key_dict:
    if isinstance(key, str) and key.startswith("-STRUT_"):
        window[key].Widget.config(height=scaled_btn_height)

window.refresh()
window['-TAB1_COL-'].contents_changed()
window['-TAB2_COL-'].contents_changed()
stretch_scrollable_col('-TAB1_COL-')
stretch_scrollable_col('-TAB2_COL-')
window.refresh()

# Reposition window
work_width, work_height = get_work_area()
screen_width, screen_height = sg.Window.get_screen_size()
current_width, current_height = window.size

safe_inner_height = work_height - decorations_height
total_outer_height = current_height + decorations_height

if current_height > safe_inner_height:
    window.set_size((current_width, safe_inner_height))
    x = (work_width - current_width) // 2
    window.move(x, 0)
    window.refresh()
else:
    psg_placed_y = ((screen_height - current_height) // 2) + y_offset
    bottom_edge = psg_placed_y + total_outer_height

    if bottom_edge > work_height:
        x = (work_width - current_width) // 2
        new_y = (work_height - total_outer_height) // 2
        window.move(x, new_y)
        window.refresh()

# --- Load settings when the application starts ---
load_settings(window)

update_gui_text(window)

if sys.platform == 'win32':
    prog = PyTaskbar.Progress(int(window.TKroot.wm_frame(), 16))
    prog.init()
    prog.setState('normal')

video_manager = VideoHandler()

graph = window["-GRAPH-"]


# --- Initialize crop box state in the window object ---
def reset_crop_state() -> None:
    """Resets all variables related to crop boxes."""
    global graph
    for fig_id in getattr(window, 'drawn_rect_ids', []):
        graph.delete_figure(fig_id)
    window.drawn_rect_ids = []
    window.start_point_img = None
    window.end_point_img = None
    window.crop_boxes = []
    window.resize_state = None
    window.hover_state = None
    crop_not_set_text = LANG.get('crop_not_set', "Not Set")
    window['-CROP_COORDS-'].update(crop_not_set_text)
    window["-BTN-CLEAR_CROP-"].update(disabled=True)


reset_crop_state()


def redraw_canvas_and_boxes() -> None:
    """Erases the graph, redraws the current frame, finalized crop boxes, and the active drawing box."""
    global graph, current_image_bytes, image_offset_x, image_offset_y, resized_frame_width, resized_frame_height

    graph.erase()
    if current_image_bytes:
        graph.draw_image(data=current_image_bytes, location=(image_offset_x, image_offset_y))

    window.drawn_rect_ids.clear()

    boxes_to_draw = [box['img_points'] for box in window.crop_boxes]

    if window.start_point_img is not None and window.end_point_img is not None:
        boxes_to_draw.append((window.start_point_img, window.end_point_img))

    for start_img, end_img in boxes_to_draw:
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


def redraw_boxes() -> None:
    """Deletes the rectangles and redraws them without erasing the graph."""
    global graph, image_offset_x, image_offset_y, resized_frame_width, resized_frame_height

    for rect_id in window.drawn_rect_ids:
        graph.delete_figure(rect_id)
    window.drawn_rect_ids.clear()

    boxes_to_draw = [box['img_points'] for box in window.crop_boxes]

    if window.start_point_img is not None and window.end_point_img is not None:
        boxes_to_draw.append((window.start_point_img, window.end_point_img))

    for start_img, end_img in boxes_to_draw:
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


def get_resize_hit(x: int | float, y: int | float, boxes: list[dict[str, Any]], tolerance: int = 8) -> tuple[int | None, str | None, str]:
    """Checks if coordinates are near the edges/corners, or inside the center of any crop box."""
    for idx, box in enumerate(boxes):
        start, end = box['img_points']
        x1, y1 = min(start[0], end[0]), min(start[1], end[1])
        x2, y2 = max(start[0], end[0]), max(start[1], end[1])

        near_left = abs(x - x1) <= tolerance and y1 <= y <= y2
        near_right = abs(x - x2) <= tolerance and y1 <= y <= y2
        near_top = abs(y - y1) <= tolerance and x1 <= x <= x2
        near_bottom = abs(y - y2) <= tolerance and x1 <= x <= x2

        # Corners
        if near_left and near_top:
            return idx, 'top-left', CURSORS['diag_nw_se']
        if near_right and near_bottom:
            return idx, 'bottom-right', CURSORS['diag_nw_se']
        if near_left and near_bottom:
            return idx, 'bottom-left', CURSORS['diag_ne_sw']
        if near_right and near_top:
            return idx, 'top-right', CURSORS['diag_ne_sw']

        # Edges
        if near_left:
            return idx, 'left', CURSORS['horizontal']
        if near_right:
            return idx, 'right', CURSORS['horizontal']
        if near_top:
            return idx, 'top', CURSORS['vertical']
        if near_bottom:
            return idx, 'bottom', CURSORS['vertical']

        # Inside box
        if x1 < x < x2 and y1 < y < y2:
            return idx, 'center', CURSORS['move']

    return None, None, CURSORS['crosshair']


# --- Bind keyboard events to the graph element ---
window.bind('<Left>', '-GRAPH-<Left>')
window.bind('<Right>', '-GRAPH-<Right>')

# --- Bind window restore event ---
window.bind('<Map>', '-WINDOW_RESTORED-')

# --- Track selection and bind keys to batch table ---
window.batch_anchor = None
window.batch_focus = None
window.last_selection = []
window.ignore_table_event = False

window['-BATCH-TABLE-'].bind('<Shift-KeyPress-Down>', '-SHIFT-DOWN')
window['-BATCH-TABLE-'].bind('<Shift-KeyPress-Up>', '-SHIFT-UP')


# --- Failsafe for PySimpleGUI's overwrite event bug (-Graph-+UP with -GRAPH-+MOVE) on fast movements---
def force_mouse_up(event: Any) -> None:
    """Sets a silent flag so the main loop can manually override the +MOVE event back to +UP."""
    if getattr(window, 'is_drawing', False):
        window.needs_mouse_up = True


window['-GRAPH-'].Widget.bind('<ButtonRelease-1>', force_mouse_up, add='+')

# --- Cursor Change Logic for -GITHUB_ISSUES_LINK- ---
issues_link_element = window['-GITHUB_ISSUES_LINK-']


def on_issues_enter(event: Any) -> None:
    """Callback when mouse enters the Issues link text."""
    issues_link_element.Widget.config(cursor="hand2")


def on_issues_leave(event: Any) -> None:
    """Callback when mouse leaves the Issues link text."""
    issues_link_element.Widget.config(cursor="")


issues_link_element.Widget.bind("<Enter>", on_issues_enter)
issues_link_element.Widget.bind("<Leave>", on_issues_leave)

# --- Cursor Change Logic for -GITHUB_RELEASES_LINK- ---
releases_link_element = window['-GITHUB_RELEASES_LINK-']


def on_releases_enter(event: Any) -> None:
    """Callback when mouse enters the Releases link text."""
    releases_link_element.Widget.config(cursor="hand2")


def on_releases_leave(event: Any) -> None:
    """Callback when mouse leaves the Releases link text."""
    releases_link_element.Widget.config(cursor="")


releases_link_element.Widget.bind("<Enter>", on_releases_enter)
releases_link_element.Widget.bind("<Leave>", on_releases_leave)

check_for_updates_checked_at_start = window.find_element('--check_for_updates').get()
if check_for_updates_checked_at_start:
    threading.Thread(target=check_for_updates, args=(window,), daemon=True).start()

save_in_video_dir_checked_at_start = window.find_element('--save_in_video_dir').get()
if not save_in_video_dir_checked_at_start:
    window['-BTN-FOLDER_BROWSE-'].update(disabled=False)


# --- Define the list of keys that, when changed, should trigger a settings save ---
KEYS_TO_AUTOSAVE = [
    '-UI_LANG_COMBO-',
    '-OCR_ENGINE_COMBO-',
    '-LANG_COMBO-',
    '-SUBTITLE_POS_COMBO-',
    '--time_start',
    '--time_end',
    '--conf_threshold',
    '--sim_threshold',
    '--max_merge_gap',
    '--brightness_threshold',
    '--ssim_threshold',
    '--ocr_image_max_width',
    '--frames_to_skip',
    '--use_fullframe',
    '--use_gpu',
    '--use_dual_zone',
    'enable_subtitle_alignment',
    '--subtitle_alignment',
    '--subtitle_alignment2',
    '--use_angle_cls',
    '--post_processing',
    '--min_subtitle_duration',
    '--use_server_model',
    '--keyboard_seek_step',
    '--default_output_dir',
    '--save_in_video_dir',
    '--send_notification',
    '--save_crop_box',
    '--check_for_updates',
    'prevent_system_sleep',
    '--normalize_to_simplified_chinese',
    '-POST_ACTION-',
    'gui_scaling',
]

window.is_drawing = False

# --- Event Loop ---
while True:
    event, values = window.read(timeout=50)

    # --- Failsafe Event Override ---
    if getattr(window, 'needs_mouse_up', False):
        if event in [sg.TIMEOUT_EVENT, "-GRAPH-+MOVE"]:
            window.needs_mouse_up = False
            event = "-GRAPH-+UP"

    # --- POLL QUEUE ---
    # window.write_event_value is causing crashes while drawing graph elements. See https://github.com/PySimpleGUI/PySimpleGUI/issues/5750
    if not window.is_drawing:
        try:
            while True:
                msg_event, msg_data = gui_queue.get_nowait()

                if msg_event == '-PROCESS_STARTED-':
                    window._videocr_process_pid = msg_data
                    window['-BTN-RUN-'].update(disabled=True)
                    window['-BTN-CANCEL-'].update(disabled=False)
                    window['-BTN-BATCH-STOP-'].update(disabled=False)

                elif msg_event == '-PROGRESS-SMOOTH-':
                    if msg_data.get('text'):
                        window['-STATUS-LINE-'].update(msg_data['text'])
                    if msg_data.get('eta'):
                        window['-ETA-LINE-'].update(msg_data['eta'])
                    if msg_data.get('percent') is not None:
                        window['-PROGRESS-BAR-'].update(msg_data['percent'])

                elif msg_event == '-VIDEOCR_OUTPUT-':
                    text_to_log = msg_data
                    if text_to_log.strip():
                        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                        final_text = f"[{timestamp}] {text_to_log}"
                    else:
                        final_text = text_to_log
                    window['-OUTPUT-'].update(final_text, append=True)

                elif msg_event == '-TASKBAR_STATE_UPDATE-':
                    update_taskbar(state=msg_data.get('state'), progress=msg_data.get('progress'))

                elif msg_event == '-NOTIFICATION_EVENT-':
                    send_notification(msg_data['title'], msg_data['message'])

                elif msg_event == '-BATCH-REFRESH-':
                    refresh_batch_table(window)

                elif msg_event == '-BATCH-FINISHED-':
                    window.is_processing = False
                    set_system_awake(False)

                    for btn in ['-BTN-BATCH-START-', '-BTN-RUN-']:
                        window[btn].update(disabled=False)

                    window['-BTN-BATCH-PAUSE-'].update(disabled=True, text=LANG.get('btn_pause', "Pause"))
                    window['-BTN-PAUSE-'].update(disabled=True, text=LANG.get('btn_pause', "Pause"))
                    window['-BTN-CANCEL-'].update(disabled=True)
                    window['-BTN-BATCH-STOP-'].update(disabled=True)
                    window['-SAVE_AS_BTN-'].update(disabled=not video_path)
                    window['--output'].update(disabled=not video_path)
                    window['-PROGRESS-BAR-'].update(0)
                    window['-STATUS-LINE-'].update("")
                    window['-ETA-LINE-'].update("")
                    msg = LANG.get('status_queue_cancelled', "Queue Cancelled") if getattr(window, 'cancelled_by_user', False) else LANG.get('status_queue_finished', "Queue Finished")
                    window['-OUTPUT-'].update('\n', append=True)
                    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                    window['-OUTPUT-'].update(f"[{timestamp}] {msg}\n", append=True)

                    if hasattr(window, '_videocr_process_pid'):
                        del window._videocr_process_pid

                    update_taskbar(state='normal', progress=0)
                    update_run_and_cancel_button_state(window, batch_queue)
                    execute_post_completion_action(window, icon=ICON_PATH)

                    if hasattr(window, 'cancelled_by_user'):
                        del window.cancelled_by_user

        except queue.Empty:
            pass

    # --- Save settings ---
    if event in KEYS_TO_AUTOSAVE:
        if values is not None:
            save_settings(window, values)

        if event == '--brightness_threshold':
            if video_path and video_duration_ms > 0:
                bt = get_valid_brightness_threshold(values.get('--brightness_threshold'))
                img_bytes, res_w, res_h, off_x, off_y = video_manager.get_frame(current_time_ms, graph_size, brightness_threshold=bt)

                if img_bytes:
                    resized_frame_width, resized_frame_height = res_w, res_h
                    image_offset_x, image_offset_y = off_x, off_y
                    current_image_bytes = img_bytes.getvalue()
                    redraw_canvas_and_boxes()

        if event in ('enable_subtitle_alignment', '--use_dual_zone'):
            update_alignment_controls(window, values)

        if event == '--use_dual_zone' or event == '--use_fullframe':
            reset_crop_state()
            if video_path and current_image_bytes:
                graph.erase()
                graph.draw_image(data=current_image_bytes, location=(image_offset_x, image_offset_y))
            save_settings(window, values)

        # --- Handle possible output path change ---
        if event == '--save_in_video_dir':
            if values.get('--save_in_video_dir', True):
                window['-BTN-FOLDER_BROWSE-'].update(disabled=True)
            else:
                window['-BTN-FOLDER_BROWSE-'].update(disabled=False)

            if video_path:
                output_path = generate_output_path(video_path, values)
                window['--output'].update(str(output_path))

        elif event == '-LANG_COMBO-':
            if video_path:
                current_out = values.get('--output', '')
                selected_lang_name = values.get('-LANG_COMBO-', DEFAULT_SUBTITLE_LANGUAGE)
                selected_engine_display = values.get('-OCR_ENGINE_COMBO-', DEFAULT_OCR_ENGINE)

                if "Google Lens" in selected_engine_display:
                    iso_code = lens_abbr_lookup.get(selected_lang_name, 'en')
                else:
                    paddle_code = paddle_abbr_lookup.get(selected_lang_name, 'en')
                    iso_code = PADDLE_TO_ISO_MAP.get(paddle_code, paddle_code)

                if current_out:
                    p = pathlib.Path(current_out)
                    directory = p.parent
                    known_codes = set(paddle_abbr_lookup.values()).union(
                        set(PADDLE_TO_ISO_MAP.values()),
                        set(lens_abbr_lookup.values())
                    )
                    base_name = None

                    if len(p.suffixes) >= 2 and p.suffixes[-1].lower() == '.srt' and p.suffixes[-2][1:] in known_codes:
                        base_name = p.name[:-(len(p.suffixes[-2]) + len(p.suffixes[-1]))]

                    elif p.suffix.lower() == '.srt':
                        base_name = p.stem

                    if base_name:
                        new_filename = f"{base_name}.{iso_code}.srt"
                        new_out = directory / new_filename

                        counter = 1
                        while new_out.exists():
                            new_filename = f"{base_name}({counter}).{iso_code}.srt"
                            new_out = directory / new_filename
                            counter += 1

                        window['--output'].update(str(new_out))

                    else:
                        output_path = generate_output_path(video_path, values)
                        window['--output'].update(str(output_path))
                else:
                    output_path = generate_output_path(video_path, values)
                    window['--output'].update(str(output_path))

        elif event == '-OCR_ENGINE_COMBO-':
            selected_engine = values['-OCR_ENGINE_COMBO-']
            current_lang = values['-LANG_COMBO-']

            if "Google Lens" in selected_engine:
                new_values = lens_display_names
            else:
                new_values = paddle_display_names

            if current_lang in new_values:
                new_value = current_lang
            else:
                new_value = DEFAULT_SUBTITLE_LANGUAGE

            window['-LANG_COMBO-'].update(values=new_values, value=new_value)

            if video_path:
                window.write_event_value('-LANG_COMBO-', new_value)

            save_settings(window, values)

    if event == sg.WIN_CLOSED:
        video_manager.close()
        set_system_awake(False)

        process_to_kill = getattr(window, '_videocr_process_pid', None)
        if process_to_kill:
            try:
                kill_process_tree(process_to_kill)
            except Exception as e:
                log_error(f"Exception during final process kill: {e}")
        break

    # --- Handle UI language change ---
    elif event == '-UI_LANG_COMBO-':
        selected_native_name = values['-UI_LANG_COMBO-']
        lang_code = available_languages.get(selected_native_name)

        if lang_code:
            current_resume_text = LANG.get('btn_resume', "Resume")
            was_paused = window['-BTN-PAUSE-'].get_text() == current_resume_text

            selected_pos_display_name = values['-SUBTITLE_POS_COMBO-']
            pos_display_to_internal_map = {LANG.get(lang_key, lang_key): internal_val for lang_key, internal_val in SUBTITLE_POSITIONS_LIST}
            saved_internal_pos = pos_display_to_internal_map.get(selected_pos_display_name, DEFAULT_INTERNAL_SUBTITLE_POSITION)

            load_language(lang_code)
            update_gui_text(window, is_paused=was_paused)

            update_subtitle_pos_combo(window, saved_internal_pos)

            if video_path:
                update_time_display(window, current_time_ms, video_duration_ms)

    # --- Handle UI scaling change ---
    elif event == 'gui_scaling':
        title = LANG.get('title_restart', "Restart Required")
        message = LANG.get('msg_restart_scaling', "The scaling factor has been updated.\nWould you like to restart the application now to apply this change?")
        restart_choice = custom_popup_yes_no(window, title, message, icon=ICON_PATH)

        if restart_choice == 'Yes':
            video_manager.close()
            set_system_awake(False)

            process_to_kill = getattr(window, '_videocr_process_pid', None)
            if process_to_kill:
                try:
                    kill_process_tree(process_to_kill)
                except Exception as e:
                    log_error(f"Exception during restart process kill: {e}")

            if sys.argv[0].endswith('.py') or sys.argv[0].endswith('.pyw'):
                # Uncompiled: Needs the python interpreter + script name
                restart_cmd = [sys.executable] + sys.argv
            else:
                # Compiled: sys.argv[0] is already the compiled executable
                restart_cmd = sys.argv

            subprocess.Popen(restart_cmd)
            break

    # --- File/Folder Handling ---
    elif event == '-BTN-OPEN-FILE-':
        video_file_types = LANG.get('video_file_types', "Video Files")
        all_file_types = LANG.get('all_file_types', "All Files")
        filename = sg.tk.filedialog.askopenfilename(
            filetypes=((video_file_types, "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.wmv *.ts *.m2ts"), (all_file_types, "*.*")),
            parent=window.TKroot
        )
        if filename:
            window['-VIDEO-LIST-'].update(value=filename, values=[filename], size=(38, None), disabled=False)
            window.write_event_value('-VIDEO-LIST-', filename)

    elif event == '-BTN-OPEN-FOLDER-':
        folder = sg.tk.filedialog.askdirectory(parent=window.TKroot)
        if folder:
            videos = scan_video_folder(folder)
            if videos:
                window['-VIDEO-LIST-'].update(value=videos[0], values=videos, size=(38, None), disabled=False)
                window.write_event_value('-VIDEO-LIST-', videos[0])
            else:
                custom_popup(window, "No Videos", "No supported videos found in folder.", icon=ICON_PATH)

    elif event == '-BTN-FOLDER_BROWSE-':
        folder = sg.tk.filedialog.askdirectory()
        if folder:
            window['--default_output_dir'].update(folder)

    elif event == '-BTN-OCR-INFO-':
        custom_popup(window, LANG.get('engine_info', "OCR Engine Information"), LANG.get('engine_message', (
            "PaddleOCR (Det. + Rec.):\n"
            "• 100% local processing.\n"
            "• Both text detection and recognition are done locally.\n\n"
            "PaddleOCR (Det.) + Google Lens (Rec.):\n"
            "• Hybrid processing.\n"
            "• PaddleOCR handles text detection locally.\n"
            "• Google Lens (online) handles text recognition.\n"
            "• Requires an active internet connection.")),
            icon=ICON_PATH
        )

    elif event == '-NEW_VERSION_FOUND-':
        update_popup(
            parent_window=window,
            version_info=values[event],
            current_version=PROGRAM_VERSION,
            icon=ICON_PATH
        )

    elif event == '-BTN-CHECK_UPDATE_MANUAL-':
        threading.Thread(target=check_for_updates, args=(window, True), daemon=True).start()

    elif event == '-NO_UPDATE_FOUND-':
        custom_popup(window, LANG.get('update_title_uptodate', "Up to Date"), LANG.get('update_msg_uptodate', "You are running the latest version of VideOCR."), icon=ICON_PATH)

    elif event == '-UPDATE_CHECK_FAILED-':
        custom_popup(window, LANG.get('update_title_error', "Error"), LANG.get('update_msg_error', "Failed to check for updates.\nPlease check your internet connection."), icon=ICON_PATH)

    elif event == '-TABGROUP-' and values.get('-TABGROUP-') == '-TAB-VIDEO-':
        if '-GRAPH-' in window.AllKeysDict:
            window['-GRAPH-'].set_focus()

    elif event == "-BTN-HELP-":
        custom_popup(window, LANG.get('help_title', "Cropping Info"), LANG.get('help_message', (
            "Draw a crop box over the subtitle region in the video.\n"
            "Use click+drag to select.\n"
            "In 'Dual Zone' mode, you can draw two crop boxes.\n"
            "If no crop box is selected, the bottom third of the video\n"
            "will be used for OCR by default.")),
            icon=ICON_PATH
        )

    elif event == "-GITHUB_ISSUES_LINK-":
        webbrowser.open("https://github.com/timminator/VideOCR/issues")

    elif event == "-GITHUB_RELEASES_LINK-":
        webbrowser.open("https://github.com/timminator/VideOCR/releases")

    elif event == '-SAVE_AS_BTN-':
        output_path = values["--output"]
        output_file_path = pathlib.Path(output_path)

        save_as_title = LANG.get('save_as_title', "Save As")
        save_as_filter_name = LANG.get('save_as_filter_name', "SubRip Subtitle")
        save_as_all_files = LANG.get('save_as_all_files', "All Files")

        # Usage of tkinter.tkFileDialog instead of sg.popup_get_file because of the window placement on screen
        filename_chosen = sg.tk.filedialog.asksaveasfilename(
            defaultextension='srt',
            filetypes=((save_as_filter_name, "*.srt"), (save_as_all_files, "*.*")),
            initialdir=output_file_path.parent,
            initialfile=output_file_path.stem,
            parent=window.TKroot,
            title=save_as_title
        )

        if filename_chosen != "":
            window["--output"].update(filename_chosen)

    elif event == '-WINDOW_RESTORED-':
        if '-GRAPH-' in window.AllKeysDict:
            window['-GRAPH-'].set_focus()

    # --- Load Video Logic ---
    elif event == "-VIDEO-LIST-":
        video_path = values["-VIDEO-LIST-"]
        window['-BTN-RUN-'].update(disabled=True)
        window["-SLIDER-"].update(disabled=True)

        time_text_empty = LANG.get('time_text_empty', 'Time: -/-')
        window["-TIME_TEXT-"].update(time_text_empty)
        window['--output'].update("", disabled=True)
        window['-SAVE_AS_BTN-'].update(disabled=True)

        reset_crop_state()
        graph.erase()

        orig_w, orig_h, duration_ms = video_manager.open(video_path).values()

        if orig_w > 0 and orig_h > 0 and duration_ms > 0:
            original_frame_width = orig_w
            original_frame_height = orig_h
            video_duration_ms = duration_ms
            current_time_ms = 0.0

            bt = get_valid_brightness_threshold(values.get('--brightness_threshold'))
            img_bytes, res_w, res_h, off_x, off_y = video_manager.get_frame(0, graph_size, brightness_threshold=bt)

            if img_bytes:
                resized_frame_width = res_w
                resized_frame_height = res_h
                image_offset_x = off_x
                image_offset_y = off_y
                current_image_bytes = img_bytes.getvalue()

                graph.draw_image(data=current_image_bytes, location=(image_offset_x, image_offset_y))
                window["-SLIDER-"].update(range=(0, video_duration_ms), value=0, disabled=False)
                update_time_display(window, 0, video_duration_ms)

                try:
                    output_path = generate_output_path(video_path, values)

                    window['--output'].update(str(output_path))
                    if not getattr(window, 'is_processing', False):
                        window['-BTN-RUN-'].update(disabled=False)
                        window['-SAVE_AS_BTN-'].update(disabled=False)

                    if '-GRAPH-' in window.AllKeysDict:
                        window['-GRAPH-'].set_focus()

                except Exception as e:
                    popup_title = LANG.get('error_set_path_title', "Unable to Set Output Path")
                    popup_msg = LANG.get('error_set_path_msg', "Could not automatically generate default output path.\nPlease specify one manually.\nError: {}")
                    custom_popup(window, popup_title, popup_msg.format(e), icon=ICON_PATH)
                    window['--output'].update("", disabled=False)
                    window['-SAVE_AS_BTN-'].update(disabled=False)

                # --- Auto-load crop box if setting is enabled ---
                if values.get('--save_crop_box') and hasattr(window, 'saved_crop_boxes_from_config') and window.saved_crop_boxes_from_config:
                    loaded_boxes_data = window.saved_crop_boxes_from_config
                    new_crop_boxes_to_apply: list[dict[str, Any]] = []

                    for box_data in loaded_boxes_data:
                        rel_coords = box_data.get('coords', {})
                        if not rel_coords:
                            continue

                        abs_coords = {
                            'crop_x': math.floor(rel_coords.get('crop_x', 0) * original_frame_width),
                            'crop_y': math.floor(rel_coords.get('crop_y', 0) * original_frame_height),
                            'crop_width': math.ceil(rel_coords.get('crop_width', 0) * original_frame_width),
                            'crop_height': math.ceil(rel_coords.get('crop_height', 0) * original_frame_height),
                        }

                        scale_w = resized_frame_width / original_frame_width if original_frame_width > 0 else 0
                        scale_h = resized_frame_height / original_frame_height if original_frame_height > 0 else 0

                        rect_x1_img = abs_coords['crop_x'] * scale_w
                        rect_y1_img = abs_coords['crop_y'] * scale_h
                        rect_x2_img = (abs_coords['crop_x'] + abs_coords['crop_width']) * scale_w
                        rect_y2_img = (abs_coords['crop_y'] + abs_coords['crop_height']) * scale_h

                        new_box_to_apply = {
                            'coords': abs_coords,
                            'img_points': ((rect_x1_img, rect_y1_img), (rect_x2_img, rect_y2_img))
                        }
                        new_crop_boxes_to_apply.append(new_box_to_apply)

                    use_dual_zone = values.get('--use_dual_zone', False)
                    limit = 2 if use_dual_zone else 1
                    window.crop_boxes = new_crop_boxes_to_apply[:limit]

                    if window.crop_boxes:
                        redraw_canvas_and_boxes()

                        if not use_dual_zone:
                            b = window.crop_boxes[0]
                            coord_text = f"({b['coords']['crop_x']}, {b['coords']['crop_y']}, {b['coords']['crop_width']}, {b['coords']['crop_height']})"
                        else:
                            coords_str_parts = []
                            zone_text = LANG.get('crop_zone_text', "Zone")
                            for i, b in enumerate(window.crop_boxes):
                                coords_str_parts.append(f"{zone_text} {i + 1}: ({b['coords']['crop_x']}, {b['coords']['crop_y']}, {b['coords']['crop_width']}, {b['coords']['crop_height']})")
                            coord_text = "  |  ".join(coords_str_parts)

                        window['-CROP_COORDS-'].update(coord_text)
                        window["-BTN-CLEAR_CROP-"].update(disabled=False)

        else:
            popup_title = LANG.get('error_invalid_video_title', "Invalid or Empty Video File")
            popup_msg = LANG.get('error_invalid_video_msg', "Could not load video, video has no frames, or FPS is zero:\n{}")
            custom_popup(window, popup_title, popup_msg.format(video_path), icon=ICON_PATH)
            video_path = None
            video_duration_ms = 0.0

    # --- Slider Moved ---
    elif event == "-SLIDER-" and video_path and video_duration_ms > 0:
        new_time_ms = float(values["-SLIDER-"])
        if abs(new_time_ms - current_time_ms) > 50:
            current_time_ms = new_time_ms
            bt = get_valid_brightness_threshold(values.get('--brightness_threshold'))
            img_bytes, res_w, res_h, off_x, off_y = video_manager.get_frame(current_time_ms, graph_size, brightness_threshold=bt)

            if img_bytes:
                resized_frame_width, resized_frame_height = res_w, res_h
                image_offset_x, image_offset_y = off_x, off_y
                current_image_bytes = img_bytes.getvalue()

                redraw_canvas_and_boxes()
                update_time_display(window, current_time_ms, video_duration_ms)

    # --- Handle Keyboard Arrow Keys (Bound to Graph) ---
    elif event in ('-GRAPH-<Left>', '-GRAPH-<Right>'):
        if video_path and video_duration_ms > 0:
            current_time = float(values["-SLIDER-"])
            try:
                seek_step_seconds = float(values["--keyboard_seek_step"])
            except (ValueError, TypeError):
                seek_step_seconds = KEY_SEEK_STEP

            step_ms = seek_step_seconds * 1000.0

            if event == '-GRAPH-<Left>':
                new_time = max(0, current_time - step_ms)
            else:  # '-GRAPH-<Right>'
                new_time = min(video_duration_ms, current_time + step_ms)

            if new_time != current_time:
                window["-SLIDER-"].update(value=new_time)
                window.write_event_value("-SLIDER-", new_time)

    # --- Graph Interaction ---
    elif event == "-GRAPH-":
        window.is_drawing = True

        if not video_path or resized_frame_width == 0:
            continue

        graph_x, graph_y = values["-GRAPH-"]

        if not (image_offset_x <= graph_x < image_offset_x + resized_frame_width and
                image_offset_y <= graph_y < image_offset_y + resized_frame_height):
            if window.start_point_img is None and window.resize_state is None:
                continue

        img_x = graph_x - image_offset_x
        img_y = graph_y - image_offset_y

        # Initiating a click
        if window.start_point_img is None and window.resize_state is None:
            if window.hover_state:
                window.resize_state = window.hover_state.copy()
                window.resize_state['last_x'] = img_x
                window.resize_state['last_y'] = img_y
            else:
                max_boxes = 2 if values.get('--use_dual_zone') else 1
                if len(window.crop_boxes) >= max_boxes:
                    reset_crop_state()
                    window.hover_state = None
                    window.resize_state = None
                    redraw_canvas_and_boxes()
                    save_settings(window, values)

                window.start_point_img = (img_x, img_y)
                window.end_point_img = None

        # Resizing
        elif window.resize_state:
            idx = window.resize_state['idx']
            edge = window.resize_state['edge']
            box = window.crop_boxes[idx]

            p1, p2 = box['img_points']
            x1, y1 = min(p1[0], p2[0]), min(p1[1], p2[1])
            x2, y2 = max(p1[0], p2[0]), max(p1[1], p2[1])

            if edge == 'center':
                # Move Box
                dx = img_x - window.resize_state['last_x']
                dy = img_y - window.resize_state['last_y']

                box_w = x2 - x1
                box_h = y2 - y1

                x1 = max(0, min(resized_frame_width - box_w, x1 + dx))
                y1 = max(0, min(resized_frame_height - box_h, y1 + dy))
                x2 = x1 + box_w
                y2 = y1 + box_h

                window.resize_state['last_x'] = img_x
                window.resize_state['last_y'] = img_y
            else:
                # Edge Resizing
                img_x_c = max(0, min(resized_frame_width, img_x))
                img_y_c = max(0, min(resized_frame_height, img_y))

                if 'left' in edge:
                    x1 = img_x_c
                if 'right' in edge:
                    x2 = img_x_c
                if 'top' in edge:
                    y1 = img_y_c
                if 'bottom' in edge:
                    y2 = img_y_c

            box['img_points'] = ((x1, y1), (x2, y2))
            redraw_boxes()

        # Drawing
        else:
            img_x_c = max(0, min(resized_frame_width, img_x))
            img_y_c = max(0, min(resized_frame_height, img_y))

            window.end_point_img = (img_x_c, img_y_c)
            redraw_boxes()

    # --- Graph Interaction Release ---
    elif event == "-GRAPH-+UP":
        window.is_drawing = False

        # Finish Resizing
        if window.resize_state:
            idx = window.resize_state['idx']
            box = window.crop_boxes[idx]
            p1, p2 = box['img_points']

            rect_x1_img = min(p1[0], p2[0])
            rect_y1_img = min(p1[1], p2[1])
            rect_x2_img = max(p1[0], p2[0])
            rect_y2_img = max(p1[1], p2[1])

            crop_x = math.floor(rect_x1_img * original_frame_width / resized_frame_width)
            crop_y = math.floor(rect_y1_img * original_frame_height / resized_frame_height)
            crop_w = math.ceil((rect_x2_img - rect_x1_img) * original_frame_width / resized_frame_width)
            crop_h = math.ceil((rect_y2_img - rect_y1_img) * original_frame_height / resized_frame_height)

            box['coords'] = {'crop_x': crop_x, 'crop_y': crop_y, 'crop_width': crop_w, 'crop_height': crop_h}
            box['img_points'] = ((rect_x1_img, rect_y1_img), (rect_x2_img, rect_y2_img))

            window.resize_state = None
            redraw_canvas_and_boxes()

            if not values.get('--use_dual_zone', False):
                b = window.crop_boxes[0]
                coord_text = f"({b['coords']['crop_x']}, {b['coords']['crop_y']}, {b['coords']['crop_width']}, {b['coords']['crop_height']})"
            else:
                coords_str_parts = []
                zone_text = LANG.get('crop_zone_text', "Zone")
                for i, b in enumerate(window.crop_boxes):
                    coords_str_parts.append(f"{zone_text} {i + 1}: ({b['coords']['crop_x']}, {b['coords']['crop_y']}, {b['coords']['crop_width']}, {b['coords']['crop_height']})")
                coord_text = "  |  ".join(coords_str_parts)

            window['-CROP_COORDS-'].update(coord_text)
            save_settings(window, values)

        # Finish Drawing
        elif window.start_point_img is not None:
            if window.end_point_img is None:
                window.start_point_img = None
                redraw_canvas_and_boxes()
                continue

            rect_x1_img = min(window.start_point_img[0], window.end_point_img[0])
            rect_y1_img = min(window.start_point_img[1], window.end_point_img[1])
            rect_x2_img = max(window.start_point_img[0], window.end_point_img[0])
            rect_y2_img = max(window.start_point_img[1], window.end_point_img[1])

            window.start_point_img = None
            window.end_point_img = None

            min_draw_size = 7
            if (rect_x2_img - rect_x1_img) < min_draw_size or (rect_y2_img - rect_y1_img) < min_draw_size:
                redraw_canvas_and_boxes()
                save_settings(window, values)
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
                zone_text = LANG.get('crop_zone_text', "Zone")
                for i, b in enumerate(window.crop_boxes):
                    coords_str_parts.append(f"{zone_text} {i + 1}: ({b['coords']['crop_x']}, {b['coords']['crop_y']}, {b['coords']['crop_width']}, {b['coords']['crop_height']})")
                coord_text = "  |  ".join(coords_str_parts)

            window['-CROP_COORDS-'].update(coord_text)
            window["-BTN-CLEAR_CROP-"].update(disabled=False)

            save_settings(window, values)

    # --- Graph Hover (Motion Events) ---
    elif event == "-GRAPH-+MOVE":
        if not video_path or resized_frame_width == 0:
            continue

        if not window.is_drawing and window.resize_state is None:
            graph_x, graph_y = values["-GRAPH-"]
            img_x = graph_x - image_offset_x
            img_y = graph_y - image_offset_y

            hit_idx, edge, cursor = get_resize_hit(img_x, img_y, window.crop_boxes)
            window['-GRAPH-'].Widget.config(cursor=cursor)
            window.hover_state = {'idx': hit_idx, 'edge': edge} if hit_idx is not None else None

    elif event == "-BTN-ADD-BATCH-":
        if not video_path:
            continue

        args, errors = get_processing_args(values, window)
        if errors or args is None:
            errors_to_display = errors if errors is not None else []
            custom_popup(window, "Validation Error", "\n".join(errors_to_display), icon=ICON_PATH)
            continue

        target_output_full = args['output']
        existing_job_index = -1

        for idx, job in enumerate(batch_queue):
            if job['args']['output'] == target_output_full:
                existing_job_index = idx
                break

        should_create_new = True

        if existing_job_index != -1:
            existing_status = batch_queue[existing_job_index]['status']

            if existing_status in ('Cancelled', 'Error', 'Completed', 'Pending'):
                display_status = get_translated_status(existing_status)
                msg = LANG.get('popup_duplicate_msg', "A job for this output file already exists (Status: {}).\n\nDo you want to update/restart it with current settings?").format(display_status)
                choice = custom_popup_yes_no(window, LANG.get('title_duplicate_job', "Duplicate Job"), msg, icon=ICON_PATH)

                if choice == 'Yes':
                    batch_queue[existing_job_index]['args'] = args
                    batch_queue[existing_job_index]['status'] = 'Pending'
                    should_create_new = False
                else:
                    continue

            elif existing_status in ('Processing', 'Paused'):
                display_status = get_translated_status(existing_status)
                msg = LANG.get('msg_duplicate_queue_running', "A job for '{}' is currently active (Status: {}).\n\nPlease change the output path or wait for it to finish.").format(os.path.basename(target_output_full), display_status)
                custom_popup(window, LANG.get('title_duplicate', "Duplicate"), msg, icon=ICON_PATH)
                continue

        if should_create_new:
            batch_queue.append({
                'filename': os.path.basename(args['video_path']),
                'output': os.path.basename(target_output_full),
                'status': 'Pending',
                'args': args
            })

        refresh_batch_table(window)
        update_run_and_cancel_button_state(window, batch_queue)

    elif event == "-BTN-BATCH-ADD-ALL-":
        all_videos = window['-VIDEO-LIST-'].Values
        if not all_videos:
            continue

        original_duration_ms = video_duration_ms

        added_count = 0
        skipped_videos: list[str] = []

        current_queue_outputs = {j['args']['output'] for j in batch_queue}

        init_text = LANG.get('msg_scanning_init', "Initializing scan...")
        prog_layout = [[sg.Text(init_text, key='-TXT-', text_color='white', background_color='#2d2d2d', font=("Arial", scale_font_size(12)), pad=(20, 20))]]
        progress_window = sg.Window(LANG.get('title_progress', "Progress"), prog_layout, no_titlebar=True, keep_on_top=True, background_color='#2d2d2d', finalize=True, modal=True)
        center_popup(window, progress_window)

        for index, v_path in enumerate(all_videos):
            progress_window['-TXT-'].update(LANG.get('msg_scanning_file', "Scanning file {} of {}...").format(index + 1, len(all_videos)))
            progress_window.refresh()

            potential_output = generate_output_path(v_path, values)
            potential_output_str = str(potential_output)

            if potential_output_str in current_queue_outputs:
                skipped_videos.append(f"{os.path.basename(v_path)} ({LANG.get('reason_dup_path', 'Duplicate Output path')})")
                continue

            _, _, duration_ms = video_manager.open(v_path).values()
            if duration_ms <= 0:
                skipped_videos.append(f"{os.path.basename(v_path)} ({LANG.get('reason_metadata', 'Metadata Error')})")
                continue

            video_duration_ms = duration_ms

            args, errors = get_processing_args(values, window)
            if errors or args is None:
                errors_to_display = errors if errors is not None else []
                skipped_videos.append(f"{os.path.basename(v_path)}: {errors_to_display[0]}")
                continue

            is_valid, err_msg = check_crop_validity(v_path, args)
            if not is_valid:
                skipped_videos.append(f"{os.path.basename(v_path)}: {err_msg}")
                continue

            args['video_path'] = v_path
            args['output'] = potential_output_str

            batch_queue.append({
                'filename': os.path.basename(v_path),
                'output': os.path.basename(potential_output_str),
                'status': 'Pending',
                'args': args
            })

            current_queue_outputs.add(potential_output_str)
            added_count += 1

        progress_window.close()

        # Restore Global
        video_duration_ms = original_duration_ms

        refresh_batch_table(window)
        update_run_and_cancel_button_state(window, batch_queue)

        if skipped_videos:
            msg = LANG.get('msg_batch_report_summary', "Added {} videos.\n\nSkipped {} video(s):\n").format(added_count, len(skipped_videos))
            msg += "\n".join(skipped_videos[:10])
            if len(skipped_videos) > 10:
                msg += "\n" + LANG.get('msg_and_others', "...and others.")
            custom_popup(window, LANG.get('title_batch_report', "Batch Report"), msg, icon=ICON_PATH)

    elif event == "-BTN-BATCH-START-":
        if window['prevent_system_sleep'].get():
            set_system_awake(True)
        start_queue(window, batch_queue)

    elif event == "-BTN-RUN-":
        is_batch_start = window['-BTN-RUN-'].get_text() == LANG.get('btn_start_queue', "Start Queue")

        if is_batch_start:
            if window['prevent_system_sleep'].get():
                set_system_awake(True)
            start_queue(window, batch_queue)

        else:
            if not video_path:
                continue

            if hasattr(window, '_videocr_process_pid') and window._videocr_process_pid:
                window['-OUTPUT-'].update(LANG.get('error_already_running', "Process is already running.\n"), append=True)
                continue

            args, errors = get_processing_args(values, window)
            if errors or args is None:
                errors_to_display = errors if errors is not None else ["Unknown validation error"]
                window['-OUTPUT-'].update(LANG.get('val_err_header', "Validation Errors:\n"), append=True)
                for error in errors_to_display:
                    window['-OUTPUT-'].update(f"- {error}\n", append=True)
                window.refresh()
                continue

            target_output_full = args['output']
            existing_job_index = -1

            for idx, job in enumerate(batch_queue):
                if job['args']['output'] == target_output_full:
                    existing_job_index = idx
                    break

            should_create_new = True

            if existing_job_index != -1:
                existing_status = batch_queue[existing_job_index]['status']

                if existing_status in ('Cancelled', 'Error', 'Completed'):
                    display_status = get_translated_status(existing_status)
                    msg = LANG.get('popup_duplicate_msg', "A job for this output file already exists (Status: {}).\n\nDo you want to restart it with current settings?").format(display_status)
                    choice = custom_popup_yes_no(window, LANG.get('title_duplicate_job', "Duplicate Job"), msg, icon=ICON_PATH)

                    if choice == 'Yes':
                        batch_queue[existing_job_index]['args'] = args
                        batch_queue[existing_job_index]['status'] = 'Pending'
                        should_create_new = False
                    else:
                        continue

            if should_create_new:
                batch_queue.append({
                    'filename': os.path.basename(args['video_path']),
                    'output': os.path.basename(args['output']),
                    'status': 'Pending',
                    'args': args
                })

            refresh_batch_table(window)

            if window['prevent_system_sleep'].get():
                set_system_awake(True)
            start_queue(window, batch_queue)

    elif event in ("-BTN-BATCH-PAUSE-", "-BTN-PAUSE-"):
        pid = getattr(window, '_videocr_process_pid', None)
        if not pid:
            continue

        is_currently_paused = window[event].get_text() == LANG.get('btn_resume', "Resume")

        if is_currently_paused:
            if window['prevent_system_sleep'].get():
                set_system_awake(True)

            if set_process_pause_state(pid, pause=False):
                for key in ('-BTN-PAUSE-', '-BTN-BATCH-PAUSE-'):
                    if key in window.AllKeysDict:
                        window[key].update(text=LANG.get('btn_pause', "Pause"))

                window['-OUTPUT-'].update(LANG.get('status_resuming', "\nResuming process...\n"), append=True)
                update_taskbar(state='normal')

                for job in batch_queue:
                    if job['status'] == 'Paused':
                        job['status'] = 'Processing'
                        break
        else:
            set_system_awake(False)

            if set_process_pause_state(pid, pause=True):
                for key in ('-BTN-PAUSE-', '-BTN-BATCH-PAUSE-'):
                    if key in window.AllKeysDict:
                        window[key].update(text=LANG.get('btn_resume', "Resume"))

                window['-OUTPUT-'].update(LANG.get('status_pausing', "\nPausing process...\n"), append=True)
                update_taskbar(state='paused')

                for job in batch_queue:
                    if job['status'] == 'Processing':
                        job['status'] = 'Paused'
                        break

        refresh_batch_table(window)

    elif event == "-BTN-BATCH-CLEAR-":
        active_jobs = [j for j in batch_queue if j['status'] in ('Processing', 'Paused')]
        if active_jobs:
            batch_queue[:] = active_jobs
        else:
            batch_queue.clear()

        refresh_batch_table(window)
        update_run_and_cancel_button_state(window, batch_queue)

    elif event == "-BTN-BATCH-REMOVE-":
        rows = values['-BATCH-TABLE-']
        if rows:
            selected_jobs = [batch_queue[i] for i in rows]

            if any(job['status'] in ('Processing', 'Paused') for job in selected_jobs):
                custom_popup(window, LANG.get('title_error', "Error"), LANG.get('popup_cannot_remove_running', "The currently running or paused job cannot be removed.\nPlease stop or cancel the process first."), icon=ICON_PATH)
                continue

            for i in sorted(rows, reverse=True):
                del batch_queue[i]

            refresh_batch_table(window)
            update_run_and_cancel_button_state(window, batch_queue)

    elif event == '-BATCH-TABLE-':
        if getattr(window, 'ignore_table_event', False):
            window.ignore_table_event = False
            window.last_selection = values['-BATCH-TABLE-']
            continue

        selected = values['-BATCH-TABLE-']
        if not selected:
            window.batch_anchor = None
            window.batch_focus = None
            window.last_selection = []
            continue

        last_sel = getattr(window, 'last_selection', [])
        added = [x for x in selected if x not in last_sel]

        if added:
            if len(added) == 1:
                window.batch_anchor = added[0]
                window.batch_focus = added[0]
            else:
                anchor = getattr(window, 'batch_anchor', added[0])
                window.batch_focus = max(added) if anchor < added[0] else min(added)
        elif len(selected) == 1:
            window.batch_anchor = selected[0]
            window.batch_focus = selected[0]

        if getattr(window, 'batch_focus', None) is not None:
            tree_widget = window['-BATCH-TABLE-'].Widget
            row_id = tree_widget.get_children()[window.batch_focus]
            tree_widget.focus(row_id)

        window.last_selection = selected

    elif event == "-BTN-BATCH-UP-":
        rows = values['-BATCH-TABLE-']
        if rows:
            rows = sorted(rows)
            if rows[0] > 0:
                for idx in rows:
                    batch_queue[idx], batch_queue[idx - 1] = batch_queue[idx - 1], batch_queue[idx]
                refresh_batch_table(window)
                window['-BATCH-TABLE-'].update(select_rows=[r - 1 for r in rows])

    elif event == "-BTN-BATCH-DOWN-":
        rows = values['-BATCH-TABLE-']
        if rows:
            rows = sorted(rows, reverse=True)
            if rows[0] < len(batch_queue) - 1:
                for idx in rows:
                    batch_queue[idx], batch_queue[idx + 1] = batch_queue[idx + 1], batch_queue[idx]
                refresh_batch_table(window)
                window['-BATCH-TABLE-'].update(select_rows=[r + 1 for r in rows])

    elif event == "-BTN-BATCH-RESET-":
        rows = values['-BATCH-TABLE-']
        if rows:
            changed = False
            for idx in rows:
                status = batch_queue[idx]['status']
                if status in ('Cancelled', 'Error', 'Completed'):
                    batch_queue[idx]['status'] = 'Pending'
                    changed = True

            if changed:
                refresh_batch_table(window)
                update_run_and_cancel_button_state(window, batch_queue)

    elif event == '-BATCH-TABLE--SHIFT-DOWN':
        if getattr(window, 'batch_anchor', None) is None or getattr(window, 'batch_focus', None) is None:
            continue

        focus = window.batch_focus
        if focus < len(batch_queue) - 1:
            focus += 1

        window.batch_focus = focus
        start, end = min(window.batch_anchor, focus), max(window.batch_anchor, focus)
        new_sel = list(range(start, end + 1))

        window.ignore_table_event = True
        window['-BATCH-TABLE-'].update(select_rows=new_sel)
        window.last_selection = new_sel

    elif event == '-BATCH-TABLE--SHIFT-UP':
        if getattr(window, 'batch_anchor', None) is None or getattr(window, 'batch_focus', None) is None:
            continue

        focus = window.batch_focus
        if focus > 0:
            focus -= 1

        window.batch_focus = focus
        start, end = min(window.batch_anchor, focus), max(window.batch_anchor, focus)
        new_sel = list(range(start, end + 1))

        window.ignore_table_event = True
        window['-BATCH-TABLE-'].update(select_rows=new_sel)
        window.last_selection = new_sel

    elif event == "-BTN-BATCH-EDIT-":
        rows = values['-BATCH-TABLE-']
        if rows and len(rows) == 1:
            idx = rows[0]
            job = batch_queue[idx]

            if job['status'] in ('Processing', 'Paused'):
                display_status = get_translated_status(job['status'])
                error_title = LANG.get('title_error', "Error")
                error_msg = LANG.get('popup_cannot_edit_running', "A job that is currently {} cannot be edited.\nPlease stop or cancel the process first.").format(display_status)
                custom_popup(window, error_title, error_msg, icon=ICON_PATH)
                continue

            args = job['args']
            v_path = args['video_path']

            if not os.path.exists(v_path):
                error_title = LANG.get('title_error', "Error")
                error_msg = LANG.get('error_video_not_found', "Video file not found:\n{}").format(v_path)
                custom_popup(window, error_title, error_msg, icon=ICON_PATH)
                continue

            window['-TABGROUP-'].Widget.select(0)
            window['-VIDEO-LIST-'].update(value=v_path)

            reset_crop_state()
            graph.erase()

            orig_w, orig_h, duration_ms = video_manager.open(v_path).values()
            bt = get_valid_brightness_threshold(args.get('brightness_threshold'))
            img_bytes, res_w, res_h, off_x, off_y = video_manager.get_frame(0, graph_size, brightness_threshold=bt)

            if img_bytes and duration_ms > 0:
                video_path = v_path
                original_frame_width = orig_w
                original_frame_height = orig_h
                video_duration_ms = duration_ms
                current_time_ms = 0.0
                resized_frame_width = res_w
                resized_frame_height = res_h
                image_offset_x = off_x
                image_offset_y = off_y
                current_image_bytes = img_bytes.getvalue()

                graph.draw_image(data=current_image_bytes, location=(image_offset_x, image_offset_y))

                window["-SLIDER-"].update(range=(0, video_duration_ms), value=0, disabled=False)
                update_time_display(window, 0, video_duration_ms)
                window['-BTN-RUN-'].update(disabled=False)
                window['-SAVE_AS_BTN-'].update(disabled=False)

                # --- RESTORE SETTINGS ---
                window['--output'].update(args.get('output', ''))

                # Restore Engine selection
                saved_engine = args.get('ocr_engine', 'paddleocr')
                if saved_engine == 'google_lens':
                    engine_display = OCR_ENGINES[1]
                    active_lang_list = lens_display_names
                    lookup = lens_abbr_lookup
                else:
                    engine_display = OCR_ENGINES[0]
                    active_lang_list = paddle_display_names
                    lookup = paddle_abbr_lookup

                window['-OCR_ENGINE_COMBO-'].update(value=engine_display)

                # Restore Language based on the restored engine
                saved_lang_abbr = args.get('lang', 'en')
                disp_name = next((k for k, v in lookup.items() if v == saved_lang_abbr), DEFAULT_SUBTITLE_LANGUAGE)
                window['-LANG_COMBO-'].update(values=active_lang_list, value=disp_name)

                # Restore remaining simple arguments
                for arg_key, arg_val in args.items():
                    if arg_key in ('ocr_engine', 'lang'):
                        continue
                    gui_key = f"--{arg_key}"
                    if gui_key in window.AllKeysDict:
                        window[gui_key].update(arg_val)

                new_boxes: list[dict[str, Any]] = []

                def restore_box(cx: float, cy: float, cw: float, ch: float, orig_w: int, orig_h: int, res_w: int, res_h: int) -> dict[str, Any]:
                    sx = res_w / orig_w if orig_w > 0 else 0
                    sy = res_h / orig_h if orig_h > 0 else 0

                    rx1 = cx * sx
                    ry1 = cy * sy
                    rx2 = (cx + cw) * sx
                    ry2 = (cy + ch) * sy

                    return {
                        'coords': {'crop_x': int(cx), 'crop_y': int(cy), 'crop_width': int(cw), 'crop_height': int(ch)},
                        'img_points': ((rx1, ry1), (rx2, ry2))
                    }

                if 'crop_x' in args:
                    new_boxes.append(restore_box(
                        args['crop_x'], args['crop_y'], args['crop_width'], args['crop_height'],
                        original_frame_width, original_frame_height, resized_frame_width, resized_frame_height
                    ))

                if args.get('use_dual_zone') and 'crop_x2' in args:
                    new_boxes.append(restore_box(
                        args['crop_x2'], args['crop_y2'], args['crop_width2'], args['crop_height2'],
                        original_frame_width, original_frame_height, resized_frame_width, resized_frame_height
                    ))

                window.crop_boxes = new_boxes
                redraw_canvas_and_boxes()

                if not new_boxes:
                    window['-CROP_COORDS-'].update("Not Set")
                    window["-BTN-CLEAR_CROP-"].update(disabled=True)
                elif len(new_boxes) == 1:
                    b = new_boxes[0]
                    window['-CROP_COORDS-'].update(f"({b['coords']['crop_x']}, {b['coords']['crop_y']}, {b['coords']['crop_width']}, {b['coords']['crop_height']})")
                    window["-BTN-CLEAR_CROP-"].update(disabled=False)
                else:
                    coords_str_parts = []
                    zone_text = LANG.get('crop_zone_text', "Zone")
                    for i, b in enumerate(new_boxes):
                        coords_str_parts.append(f"{zone_text} {i + 1}: ({b['coords']['crop_x']}, {b['coords']['crop_y']}, {b['coords']['crop_width']}, {b['coords']['crop_height']})")
                    window['-CROP_COORDS-'].update("  |  ".join(coords_str_parts))
                    window["-BTN-CLEAR_CROP-"].update(disabled=False)

                del batch_queue[idx]
                refresh_batch_table(window)
                update_run_and_cancel_button_state(window, batch_queue)

    # --- Clear Crop Button ---
    elif event == "-BTN-CLEAR_CROP-":
        reset_crop_state()
        if video_path and current_image_bytes:
            graph.erase()
            graph.draw_image(data=current_image_bytes, location=(image_offset_x, image_offset_y))
        save_settings(window, values)

    # --- Cancel Button Clicked ---
    elif event in ("-BTN-CANCEL-", "-BTN-BATCH-STOP-"):
        pid_to_kill = getattr(window, '_videocr_process_pid', None)
        if pid_to_kill:
            window.cancelled_by_user = True
            window['-OUTPUT-'].update(LANG.get('status_cancelling', "\nCancelling process...\n"), append=True)
            window.refresh()
            try:
                if window['-BTN-PAUSE-'].get_text() == LANG.get('btn_resume', "Resume"):
                    set_process_pause_state(pid_to_kill, pause=False)

                kill_process_tree(pid_to_kill)
                window['-OUTPUT-'].update(LANG.get('status_cancelled', "\nProcess cancelled by user.\n"), append=True)
            except Exception as e:
                error_msg = LANG.get('error_cancel', "\nError attempting to cancel process: {}\n")
                window['-OUTPUT-'].update(error_msg.format(e), append=True)
            finally:
                if hasattr(window, '_videocr_process_pid'):
                    del window._videocr_process_pid
        else:
            window['-OUTPUT-'].update(LANG.get('error_no_process_to_cancel', "\nNo process is currently running to cancel.\n"), append=True)
            window['-BTN-CANCEL-'].update(disabled=True)
            window['-BTN-BATCH-STOP-'].update(disabled=True)
            window['-BTN-RUN-'].update(disabled=not video_path)

# --- Cleanup ---
window.close()
