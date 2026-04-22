import os
from flask import Flask, request, render_template, send_from_directory, redirect, url_for
import yt_dlp
from moviepy.editor import VideoFileClip
import whisper
import numpy as np

app = Flask(__name__)

def download_video_youtube(youtube_url, output_file="input.mp4"):
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',
        'outtmpl': output_file,
        'quiet': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_url])
    return output_file

def transcribe_audio(input_file):
    model = whisper.load_model("base")
    result = model.transcribe(input_file)
    return result

def find_viral_segment(transcript, segment_duration=59):
    segments = transcript["segments"]
    starts = np.array([seg['start'] for seg in segments])
    ends = np.array([seg['end'] for seg in segments])
    texts = [seg['text'] for seg in segments]
    n_segs = len(segments)
    best_score = 0
    best_idx = 0
    for i in range(n_segs):
        seg_start = starts[i]
        seg_end = seg_start + segment_duration
        window_idxs = np.where((starts < seg_end) & (ends > seg_start))[0]
        words_in_window = sum(len(texts[j].split()) for j in window_idxs)
        score = words_in_window
        if score > best_score:
            best_score = score
            best_idx = i
    clip_start = starts[best_idx]
    clip_end = min(clip_start + segment_duration, ends[-1])
    return clip_start, clip_end

def crop_to_916(input_video, output_video, start_time, end_time):
    with VideoFileClip(input_video) as video:
        short_clip = video.subclip(start_time, end_time)
        h = short_clip.h
        w = short_clip.w
        target_h = h
        target_w = int(h * 9 / 16)
        if w > target_w:
            x_center = w // 2
            x1 = x_center - target_w // 2
            x2 = x1 + target_w
            short_clip = short_clip.crop(x1=x1, y1=0, x2=x2, y2=h)
        elif w < target_w:
            short_clip = short_clip.resize(width=target_w)
        out_clip = short_clip.resize(height=1080)
        out_clip.write_videofile(output_video, codec="libx264", fps=30)
    return output_video

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        youtube_url = request.form['youtube_url']
        filename = f"input_{np.random.randint(10000)}.mp4"
        output_filename = f"short_{np.random.randint(10000)}.mp4"
        try:
            download_video_youtube(youtube_url, filename)
            transcript = transcribe_audio(filename)
            start, end = find_viral_segment(transcript)
            crop_to_916(filename, output_filename, start, end)
            os.remove(filename)
            return redirect(url_for('download_file', filename=output_filename))
        except Exception as e:
            return f"Terjadi error: {e}"
    return '''
    <h1>Auto Short Viral AI</h1>
    <form method="post">
        YouTube Link: <input name="youtube_url" type="text" size="60">
        <input type="submit" value="Proses">
    </form>
    '''

@app.route('/downloads/<filename>')
def download_file(filename):
    return send_from_directory('.', filename, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
