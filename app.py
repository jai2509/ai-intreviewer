import streamlit as st
from streamlit_webrtc import webrtc_streamer
import av
import numpy as np
import tempfile
import wave
import time

st.header("🎙️ Answer Interview Questions by Voice")

# Define a class to handle audio frames
class AudioProcessor:
    def __init__(self):
        self.frames = []

    def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
        audio = frame.to_ndarray()
        self.frames.append(audio)
        return frame

# Stream audio
audio_processor = AudioProcessor()
ctx = webrtc_streamer(
    key="audio",
    mode="SENDONLY",
    media_stream_constraints={"audio": True, "video": False},
    audio_receiver_size=1024,
    audio_frame_callback=audio_processor.recv,
    rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
)

# Save button
if st.button("✅ Save & Transcribe Answer"):
    if not audio_processor.frames:
        st.error("⚠️ No audio captured. Try again.")
    else:
        # Convert to WAV
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            wav_path = f.name
            wf = wave.open(wav_path, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit PCM
            wf.setframerate(48000)
            for frame in audio_processor.frames:
                wf.writeframes(frame.tobytes())
            wf.close()

        # Transcribe with AssemblyAI
        def transcribe_audio(filepath):
            headers = {'authorization': os.getenv("ASSEMBLY_API_KEY")}
            with open(filepath, 'rb') as f:
                response = requests.post('https://api.assemblyai.com/v2/upload', headers=headers, files={'file': f})
                upload_url = response.json()['upload_url']

            json_data = {'audio_url': upload_url}
            transcript_response = requests.post('https://api.assemblyai.com/v2/transcript', json=json_data, headers=headers)
            transcript_id = transcript_response.json()['id']

            while True:
                polling = requests.get(f'https://api.assemblyai.com/v2/transcript/{transcript_id}', headers=headers)
                status = polling.json()['status']
                if status == 'completed':
                    return polling.json()['text']
                elif status == 'error':
                    return "❌ Transcription failed."
                time.sleep(3)

        transcription = transcribe_audio(wav_path)
        st.success("🗣️ Transcription:")
        st.write(transcription)
