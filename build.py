import argparse
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

import requests

# --- Configuration ---
APP_VERSION = "1.3.2"
PADDLE_VERSION = "1.3.2"

SUPPORT_FILES_URLS = {
    "Windows": f"https://github.com/timminator/PaddleOCR-Standalone/releases/download/v{PADDLE_VERSION}/PaddleOCR.PP-OCRv5.support.files.VideOCR.7z",
    "Linux": f"https://github.com/timminator/PaddleOCR-Standalone/releases/download/v{PADDLE_VERSION}/PaddleOCR.PP-OCRv5.support.files.VideOCR.tar.xz"
}

PADDLE_URLS = {
    "Windows": {
        "cpu": f"https://github.com/timminator/PaddleOCR-Standalone/releases/download/v{PADDLE_VERSION}/PaddleOCR-CPU-v{PADDLE_VERSION}.7z",
        "gpu-cuda11.8": f"https://github.com/timminator/PaddleOCR-Standalone/releases/download/v{PADDLE_VERSION}/PaddleOCR-GPU-v{PADDLE_VERSION}-CUDA-11.8.7z",
        "gpu-cuda12.9": f"https://github.com/timminator/PaddleOCR-Standalone/releases/download/v{PADDLE_VERSION}/PaddleOCR-GPU-v{PADDLE_VERSION}-CUDA-12.9.7z",
    },
    "Linux": {
        "cpu": f"https://github.com/timminator/PaddleOCR-Standalone/releases/download/v{PADDLE_VERSION}/PaddleOCR-CPU-v{PADDLE_VERSION}-Linux.7z",
        "gpu-cuda11.8": f"https://github.com/timminator/PaddleOCR-Standalone/releases/download/v{PADDLE_VERSION}/PaddleOCR-GPU-v{PADDLE_VERSION}-CUDA-11.8-Linux.7z",
        "gpu-cuda12.9": [
            f"https://github.com/timminator/PaddleOCR-Standalone/releases/download/v{PADDLE_VERSION}/PaddleOCR-GPU-v{PADDLE_VERSION}-CUDA-12.9-Linux.7z.001",
            f"https://github.com/timminator/PaddleOCR-Standalone/releases/download/v{PADDLE_VERSION}/PaddleOCR-GPU-v{PADDLE_VERSION}-CUDA-12.9-Linux.7z.002",
        ]
    }
}


# --- Helper Functions ---
def print_header(message):
    """Prints a formatted header."""
    print("\n" + "=" * 60)
    print(f" {message}")
    print("=" * 60)


def check_tkinter():
    """Checks if Tkinter is installed and available."""
    print_header("Checking for Tkinter support...")
    try:
        import tkinter
        print("Tkinter support found.")
        root = tkinter.Tk()
        root.destroy()
    except ImportError:
        print("ERROR: Tkinter is not installed or not available.")
        print("Please install it. On Debian/Ubuntu: sudo apt-get install python3-tk")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Tkinter found, but failed to initialize: {e}")
        print("This might be an issue with your display server (e.g., running in a headless environment).")
        sys.exit(1)


def check_dbus():
    """On Linux, checks if dbus is likely installed for better plyer support."""
    if platform.system() == "Linux":
        print_header("Checking for D-Bus on Linux...")
        if shutil.which("dbus-daemon"):
            print("D-Bus daemon found. Plyer notifications should work well.")
        else:
            print("WARNING: D-Bus daemon not found. Plyer notifications might not work correctly.")
            print("On Debian/Ubuntu, you can install it with: sudo apt-get install dbus")


def check_7zip():
    """Checks if 7-Zip is installed and available."""
    print_header("Checking for 7-Zip...")
    if not (shutil.which("7z") or shutil.which("7z.exe")):
        print("ERROR: 7-Zip executable ('7z' or '7z.exe') not found in your system's PATH.")
        print("Please install 7-Zip and ensure it's added to your PATH.")
        print(" - Windows: https://www.7-zip.org/")
        print(" - Linux (Debian/Ubuntu): sudo apt-get install p7zip-full")
        sys.exit(1)
    print("7-Zip found.")


def run_command(command, cwd=None):
    """Runs a command in the shell, streams its output, and exits if it fails."""
    try:
        print(f"\nRunning command: {' '.join(command)}" + (f" in '{cwd}'" if cwd else ""))
        subprocess.run(command, check=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Command failed with exit code {e.returncode}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"ERROR: Command '{command[0]}' not found. Is it in your PATH?")
        sys.exit(1)


def download_file(urls, dest_folder):
    """Downloads a file or a sequence of files from URLs into a destination folder."""
    if not isinstance(urls, list):
        urls = [urls]

    first_file_path = None
    for url in urls:
        local_filename = url.split('/')[-1]
        file_path = Path(dest_folder) / local_filename
        if not first_file_path:
            first_file_path = file_path

        print(f"Downloading {local_filename}...")
        try:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(file_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            print(f"Downloaded to {file_path}")
        except requests.exceptions.RequestException as e:
            print(f"ERROR: Failed to download {url}. Reason: {e}")
            sys.exit(1)

    return first_file_path


def extract_archive(file_path, dest_folder):
    """Extracts a .7z, multipart .7z, or .tar.xz archive."""
    print(f"Extracting {file_path.name}...")

    if file_path.suffix == ".7z" or str(file_path).endswith(".7z.001"):
        seven_zip_exe = shutil.which("7z") or shutil.which("7z.exe")
        if seven_zip_exe:
            command = [seven_zip_exe, "x", str(file_path), f"-o{dest_folder}", "-y"]
            run_command(command)
        else:
            print("ERROR: 7-Zip executable not found in PATH.")
            sys.exit(1)
    elif file_path.suffix == ".xz":
        try:
            with tarfile.open(file_path, 'r:xz') as archive:
                archive.extractall(path=dest_folder, filter='data')
        except Exception as e:
            print(f"ERROR: Failed to extract {file_path}. Reason: {e}")
            sys.exit(1)
    else:
        raise ValueError(f"Unsupported archive format: {file_path.suffix}")

    print(f"Extracted to {dest_folder}")


def sign_file(signtool_path, cert_name, file_to_sign):
    """Signs a file using signtool.exe on Windows."""
    if not signtool_path or platform.system() != "Windows":
        return
    print(f"Signing {file_to_sign.name}...")
    if not Path(signtool_path).is_file():
        print(f"ERROR: Sign tool not found at '{signtool_path}'")
        sys.exit(1)
    command = [
        signtool_path,
        "sign",
        "/tr", "http://timestamp.digicert.com",
        "/td", "sha256",
        "/fd", "sha256"
    ]
    if cert_name:
        command.extend(["/n", cert_name])
    else:
        command.append("/a")

    command.append(str(file_to_sign))
    run_command(command)
    print(f"Successfully signed {file_to_sign.name}")


def create_final_archive(folder_path, build_target):
    """Creates a compressed archive of the final build folder."""
    print_header(f"Creating final archive for {folder_path.name}")

    try:
        seven_zip_exe = shutil.which("7z") or shutil.which("7z.exe")
        if not seven_zip_exe:
            print("WARNING: 7-Zip not found, cannot create .7z archive. Skipping.")
            return

        archive_path = folder_path.parent / f"{folder_path.name}.7z"
        print(f"Creating {archive_path.name}...")

        is_linux_cuda12_split = platform.system() == "Linux" and build_target == "gpu-cuda12.9"

        command = [
            seven_zip_exe, "a", "-t7z",
            "-mx=9", "-m0=lzma2", "-md=64m", "-mfb=64", "-ms=on",
        ]

        if is_linux_cuda12_split:
            print("Applying 1999MB volume splitting for Linux CUDA 12.9 build...")
            command.extend(["-v1999m"])

        command.extend([str(archive_path.name), str(folder_path.name)])

        run_command(command, cwd=str(folder_path.parent))

        print(f"Archive created successfully: {archive_path}")
    except Exception as e:
        print(f"ERROR: Failed to create archive. Reason: {e}")
        sys.exit(1)


def create_windows_installer(final_app_path, args):
    """Creates a Windows installer using Inno Setup by passing parameters to the compiler."""
    if platform.system() != "Windows":
        return

    iscc_exe = args.iscc or shutil.which("iscc") or shutil.which("ISCC.exe")
    if not iscc_exe or not Path(iscc_exe).is_file():
        print("\nWARNING: Inno Setup Compiler (iscc.exe) not found.")
        print("         Skipping installer creation.")
        print("         To create an installer, install Inno Setup and add it to your PATH,")
        print("         or provide the path to iscc.exe using the --iscc argument.")
        return

    display_target_name = final_app_path.name.replace("VideOCR-", "").replace(f"-v{APP_VERSION}", "")
    print_header(f"Creating Windows Installer for {display_target_name}")

    script_path = Path("Installer/Windows/installer_template.iss")
    if not script_path.is_file():
        print(f"WARNING: Installer script not found at '{script_path}'. Skipping installer creation.")
        return

    releases_dir = final_app_path.parent
    output_filename = f"{final_app_path.name}-setup-x64"

    command = [
        iscc_exe,
        "/Qp",
        f"/DMyAppVersion={APP_VERSION}",
        f"/DSourceDir={str(final_app_path.resolve())}",
        f"/DOutputBaseFilename={output_filename}",
        f"/DOutputDir={str(releases_dir.resolve())}",
    ]

    if args.signtool:
        signtool_params = 'sign /tr http://timestamp.digicert.com /td sha256 /fd sha256'
        if args.sign_cert_name:
            signtool_params += f' /n $q{args.sign_cert_name}$q $f'
        else:
            signtool_params += ' /a $f'

        iscc_sign_param = f'/Ssigntool=$q{args.signtool}$q {signtool_params}'
        command.append(iscc_sign_param)

    command.append(str(script_path))

    run_command(command)
    print("\nInstaller created successfully.")


# --- Main Build Logic ---
def package_target(build_target, args, releases_dir, base_gui_dist, base_cli_dist):
    """Packages a single distribution for the specified target using pre-compiled files."""

    if "gpu" in build_target:
        display_target_name = build_target.replace("gpu-", "GPU-").replace("cuda", "CUDA-")
    else:
        display_target_name = build_target.upper()

    print_header(f"Packaging for Target: {display_target_name}")
    os_name = platform.system()
    os_suffix = "-Linux" if os_name == "Linux" else ""

    # Create a temporary directory for this target's packaging process
    work_dir = releases_dir / f"work_{build_target}"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir()

    print(f"Creating temporary work directories in '{work_dir}'...")
    temp_gui_dist = work_dir / "gui_dist"
    temp_cli_dist = work_dir / "cli_dist"
    shutil.copytree(base_gui_dist, temp_gui_dist)
    shutil.copytree(base_cli_dist, temp_cli_dist)

    # Download and Extract Dependencies into the temporary CLI folder
    print_header(f"Downloading Dependencies for {display_target_name} target")
    support_archive_path = download_file(SUPPORT_FILES_URLS[os_name], temp_cli_dist)
    paddle_url = PADDLE_URLS[os_name][build_target]
    paddle_archive_path = download_file(paddle_url, temp_cli_dist)

    extract_archive(support_archive_path, temp_cli_dist)
    extract_archive(paddle_archive_path, temp_cli_dist)

    print("Cleaning up downloaded archives...")
    os.remove(support_archive_path)
    if isinstance(paddle_url, list):
        for url in paddle_url:
            filename = url.split('/')[-1]
            filepath = Path(temp_cli_dist) / filename
            if filepath.exists():
                os.remove(filepath)
    else:
        os.remove(paddle_archive_path)

    # Assemble Final Directory Structure
    print_header(f"Assembling Final Directory Structure for {display_target_name}")

    # Define final names
    release_tag = f"-{args.release_type}" if args.release_type else ""
    cuda_suffix = ""
    if "gpu" in build_target:
        base_target_name = "GPU"
        cuda_version = build_target.split('-')[-1]
        cuda_suffix = f"-{cuda_version.replace('cuda', 'CUDA-')}"
    else:
        base_target_name = build_target.upper()

    cli_final_name = f"videocr-cli-{base_target_name}-v{APP_VERSION}{cuda_suffix}{release_tag}{os_suffix}"
    final_app_folder_name = f"VideOCR-{base_target_name}-v{APP_VERSION}{cuda_suffix}{release_tag}{os_suffix}"

    # Move the temp CLI folder to its final standalone location in Releases
    final_cli_path = releases_dir / cli_final_name
    print(f"Moving standalone CLI to '{final_cli_path}'")
    shutil.move(str(temp_cli_dist), final_cli_path)

    # Copy the final CLI folder into the GUI folder
    print(f"Copying CLI into GUI folder as '{cli_final_name}'")
    shutil.copytree(final_cli_path, temp_gui_dist / cli_final_name)

    # Copy Linux installer scripts if applicable
    if os_name == "Linux":
        print("Copying Linux installer scripts...")
        installer_src = Path("Installer/Linux")
        for script_name in ["install_videocr.sh", "uninstall_videocr.sh"]:
            src_path = installer_src / script_name
            dest_path = temp_gui_dist / script_name
            if src_path.exists():
                shutil.copy(src_path, dest_path)
                os.chmod(dest_path, dest_path.stat().st_mode | stat.S_IEXEC)
                print(f"Copied and set +x on {script_name}")
            else:
                print(f"WARNING: Installer script not found at {src_path}")

    # Move final GUI folder to Releases
    final_app_path = releases_dir / final_app_folder_name
    print(f"Moving final application to '{final_app_path}'")
    shutil.move(str(temp_gui_dist), final_app_path)

    shutil.rmtree(work_dir)

    if args.archive and args.archive.lower() == 'true':
        create_final_archive(final_app_path, build_target)
        create_final_archive(final_cli_path, build_target)

    if platform.system() == "Windows" and args.windows_installer and args.windows_installer.lower() == 'true':
        create_windows_installer(final_app_path, args)


def main():
    parser = argparse.ArgumentParser(description="VideOCR Build Script", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "--target",
        choices=["cpu", "gpu", "all"],
        default="cpu",
        help="The build target for PaddleOCR: 'cpu', 'gpu' (builds all GPU versions), or 'all'. Defaults to 'cpu'."
    )
    parser.add_argument(
        "--signtool",
        default=None,
        help="(Optional, Windows only) Path to signtool.exe for code signing."
    )
    parser.add_argument(
        "--sign-cert-name",
        default=None,
        help="(Optional, Windows only) The subject name of the certificate to use for signing."
    )
    parser.add_argument(
        "--iscc",
        default=None,
        help="(Optional, Windows only) Path to the Inno Setup compiler (iscc.exe)."
    )
    parser.add_argument(
        "--archive",
        default='false',
        help="(Optional) Set to 'true' to create a compressed archive of the final build folder."
    )
    parser.add_argument(
        "--windows-installer",
        default='false',
        help="(Optional, Windows only) Set to 'true' to create an Inno Setup installer."
    )
    parser.add_argument(
        "--release-type",
        default=None,
        help="(Optional) Specify a release type (e.g., 'Beta', 'RC1') to append to the output artifact names."
    )
    args = parser.parse_args()

    # Prerequisite Checks
    check_tkinter()
    check_dbus()
    check_7zip()

    releases_dir = Path("Releases")
    if releases_dir.exists():
        print_header("Cleaning previous build artifacts")
        print(f"Removing existing directory: {releases_dir}")
        shutil.rmtree(releases_dir)
    releases_dir.mkdir(exist_ok=True)

    print_header("Compiling Binaries")

    # Compile GUI
    gui_script = "VideOCR.py"
    gui_dist_folder = Path("VideOCR.dist")
    if gui_dist_folder.exists():
        shutil.rmtree(gui_dist_folder)
    run_command([sys.executable, "-m", "nuitka", gui_script])
    if not gui_dist_folder.is_dir():
        print(f"ERROR: Nuitka failed to create the GUI dist folder: {gui_dist_folder}")
        sys.exit(1)
    gui_exe = gui_dist_folder / "VideOCR.exe"
    if gui_exe.exists():
        sign_file(args.signtool, args.sign_cert_name, gui_exe)

    # Compile CLI
    cli_folder = Path("CLI")
    cli_script = "videocr_cli.py"
    cli_dist_folder = cli_folder / "videocr_cli.dist"
    if cli_dist_folder.exists():
        shutil.rmtree(cli_dist_folder)
    run_command([sys.executable, "-m", "nuitka", cli_script], cwd=str(cli_folder))
    if not cli_dist_folder.is_dir():
        print(f"ERROR: Nuitka failed to create the CLI dist folder: {cli_dist_folder}")
        sys.exit(1)
    cli_exe = cli_dist_folder / "videocr-cli.exe"
    if cli_exe.exists():
        sign_file(args.signtool, args.sign_cert_name, cli_exe)

    # --- Package for each target ---
    if args.target == 'cpu':
        targets_to_build = ['cpu']
    elif args.target == 'gpu':
        targets_to_build = ['gpu-cuda11.8', 'gpu-cuda12.9']
    elif args.target == 'all':
        targets_to_build = ['cpu', 'gpu-cuda11.8', 'gpu-cuda12.9']
    else:
        targets_to_build = [args.target]

    for i, build_target in enumerate(targets_to_build):
        package_target(build_target, args, releases_dir, gui_dist_folder, cli_dist_folder)
        if i < len(targets_to_build) - 1:
            if "gpu" in build_target:
                completed_target_name = build_target.replace("gpu-", "GPU-").replace("cuda", "CUDA-")
            else:
                completed_target_name = build_target.upper()
            print("\n" + "#" * 60)
            print(f"Completed packaging for {completed_target_name}. Starting next target...")
            print("#" * 60)

    # --- Final Cleanup ---
    print_header("Final Cleanup")
    print("Removing temporary compilation directories...")
    shutil.rmtree(gui_dist_folder)
    shutil.rmtree(cli_dist_folder)

    print_header("All Builds Complete!")
    print(f"All outputs are located in the '{releases_dir}' folder.")


if __name__ == "__main__":
    main()
