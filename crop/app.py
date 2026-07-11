import os
import uuid
import base64
import shutil
import threading
import subprocess
import cv2
from flask import Flask, request, jsonify, render_template, send_from_directory, send_file
from werkzeug.utils import secure_filename

# Initialize Flask application
app = Flask(__name__)

# Absolute paths configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Leverage local python virtual environments ffmpeg binaries if present
root_dir = os.path.dirname(BASE_DIR)
venv_scripts_dir = os.path.join(root_dir, 'venv', 'Scripts')
if os.path.exists(os.path.join(venv_scripts_dir, 'ffmpeg.exe')):
    os.environ["PATH"] = venv_scripts_dir + os.pathsep + os.environ.get("PATH", "")

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'output')

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Allowed file configurations
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi'}

# Global jobs progress dictionary to track status
jobs = {}
jobs_lock = threading.Lock()

def allowed_video(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS

def get_video_info(video_path):
    """
    Extracts video metadata (dimensions, duration, frames, FPS) using OpenCV.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps > 0 else 0
    cap.release()
    return {
        'width': width,
        'height': height,
        'fps': fps,
        'duration': duration,
        'frames': frame_count
    }

def extract_first_frame_base64(video_path):
    """
    Reads the first frames of the video and encodes it to a base64 JPEG image.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    success, frame = cap.read()
    cap.release()
    if success:
        retval, buffer = cv2.imencode('.jpg', frame)
        if retval:
            b64_str = base64.b64encode(buffer).decode('utf-8')
            return f"data:image/jpeg;base64,{b64_str}"
    return None

def process_video_thread(job_id, input_path, crop, logo_data, logo_options, video_info, split_count):
    """
    Runs the crop, overlay, and optional splitting FFmpeg command in a background thread, tracking progress.
    """
    try:
        # Pre-clean output.mp4 and output.zip to avoid downloading old cached files
        final_mp4 = os.path.join(OUTPUT_FOLDER, 'output.mp4')
        final_zip = os.path.join(OUTPUT_FOLDER, 'output.zip')
        for path in [final_mp4, final_zip]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

        # Parse crop parameters
        crop_x = int(crop['x'])
        crop_y = int(crop['y'])
        crop_w = int(crop['width'])
        crop_h = int(crop['height'])

        # Sanitize crop coordinates to avoid out-of-boundary exceptions in FFmpeg
        crop_x = max(0, min(crop_x, video_info['width'] - 1))
        crop_y = max(0, min(crop_y, video_info['height'] - 1))
        crop_w = max(1, min(crop_w, video_info['width'] - crop_x))
        crop_h = max(1, min(crop_h, video_info['height'] - crop_y))

        temp_logo_path = None

        if logo_data:
            # Parse logo Base64 string and write to a temporary file
            try:
                header, encoded = logo_data.split(",", 1)
                logo_bytes = base64.b64decode(encoded)
                temp_logo_path = os.path.join(UPLOAD_FOLDER, f"logo_{job_id}.png")
                with open(temp_logo_path, "wb") as f:
                    f.write(logo_bytes)

                # Determine raw logo dimensions using OpenCV
                logo_img = cv2.imread(temp_logo_path, cv2.IMREAD_UNCHANGED)
                if logo_img is not None:
                    logo_h_orig, logo_w_orig = logo_img.shape[:2]
                else:
                    logo_w_orig, logo_h_orig = 100, 100  # Fallback size
            except Exception as e:
                raise Exception(f"Failed to process uploaded logo image: {e}")

            # Calculate visual scale and positions
            scale_percent = logo_options.get('scale', 20)
            target_w = int(crop_w * (scale_percent / 100.0))
            target_h = int(target_w * (logo_h_orig / logo_w_orig))
            if target_h == 0:
                target_h = 1

            opacity_val = float(logo_options.get('opacity', 100)) / 100.0
            position = logo_options.get('position', 'bottom-right')
            margin = int(logo_options.get('margin', 10))

            if position == 'bottom-right':
                overlay_x = f"W-w-{margin}"
                overlay_y = f"H-h-{margin}"
            elif position == 'bottom-left':
                overlay_x = f"{margin}"
                overlay_y = f"H-h-{margin}"
            elif position == 'top-right':
                overlay_x = f"W-w-{margin}"
                overlay_y = f"{margin}"
            elif position == 'top-left':
                overlay_x = f"{margin}"
                overlay_y = f"{margin}"
            else:
                overlay_x = f"W-w-{margin}"
                overlay_y = f"H-h-{margin}"

            # Advanced filter complex: Scale logo -> apply opacity -> Crop Video -> Overlay Logo
            filter_complex = (
                f"[1:v]scale={target_w}:{target_h},format=rgba,colorchannelmixer=aa={opacity_val}[logo];"
                f"[0:v]crop={crop_w}:{crop_h}:{crop_x}:{crop_y}[cropped];"
                f"[cropped][logo]overlay={overlay_x}:{overlay_y}[outv]"
            )
        else:
            # No logo: perform crop only
            filter_complex = f"[0:v]crop={crop_w}:{crop_h}:{crop_x}:{crop_y}[outv]"

        import time
        start_time_processing = time.time()
        total_duration = video_info['duration']
        part_duration = total_duration / split_count
        part_output_paths = []

        for part_idx in range(split_count):
            if split_count > 1:
                part_start = part_idx * part_duration
                part_dur = part_duration if part_idx < split_count - 1 else (total_duration - part_start)
                part_output_filename = f"output_{job_id}_part_{part_idx + 1}.mp4"
                part_output_path = os.path.join(OUTPUT_FOLDER, part_output_filename)
            else:
                part_start = 0
                part_dur = total_duration
                part_output_filename = f"output_{job_id}.mp4"
                part_output_path = os.path.join(OUTPUT_FOLDER, part_output_filename)

            part_output_paths.append(part_output_path)

            # Build command with input seeking to keep timeline matching 0-based filters
            cmd = ['ffmpeg', '-y', '-progress', 'pipe:1']
            if split_count > 1:
                cmd.extend(['-ss', f"{part_start:.4f}", '-t', f"{part_dur:.4f}"])
            
            cmd.extend(['-i', input_path])
            if logo_data:
                cmd.extend(['-i', temp_logo_path])
            
            cmd.extend([
                '-filter_complex', filter_complex,
                '-map', '[outv]',
                '-map', '0:a?',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-c:a', 'copy',
                part_output_path
            ])

            # Spawn FFmpeg in background
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )

            # Asynchronously capture standard error to log errors without locking progress stream
            stderr_lines = []
            def read_stderr():
                for line in process.stderr:
                    stderr_lines.append(line)
            
            stderr_thread = threading.Thread(target=read_stderr)
            stderr_thread.start()

            # Monitor progress from stdout
            for line in process.stdout:
                if '=' in line:
                    try:
                        key, val = line.strip().split('=', 1)
                        if key == 'out_time_us':
                            out_time_us = int(val)
                            curr_secs = out_time_us / 1000000.0
                            if part_dur > 0:
                                # Progress of the current part slice
                                part_progress = min(99.9, (curr_secs / part_dur) * 100.0)
                                # Combined overall progress percentage
                                overall_pct = ((part_idx * 100.0) + part_progress) / split_count
                                overall_pct = min(99.9, overall_pct)
                                
                                elapsed = time.time() - start_time_processing
                                if overall_pct > 0:
                                    total_est = (elapsed / overall_pct) * 100.0
                                    eta = max(0, int(total_est - elapsed))
                                else:
                                    eta = 0
                                
                                with jobs_lock:
                                    if job_id in jobs:
                                        jobs[job_id]['progress'] = round(overall_pct, 1)
                                        jobs[job_id]['eta'] = eta
                    except Exception:
                        pass

            process.wait()
            stderr_thread.join()

            if process.returncode != 0:
                err_log = "".join(stderr_lines[-10:])
                raise Exception(f"FFmpeg error at segment {part_idx + 1}: {err_log if err_log else 'Unknown error'}")

        # Cleanup temporary logo file
        if temp_logo_path and os.path.exists(temp_logo_path):
            try:
                os.remove(temp_logo_path)
            except Exception:
                pass

        # Final packaging copies and ZIPs
        if split_count > 1:
            import zipfile
            with zipfile.ZipFile(final_zip, 'w') as zipf:
                for idx, path_element in enumerate(part_output_paths):
                    zipf.write(path_element, arcname=f"cropped_split_{idx+1}.mp4")
            
            # Make part 1 copy as output.mp4 for video element preview loaders
            shutil.copy2(part_output_paths[0], final_mp4)
        else:
            # Single video flow
            shutil.copy2(part_output_paths[0], final_mp4)

        with jobs_lock:
            if job_id in jobs:
                jobs[job_id]['status'] = 'completed'
                jobs[job_id]['progress'] = 100.0
                jobs[job_id]['eta'] = 0

    except Exception as e:
        with jobs_lock:
            if job_id in jobs:
                jobs[job_id]['status'] = 'failed'
                jobs[job_id]['error'] = str(e)


# ------------------ ROUTES ------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file part in request'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No selected video file'}), 400
        
    if not allowed_video(file.filename):
        return jsonify({'error': 'Unsupported file format. Please upload MP4, MOV, or AVI.'}), 400
        
    # Generate unique ID and save file
    job_id = str(uuid.uuid4())
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = secure_filename(f"input_{job_id}.{ext}")
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(input_path)

    # Fetch video details using OpenCV
    video_info = get_video_info(input_path)
    if not video_info:
        # Cleanup invalid files
        try:
            os.remove(input_path)
        except Exception:
            pass
        return jsonify({'error': 'Failed to read video properties. The file might be corrupted.'}), 400

    # Extract first frame
    first_frame_b64 = extract_first_frame_base64(input_path)
    if not first_frame_b64:
        try:
            os.remove(input_path)
        except Exception:
            pass
        return jsonify({'error': 'Failed to extract video preview frame.'}), 400

    # Initialize job parameters
    with jobs_lock:
        jobs[job_id] = {
            'status': 'uploaded',
            'progress': 0.0,
            'eta': 0,
            'input_path': input_path,
            'video_info': video_info,
            'error': None
        }

    return jsonify({
        'job_id': job_id,
        'width': video_info['width'],
        'height': video_info['height'],
        'duration': round(video_info['duration'], 2),
        'fps': round(video_info['fps'], 2),
        'first_frame': first_frame_b64
    })

@app.route('/process', methods=['POST'])
def process_video():
    data = request.get_json()
    if not data or 'job_id' not in data or 'crop' not in data:
        return jsonify({'error': 'Missing required parameters'}), 400

    job_id = data['job_id']
    crop = data['crop'] # contains {x, y, width, height}
    logo_data = data.get('logo') # base64 transparent PNG, optional
    logo_options = data.get('logo_options', {})
    split_count = int(data.get('split_count', 1))
    if split_count < 1:
        split_count = 1

    with jobs_lock:
        job = jobs.get(job_id)

    if not job:
        return jsonify({'error': 'Invalid or expired job ID'}), 404

    # Prepare paths
    input_path = job['input_path']
    
    # Update job state
    with jobs_lock:
        jobs[job_id]['status'] = 'processing'
        jobs[job_id]['progress'] = 0.0
        jobs[job_id]['eta'] = 9999

    # Spawn thread to crop
    t = threading.Thread(
        target=process_video_thread,
        args=(job_id, input_path, crop, logo_data, logo_options, job['video_info'], split_count)
    )
    t.start()

    return jsonify({'message': 'Processing started successfully.', 'job_id': job_id})

@app.route('/status', methods=['GET'])
def get_status():
    job_id = request.args.get('job_id')
    if not job_id:
        return jsonify({'error': 'Missing job_id'}), 400

    with jobs_lock:
        job = jobs.get(job_id)

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    response_data = {
        'status': job['status'],
        'progress': job['progress'],
        'eta': job['eta'],
        'error': job['error']
    }
    return jsonify(response_data)

@app.route('/download', methods=['GET'])
def download_video():
    zip_file = os.path.join(OUTPUT_FOLDER, 'output.zip')
    if os.path.exists(zip_file):
        return send_file(zip_file, as_attachment=True, download_name='split_videos.zip')

    output_file = os.path.join(OUTPUT_FOLDER, 'output.mp4')
    if os.path.exists(output_file):
        return send_file(output_file, as_attachment=True, download_name='output.mp4')
    return jsonify({'error': 'Output file not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)
