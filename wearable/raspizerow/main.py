import threading
import queue
import numpy as np
import pyaudio
import requests
import time
import os
import argparse
import wave

DO_NOT_APPLY_GAIN = 1.0

# Assuming 2 bytes per sample for FORMAT=pyaudio.paInt16 and mono audio
bytes_per_sample = 2
channels = 1
sample_rate = 44100
duration_in_seconds = 60  # Duration you want to accumulate before sending
target_bytes = sample_rate * duration_in_seconds * bytes_per_sample * channels
audio_gain = DO_NOT_APPLY_GAIN
save_to_local_file = False

class SafeQueue:
    def __init__(self):
        self.queue = queue.Queue()

    def push(self, value):
        self.queue.put(value)

    def pop(self):
        return self.queue.get()

    def empty(self):
        return self.queue.empty()

audio_queue = SafeQueue()

def record_audio(audio, stream, chunk_size):
    while True:
        data = stream.read(chunk_size)
        audio_queue.push(data)

def create_wav_header(bits_per_sample, data_size):
    header = bytearray()

    # "RIFF" chunk descriptor
    header.extend(b'RIFF')

    # Chunk size: 4 + (8 + SubChunk1Size) + (8 + SubChunk2Size)
    chunk_size = 36 + data_size
    header.extend(chunk_size.to_bytes(4, 'little'))

    # Format
    header.extend(b'WAVE')

    # "fmt " sub-chunk
    header.extend(b'fmt ')

    # Sub-chunk 1 size (16 for PCM)
    subchunk1_size = 16
    header.extend(subchunk1_size.to_bytes(4, 'little'))

    # Audio format (PCM = 1)
    audio_format = 1
    header.extend(audio_format.to_bytes(2, 'little'))

    # Number of channels
    header.extend(channels.to_bytes(2, 'little'))

    # Sample rate
    header.extend(sample_rate.to_bytes(4, 'little'))

    # Byte rate (SampleRate * NumChannels * BitsPerSample/8)
    byte_rate = sample_rate * channels * bits_per_sample // 8
    header.extend(byte_rate.to_bytes(4, 'little'))

    # Block align (NumChannels * BitsPerSample/8)
    block_align = channels * bits_per_sample // 8
    header.extend(block_align.to_bytes(2, 'little'))

    # Bits per sample
    header.extend(bits_per_sample.to_bytes(2, 'little'))

    # "data" sub-chunk
    header.extend(b'data')

    # Sub-chunk 2 size (data size)
    header.extend(data_size.to_bytes(4, 'little'))

    return header

def save_wav_to_file(buffer):
    timestamp = int(time.time())
    os.makedirs("data", exist_ok=True)
    filename = f"data/{timestamp}_audio.wav"

    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(bytes_per_sample)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(buffer)

def send_wav_buffer(buffer):
    if save_to_local_file:
        save_wav_to_file(buffer)

    supabase_url = os.environ.get("SUPABASE_URL")
    if not supabase_url:
        print("Environment variable SUPABASE_URL is not set.")
        return

    url = f"{supabase_url}/functions/v1/process-audio"
    auth_token = os.environ.get("AUTH_TOKEN")

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "audio/wav"
    }

    try:
        response = requests.post(url, headers=headers, data=buffer)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error sending request: {e}")

def handle_audio_buffer():
    while True:
        data_chunk = bytearray()
        while len(data_chunk) < target_bytes:
            buffer = audio_queue.pop()
            data_chunk.extend(buffer)

        if audio_gain != DO_NOT_APPLY_GAIN:
            # Apply volume increase by scaling the audio samples
            data_array = np.frombuffer(data_chunk, dtype=np.int16)
            data_array = np.clip(data_array * audio_gain, -2**15, 2**15 - 1).astype(np.int16)
            data_chunk = data_array.tobytes()

        if data_chunk:
            wav_header = create_wav_header(16, len(data_chunk))
            wav_buffer = wav_header + data_chunk
            send_wav_buffer(wav_buffer)

def process_args():
    parser = argparse.ArgumentParser(description="Command line options")
    parser.add_argument("-s", "--save", action="store_true", help="Save audio to local file")
    parser.add_argument("-g", "--gain", type=float, default=DO_NOT_APPLY_GAIN, help="Microphone gain (increase volume of audio)")
    return parser.parse_args()

def main():
    args = process_args()
    global save_to_local_file, audio_gain
    save_to_local_file = args.save
    audio_gain = args.gain

    # Set up PyAudio
    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16,
                        channels=channels,
                        rate=sample_rate,
                        input=True,
                        frames_per_buffer=1024,
                        input_device_index=0)

    recording_thread = threading.Thread(target=record_audio, args=(audio, stream, 1024))
    sending_thread = threading.Thread(target=handle_audio_buffer)

    recording_thread.start()
    sending_thread.start()

    recording_thread.join()
    sending_thread.join()

    # Close the stream and PyAudio
    stream.stop_stream()
    stream.close()
    audio.terminate()

if __name__ == "__main__":
    main()