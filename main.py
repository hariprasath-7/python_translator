import asyncio
import io
import sys
import time
import wave
import winsound
from deep_translator import GoogleTranslator, MyMemoryTranslator
from deep_translator.exceptions import TooManyRequests
import edge_tts
from gtts import gTTS
import miniaudio
import numpy as np
import sounddevice as sd
import speech_recognition as sr

# Ensure UTF-8 encoding in Windows terminals for Tamil unicode characters
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

google_translator = GoogleTranslator(source="en", target="ta")
mymemory_translator = MyMemoryTranslator(source="en-GB", target="ta-IN")
recognizer = sr.Recognizer()

# Translator & Audio settings
use_mymemory = False
voice_output_enabled = True
selected_output_device_idx = None  # None = system default


def get_available_output_devices():
    """Returns list of valid audio playback devices."""
    devices = sd.query_devices()
    outputs = []
    for idx, d in enumerate(devices):
        if d["max_output_channels"] > 0 and d.get("hostapi", 0) == 0:
            outputs.append((idx, d["name"]))
    return outputs


def get_current_device_name():
    global selected_output_device_idx
    devices = sd.query_devices()
    if selected_output_device_idx is not None:
        return devices[selected_output_device_idx]["name"]
    default_out_idx = sd.default.device[1]
    if default_out_idx is not None and default_out_idx >= 0:
        return f"{devices[default_out_idx]['name']} (System Default)"
    return "Default Output Device"


def translate(text: str) -> str:
    global use_mymemory

    if not use_mymemory:
        try:
            return google_translator.translate(text)
        except TooManyRequests:
            print("\n[Notice] Google Translate rate limit reached. Switching to MyMemory translator...")
            use_mymemory = True
        except Exception as e:
            print(f"\n[Notice] Google Translate unavailable ({e}). Trying fallback translator...")
            use_mymemory = True

    return mymemory_translator.translate(text)


def speak_tamil(text: str) -> None:
    """
    Synthesizes and plays Tamil speech aloud.
    Uses Microsoft Edge Neural Tamil voice by default with gTTS as fallback.
    Plays at 44.1kHz Stereo through the selected audio device.
    """
    global selected_output_device_idx
    if not text.strip():
        return

    audio_bytes = b""

    # 1. Primary: Natural Microsoft Neural Tamil Voice
    try:
        async def _synth():
            communicate = edge_tts.Communicate(text, "ta-IN-PallaviNeural")
            data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    data += chunk["data"]
            return data

        audio_bytes = asyncio.run(_synth())
    except Exception:
        # 2. Fallback: Google Text-to-Speech (gTTS)
        try:
            tts = gTTS(text=text, lang="ta")
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            audio_bytes = fp.read()
        except Exception as e:
            print(f"[Notice] Speech synthesis error: {e}")
            return

    try:
        # Decode to 44.1kHz 16-bit Stereo (compatible with all Windows sound devices)
        decoded = miniaudio.decode(audio_bytes, nchannels=2, sample_rate=44100)
        arr = np.array(decoded.samples, dtype=np.int16).reshape(-1, 2)

        # Also save to local WAV file for reference
        try:
            with wave.open("translated_tamil.wav", "wb") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(44100)
                wf.writeframes(arr.tobytes())
        except Exception:
            pass

        device_name = get_current_device_name()
        print(f"🔊 Playing voice output through: [{device_name}]...")

        # Play through selected device via sounddevice
        sd.play(arr, samplerate=44100, device=selected_output_device_idx)
        sd.wait()

    except Exception as sd_err:
        # Fallback to Windows native winsound
        try:
            print(f"[Notice] sounddevice playback fallback ({sd_err}), using Windows default audio...")
            wav_fp = io.BytesIO()
            with wave.open(wav_fp, "wb") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(44100)
                wf.writeframes(decoded.samples)
            winsound.PlaySound(wav_fp.getvalue(), winsound.SND_MEMORY)
        except Exception as e:
            print(f"[Notice] Audio playback error: {e}")


def record_voice(sample_rate: int = 16000) -> str | None:
    """Records audio from microphone until user presses Enter, then converts speech to text."""
    audio_frames = []

    def audio_callback(indata, frames, time_info, status):
        audio_frames.append(indata.copy())

    print("\n--------------------------------------------------")
    print("🎤 [MIC ON] Start speaking in English now.")
    print("   👉 When you finish speaking, press [ENTER].")
    print("--------------------------------------------------")

    try:
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16", callback=audio_callback):
            input()  # Wait for Enter
    except KeyboardInterrupt:
        print("\n[Notice] Recording cancelled.")
        return None
    except Exception as e:
        print(f"[Error] Microphone error: {e}")
        return None

    if not audio_frames:
        print("[Notice] No audio captured.")
        return None

    print("⏳ Transcribing speech...")
    audio_data = np.concatenate(audio_frames, axis=0)
    audio = sr.AudioData(audio_data.tobytes(), sample_rate, 2)

    try:
        recognized_text = recognizer.recognize_google(audio, language="en-US")
        print(f'🗣️ You said: "{recognized_text}"')
        return recognized_text
    except sr.UnknownValueError:
        print("[Notice] Could not recognize speech. Please speak clearly into the microphone.")
        return None
    except sr.RequestError as e:
        print(f"[Error] Speech recognition service error: {e}")
        return None


def process_translation(english_text: str):
    """Translates text and speaks the Tamil translation."""
    try:
        tamil_text = translate(english_text)
        print("🔤 Tamil Translation:", tamil_text)

        if voice_output_enabled and tamil_text:
            speak_tamil(tamil_text)

    except Exception as e:
        print("Translation failed:", e)
        print("Please wait a few minutes and try again.")
        time.sleep(2)


def select_device_menu():
    global selected_output_device_idx
    devices = get_available_output_devices()
    print("\nAvailable Playback Devices:")
    for num, (idx, name) in enumerate(devices):
        marker = " *" if (selected_output_device_idx == idx or (selected_output_device_idx is None and idx == sd.default.device[1])) else ""
        print(f"  [{num + 1}] {name}{marker}")
    print("  [0] System Default")

    try:
        choice = input("Enter device number to select: ").strip()
        if choice == "0":
            selected_output_device_idx = None
            print("Switched to System Default audio device.")
        elif choice.isdigit() and 1 <= int(choice) <= len(devices):
            selected_output_device_idx = devices[int(choice) - 1][0]
            print(f"Switched audio output to: {devices[int(choice) - 1][1]}")
    except Exception:
        pass


def auto_switch_device(target_keyword: str):
    global selected_output_device_idx
    devices = get_available_output_devices()
    for idx, name in devices:
        if target_keyword.lower() in name.lower():
            selected_output_device_idx = idx
            print(f"Switched audio output to: {name}")
            return
    print(f"Could not find a device matching '{target_keyword}'.")


print("==================================================")
print("     English -> Tamil Voice & Text Translator     ")
print("==================================================")
print(f"Audio Output : {get_current_device_name()}")
print("Commands:")
print("  [ENTER] or 'v'  -> Speak in English (Voice input)")
print("  [Any text]      -> Translate typed English text")
print("  'test'          -> Test Tamil voice playback")
print("  'spk'           -> Switch audio to Laptop Speakers")
print("  'hp'            -> Switch audio to Headphones")
print("  'device'        -> Choose audio output device")
print("  'mute'          -> Toggle voice output on/off")
print("  'exit'          -> Quit")
print("==================================================")

while True:
    try:
        prompt = input(f"\nEnter text (or press ENTER for voice, 'exit' to quit): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nTranslator closed!")
        break

    if prompt.lower() == "exit":
        print("Translator closed!")
        break

    if prompt.lower() == "test":
        print("Playing Tamil test audio...")
        speak_tamil("வணக்கம், நீங்கள் இப்போது குரலை கேட்க முடிகிறதா?")
        continue

    if prompt.lower() == "spk":
        auto_switch_device("Speakers")
        continue

    if prompt.lower() == "hp":
        auto_switch_device("Headphone")
        continue

    if prompt.lower() in ("device", "devices"):
        select_device_menu()
        continue

    if prompt.lower() == "mute":
        voice_output_enabled = not voice_output_enabled
        status = "ON" if voice_output_enabled else "OFF"
        print(f"Voice output is now {status}.")
        continue

    # Voice input mode
    if prompt == "" or prompt.lower() in ("v", "voice", "speak"):
        spoken_text = record_voice()
        if spoken_text:
            process_translation(spoken_text)
        continue

    # Text input mode
    process_translation(prompt)