from streamlit_webrtc import webrtc_streamer, WebRtcMode, ClientSettings
import av
import threading
import queue
import numpy as np
import wave
import tempfile

# Audio queue for capturing stream
audio_queue = queue.Queue()

# WebRTC settings
client_settings = ClientSettings(
    media_stream_constraints={"audio": True, "video": False},
    rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
)

class AudioProcessor:
    def __init__(self):
        self.recorded_frames = []

    def recv(self, frame: av.AudioFrame):
        pcm = frame.to_ndarray()
        self.recorded_frames.append(pcm)
        return frame

    def get_wav_bytes(self):
        if not self.recorded_frames:
            return None

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wf = wave.open(f.name, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(b''.join([x.tobytes() for x in self.recorded_frames]))
            wf.close()
            return f.name

# Replace inside your interview section
st.header("🎙️ Voice Interview")
if "questions" in st.session_state:
    for idx, question in enumerate(st.session_state["questions"]):
        st.subheader(f"Q{idx+1}: {question}")
        
        st.info("🎤 Click below to record your answer")
        audio_processor = AudioProcessor()

        webrtc_ctx = webrtc_streamer(
            key=f"question_{idx}",
            mode=WebRtcMode.SENDONLY,
            client_settings=client_settings,
            audio_receiver_size=256,
            media_stream_constraints={"audio": True, "video": False},
            async_processing=True,
        )

        if webrtc_ctx.state.playing:
            st.warning("Recording... speak now!")
        
        if st.button(f"✅ Submit Answer for Q{idx+1}", key=f"submit_{idx}"):
            if webrtc_ctx.audio_receiver:
                audio_frames = []
                try:
                    while True:
                        frame = webrtc_ctx.audio_receiver.get_frame(timeout=1)
                        audio_processor.recv(frame)
                except queue.Empty:
                    pass

                wav_file_path = audio_processor.get_wav_bytes()
                if wav_file_path:
                    def transcribe_audio(filepath):
                        headers = {'authorization': ASSEMBLY_API_KEY}
                        with open(filepath, 'rb') as f:
                            response = requests.post('https://api.assemblyai.com/v2/upload',
                                                     headers=headers, files={'file': f})
                            upload_url = response.json()['upload_url']

                        json_data = {'audio_url': upload_url}
                        transcript_response = requests.post('https://api.assemblyai.com/v2/transcript',
                                                            json=json_data, headers=headers)
                        transcript_id = transcript_response.json()['id']

                        while True:
                            polling = requests.get(f'https://api.assemblyai.com/v2/transcript/{transcript_id}',
                                                   headers=headers)
                            status = polling.json()['status']
                            if status == 'completed':
                                return polling.json()['text']
                            elif status == 'error':
                                return "Transcription failed."
                            time.sleep(3)

                    transcription = transcribe_audio(wav_file_path)
                    st.write(f"🗣️ Your Answer: {transcription}")
                    st.session_state[f"answer_{idx}"] = transcription
                else:
                    st.error("No audio was recorded.")
            else:
                st.error("WebRTC audio stream not available yet.")
